"""
Strands格式的图像生成工具
只包含带上下文的图像生成工具
注意：此文件提供工具创建函数，不直接注册为工具
"""

# 告诉 strands 库不要自动注册此文件为工具
# 这可以防止 "tool function missing" 警告
__STRANDS_TOOL__ = False
__all__ = ['create_generate_image_with_context', 'generate_file_id', 'generate_image_id', 'strands_image_generators']

# 全局变量来跟踪已发送的file_generated事件，防止重复
_sent_file_events = set()
import random
import base64
import json
import traceback
import os
import asyncio
from mimetypes import guess_type

from pydantic import BaseModel, Field
from strands import tool
import aiofiles
try:
    from nanoid import generate
except ImportError:
    # Fallback ID generation if nanoid is not available
    import random
    import string
    def generate(size=8):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=size))

from common import DEFAULT_PORT
from services.config_service import FILES_DIR
from services.db_service import db_service
from services.websocket_service import send_to_websocket, broadcast_session_update

# run_async_safe 函数已移除 - 现在直接使用 async/await

# Import all generators with absolute imports
try:
    # 尝试绝对导入
    import sys
    import os

    # 确保服务器根目录在 Python 路径中
    server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if server_root not in sys.path:
        sys.path.insert(0, server_root)

    from tools.img_generators import (
        ReplicateGenerator,
        ComfyUIGenerator,
        WavespeedGenerator,
        JaazGenerator,
        OpenAIGenerator
    )
    print("✅ Image generators imported successfully")

except ImportError as e:
    print(f"❌ Failed to import image generators: {e}")
    # 创建空的生成器类作为备用
    class DummyGenerator:
        async def generate(self, *args, **kwargs):
            raise NotImplementedError("Image generator not available")

    ReplicateGenerator = DummyGenerator
    ComfyUIGenerator = DummyGenerator
    WavespeedGenerator = DummyGenerator
    JaazGenerator = DummyGenerator
    OpenAIGenerator = DummyGenerator


# 生成唯一文件 ID
def generate_file_id():
    return 'im_' + generate(size=8)


def get_most_recent_image_from_session(session_id: str, user_id: str = None) -> str:
    """
    从指定session中获取最近的图像ID（包括用户上传的和助手生成的）

    Args:
        session_id: 会话ID
        user_id: 用户ID，如果提供则用于用户验证

    Returns:
        最近图像的文件ID，如果没有找到则返回空字符串
    """
    try:
        print(f"🔍 DEBUG: get_most_recent_image_from_session called with session_id={session_id}, user_id={user_id}")
        # 获取session的聊天历史
        if user_id:
            # 如果提供了user_id，直接使用user-aware服务
            print(f"🔍 DEBUG: Using UserContextManager with user_id={user_id}")
            from services.user_context import UserContextManager
            with UserContextManager(user_id):
                messages = db_service.get_chat_history(session_id)
                print(f"🔍 DEBUG: Successfully got {len(messages)} messages from chat history")
        else:
            print(f"🔍 DEBUG: No user_id provided, trying current context")
            # 尝试从当前上下文获取user_id
            try:
                messages = db_service.get_chat_history(session_id)
                print(f"🔍 DEBUG: Successfully got {len(messages)} messages from current context")
            except Exception as auth_error:
                print(f"🔍 DEBUG: Auth error in current context: {auth_error}")
                # 如果认证失败，尝试从strands上下文获取user_id
                try:
                    from services.strands_context import get_user_id
                    strands_user_id = get_user_id()
                    print(f"🔍 DEBUG: Got strands_user_id: {strands_user_id}")
                    if strands_user_id:
                        from services.user_context import UserContextManager
                        with UserContextManager(strands_user_id):
                            messages = db_service.get_chat_history(session_id)
                            print(f"🔍 DEBUG: Successfully got {len(messages)} messages with strands user context")
                    else:
                        raise auth_error
                except Exception as e:
                    print(f"🔍 DEBUG: Failed to get user from strands context: {e}")
                    raise auth_error

        # 从最新的消息开始查找图像消息
        for i, message in enumerate(reversed(messages)):
            # 确保message是字典类型
            if not isinstance(message, dict):
                continue
            # 查找助手生成的图像和用户上传的图像
            if message.get('content'):
                content = message.get('content', [])

                # 处理字符串格式的content（可能是JSON字符串或包含图像引用的文本）
                if isinstance(content, str):
                    # 首先尝试解析为JSON
                    try:
                        import json
                        parsed_content = json.loads(content)
                        if isinstance(parsed_content, list):
                            # 递归处理解析后的列表
                            for item in parsed_content:
                                if (isinstance(item, dict) and
                                    item.get('type') == 'image_url' and
                                    item.get('image_url', {}).get('url')):

                                    url = item['image_url']['url']
                                    if '/api/file/' in url:
                                        file_id = url.split('/api/file/')[-1]
                                        print(f"🎯 Found recent image in session (from JSON): {file_id}")
                                        return file_id
                        elif isinstance(parsed_content, dict) and parsed_content.get('content'):
                            # 处理嵌套的content结构
                            nested_content = parsed_content['content']
                            if isinstance(nested_content, list):
                                for item in nested_content:
                                    if (isinstance(item, dict) and
                                        item.get('type') == 'image_url' and
                                        item.get('image_url', {}).get('url')):

                                        url = item['image_url']['url']
                                        if '/api/file/' in url:
                                            file_id = url.split('/api/file/')[-1]
                                            print(f"🎯 Found recent image in session (from nested JSON): {file_id}")
                                            return file_id
                    except (json.JSONDecodeError, TypeError):
                        # 如果不是JSON，则作为普通字符串处理
                        pass

                    # 查找字符串中的图像引用，如 ![...](/api/file/im_xxx.jpeg)
                    import re
                    image_pattern = r'/api/file/(im_[a-zA-Z0-9_-]+\.[a-zA-Z0-9]+)'
                    matches = re.findall(image_pattern, content)
                    if matches:
                        file_id = matches[-1]  # 取最后一个匹配的图像
                        print(f"🎯 Found recent image in session (from text): {file_id}")
                        return file_id

                # 处理列表格式的content
                elif isinstance(content, list):
                    for item in content:
                        if (isinstance(item, dict) and
                            item.get('type') == 'image_url' and
                            item.get('image_url', {}).get('url')):

                            url = item['image_url']['url']
                            # 从URL中提取文件ID，例如 '/api/file/im_abc123.png' -> 'im_abc123.png'
                            if '/api/file/' in url:
                                file_id = url.split('/api/file/')[-1]
                                print(f"🎯 Found recent image in session (from list): {file_id}")
                                return file_id

        return ""

    except Exception as e:
        print(f"❌ Error getting recent image from session {session_id}: {e}")
        return ""


# Initialize provider instances
PROVIDERS = {
    'replicate': ReplicateGenerator(),
    'comfyui': ComfyUIGenerator(),
    'wavespeed': WavespeedGenerator(),
    'jaaz': JaazGenerator(),
    'openai': OpenAIGenerator(),
}


def create_generate_image_with_context(session_id: str, canvas_id: str, image_model: dict, user_id: str = None):
    """创建一个带有上下文信息的 generate_image 工具"""
    from strands import tool

    @tool
    async def generate_image_with_context(
        prompt: str = Field(description="Detailed description of the image to generate"),
        aspect_ratio: str = Field(default="1:1", description="Aspect ratio for the image (1:1, 4:3, 16:9, 3:4)"),
        input_image: str = Field(default="", description="Optional image to use as reference. Pass image_id here, e.g. 'im_jurheut7.png'. Leave empty if not needed. Best for image editing cases like: Editing specific parts of the image, Removing specific objects, Maintaining visual elements across scenes"),
        use_previous_image: bool = Field(default=True, description="Whether to automatically use the most recent image from the current session as input. Set to TRUE when you want to edit, modify, or build upon the previously generated image (e.g., 'change the color', 'add something', 'remove object'). Set to FALSE when creating a completely new, unrelated image or when the user explicitly asks for a new image.")
    ) -> str:
        """
        Generate an image based on the provided prompt and parameters.

        This tool creates images using AI image generation models. It supports various aspect ratios
        and can optionally use an input image as reference for editing or style transfer.

        Args:
            prompt: Detailed description of what the image should contain
            aspect_ratio: The desired aspect ratio (1:1, 4:3, 16:9, 3:4)
            input_image: Optional reference image ID for editing tasks
            use_previous_image: Whether to automatically use the most recent image from the current session as input

        Returns:
            A message indicating successful image generation with file details
        """
        # 生成唯一的调用ID来跟踪重复调用
        call_id = generate_file_id()
        print(f"🎨️ generate_image_with_context tool called! Call ID: {call_id}")
        print(f"🔍 DEBUG: Using provided context - session_id: {session_id}, canvas_id: {canvas_id}")
        print(f"🔍 DEBUG: Using provided image_model: {image_model}")
        print(f"🔍 DEBUG: Using provided user_id: {user_id}")
        
        try:
            # 使用提供的上下文信息而不是从contextvars获取
            tool_call_id = generate_file_id()
            
            model = image_model.get('model', 'flux-kontext')
            provider = image_model.get('provider', 'comfyui')
            
            print(f"🔍 DEBUG: model={model}, provider={provider}")
            
            # Get provider instance
            generator = PROVIDERS.get(provider)
            if not generator:
                raise ValueError(f"Unsupported provider: {provider}")
            
            # Handle input_image parameter
            if not isinstance(input_image, str):
                input_image = ""

            # Check if the model supports input images before using previous image
            model_supports_input = 'kontext' in model.lower() or 'i2v' in model.lower() or 'edit' in model.lower()

            # Handle use_previous_image parameter - only for models that support input images
            if use_previous_image and not input_image and model_supports_input:
                print(f"� Using previous image from session")
                try:
                    # Use the user_id passed to the function
                    effective_user_id = user_id
                    if not effective_user_id:
                        # Fallback: try to get user_id from strands context if not provided
                        try:
                            from services.strands_context import get_user_id
                            effective_user_id = get_user_id()
                            print(f"🔍 DEBUG: Got user_id from strands context: {effective_user_id}")
                        except Exception as e:
                            print(f"🔍 DEBUG: Failed to get user_id from strands context: {e}")
                            pass

                    # Get the most recent image from the current session
                    print(f"🔍 DEBUG: Calling get_most_recent_image_from_session with session_id={session_id}, user_id={effective_user_id}")
                    previous_image_id = get_most_recent_image_from_session(session_id, effective_user_id)
                    if previous_image_id:
                        # Convert the file to base64
                        try:
                            # 首先尝试从数据库获取文件信息
                            file_record = None
                            file_id_without_ext = previous_image_id.split('.')[0] if '.' in previous_image_id else previous_image_id
                            try:
                                file_record = db_service.get_file(file_id_without_ext)
                            except Exception as db_error:
                                pass  # 静默处理数据库查找错误

                            file_path = None
                            if file_record:
                                # 使用数据库中的文件路径
                                file_path = os.path.join(FILES_DIR, file_record['file_path'])
                            else:
                                # 尝试直接路径
                                file_path = os.path.join(FILES_DIR, previous_image_id)

                                # 如果文件不存在且没有扩展名，尝试常见扩展名
                                if not os.path.exists(file_path) and '.' not in previous_image_id:
                                    for ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                                        test_path = os.path.join(FILES_DIR, f'{previous_image_id}.{ext}')
                                        if os.path.exists(test_path):
                                            file_path = test_path
                                            break

                            if file_path and os.path.exists(file_path):
                                with open(file_path, 'rb') as f:
                                    image_data = f.read()
                                    input_image = base64.b64encode(image_data).decode('utf-8')
                                    print(f"✅ Previous image loaded successfully")
                            else:
                                print(f"❌ Previous image file not found")
                                return "I found a reference to a previous image in this conversation, but the image file is no longer available. Please upload a new image that I can help you edit."
                        except Exception as file_error:
                            print(f"❌ Error reading previous image file: {file_error}")
                            return "I found a previous image in this conversation, but I encountered an error while trying to access it. Please upload a new image that I can help you edit."
                    else:
                        # 当没有找到图像时，返回友好的错误信息
                        return "I don't see any previous images in this conversation that I can edit or modify. Please upload an image first, or create a new image that I can then help you edit."
                except Exception as e:
                    print(f"❌ Error getting previous image: {e}")
                    return "I encountered an error while trying to access previous images in this conversation. Please upload an image or try again."
            elif use_previous_image and not input_image and not model_supports_input:
                # User wants to use previous image but the model doesn't support it
                print(f"⚠️ Model {model} doesn't support input images, ignoring use_previous_image=True")
                # Continue with text-to-image generation without previous image

            print(f"🎨 Generating image: {model}")

            # Process input_image if provided
            processed_input_image = None
            if input_image and input_image.strip():

                # Check if it's already base64 (from use_previous_image processing)
                if use_previous_image and len(input_image) > 100 and not input_image.startswith('im_'):
                    # It's already base64 encoded from previous image processing
                    processed_input_image = input_image
                # Check if input_image is a file ID (like 'im_mzp-QKbW.jpeg')
                elif input_image.startswith('im_') and ('.' in input_image):
                    # It's a file ID, need to convert to base64
                    try:
                        file_path = os.path.join(FILES_DIR, input_image)

                        # Ensure the files directory exists
                        os.makedirs(FILES_DIR, exist_ok=True)

                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                image_data = f.read()
                                processed_input_image = base64.b64encode(image_data).decode('utf-8')
                        else:
                            print(f"❌ Input image file not found: {file_path}")
                            processed_input_image = None
                    except Exception as e:
                        print(f"❌ Error reading input image file: {e}")
                        processed_input_image = None
                elif input_image.startswith('data:'):
                    # It's already a data URL, extract base64 part
                    processed_input_image = input_image.split(',')[1] if ',' in input_image else input_image
                else:
                    # Assume it's already base64 encoded
                    processed_input_image = input_image

            # Generate image using async generator (直接使用 await)
            try:
                file_id, width, height, file_path = await generator.generate(
                    prompt=prompt,
                    model=model,
                    aspect_ratio=aspect_ratio,
                    input_image=processed_input_image,
                    ctx={'session_id': session_id, 'tool_call_id': tool_call_id}
                )
            except Exception as e:
                print(f"❌ Image generation error: {e}")
                raise e

            print(f"✅ Generated image: {file_id} ({width}x{height})")

            # Save to database using synchronous operations
            try:
                # Use UserContextManager to set the correct user context for database operations
                effective_user_id = user_id
                if not effective_user_id:
                    # Fallback: try to get user_id from strands context
                    try:
                        from services.strands_context import get_user_id
                        effective_user_id = get_user_id()
                    except Exception:
                        pass

                if effective_user_id:
                    from services.user_context import UserContextManager
                    with UserContextManager(effective_user_id):
                        # 保存文件记录
                        db_service.create_file(file_id, file_path, width, height)

                        # 保存图像消息
                        if session_id:
                            # Create image message for database
                            image_message = {
                                'role': 'assistant',
                                'content': [
                                    {
                                        'type': 'image_url',
                                        'image_url': {
                                            'url': f'/api/file/{file_id}'
                                        }
                                    }
                                ]
                            }

                            db_service.create_message(session_id, 'assistant', json.dumps(image_message))
                else:
                    print(f"⚠️ No user_id available for database operations, skipping database save")

                # Always broadcast file_generated event to websocket (regardless of database save status)
                # 检查是否已经发送过这个file_generated事件
                file_event_key = f"file_generated_{session_id}_{file_id}_{tool_call_id}"
                if file_event_key in _sent_file_events:
                    print(f"🔄 Skipping duplicate file_generated event: {file_id}")
                else:
                    _sent_file_events.add(file_event_key)
                    message_data = {
                        'type': 'file_generated',
                        'file_id': file_id,
                        'file_path': file_path,
                        'width': width,
                        'height': height,
                        'tool_call_id': tool_call_id
                    }
                    print(f"🔍 DEBUG: Broadcasting file_generated message: {message_data}")
                    await broadcast_session_update(session_id, canvas_id, message_data, effective_user_id)
                    print(f"🔍 DEBUG: Successfully broadcasted file_generated message for session {session_id}")

            except Exception as db_error:
                print(f"🔍 DEBUG: Database save error: {db_error}")
                traceback.print_exc()
            
            return f"Image generated successfully! File ID: {file_id}, Size: {width}x{height}. The image has been saved and is ready for use."
            
        except Exception as e:
            print(f"Error generating image: {e}")
            traceback.print_exc()
            return f"Failed to generate image: {str(e)}"
    
    return generate_image_with_context


def generate_image_id():
    """生成图像ID"""
    return generate_file_id()


# 添加一个虚拟的工具函数来满足 strands 库的期望
# 这可以防止 "tool function missing" 警告
@tool
def strands_image_generators(
    message: str = Field(default="This is a placeholder tool", description="Placeholder message")
) -> str:
    """
    这是一个占位符工具，用于防止 strands 库的 "tool function missing" 警告。
    实际的图像生成功能由 create_generate_image_with_context 函数提供。

    Args:
        message: 占位符消息

    Returns:
        说明信息
    """
    return "This is a placeholder tool. Use create_generate_image_with_context for actual image generation."
