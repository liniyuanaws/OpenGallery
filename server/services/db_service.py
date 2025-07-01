from typing import List, Dict, Any, Optional
from .unified_db_service import unified_db_service

class DatabaseService:
    """Legacy database service that delegates to unified database service"""

    def __init__(self):
        # The unified service handles all initialization
        self.unified_service = unified_db_service

    async def create_canvas(self, id: str, name: str):
        """Create a new canvas"""
        return await self.unified_service.create_canvas(id, name)

    async def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases"""
        return await self.unified_service.list_canvases()

    async def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        return await self.unified_service.create_chat_session(id, model, provider, canvas_id, title)

    async def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message"""
        return await self.unified_service.create_message(session_id, role, message)

    async def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session"""
        messages_data = await self.unified_service.list_messages(session_id)

        messages = []
        for row in messages_data:
            if row.get('message'):
                try:
                    import json
                    msg = json.loads(row['message'])
                    messages.append(msg)
                except:
                    pass

        return messages

    async def list_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """List all chat sessions"""
        return await self.unified_service.list_chat_sessions(canvas_id)

    async def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data"""
        return await self.unified_service.save_canvas_data(id, data, thumbnail)

    async def get_canvas_data(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas data"""
        canvas = await self.unified_service.get_canvas(id)
        if not canvas:
            return None

        sessions = await self.list_sessions(id)

        import json
        return {
            'data': json.loads(canvas.get('data', '{}')) if canvas.get('data') else {},
            'name': canvas.get('name', ''),
            'sessions': sessions
        }

    async def delete_canvas(self, id: str):
        """Delete canvas and related data"""
        return await self.unified_service.delete_canvas(id)

    async def rename_canvas(self, id: str, name: str):
        """Rename canvas"""
        return await self.unified_service.rename_canvas(id, name)

    async def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow"""
        return await self.unified_service.create_comfy_workflow(name, api_json, description, inputs, outputs)

    async def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows"""
        return await self.unified_service.list_comfy_workflows()

    async def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow"""
        return await self.unified_service.delete_comfy_workflow(id)

    async def create_file(self, file_id: str, file_path: str, width: int = None, height: int = None):
        """Create a new file record"""
        return await self.unified_service.create_file(file_id, file_path, width, height)

    async def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        return await self.unified_service.get_file(file_id)

    async def list_files(self) -> List[Dict[str, Any]]:
        """List all files"""
        return await self.unified_service.list_files()

    async def delete_file(self, file_id: str):
        """Delete a file record"""
        return await self.unified_service.delete_file(file_id)

# Create a singleton instance
db_service = DatabaseService()