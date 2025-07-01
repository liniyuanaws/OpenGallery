from typing import List, Dict, Any, Optional
from .database_interface import DatabaseFactory, DatabaseInterface
from .config_service import config_service

class UnifiedDatabaseService:
    """Unified database service that can use either SQLite or DynamoDB"""
    
    def __init__(self):
        self.primary_db: DatabaseInterface = None
        self.backup_db: DatabaseInterface = None
        self._initialize_databases()
    
    def _initialize_databases(self):
        """Initialize primary and backup databases based on configuration"""
        db_config = config_service.get_database_config()
        db_type = db_config.get('type', 'sqlite').lower()
        
        try:
            if db_type == 'dynamodb':
                # Primary: DynamoDB, Backup: SQLite
                print("Initializing DynamoDB as primary database")
                dynamodb_config = db_config.get('dynamodb', {})
                self.primary_db = DatabaseFactory.create_database(
                    'dynamodb', 
                    region_name=dynamodb_config.get('region', 'us-west-2')
                )
                
                print("Initializing SQLite as backup database")
                sqlite_config = db_config.get('sqlite', {})
                self.backup_db = DatabaseFactory.create_database(
                    'sqlite',
                    db_path=sqlite_config.get('path')
                )
            else:
                # Primary: SQLite, Backup: None (for now)
                print("Initializing SQLite as primary database")
                sqlite_config = db_config.get('sqlite', {})
                self.primary_db = DatabaseFactory.create_database(
                    'sqlite',
                    db_path=sqlite_config.get('path')
                )
                print("No backup database configured for SQLite mode")
                
        except Exception as e:
            print(f"Error initializing primary database: {e}")
            print("Falling back to SQLite")
            # Fallback to SQLite if DynamoDB fails
            self.primary_db = DatabaseFactory.create_database('sqlite')
            self.backup_db = None
    
    async def _execute_with_fallback(self, operation_name: str, *args, **kwargs):
        """Execute database operation with fallback to backup if primary fails"""
        try:
            # Try primary database first
            method = getattr(self.primary_db, operation_name)
            result = await method(*args, **kwargs)
            
            # If we have a backup database and the operation was a write operation,
            # also execute on backup for data consistency
            if self.backup_db and operation_name in [
                'create_canvas', 'save_canvas_data', 'rename_canvas', 'delete_canvas',
                'create_chat_session', 'update_chat_session_title', 'delete_chat_session',
                'create_message', 'create_comfy_workflow', 'delete_comfy_workflow',
                'create_file', 'delete_file', 'set_db_version'
            ]:
                try:
                    backup_method = getattr(self.backup_db, operation_name)
                    await backup_method(*args, **kwargs)
                    print(f"Successfully synced {operation_name} to backup database")
                except Exception as backup_error:
                    print(f"Warning: Failed to sync {operation_name} to backup database: {backup_error}")
            
            return result
            
        except Exception as primary_error:
            print(f"Primary database operation {operation_name} failed: {primary_error}")
            
            # If primary fails and we have a backup, try backup
            if self.backup_db:
                try:
                    print(f"Attempting {operation_name} on backup database")
                    backup_method = getattr(self.backup_db, operation_name)
                    return await backup_method(*args, **kwargs)
                except Exception as backup_error:
                    print(f"Backup database operation {operation_name} also failed: {backup_error}")
                    raise backup_error
            else:
                raise primary_error
    
    # Canvas operations
    async def create_canvas(self, id: str, name: str):
        """Create a new canvas"""
        return await self._execute_with_fallback('create_canvas', id, name)
    
    async def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases"""
        return await self._execute_with_fallback('list_canvases')
    
    async def get_canvas(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas by ID"""
        return await self._execute_with_fallback('get_canvas', id)
    
    async def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data"""
        return await self._execute_with_fallback('save_canvas_data', id, data, thumbnail)
    
    async def rename_canvas(self, id: str, name: str):
        """Rename canvas"""
        return await self._execute_with_fallback('rename_canvas', id, name)
    
    async def delete_canvas(self, id: str):
        """Delete canvas"""
        return await self._execute_with_fallback('delete_canvas', id)
    
    # Chat session operations
    async def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        return await self._execute_with_fallback('create_chat_session', id, model, provider, canvas_id, title)
    
    async def list_chat_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """Get chat sessions for a canvas"""
        return await self._execute_with_fallback('list_chat_sessions', canvas_id)
    
    async def get_chat_session(self, id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID"""
        return await self._execute_with_fallback('get_chat_session', id)
    
    async def update_chat_session_title(self, id: str, title: str):
        """Update chat session title"""
        return await self._execute_with_fallback('update_chat_session_title', id, title)
    
    async def delete_chat_session(self, id: str):
        """Delete chat session"""
        return await self._execute_with_fallback('delete_chat_session', id)
    
    # Chat message operations
    async def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message"""
        return await self._execute_with_fallback('create_message', session_id, role, message)
    
    async def list_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages for a chat session"""
        return await self._execute_with_fallback('list_messages', session_id)
    
    # ComfyUI workflow operations
    async def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow"""
        return await self._execute_with_fallback('create_comfy_workflow', name, api_json, description, inputs, outputs)
    
    async def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows"""
        return await self._execute_with_fallback('list_comfy_workflows')
    
    async def get_comfy_workflow(self, id: int) -> Optional[Dict[str, Any]]:
        """Get comfy workflow by ID"""
        return await self._execute_with_fallback('get_comfy_workflow', id)

    async def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow"""
        return await self._execute_with_fallback('delete_comfy_workflow', id)
    
    # File operations
    async def create_file(self, file_id: str, file_path: str, width: int = None, height: int = None):
        """Create a new file record"""
        return await self._execute_with_fallback('create_file', file_id, file_path, width, height)
    
    async def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        return await self._execute_with_fallback('get_file', file_id)
    
    async def list_files(self) -> List[Dict[str, Any]]:
        """List all files"""
        return await self._execute_with_fallback('list_files')
    
    async def delete_file(self, file_id: str):
        """Delete a file record"""
        return await self._execute_with_fallback('delete_file', file_id)
    
    # Database version operations
    async def get_db_version(self) -> int:
        """Get current database version"""
        return await self._execute_with_fallback('get_db_version')
    
    async def set_db_version(self, version: int):
        """Set database version"""
        return await self._execute_with_fallback('set_db_version', version)

# Create a singleton instance
unified_db_service = UnifiedDatabaseService()
