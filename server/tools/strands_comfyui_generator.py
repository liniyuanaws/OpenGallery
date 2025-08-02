"""
智能 ComfyUI 生成工具
根据模型名称自动判断是图像还是视频生成
"""

import os
import traceback
from typing import Dict, Any, Optional
from strands import tool
from pydantic import Field

from services.strands_context import get_session_id, get_canvas_id, get_user_id


def create_smart_comfyui_generator(session_id: str, canvas_id: str, comfyui_model: Dict[str, Any], user_id: str = None):
    """
    创建智能的 ComfyUI 生成工具，根据模型自动判断生成类型
    
    Args:
        session_id: 会话ID
        canvas_id: 画布ID
        comfyui_model: ComfyUI 模型配置
        user_id: 用户ID
    """
    
    @tool
    async def generate_with_comfyui(
        prompt: str = Field(..., description="Detailed description of what to generate"),
        aspect_ratio: str = Field(default="1:1", description="Aspect ratio (1:1, 16:9, 4:3, 3:4, 9:16)"),
        input_image: str = Field(default="", description="Input image file ID for image-to-image or image-to-video generation"),
        use_previous_image: bool = Field(default=True, description="Whether to use the most recent image from this conversation as input"),
        duration: int = Field(default=5, description="Video duration in seconds (for video generation only)")
    ) -> str:
        """
        Smart ComfyUI generator that automatically determines whether to generate images or videos
        based on the selected model. Supports both text-to-image/video and image-to-image/video generation.
        
        Model types:
        - flux-* models: Generate images
        - wan-* models: Generate videos
        
        Args:
            prompt: Detailed description of what to generate
            aspect_ratio: Aspect ratio for the output
            input_image: Input image file ID for I2I/I2V generation
            use_previous_image: Whether to use the most recent image from conversation
            duration: Video duration in seconds (for video models only)
        """
        try:
            model_name = comfyui_model.get('model', '')
            media_type = comfyui_model.get('media_type', '')
            
            print(f"🎨🎬 Smart ComfyUI Generator: model={model_name}, media_type={media_type}")
            
            # 根据模型名称或 media_type 判断生成类型
            is_video_model = (
                'wan-' in model_name.lower() or 
                'video' in model_name.lower() or 
                media_type == 'video'
            )
            
            if is_video_model:
                print(f"🎬 Detected video model, using video generation")
                # 使用视频生成工具
                from tools.strands_video_generators import create_generate_video_with_context
                video_generator = create_generate_video_with_context(session_id, canvas_id, comfyui_model, user_id)

                return await video_generator(
                    prompt=prompt,
                    input_image=input_image,
                    use_previous_image=use_previous_image,
                    duration=duration
                )
            else:
                print(f"🎨 Detected image model, using image generation")
                # 使用图像生成工具
                from tools.strands_image_generators import create_generate_image_with_context
                image_generator = create_generate_image_with_context(session_id, canvas_id, comfyui_model, user_id)

                return await image_generator(
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    input_image=input_image,
                    use_previous_image=use_previous_image
                )
                
        except Exception as e:
            print(f"❌ Smart ComfyUI Generator error: {e}")
            traceback.print_exc()
            return f"❌ Generation Error: {str(e)}"
    
    return generate_with_comfyui


def get_smart_comfyui_tools():
    """返回智能 ComfyUI 工具列表"""
    return [create_smart_comfyui_generator]
