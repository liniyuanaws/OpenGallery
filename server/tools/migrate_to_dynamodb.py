#!/usr/bin/env python3
"""
Data migration tool to migrate from SQLite to DynamoDB
"""
import asyncio
import sys
import os
import argparse
from typing import List, Dict, Any

# Add the parent directory to the path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sqlite_adapter import SQLiteAdapter
from services.dynamodb_adapter import DynamoDBAdapter

class DataMigrator:
    """Tool to migrate data from SQLite to DynamoDB"""
    
    def __init__(self, sqlite_path: str = None, dynamodb_region: str = 'us-west-2'):
        self.sqlite_adapter = SQLiteAdapter(db_path=sqlite_path)
        self.dynamodb_adapter = DynamoDBAdapter(region_name=dynamodb_region)
    
    async def migrate_canvases(self):
        """Migrate canvases from SQLite to DynamoDB"""
        print("Migrating canvases...")
        canvases = await self.sqlite_adapter.list_canvases()
        
        for canvas in canvases:
            try:
                # Check if canvas already exists in DynamoDB
                existing = await self.dynamodb_adapter.get_canvas(canvas['id'])
                if existing:
                    print(f"Canvas {canvas['id']} already exists in DynamoDB, skipping...")
                    continue
                
                # Create canvas in DynamoDB
                await self.dynamodb_adapter.create_canvas(canvas['id'], canvas['name'])
                
                # Update with additional data if present
                if canvas.get('data') or canvas.get('thumbnail'):
                    await self.dynamodb_adapter.save_canvas_data(
                        canvas['id'], 
                        canvas.get('data', ''), 
                        canvas.get('thumbnail')
                    )
                
                print(f"Migrated canvas: {canvas['name']} ({canvas['id']})")
                
            except Exception as e:
                print(f"Error migrating canvas {canvas['id']}: {e}")
        
        print(f"Completed migrating {len(canvases)} canvases")
    
    async def migrate_chat_sessions(self):
        """Migrate chat sessions from SQLite to DynamoDB"""
        print("Migrating chat sessions...")
        
        # Get all canvases to find their sessions
        canvases = await self.sqlite_adapter.list_canvases()
        total_sessions = 0
        
        for canvas in canvases:
            sessions = await self.sqlite_adapter.list_chat_sessions(canvas['id'])
            
            for session in sessions:
                try:
                    # Check if session already exists
                    existing = await self.dynamodb_adapter.get_chat_session(session['id'])
                    if existing:
                        print(f"Session {session['id']} already exists, skipping...")
                        continue
                    
                    # Create session in DynamoDB
                    await self.dynamodb_adapter.create_chat_session(
                        session['id'],
                        session.get('model', ''),
                        session.get('provider', ''),
                        canvas['id'],
                        session.get('title')
                    )
                    
                    print(f"Migrated session: {session.get('title', session['id'])}")
                    total_sessions += 1
                    
                except Exception as e:
                    print(f"Error migrating session {session['id']}: {e}")
        
        print(f"Completed migrating {total_sessions} chat sessions")
    
    async def migrate_chat_messages(self):
        """Migrate chat messages from SQLite to DynamoDB"""
        print("Migrating chat messages...")
        
        # Get all canvases to find their sessions and messages
        canvases = await self.sqlite_adapter.list_canvases()
        total_messages = 0
        
        for canvas in canvases:
            sessions = await self.sqlite_adapter.list_chat_sessions(canvas['id'])
            
            for session in sessions:
                try:
                    messages = await self.sqlite_adapter.list_messages(session['id'])
                    
                    for message in messages:
                        try:
                            await self.dynamodb_adapter.create_message(
                                session['id'],
                                message['role'],
                                message['message']
                            )
                            total_messages += 1
                            
                        except Exception as e:
                            print(f"Error migrating message {message.get('id', 'unknown')}: {e}")
                    
                    if messages:
                        print(f"Migrated {len(messages)} messages for session {session['id']}")
                        
                except Exception as e:
                    print(f"Error getting messages for session {session['id']}: {e}")
        
        print(f"Completed migrating {total_messages} chat messages")
    
    async def migrate_comfy_workflows(self):
        """Migrate ComfyUI workflows from SQLite to DynamoDB"""
        print("Migrating ComfyUI workflows...")
        workflows = await self.sqlite_adapter.list_comfy_workflows()
        
        for workflow in workflows:
            try:
                # Check if workflow already exists
                existing = await self.dynamodb_adapter.get_comfy_workflow(workflow['id'])
                if existing:
                    print(f"Workflow {workflow['id']} already exists, skipping...")
                    continue
                
                await self.dynamodb_adapter.create_comfy_workflow(
                    workflow['name'],
                    workflow['api_json'],
                    workflow['description'],
                    workflow['inputs'],
                    workflow.get('outputs')
                )
                
                print(f"Migrated workflow: {workflow['name']}")
                
            except Exception as e:
                print(f"Error migrating workflow {workflow['id']}: {e}")
        
        print(f"Completed migrating {len(workflows)} ComfyUI workflows")
    
    async def migrate_files(self):
        """Migrate file records from SQLite to DynamoDB"""
        print("Migrating file records...")
        files = await self.sqlite_adapter.list_files()
        
        for file_record in files:
            try:
                # Check if file already exists
                existing = await self.dynamodb_adapter.get_file(file_record['id'])
                if existing:
                    print(f"File {file_record['id']} already exists, skipping...")
                    continue
                
                await self.dynamodb_adapter.create_file(
                    file_record['id'],
                    file_record['file_path'],
                    file_record.get('width'),
                    file_record.get('height')
                )
                
                print(f"Migrated file: {file_record['file_path']}")
                
            except Exception as e:
                print(f"Error migrating file {file_record['id']}: {e}")
        
        print(f"Completed migrating {len(files)} file records")
    
    async def migrate_all(self):
        """Migrate all data from SQLite to DynamoDB"""
        print("Starting full migration from SQLite to DynamoDB...")
        print("=" * 50)
        
        try:
            await self.migrate_canvases()
            print()
            
            await self.migrate_chat_sessions()
            print()
            
            await self.migrate_chat_messages()
            print()
            
            await self.migrate_comfy_workflows()
            print()
            
            await self.migrate_files()
            print()
            
            # Set database version
            version = await self.sqlite_adapter.get_db_version()
            await self.dynamodb_adapter.set_db_version(version)
            print(f"Set DynamoDB version to {version}")
            
            print("=" * 50)
            print("Migration completed successfully!")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            raise

async def main():
    parser = argparse.ArgumentParser(description='Migrate data from SQLite to DynamoDB')
    parser.add_argument('--sqlite-path', help='Path to SQLite database file')
    parser.add_argument('--dynamodb-region', default='us-west-2', help='DynamoDB region')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without actually migrating')
    
    args = parser.parse_args()
    
    migrator = DataMigrator(
        sqlite_path=args.sqlite_path,
        dynamodb_region=args.dynamodb_region
    )
    
    if args.dry_run:
        print("DRY RUN MODE - No data will be migrated")
        print("=" * 50)
        
        # Show what would be migrated
        canvases = await migrator.sqlite_adapter.list_canvases()
        print(f"Would migrate {len(canvases)} canvases")
        
        total_sessions = 0
        total_messages = 0
        for canvas in canvases:
            sessions = await migrator.sqlite_adapter.list_chat_sessions(canvas['id'])
            total_sessions += len(sessions)
            for session in sessions:
                messages = await migrator.sqlite_adapter.list_messages(session['id'])
                total_messages += len(messages)
        
        print(f"Would migrate {total_sessions} chat sessions")
        print(f"Would migrate {total_messages} chat messages")
        
        workflows = await migrator.sqlite_adapter.list_comfy_workflows()
        print(f"Would migrate {len(workflows)} ComfyUI workflows")
        
        files = await migrator.sqlite_adapter.list_files()
        print(f"Would migrate {len(files)} file records")
        
    else:
        await migrator.migrate_all()

if __name__ == "__main__":
    asyncio.run(main())
