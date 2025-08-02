"""
Strands video generation tools
"""

import os
import traceback
import base64
import json
from typing import Dict, Any, Optional
from strands import tool
from pydantic import Field

# Import video generators
from tools.video_generators import ComfyUIVideoGenerator

# Import utilities
try:
    from nanoid import generate
except ImportError:
    # Fallback ID generation if nanoid is not available
    import random
    import string
    def generate(size=8):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=size))

# 生成唯一文件 ID
def generate_file_id():
    return 'vid_' + generate(size=8)
from services.config_service import FILES_DIR
from services.db_service import db_service
from services.strands_context import get_session_id, get_canvas_id, get_user_id
from services.websocket_service import broadcast_session_update

# Provider mapping
PROVIDERS = {
    'comfyui': ComfyUIVideoGenerator(),
}

# 全局变量来跟踪已发送的事件，防止重复
_sent_file_events = set()


def create_generate_video_with_context(session_id: str, canvas_id: str, video_model: dict, user_id: str = None):
    """创建一个带有上下文信息的 generate_video 工具"""
    from strands import tool

    @tool
    async def generate_video_with_context(
        prompt: str = Field(description="Detailed description of the video to generate"),
        input_image: str = Field(default="", description="Optional image to use as reference for image-to-video generation. Pass image_id here, e.g. 'im_jurheut7.png'. Leave empty for text-to-video generation."),
        duration: int = Field(default=5, description="Video duration in seconds (typically 3-10 seconds)"),
        use_previous_image: bool = Field(default=True, description="Whether to automatically use the most recent image from the current session as input for image-to-video generation")
    ) -> str:
        """
        Generate a video based on text prompt and optionally an input image.
        
        This tool can work in two modes:
        1. Text-to-Video (T2V): Generate video from text prompt only
        2. Image-to-Video (I2V): Generate video from text prompt + input image
        
        Args:
            prompt: Detailed description of what the video should contain
            input_image: Optional reference image ID for image-to-video generation
            duration: Video duration in seconds
            use_previous_image: Whether to automatically use the most recent image as input
            
        Returns:
            A message indicating successful video generation with file details
        """
        print("🎬 generate_video_with_context tool called!")
        print(f"🔍 DEBUG: Using provided context - session_id: {session_id}, canvas_id: {canvas_id}")
        print(f"🔍 DEBUG: Using provided video_model: {video_model}")
        print(f"🔍 DEBUG: Using provided user_id: {user_id}")
        
        try:
            # 使用提供的上下文信息而不是从contextvars获取
            tool_call_id = generate_file_id()
            
            model = video_model.get('model', 'wan-t2v')
            provider = video_model.get('provider', 'comfyui')
            
            print(f"🔍 DEBUG: model={model}, provider={provider}")
            
            # Get provider instance
            generator = PROVIDERS.get(provider)
            if not generator:
                raise ValueError(f"Unsupported provider: {provider}")
            
            # Handle input_image parameter
            if not isinstance(input_image, str):
                input_image = ""
                
            processed_input_image = None
            
            # Check if the model supports input images before using previous image
            model_supports_input = 'i2v' in model.lower() or 'image' in model.lower() or 'edit' in model.lower()

            # Handle use_previous_image logic - only for models that support input images
            if use_previous_image and not input_image and model_supports_input:
                print("🔍 DEBUG: use_previous_image=True, looking for previous image...")
                try:
                    # Use the more robust function from image generators
                    from tools.strands_image_generators import get_most_recent_image_from_session
                    previous_image_id = get_most_recent_image_from_session(session_id, user_id)
                    if previous_image_id:
                        print(f"🔍 DEBUG: Found previous image: {previous_image_id}")
                        input_image = previous_image_id
                    else:
                        print("🔍 DEBUG: No previous images found")
                except Exception as e:
                    print(f"⚠️ Warning: Could not retrieve previous image: {e}")
            elif use_previous_image and not input_image and not model_supports_input:
                # User wants to use previous image but the model doesn't support it
                print(f"⚠️ Model {model} doesn't support input images, ignoring use_previous_image=True")
                # Continue with text-to-video generation without previous image

            # Process input image if provided
            if input_image:
                print(f"🔍 DEBUG: Processing input image: {input_image}")
                try:
                    # Get file record from database
                    file_record = db_service.get_file(input_image)
                    
                    if file_record:
                        # 使用数据库中的文件路径
                        file_path = os.path.join(FILES_DIR, file_record['file_path'])
                    else:
                        # 尝试直接路径
                        file_path = os.path.join(FILES_DIR, input_image)
                        
                        # 如果文件不存在且没有扩展名，尝试常见扩展名
                        if not os.path.exists(file_path) and '.' not in input_image:
                            for ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                                test_path = f"{file_path}.{ext}"
                                if os.path.exists(test_path):
                                    file_path = test_path
                                    break
                    
                    if os.path.exists(file_path):
                        # Convert image to base64 for ComfyUI
                        with open(file_path, 'rb') as f:
                            image_data = f.read()
                            processed_input_image = base64.b64encode(image_data).decode('utf-8')
                        print(f"✅ Successfully loaded input image: {file_path}")
                    else:
                        print(f"⚠️ Warning: Input image file not found: {file_path}")
                        processed_input_image = None
                        
                except Exception as e:
                    print(f"⚠️ Warning: Error processing input image: {e}")
                    processed_input_image = None
            
            # Determine if this should be T2V or I2V based on input
            if processed_input_image:
                print("🔍 DEBUG: Using Image-to-Video (I2V) mode")
                # Force model to I2V if we have an input image
                if 't2v' in model.lower():
                    model = model.replace('t2v', 'i2v')
                elif 'i2v' not in model.lower():
                    model = 'wan-i2v'  # Default I2V model
            else:
                print("🔍 DEBUG: Using Text-to-Video (T2V) mode")
                # Force model to T2V if no input image
                if 'i2v' in model.lower():
                    model = model.replace('i2v', 't2v')
                elif 't2v' not in model.lower():
                    model = 'wan-t2v'  # Default T2V model
            
            print(f"🔍 DEBUG: Final model: {model}")

            # Generate video using async generator (直接使用 await)
            try:
                file_id, width, height, duration_seconds, file_path = await generator.generate(
                    prompt=prompt,
                    model=model,
                    input_image=processed_input_image,
                    duration=duration,
                    ctx={'session_id': session_id, 'tool_call_id': tool_call_id}
                )
            except Exception as e:
                print(f"❌ Video generation error: {e}")
                raise e

            print(f"✅ Generated video: {file_id} ({width}x{height}, {duration_seconds}s)")

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
                        print(f"🔍 DEBUG: Creating file record with user_id: {effective_user_id}")
                        # Create file record in database with video-specific metadata
                        db_service.create_file(file_id, file_path, width, height)
                        print(f"✅ File record created successfully")

                        # Save video message to database (similar to image generation)
                        if session_id:
                            # Create video message for database with download link
                            video_url = f"/api/file/{file_id}"
                            video_message_content = f"✅ Video generated successfully!\n\n📹 **Video Details:**\n- File ID: `{file_id}`\n- Dimensions: {width}x{height}\n- Duration: {duration_seconds} seconds\n- Model: {model}\n- Mode: {'Image-to-Video' if processed_input_image else 'Text-to-Video'}\n\n📥 **Download Video:**\n[Download {file_id}]({video_url})\n\nThe video has been saved and is ready for download."

                            video_message = {
                                'role': 'assistant',
                                'content': video_message_content
                            }

                            db_service.create_message(session_id, 'assistant', json.dumps(video_message))
                            print(f"✅ Video message saved to database")
                else:
                    print("⚠️ Warning: No user_id available, skipping database record creation")

            except Exception as e:
                print(f"⚠️ Warning: Error creating file record or saving message: {e}")
                # Continue even if database record creation fails

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
                    'duration': duration_seconds,
                    'tool_call_id': tool_call_id,
                    'file_type': 'video'
                }
                print(f"🔍 DEBUG: Broadcasting file_generated message: {message_data}")
                await broadcast_session_update(session_id, canvas_id, message_data, effective_user_id)
                print(f"🔍 DEBUG: Successfully broadcasted file_generated message for session {session_id}")

            # Return message with download link for video file
            video_url = f"/api/file/{file_id}"
            return f"✅ Video generated successfully!\n\n📹 **Video Details:**\n- File ID: `{file_id}`\n- Dimensions: {width}x{height}\n- Duration: {duration_seconds} seconds\n- Model: {model}\n- Mode: {'Image-to-Video' if processed_input_image else 'Text-to-Video'}\n\n📥 **Download Video:**\n[Download {file_id}]({video_url})\n\nThe video has been saved and is ready for download."
            
        except Exception as e:
            print(f"Error generating video: {e}")
            traceback.print_exc()
            return f"Failed to generate video: {str(e)}"
    
    return generate_video_with_context


def generate_video_id():
    """生成视频ID"""
    return generate_file_id()


# 添加一个虚拟的工具函数来满足 strands 库的期望
# 这可以防止 "tool function missing" 警告
@tool
def strands_video_generators(
    message: str = Field(default="This is a placeholder tool", description="Placeholder message")
) -> str:
    """
    这是一个占位符工具，用于防止 strands 库的 "tool function missing" 警告。
    实际的视频生成功能由 create_generate_video_with_context 函数提供。

    Args:
        message: 占位符消息

    Returns:
        说明信息
    """
    return "This is a placeholder tool. Use create_generate_video_with_context for actual video generation."
