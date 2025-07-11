from typing import List, Dict, Any, Optional
from .unified_db_service import unified_db_service
from .user_aware_db_service import user_aware_db_service
from .user_context import get_current_user_id

class DatabaseService:
    """Database service that enforces user isolation"""

    def __init__(self):
        # Use the user-aware service for multi-tenant support
        self.user_aware_service = user_aware_db_service
        # Keep unified service for backward compatibility
        self.unified_service = unified_db_service

    def create_canvas(self, id: str, name: str):
        """Create a new canvas for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.create_canvas(id, name, user_id)

    def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.list_canvases(user_id)

    def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.create_chat_session(id, model, provider, canvas_id, user_id, title)

    def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.create_message(session_id, role, message, user_id)

    def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session for the current user"""
        user_id = get_current_user_id()
        messages_data = self.user_aware_service.list_messages(session_id, user_id)

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

    def list_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """List all chat sessions for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.list_chat_sessions(canvas_id, user_id)

    def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.save_canvas_data(id, data, user_id, thumbnail)

    def get_canvas_data(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas data for the current user"""
        user_id = get_current_user_id()
        canvas = self.user_aware_service.get_canvas(id, user_id)
        if not canvas:
            return None

        sessions = self.list_sessions(id)

        import json
        return {
            'data': json.loads(canvas.get('data', '{}')) if canvas.get('data') else {},
            'name': canvas.get('name', ''),
            'sessions': sessions
        }

    def delete_canvas(self, id: str):
        """Delete canvas and related data for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.delete_canvas(id, user_id)

    def rename_canvas(self, id: str, name: str):
        """Rename canvas for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.rename_canvas(id, name, user_id)

    def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.create_comfy_workflow(name, api_json, description, inputs, user_id, outputs)

    def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.list_comfy_workflows(user_id)

    def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.delete_comfy_workflow(id, user_id)

    def create_file(self, file_id: str, file_path: str, width: int = None, height: int = None):
        """Create a new file record for the current user"""
        user_id = get_current_user_id()
        return self.user_aware_service.create_file(file_id, file_path, user_id, width, height)

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        return self.unified_service.get_file(file_id)

    def list_files(self) -> List[Dict[str, Any]]:
        """List all files"""
        return self.unified_service.list_files()

    def delete_file(self, file_id: str):
        """Delete a file record"""
        return self.unified_service.delete_file(file_id)

# Create a singleton instance
db_service = DatabaseService()