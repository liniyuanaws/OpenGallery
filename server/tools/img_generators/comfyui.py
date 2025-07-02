from typing import Optional, Dict, Any
import os
import json
import sys
import copy
import random
import traceback
try:
    from .base import ImageGenerator, get_image_info_and_save, generate_image_id
except ImportError:
    # 使用绝对导入作为备用
    from tools.img_generators.base import ImageGenerator, get_image_info_and_save, generate_image_id
from services.config_service import config_service, FILES_DIR
from routers.comfyui_execution import execute


def get_asset_path(filename):
    # To get the correct path for pyinstaller bundled application
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle, the path is relative to the executable
        base_path = sys._MEIPASS
    else:
        # If the application is run in a normal Python environment
        base_path = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))

    return os.path.join(base_path, 'asset', filename)


class ComfyUIGenerator(ImageGenerator):
    """ComfyUI image generator implementation"""

    def __init__(self):
        # Load workflows
        asset_dir = get_asset_path('flux_comfy_workflow.json')
        basic_comfy_t2i_workflow = get_asset_path(
            'default_comfy_t2i_workflow.json')
        flux_kontext_workflow = get_asset_path(
            'flux_kontext_workflow.json')

        self.flux_comfy_workflow = None
        self.basic_comfy_t2i_workflow = None
        self.flux_kontext_workflow = None

        try:
            self.flux_comfy_workflow = json.load(open(asset_dir, 'r'))
            self.basic_comfy_t2i_workflow = json.load(
                open(basic_comfy_t2i_workflow, 'r'))
            self.flux_kontext_workflow = json.load(
                open(flux_kontext_workflow, 'r'))
        except Exception as e:
            traceback.print_exc()

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_image: Optional[str] = None,
        **kwargs
    ) -> tuple[str, int, int, str]:
        # Get context from kwargs
        ctx = kwargs.get('ctx', {})
        print(f"🎨 ComfyUI generating: {model}")

        api_url = config_service.app_config.get('comfyui', {}).get('url', '')

        if not api_url:
            raise Exception("ComfyUI URL not configured")

        api_url = api_url.replace('http://', '').replace('https://', '')
        host = api_url.split(':')[0]
        port = api_url.split(':')[1]

        # Handle flux-kontext model
        if 'kontext' in model:
            if not self.flux_kontext_workflow:
                raise Exception('Flux kontext workflow json not found')
            return await self._run_flux_kontext_workflow(prompt, input_image, host, port, ctx)

        # Handle other flux models
        elif 'flux' in model:
            print(f"🔍 DEBUG: Using flux workflow for model: {model}")
            if not self.flux_comfy_workflow:
                raise Exception('Flux workflow json not found')
            workflow = copy.deepcopy(self.flux_comfy_workflow)
            workflow['6']['inputs']['text'] = prompt
            workflow['31']['inputs']['seed'] = random.randint(0, 99999999998)
            print(f"🔍 DEBUG: Flux workflow configured with prompt and model")
        else:
            print(f"🔍 DEBUG: Using basic workflow for model: {model}")
            if not self.basic_comfy_t2i_workflow:
                raise Exception('Basic workflow json not found')
            workflow = copy.deepcopy(self.basic_comfy_t2i_workflow)
            workflow['6']['inputs']['text'] = prompt
            workflow['4']['inputs']['ckpt_name'] = model
            print(f"🔍 DEBUG: Basic workflow configured with prompt and model")

        execution = await execute(workflow, host, port, ctx=ctx)

        if not execution.outputs:
            raise Exception("No outputs from ComfyUI execution")

        url = execution.outputs[0]

        # get image dimensions
        image_id = generate_image_id()
        mime_type, width, height, extension = await get_image_info_and_save(
            url, os.path.join(FILES_DIR, f'{image_id}')
        )
        filename = f'{image_id}.{extension}'
        return image_id, width, height, filename

    async def _run_flux_kontext_workflow(self, user_prompt: str, input_image_base64: Optional[str], host: str, port: str, ctx: dict) -> tuple[str, int, int, str]:
        """
        Run flux kontext workflow similar to the provided reference implementation
        """
        workflow = copy.deepcopy(self.flux_kontext_workflow)

        if input_image_base64:
            workflow['197']['inputs']['image'] = input_image_base64
        else:
            # When no input image is provided, create a simple 1x1 pixel transparent PNG as placeholder
            # This prevents the ETN_LoadImageBase64 node from failing with empty string
            # 1x1 transparent PNG in base64
            placeholder_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQIHWNgAAIAAAUAAY27m/MAAAAASUVORK5CYII="
            workflow['197']['inputs']['image'] = placeholder_image
            print("🔍 DEBUG: Using placeholder image for flux-kontext workflow (no input image provided)")

        workflow['196']['inputs']['text'] = user_prompt
        workflow['31']['inputs']['seed'] = random.randint(0, 99999999998)

        execution = await execute(workflow, host, port, ctx=ctx)

        if not execution.outputs:
            raise Exception('No outputs from flux kontext workflow')

        url = execution.outputs[0]

        # get image dimensions
        image_id = generate_image_id()
        mime_type, width, height, extension = await get_image_info_and_save(
            url, os.path.join(FILES_DIR, f'{image_id}')
        )
        filename = f'{image_id}.{extension}'
        return image_id, width, height, filename
