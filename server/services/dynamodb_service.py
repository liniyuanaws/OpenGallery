import boto3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError
import uuid

class DynamoDBService:
    def __init__(self, region_name='us-west-2'):
        """Initialize DynamoDB service"""
        self.region_name = region_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.client = boto3.client('dynamodb', region_name=region_name)
        
        # Table names
        self.tables = {
            'canvases': 'jaaz-canvases',
            'chat_sessions': 'jaaz-chat-sessions', 
            'chat_messages': 'jaaz-chat-messages',
            'comfy_workflows': 'jaaz-comfy-workflows',
            'files': 'jaaz-files',
            'db_version': 'jaaz-db-version'
        }
        
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """Create tables if they don't exist"""
        try:
            # Create canvases table
            self._create_table_if_not_exists(
                table_name=self.tables['canvases'],
                key_schema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'updated_at', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'updated_at-index',
                        'KeySchema': [
                            {'AttributeName': 'updated_at', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )
            
            # Create chat_sessions table
            self._create_table_if_not_exists(
                table_name=self.tables['chat_sessions'],
                key_schema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'canvas_id', 'AttributeType': 'S'},
                    {'AttributeName': 'updated_at', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'canvas_id-updated_at-index',
                        'KeySchema': [
                            {'AttributeName': 'canvas_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )
            
            # Create chat_messages table
            self._create_table_if_not_exists(
                table_name=self.tables['chat_messages'],
                key_schema=[
                    {'AttributeName': 'session_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'id', 'KeyType': 'RANGE'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'session_id', 'AttributeType': 'S'},
                    {'AttributeName': 'id', 'AttributeType': 'S'}
                ]
            )
            
            # Create comfy_workflows table
            self._create_table_if_not_exists(
                table_name=self.tables['comfy_workflows'],
                key_schema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'updated_at', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'updated_at-index',
                        'KeySchema': [
                            {'AttributeName': 'updated_at', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )
            
            # Create files table
            self._create_table_if_not_exists(
                table_name=self.tables['files'],
                key_schema=[
                    {'AttributeName': 'id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'created_at', 'AttributeType': 'S'}
                ],
                global_secondary_indexes=[
                    {
                        'IndexName': 'created_at-index',
                        'KeySchema': [
                            {'AttributeName': 'created_at', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ]
            )
            
            # Create db_version table
            self._create_table_if_not_exists(
                table_name=self.tables['db_version'],
                key_schema=[
                    {'AttributeName': 'version', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'version', 'AttributeType': 'N'}
                ]
            )
            
        except Exception as e:
            print(f"Error creating DynamoDB tables: {e}")
            raise
    
    def _create_table_if_not_exists(self, table_name: str, key_schema: List[Dict], 
                                   attribute_definitions: List[Dict], 
                                   global_secondary_indexes: List[Dict] = None):
        """Create a table if it doesn't exist"""
        try:
            # Check if table exists
            self.client.describe_table(TableName=table_name)
            print(f"Table {table_name} already exists")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Table doesn't exist, create it
                print(f"Creating table {table_name}")
                
                table_params = {
                    'TableName': table_name,
                    'KeySchema': key_schema,
                    'AttributeDefinitions': attribute_definitions,
                    'BillingMode': 'PROVISIONED',
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
                
                if global_secondary_indexes:
                    table_params['GlobalSecondaryIndexes'] = global_secondary_indexes
                
                self.client.create_table(**table_params)
                
                # Wait for table to be created
                waiter = self.client.get_waiter('table_exists')
                waiter.wait(TableName=table_name)
                print(f"Table {table_name} created successfully")
            else:
                raise
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    # Canvas operations
    def create_canvas(self, id: str, name: str):
        """Create a new canvas"""
        table = self.dynamodb.Table(self.tables['canvases'])
        timestamp = self._get_current_timestamp()

        item = {
            'id': id,
            'name': name,
            'description': '',
            'thumbnail': '',
            'created_at': timestamp,
            'updated_at': timestamp
        }

        table.put_item(Item=item)

    def list_canvases(self) -> List[Dict[str, Any]]:
        """Get all canvases"""
        table = self.dynamodb.Table(self.tables['canvases'])

        response = table.scan()
        items = response.get('Items', [])

        # Sort by updated_at DESC
        items.sort(key=lambda x: x.get('updated_at', ''), reverse=True)

        return items

    def get_canvas(self, id: str) -> Optional[Dict[str, Any]]:
        """Get canvas by ID"""
        table = self.dynamodb.Table(self.tables['canvases'])

        response = table.get_item(Key={'id': id})
        return response.get('Item')

    def save_canvas_data(self, id: str, data: str, thumbnail: str = None):
        """Save canvas data"""
        table = self.dynamodb.Table(self.tables['canvases'])
        timestamp = self._get_current_timestamp()

        update_expression = "SET #data = :data, updated_at = :updated_at"
        expression_attribute_names = {'#data': 'data'}
        expression_attribute_values = {
            ':data': data,
            ':updated_at': timestamp
        }

        if thumbnail:
            update_expression += ", thumbnail = :thumbnail"
            expression_attribute_values[':thumbnail'] = thumbnail

        table.update_item(
            Key={'id': id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )

    def rename_canvas(self, id: str, name: str):
        """Rename canvas"""
        table = self.dynamodb.Table(self.tables['canvases'])
        timestamp = self._get_current_timestamp()

        table.update_item(
            Key={'id': id},
            UpdateExpression="SET #name = :name, updated_at = :updated_at",
            ExpressionAttributeNames={'#name': 'name'},
            ExpressionAttributeValues={
                ':name': name,
                ':updated_at': timestamp
            }
        )

    def delete_canvas(self, id: str):
        """Delete canvas"""
        table = self.dynamodb.Table(self.tables['canvases'])
        table.delete_item(Key={'id': id})

    # Chat session operations
    def create_chat_session(self, id: str, model: str, provider: str, canvas_id: str, title: Optional[str] = None):
        """Save a new chat session"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])
        timestamp = self._get_current_timestamp()

        item = {
            'id': id,
            'model': model,
            'provider': provider,
            'canvas_id': canvas_id,
            'title': title or '',
            'created_at': timestamp,
            'updated_at': timestamp
        }

        table.put_item(Item=item)

    def list_chat_sessions(self, canvas_id: str) -> List[Dict[str, Any]]:
        """Get chat sessions for a canvas"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])

        response = table.query(
            IndexName='canvas_id-updated_at-index',
            KeyConditionExpression='canvas_id = :canvas_id',
            ExpressionAttributeValues={':canvas_id': canvas_id},
            ScanIndexForward=False  # Sort by updated_at DESC
        )

        return response.get('Items', [])

    def get_chat_session(self, id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])

        response = table.get_item(Key={'id': id})
        return response.get('Item')

    def update_chat_session_title(self, id: str, title: str):
        """Update chat session title"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])
        timestamp = self._get_current_timestamp()

        table.update_item(
            Key={'id': id},
            UpdateExpression="SET title = :title, updated_at = :updated_at",
            ExpressionAttributeValues={
                ':title': title,
                ':updated_at': timestamp
            }
        )

    def delete_chat_session(self, id: str):
        """Delete chat session"""
        table = self.dynamodb.Table(self.tables['chat_sessions'])
        table.delete_item(Key={'id': id})

    # Chat message operations
    def create_message(self, session_id: str, role: str, message: str):
        """Save a chat message"""
        table = self.dynamodb.Table(self.tables['chat_messages'])
        timestamp = self._get_current_timestamp()
        # Use timestamp with microseconds as sort key to maintain order
        # Format: YYYYMMDD_HHMMSS_microseconds
        from datetime import datetime
        now = datetime.utcnow()
        message_id = now.strftime('%Y%m%d_%H%M%S_%f')

        item = {
            'session_id': session_id,
            'id': message_id,
            'role': role,
            'message': message,
            'created_at': timestamp,
            'updated_at': timestamp
        }

        table.put_item(Item=item)

    def list_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages for a chat session"""
        table = self.dynamodb.Table(self.tables['chat_messages'])

        response = table.query(
            KeyConditionExpression='session_id = :session_id',
            ExpressionAttributeValues={':session_id': session_id},
            ScanIndexForward=True  # Sort by id ASC (chronological order)
        )

        items = response.get('Items', [])
        # Additional sorting by created_at as backup in case id sorting isn't perfect
        items.sort(key=lambda x: x.get('created_at', ''))

        return items

    # ComfyUI workflow operations
    def create_comfy_workflow(self, name: str, api_json: str, description: str, inputs: str, outputs: str = None):
        """Create a new comfy workflow"""
        table = self.dynamodb.Table(self.tables['comfy_workflows'])
        timestamp = self._get_current_timestamp()
        workflow_id = str(uuid.uuid4())

        item = {
            'id': workflow_id,
            'name': name,
            'api_json': api_json,
            'description': description,
            'inputs': inputs,
            'outputs': outputs or '',
            'created_at': timestamp,
            'updated_at': timestamp
        }

        table.put_item(Item=item)

    def list_comfy_workflows(self) -> List[Dict[str, Any]]:
        """List all comfy workflows"""
        table = self.dynamodb.Table(self.tables['comfy_workflows'])

        response = table.scan()
        items = response.get('Items', [])

        # Sort by updated_at DESC
        items.sort(key=lambda x: x.get('updated_at', ''), reverse=True)

        return items

    def get_comfy_workflow(self, id: int) -> Optional[Dict[str, Any]]:
        """Get comfy workflow by ID"""
        table = self.dynamodb.Table(self.tables['comfy_workflows'])

        response = table.get_item(Key={'id': str(id)})
        return response.get('Item')

    def delete_comfy_workflow(self, id: int):
        """Delete a comfy workflow"""
        table = self.dynamodb.Table(self.tables['comfy_workflows'])
        table.delete_item(Key={'id': str(id)})

    # File operations
    def create_file(self, file_id: str, file_path: str, width: int = None, height: int = None):
        """Create a new file record"""
        table = self.dynamodb.Table(self.tables['files'])
        timestamp = self._get_current_timestamp()

        item = {
            'id': file_id,
            'file_path': file_path,
            'created_at': timestamp,
            'updated_at': timestamp
        }

        if width is not None:
            item['width'] = width
        if height is not None:
            item['height'] = height

        table.put_item(Item=item)

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file record by ID"""
        table = self.dynamodb.Table(self.tables['files'])

        response = table.get_item(Key={'id': file_id})
        return response.get('Item')

    def list_files(self) -> List[Dict[str, Any]]:
        """List all files"""
        table = self.dynamodb.Table(self.tables['files'])

        response = table.scan()
        items = response.get('Items', [])

        # Sort by created_at DESC
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return items

    def delete_file(self, file_id: str):
        """Delete a file record"""
        table = self.dynamodb.Table(self.tables['files'])
        table.delete_item(Key={'id': file_id})

    # Database version operations
    def get_db_version(self) -> int:
        """Get current database version"""
        table = self.dynamodb.Table(self.tables['db_version'])

        response = table.scan()
        items = response.get('Items', [])

        if not items:
            return 0

        # Return the highest version number
        return max(int(item['version']) for item in items)

    def set_db_version(self, version: int):
        """Set database version"""
        table = self.dynamodb.Table(self.tables['db_version'])

        table.put_item(Item={'version': version})
