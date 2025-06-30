"""
Strands格式的图像生成工具
只包含带上下文的图像生成工具
注意：此文件提供工具创建函数，不直接注册为工具
"""

# 告诉 strands 库不要自动注册此文件为工具
# 这可以防止 "tool function missing" 警告
__STRANDS_TOOL__ = False
__all__ = ['create_generate_image_with_context', 'generate_file_id', 'generate_image_id', 'strands_image_generators']
import random
import base64
import json
import time
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


async def get_most_recent_image_from_session(session_id: str) -> str:
    """
    从指定session中获取最近的图像ID（包括用户上传的和助手生成的）

    Args:
        session_id: 会话ID

    Returns:
        最近图像的文件ID，如果没有找到则返回空字符串
    """
    try:
        # 获取session的聊天历史
        messages = await db_service.get_chat_history(session_id)
        print(f"🔍 DEBUG: Found {len(messages)} messages in session {session_id}")

        # 从最新的消息开始查找图像消息
        for i, message in enumerate(reversed(messages)):
            print(f"🔍 DEBUG: Checking message {i}: role={message.get('role')}, content_type={type(message.get('content'))}")
            # 查找助手生成的图像和用户上传的图像
            if message.get('content'):
                content = message.get('content', [])

                # 处理字符串格式的content（可能包含图像引用）
                if isinstance(content, str):
                    print(f"🔍 DEBUG: Checking string content: {content[:100]}...")
                    # 查找字符串中的图像引用，如 ![...](/api/file/im_xxx.jpeg)
                    import re
                    image_pattern = r'/api/file/(im_[a-zA-Z0-9_-]+\.[a-zA-Z0-9]+)'
                    matches = re.findall(image_pattern, content)
                    if matches:
                        file_id = matches[-1]  # 取最后一个匹配的图像
                        print(f"🔍 DEBUG: Found recent image in session {session_id}: {file_id}")
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
                                print(f"🔍 DEBUG: Found recent image in session {session_id}: {file_id}")
                                return file_id

        print(f"🔍 DEBUG: No images found in session {session_id}")
        return ""

    except Exception as e:
        print(f"🔍 DEBUG: Error getting recent image from session {session_id}: {e}")
        return ""


# Initialize provider instances
PROVIDERS = {
    'replicate': ReplicateGenerator(),
    'comfyui': ComfyUIGenerator(),
    'wavespeed': WavespeedGenerator(),
    'jaaz': JaazGenerator(),
    'openai': OpenAIGenerator(),
}


def create_generate_image_with_context(session_id: str, canvas_id: str, image_model: dict):
    """创建一个带有上下文信息的 generate_image 工具"""
    from strands import tool

    @tool
    def generate_image_with_context(
        prompt: str = Field(description="Detailed description of the image to generate"),
        aspect_ratio: str = Field(default="1:1", description="Aspect ratio for the image (1:1, 4:3, 16:9, 3:4)"),
        input_image: str = Field(default="", description="Optional image to use as reference. Pass image_id here, e.g. 'im_jurheut7.png'. Leave empty if not needed. Best for image editing cases like: Editing specific parts of the image, Removing specific objects, Maintaining visual elements across scenes"),
        use_previous_image: bool = Field(default=False, description="Whether to automatically use the most recent image from the current session as input. Set to true when you want to edit or modify the previously generated image. This is useful for iterative image editing workflows where you want to build upon the last generated image.")
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
        print("🎨️ generate_image_with_context tool called!")
        print(f"🔍 DEBUG: Using provided context - session_id: {session_id}, canvas_id: {canvas_id}")
        print(f"🔍 DEBUG: Using provided image_model: {image_model}")
        
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

            # Handle use_previous_image parameter
            if use_previous_image and not input_image:
                print(f"🔍 DEBUG: use_previous_image=True, attempting to get previous image from session")
                try:
                    # Get the most recent image from the current session
                    previous_image_id = asyncio.run(get_most_recent_image_from_session(session_id))
                    if previous_image_id:
                        # Convert the file to base64
                        try:
                            # 首先尝试从数据库获取文件信息
                            file_record = None
                            file_id_without_ext = previous_image_id.split('.')[0] if '.' in previous_image_id else previous_image_id
                            try:
                                file_record = asyncio.run(db_service.get_file(file_id_without_ext))
                            except Exception as db_error:
                                print(f"🔍 DEBUG: Database lookup error: {db_error}")

                            file_path = None
                            if file_record:
                                # 使用数据库中的文件路径
                                file_path = os.path.join(FILES_DIR, file_record['file_path'])
                                print(f"🔍 DEBUG: Using database file path: {file_path}")
                            else:
                                # 尝试直接路径
                                file_path = os.path.join(FILES_DIR, previous_image_id)
                                print(f"🔍 DEBUG: Trying direct file path: {file_path}")

                                # 如果文件不存在且没有扩展名，尝试常见扩展名
                                if not os.path.exists(file_path) and '.' not in previous_image_id:
                                    for ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                                        test_path = os.path.join(FILES_DIR, f'{previous_image_id}.{ext}')
                                        print(f"🔍 DEBUG: Trying with extension: {test_path}")
                                        if os.path.exists(test_path):
                                            file_path = test_path
                                            break

                            if file_path and os.path.exists(file_path):
                                with open(file_path, 'rb') as f:
                                    image_data = f.read()
                                    input_image = base64.b64encode(image_data).decode('utf-8')
                                    print(f"🔍 DEBUG: Converted previous image to base64, length: {len(input_image)}")
                            else:
                                print(f"❌ DEBUG: Previous image file not found: {file_path}")
                                input_image = ""
                        except Exception as file_error:
                            print(f"❌ DEBUG: Error reading previous image file: {file_error}")
                            input_image = ""
                    else:
                        print(f"🔍 DEBUG: No previous image found in session {session_id}")
                except Exception as e:
                    print(f"🔍 DEBUG: Error getting previous image: {e}")

            print(f"🔍 DEBUG: Generator parameters - prompt='{prompt}', model='{model}', aspect_ratio='{aspect_ratio}', input_image='{input_image}', use_previous_image={use_previous_image}")
            
            # Process input_image if provided
            processed_input_image = None
            if input_image and input_image.strip():
                print(f"🔍 DEBUG: Processing input_image: {input_image}")

                # Check if it's already base64 (from use_previous_image processing)
                if use_previous_image and len(input_image) > 100 and not input_image.startswith('im_'):
                    # It's already base64 encoded from previous image processing
                    processed_input_image = input_image
                    print(f"🔍 DEBUG: Using previous image as base64, length: {len(processed_input_image)}")
                # Check if input_image is a file ID (like 'im_mzp-QKbW.jpeg')
                elif input_image.startswith('im_') and ('.' in input_image):
                    # It's a file ID, need to convert to base64
                    try:
                        file_path = os.path.join(FILES_DIR, input_image)
                        print(f"🔍 DEBUG: Reading image file from: {file_path}")
                        print(f"🔍 DEBUG: FILES_DIR = {FILES_DIR}")

                        # Ensure the files directory exists
                        os.makedirs(FILES_DIR, exist_ok=True)

                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                image_data = f.read()
                                processed_input_image = base64.b64encode(image_data).decode('utf-8')
                                print(f"🔍 DEBUG: Converted file to base64, length: {len(processed_input_image)}")
                        else:
                            print(f"❌ DEBUG: Input image file not found: {file_path}")
                            processed_input_image = None
                    except Exception as e:
                        print(f"❌ DEBUG: Error reading input image file: {e}")
                        processed_input_image = None
                elif input_image.startswith('data:'):
                    # It's already a data URL, extract base64 part
                    processed_input_image = input_image.split(',')[1] if ',' in input_image else input_image
                    print(f"🔍 DEBUG: Extracted base64 from data URL, length: {len(processed_input_image)}")
                else:
                    # Assume it's already base64 encoded
                    processed_input_image = input_image
                    print(f"🔍 DEBUG: Using input as base64, length: {len(processed_input_image)}")

            # Generate image
            try:
                file_id, width, height, file_path = asyncio.run(generator.generate(
                    prompt=prompt,
                    model=model,
                    aspect_ratio=aspect_ratio,
                    input_image=processed_input_image,
                    ctx={'session_id': session_id, 'tool_call_id': tool_call_id}
                ))
            except Exception as e:
                if "asyncio.run() cannot be called from a running event loop" in str(e):
                    print("🔍 DEBUG: Using different async approach")
                    # 使用同步方式调用异步函数
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # 如果事件循环正在运行，创建任务并等待
                            future = asyncio.ensure_future(generator.generate(
                                prompt=prompt,
                                model=model,
                                aspect_ratio=aspect_ratio,
                                input_image=processed_input_image,
                                ctx={'session_id': session_id, 'tool_call_id': tool_call_id}
                            ))
                            # 等待完成
                            while not future.done():
                                time.sleep(0.1)
                            file_id, width, height, file_path = future.result()
                        else:
                            file_id, width, height, file_path = loop.run_until_complete(generator.generate(
                                prompt=prompt,
                                model=model,
                                aspect_ratio=aspect_ratio,
                                input_image=processed_input_image,
                                ctx={'session_id': session_id, 'tool_call_id': tool_call_id}
                            ))
                    except Exception as async_error:
                        print(f"🔍 DEBUG: Async error: {async_error}")
                        raise async_error
                else:
                    raise e
            
            print(f"🔍 DEBUG: Generated image: file_id={file_id}, size: {width}x{height}")
            
            # Save to database
            try:
                asyncio.run(db_service.create_file(file_id, file_path, width, height))
            except Exception as db_error:
                print(f"🔍 DEBUG: Database save error: {db_error}")
            
            # Save image message to database and broadcast to websocket
            if session_id:
                try:
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

                    # Save image message to database
                    print(f"🔍 DEBUG: Saving image message to database for session {session_id}")
                    asyncio.run(db_service.create_message(session_id, 'assistant', json.dumps(image_message)))
                    print(f"🔍 DEBUG: Image message saved to database")

                    # Broadcast file_generated event to websocket
                    message_data = {
                        'type': 'file_generated',
                        'file_id': file_id,
                        'file_path': file_path,
                        'width': width,
                        'height': height,
                        'tool_call_id': tool_call_id
                    }
                    print(f"🔍 DEBUG: Broadcasting file_generated message: {message_data}")
                    asyncio.run(broadcast_session_update(session_id, canvas_id, message_data))
                    print(f"🔍 DEBUG: Successfully broadcasted file_generated message for session {session_id}")
                except Exception as ws_error:
                    print(f"🔍 DEBUG: Websocket broadcast error: {ws_error}")
                    import traceback
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
