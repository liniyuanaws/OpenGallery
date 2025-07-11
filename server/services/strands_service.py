"""
Strands Agent Service
统一的 AWS Strands Agent 服务，支持单agent和多agent模式
"""
import asyncio
import json
import traceback
from typing import List, Dict, Any, Optional

from strands import Agent, tool
try:
    from strands.models import BedrockModel, AnthropicModel, OpenAIModel, OllamaModel
except ImportError:
    from strands.models import BedrockModel
    AnthropicModel = BedrockModel
    OpenAIModel = BedrockModel
    OllamaModel = BedrockModel

from services.db_service import db_service
from services.config_service import config_service
from services.websocket_service import send_to_websocket, send_to_user_websocket
from services.strands_context import SessionContextManager
from services.user_context import get_current_user_id


async def send_user_websocket_message(session_id: str, event: dict):
    """Send WebSocket message to the current user"""
    try:
        user_id = get_current_user_id()
        await send_to_user_websocket(session_id, event, user_id)
    except Exception as e:
        # Fallback to broadcast if user context is not available
        print(f"⚠️ User context not available, falling back to broadcast: {e}")
        await send_to_websocket(session_id, event)


def create_model_instance(text_model: Dict[str, Any]):
    """创建模型实例"""
    model = text_model.get('model')
    provider = text_model.get('provider')
    url = text_model.get('url')
    api_key = config_service.app_config.get(provider, {}).get("api_key", "")
    max_tokens = text_model.get('max_tokens', 8148)
    
    if provider == 'ollama':
        try:
            return OllamaModel(
                model=model,
                base_url=url,
            )
        except:
            return BedrockModel(model_id=model)
    elif provider == 'bedrock':
        region = config_service.app_config.get(provider, {}).get("region", "us-west-2")
        return BedrockModel(
            model_id=model,
            region_name=region,
            max_tokens=max_tokens,
            temperature=0
        )
    elif provider == 'anthropic':
        try:
            return AnthropicModel(
                model=model,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=0
            )
        except:
            return BedrockModel(model_id=model)
    else:
        try:
            return OpenAIModel(
                model=model,
                api_key=api_key,
                base_url=url,
                temperature=0,
                max_tokens=max_tokens,
            )
        except:
            return BedrockModel(model_id=model)


def get_specialized_agents():
    """获取专门化agent工具列表"""
    try:
        from tools.strands_specialized_agents import get_specialized_agents

        agents = get_specialized_agents()
        print(f"✅ Loaded {len(agents)} specialized agents")
        for agent in agents:
            print(f"  - {agent.__name__}: {type(agent)}")
        return agents
    except Exception as e:
        print(f"❌ Failed to load specialized agents: {e}")
        traceback.print_exc()
        return []


async def strands_agent(messages, canvas_id, session_id, text_model, image_model, system_prompt: str = None):
    """单个 Strands Agent 处理"""
    try:
        model = create_model_instance(text_model)

        # 创建系统提示
        agent_system_prompt = system_prompt or """
You are a professional AI assistant with image generation capabilities.

Available tools:
- generate_image_with_context: Generate images based on text descriptions

When users request image generation:
1. Analyze their request to understand what they want
2. Create a detailed, descriptive prompt for the image
3. Use the generate_image_with_context tool to create the image
4. Choose appropriate aspect ratios based on the content

IMPORTANT - Image Context Usage:
- The tool has use_previous_image=True by default, which automatically uses the most recent image from this conversation
- Use use_previous_image=TRUE when the user wants to EDIT, MODIFY, or BUILD UPON an existing image (e.g., "change the dress color", "add a hat", "remove the background")
- Use use_previous_image=FALSE when the user wants a COMPLETELY NEW, UNRELATED image or explicitly asks for a "new image"
- If no previous image exists in the conversation, the tool will inform you appropriately

For other tasks, use your general knowledge and reasoning capabilities.
Be helpful, accurate, and creative in your responses.
"""

        # 转换消息格式
        user_prompt = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_prompt = msg.get('content', '')
                break

        if not user_prompt:
            user_prompt = "Hello, how can I help you?"

        # 使用上下文管理器，传递当前用户ID
        try:
            current_user_id = get_current_user_id()
        except Exception:
            current_user_id = None

        with SessionContextManager(session_id, canvas_id, {'image': image_model}, user_id=current_user_id):
            print(f"💬 Processing: {user_prompt[:50]}...")

            # 验证上下文是否正确设置
            from services.strands_context import get_image_model
            context_image_model = get_image_model()

            # 创建带有上下文信息的图像生成工具
            from tools.strands_image_generators import create_generate_image_with_context
            contextual_generate_image = create_generate_image_with_context(session_id, canvas_id, image_model, current_user_id)

            # 只使用带上下文的generate_image工具
            tools = [contextual_generate_image]

            print(f"🔍 DEBUG: Using tools: {[tool.__name__ for tool in tools]}")

            # 创建带有上下文工具的agent
            agent = Agent(
                model=model,
                tools=tools,
                system_prompt=agent_system_prompt
            )

            print(f"✅ Agent created with {len(tools)} tools")

            # 使用同步调用替代流式处理
            print("🔍 DEBUG: Calling agent with synchronous call...")

            try:
                # 使用同步调用
                response = agent(user_prompt)

                # 处理同步响应
                if hasattr(response, 'content'):
                    response_text = response.content
                elif isinstance(response, str):
                    response_text = response
                else:
                    response_text = str(response)



                # 发送 delta 事件到 WebSocket
                await send_user_websocket_message(session_id, {
                    'type': 'delta',
                    'text': response_text
                })

                # 同时保存完整的文本消息到数据库
                if response_text.strip():  # 只保存非空消息
                    text_message = {
                        'role': 'assistant',
                        'content': response_text
                    }
                    db_service.create_message(session_id, 'assistant', json.dumps(text_message))

            except Exception as e:
                print(f"❌ Agent error: {e}")
                await send_user_websocket_message(session_id, {
                    'type': 'error',
                    'error': str(e)
                })

        # 发送完成事件
        await send_user_websocket_message(session_id, {
            'type': 'done'
        })

    except Exception as e:
        print('Error in strands_agent', e)
        traceback.print_exc()
        await send_user_websocket_message(session_id, {
            'type': 'error',
            'error': str(e)
        })


async def strands_multi_agent(messages, canvas_id, session_id, text_model, image_model, system_prompt: str = None):
    """多Agent Swarm处理"""
    try:
        model = create_model_instance(text_model)

        # 创建主Agent，使用专门化agent工具
        orchestrator_system_prompt = system_prompt or """
You are an intelligent orchestrator agent that coordinates multiple specialized agents to handle complex tasks.

Available Specialized Agents:
- planner_agent: Creates detailed execution plans and project breakdowns
- image_designer_agent: Generates images and handles visual content creation

Your Coordination Capabilities:
- Analyze complex projects and break them down into manageable components
- Coordinate multiple specialists working together on complex projects
- Manage task dependencies, sequencing, and resource allocation
- Track progress and ensure quality across multi-step workflows
- Provide comprehensive project management and execution guidance

Routing Guidelines:
1. For planning tasks → use planner_agent
2. For image/visual content → use image_designer_agent
3. For complex projects → coordinate specialists directly using your built-in capabilities

Always analyze the user's request and route to the most appropriate specialist(s).
You can use multiple agents in sequence for complex tasks and coordinate their work directly.
For analysis, research, or data processing tasks, use your own reasoning capabilities or route to planner_agent for structured analysis.
"""

        # 创建专门化agents作为工具
        specialized_agents = get_specialized_agents()

        print(f"🔧 Creating multi-agent with {len(specialized_agents)} specialized agents:")
        for i, agent_tool in enumerate(specialized_agents):
            agent_name = getattr(agent_tool, '__name__', str(agent_tool))
            agent_type = type(agent_tool).__name__
            print(f"  {i+1}. {agent_name} ({agent_type})")

        agent = Agent(
            model=model,
            tools=specialized_agents,
            system_prompt=orchestrator_system_prompt
        )

        print(f"✅ Multi-agent created successfully")
        
        # 转换消息格式 - 取最后一条用户消息
        user_prompt = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_prompt = msg.get('content', '')
                break

        if not user_prompt:
            user_prompt = "Hello, how can I help you?"

        # 使用上下文管理器设置会话上下文，传递当前用户ID
        try:
            current_user_id = get_current_user_id()
        except Exception:
            current_user_id = None

        with SessionContextManager(session_id, canvas_id, {'image': image_model}, user_id=current_user_id):
            print(f"🔍 DEBUG: Starting multi-agent stream call with prompt: {user_prompt}")
            print(f"🔍 DEBUG: Session context - session_id: {session_id}, canvas_id: {canvas_id}")
            print(f"🔍 DEBUG: Image model: {image_model}")

            # 使用同步调用替代流式处理
            print("🔍 DEBUG: Calling multi-agent with synchronous call...")

            try:
                # 使用同步调用
                response = agent(user_prompt)

                # 处理同步响应
                if hasattr(response, 'content'):
                    response_text = response.content
                elif isinstance(response, str):
                    response_text = response
                else:
                    response_text = str(response)


                await send_user_websocket_message(session_id, {
                    'type': 'delta',
                    'text': response_text
                })

            except Exception as e:
                print(f"❌ Multi-agent error: {e}")
                await send_user_websocket_message(session_id, {
                    'type': 'error',
                    'error': str(e)
                })

        # 发送完成事件
        await send_user_websocket_message(session_id, {
            'type': 'done'
        })

    except Exception as e:
        print('Error in strands_multi_agent', e)
        tb_str = traceback.format_exc()
        print(f"Full traceback:\n{tb_str}")
        traceback.print_exc()
        await send_user_websocket_message(session_id, {
            'type': 'error',
            'error': str(e)
        })


async def handle_agent_event(event, session_id):
    """处理 Agent 事件"""
    if not isinstance(event, dict):
        return
    
    # 只处理重要的事件，减少噪音
    if 'event' in event:
        inner_event = event['event']
        
        # 处理工具调用开始
        if 'contentBlockStart' in inner_event:
            start = inner_event['contentBlockStart']['start']
            if 'toolUse' in start:
                tool_use = start['toolUse']
                print(f"🔧 Tool call started: {tool_use.get('name', '')}")
                await send_user_websocket_message(session_id, {
                    'type': 'tool_call',
                    'id': tool_use.get('toolUseId', ''),
                    'name': tool_use.get('name', ''),
                    'arguments': ''
                })

        # 处理文本和工具参数增量
        elif 'contentBlockDelta' in inner_event:
            delta = inner_event['contentBlockDelta']['delta']
            if 'text' in delta:
                await send_user_websocket_message(session_id, {
                    'type': 'delta',
                    'text': delta['text']
                })
            elif 'toolUse' in delta:
                await send_user_websocket_message(session_id, {
                    'type': 'tool_call_arguments',
                    'id': '',
                    'text': delta['toolUse'].get('input', '')
                })
        
        # 处理工具调用完成
        elif 'contentBlockStop' in inner_event:
            stop_info = inner_event['contentBlockStop']
            if 'toolUse' in stop_info:
                print(f"🔧 Tool call completed")
    
    # 处理简单的文本数据事件
    elif "data" in event and "delta" in event:
        # 只处理纯文本数据，避免重复处理
        if "event_loop_metrics" in event:
            # 这是一个包含文本的数据事件
            await send_user_websocket_message(session_id, {
                'type': 'delta',
                'text': event["data"]
            })


# 向后兼容的别名
clean_strands_agent = strands_agent
handle_clean_agent_event = handle_agent_event


# 支持并行agent的辅助函数
def create_parallel_agents(agent_type: str, count: int, base_config: dict) -> list:
    """创建并行agent配置"""
    parallel_agents = []
    for i in range(count):
        agent_config = base_config.copy()
        agent_config['name'] = f"{agent_type}_{i+1}"
        parallel_agents.append(agent_config)
    return parallel_agents
