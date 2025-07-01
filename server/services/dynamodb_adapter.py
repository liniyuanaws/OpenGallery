from typing import List, Dict, Any, Optional
from .database_interface import DatabaseInterface
from .dynamodb_service import DynamoDBService

class DynamoDBAdapter(DatabaseInterface):
    """DynamoDB adapter implementing the database interface"""
    
    def __init__(self, region_name='us-west-2'):
        self.dynamodb_service = DynamoDBService(region_name=region_name)
    
    # Canvas operations
    async def create_canvas(self, id: str, name: str):
        """Create a new canvas"""
        return await self.dynamodb_service.create_canvas(id, name)
    
    async def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases"""
        return await self.dynamodb_service.list_canvases()
    
    async def get_canvas(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas by ID"""
        return await self.dynamodb_service.get_canvas(id)
    
    async def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data"""
        return await self.dynamodb_service.save_canvas_data(id, data, thumbnail)
    
    async def rename_canvas(self, id: str, name: str):
        """Rename canvas"""
        return await self.dynamodb_service.rename_canvas(id, name)
    
    async def delete_canvas(self, id: str):
        """Delete canvas"""
        return await self.dynamodb_service.delete_canvas(id)
    
    # Chat session operations
    async def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        return await self.dynamodb_service.create_chat_session(id, model, provider, canvas_id, title)
    
    async def list_chat_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """Get chat sessions for a canvas"""
        return await self.dynamodb_service.list_chat_sessions(canvas_id)
    
    async def get_chat_session(self, id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID"""
        return await self.dynamodb_service.get_chat_session(id)
    
    async def update_chat_session_title(self, id: str, title: str):
        """Update chat session title"""
        return await self.dynamodb_service.update_chat_session_title(id, title)
    
    async def delete_chat_session(self, id: str):
        """Delete chat session"""
        return await self.dynamodb_service.delete_chat_session(id)
    
    # Chat message operations
    async def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message"""
        return await self.dynamodb_service.create_message(session_id, role, message)
    
    async def list_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages for a chat session"""
        return await self.dynamodb_service.list_messages(session_id)
    
    # ComfyUI workflow operations
    async def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow"""
        return await self.dynamodb_service.create_comfy_workflow(name, api_json, description, inputs, outputs)
    
    async def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows"""
        return await self.dynamodb_service.list_comfy_workflows()
    
    async def get_comfy_workflow(self, id: int) -> Optional[Dict[str, Any]]:
        """Get comfy workflow by ID"""
        return await self.dynamodb_service.get_comfy_workflow(id)

    async def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow"""
        return await self.dynamodb_service.delete_comfy_workflow(id)
    
    # File operations
    async def create_file(self, file_id: str, file_path: str, width: int = None, height: int = None):
        """Create a new file record"""
        return await self.dynamodb_service.create_file(file_id, file_path, width, height)
    
    async def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        return await self.dynamodb_service.get_file(file_id)
    
    async def list_files(self) -> List[Dict[str, Any]]:
        """List all files"""
        return await self.dynamodb_service.list_files()
    
    async def delete_file(self, file_id: str):
        """Delete a file record"""
        return await self.dynamodb_service.delete_file(file_id)
    
    # Database version operations
    async def get_db_version(self) -> int:
        """Get current database version"""
        return await self.dynamodb_service.get_db_version()
    
    async def set_db_version(self, version: int):
        """Set database version"""
        return await self.dynamodb_service.set_db_version(version)
