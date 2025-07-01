import os
import time
from fastapi import APIRouter
import requests
from services.config_service import config_service
from services.db_service import db_service

#services
from services.files_service import download_file
from services.websocket_service import broadcast_init_done

router = APIRouter(prefix="/api")

# @router.get("/workspace_list")
# async def workspace_list():
#     return [{"name": entry.name, "is_dir": entry.is_dir(), "path": str(entry)} for entry in Path(WORKSPACE_ROOT).iterdir()]

async def initialize():
    # await initialize_mcp()
    await broadcast_init_done()

@router.get("/workspace_download")
async def workspace_download(path: str):
    return download_file(path)

def get_ollama_model_list():
    # Check if Ollama is configured with API key or models
    ollama_config = config_service.get_config().get('ollama', {})

    # Skip Ollama if no models are configured and no API key is set
    if not ollama_config.get('models') and not ollama_config.get('api_key'):
        return []

    base_url = ollama_config.get('url', os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
    try:
        response = requests.get(f'{base_url}/api/tags', timeout=5)
        response.raise_for_status()
        data = response.json()
        return [model['name'] for model in data.get('models', [])]
    except requests.RequestException as e:
        # Only print error if Ollama is explicitly configured
        if ollama_config.get('models') or ollama_config.get('api_key'):
            print(f"Error querying Ollama: {e}")
        return []


@router.get("/list_models")
async def get_models():
    config = config_service.get_config()
    res = []
    ollama_models = get_ollama_model_list()
    ollama_url = config_service.get_config().get('ollama', {}).get(
        'url', os.getenv('OLLAMA_HOST', 'http://localhost:11434'))

    # Only print ollama_models if there are any or if Ollama is configured
    ollama_config = config_service.get_config().get('ollama', {})
    if ollama_models or ollama_config.get('models') or ollama_config.get('api_key'):
        print('👇ollama_models', ollama_models)
    for ollama_model in ollama_models:
        res.append({
            'provider': 'ollama',
            'model': ollama_model,
            'url': ollama_url,
            'type': 'text'
        })
    for provider in config.keys():
        models = config[provider].get('models', {})
        for model_name in models:
            if provider == 'ollama':
                continue
            # Skip providers that require API key but don't have one (except bedrock and comfyui)
            if provider not in ['comfyui', 'bedrock'] and config[provider].get('api_key', '') == '':
                continue
            model = models[model_name]
            res.append({
                'provider': provider,
                'model': model_name,
                'url': config[provider].get('url', ''),
                'type': model.get('type', 'text')
            })
    return res


@router.get("/list_chat_sessions")
async def list_chat_sessions():
    return await db_service.list_sessions()


@router.get("/chat_session/{session_id}")
async def get_chat_session(session_id: str):
    """获取聊天历史和最后一幅图像信息"""
    messages = await db_service.get_chat_history(session_id)

    # 获取最后一幅图像
    last_image_id = ""
    try:
        from tools.strands_image_generators import get_most_recent_image_from_session
        last_image_id = await get_most_recent_image_from_session(session_id)
    except Exception as e:
        print(f"❌ Error getting last image for session {session_id}: {e}")

    return {
        "messages": messages,
        "last_image_id": last_image_id
    }

@router.get("/chat_session/{session_id}/status")
async def get_chat_session_status(session_id: str):
    """获取会话状态，包括消息和处理状态"""
    from services.stream_service import get_stream_task

    messages = await db_service.get_chat_history(session_id)
    task = get_stream_task(session_id)
    is_processing = task is not None and not task.done()

    return {
        "session_id": session_id,
        "messages": messages,
        "is_processing": is_processing,
        "timestamp": int(time.time() * 1000)  # 毫秒时间戳
    }
