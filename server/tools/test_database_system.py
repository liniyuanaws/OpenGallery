#!/usr/bin/env python3
"""
Test script to verify the database system is working correctly
"""
import asyncio
import sys
import os
import uuid
from datetime import datetime

# Add the parent directory to the path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.unified_db_service import unified_db_service

async def test_canvas_operations():
    """Test canvas CRUD operations"""
    print("Testing canvas operations...")
    
    # Create a test canvas
    canvas_id = str(uuid.uuid4())
    canvas_name = f"Test Canvas {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        # Create canvas
        await unified_db_service.create_canvas(canvas_id, canvas_name)
        print(f"✓ Created canvas: {canvas_name}")
        
        # List canvases
        canvases = await unified_db_service.list_canvases()
        print(f"✓ Listed {len(canvases)} canvases")
        
        # Get specific canvas
        canvas = await unified_db_service.get_canvas(canvas_id)
        if canvas:
            print(f"✓ Retrieved canvas: {canvas['name']}")
        else:
            print("✗ Failed to retrieve canvas")
            return False
        
        # Update canvas data
        test_data = '{"test": "data"}'
        await unified_db_service.save_canvas_data(canvas_id, test_data, "thumbnail_url")
        print("✓ Updated canvas data")
        
        # Rename canvas
        new_name = f"Renamed {canvas_name}"
        await unified_db_service.rename_canvas(canvas_id, new_name)
        print("✓ Renamed canvas")
        
        # Verify rename
        updated_canvas = await unified_db_service.get_canvas(canvas_id)
        if updated_canvas and updated_canvas['name'] == new_name:
            print("✓ Verified canvas rename")
        else:
            print("✗ Canvas rename verification failed")
        
        # Clean up - delete canvas
        await unified_db_service.delete_canvas(canvas_id)
        print("✓ Deleted test canvas")
        
        return True
        
    except Exception as e:
        print(f"✗ Canvas operations failed: {e}")
        return False

async def test_chat_operations():
    """Test chat session and message operations"""
    print("\nTesting chat operations...")
    
    # First create a canvas for the chat session
    canvas_id = str(uuid.uuid4())
    canvas_name = "Test Chat Canvas"
    
    try:
        await unified_db_service.create_canvas(canvas_id, canvas_name)
        
        # Create a chat session
        session_id = str(uuid.uuid4())
        await unified_db_service.create_chat_session(
            session_id, "gpt-4", "openai", canvas_id, "Test Chat Session"
        )
        print("✓ Created chat session")
        
        # List chat sessions
        sessions = await unified_db_service.list_chat_sessions(canvas_id)
        print(f"✓ Listed {len(sessions)} chat sessions")
        
        # Get specific session
        session = await unified_db_service.get_chat_session(session_id)
        if session:
            print(f"✓ Retrieved session: {session.get('title', 'No title')}")
        else:
            print("✗ Failed to retrieve session")
            return False
        
        # Create messages
        await unified_db_service.create_message(session_id, "user", "Hello, world!")
        await unified_db_service.create_message(session_id, "assistant", "Hello! How can I help you?")
        print("✓ Created chat messages")
        
        # List messages
        messages = await unified_db_service.list_messages(session_id)
        print(f"✓ Listed {len(messages)} messages")
        
        # Update session title
        new_title = "Updated Test Session"
        await unified_db_service.update_chat_session_title(session_id, new_title)
        print("✓ Updated session title")
        
        # Clean up
        await unified_db_service.delete_chat_session(session_id)
        await unified_db_service.delete_canvas(canvas_id)
        print("✓ Cleaned up test data")
        
        return True
        
    except Exception as e:
        print(f"✗ Chat operations failed: {e}")
        # Clean up on error
        try:
            await unified_db_service.delete_canvas(canvas_id)
        except:
            pass
        return False

async def test_file_operations():
    """Test file operations"""
    print("\nTesting file operations...")
    
    try:
        # Create a file record
        file_id = str(uuid.uuid4())
        file_path = f"/test/path/file_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        
        await unified_db_service.create_file(file_id, file_path, 1920, 1080)
        print("✓ Created file record")
        
        # Get file
        file_record = await unified_db_service.get_file(file_id)
        if file_record:
            print(f"✓ Retrieved file: {file_record['file_path']}")
        else:
            print("✗ Failed to retrieve file")
            return False
        
        # List files
        files = await unified_db_service.list_files()
        print(f"✓ Listed {len(files)} files")
        
        # Delete file
        await unified_db_service.delete_file(file_id)
        print("✓ Deleted file record")
        
        return True
        
    except Exception as e:
        print(f"✗ File operations failed: {e}")
        return False

async def test_workflow_operations():
    """Test ComfyUI workflow operations"""
    print("\nTesting workflow operations...")
    
    try:
        # Create a workflow
        workflow_name = f"Test Workflow {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        api_json = '{"test": "workflow"}'
        description = "Test workflow description"
        inputs = '{"input1": "text"}'
        outputs = '{"output1": "image"}'
        
        await unified_db_service.create_comfy_workflow(
            workflow_name, api_json, description, inputs, outputs
        )
        print("✓ Created ComfyUI workflow")
        
        # List workflows
        workflows = await unified_db_service.list_comfy_workflows()
        print(f"✓ Listed {len(workflows)} workflows")
        
        if workflows:
            # Get specific workflow (use the first one we find)
            workflow_id = workflows[0]['id']
            workflow = await unified_db_service.get_comfy_workflow(int(workflow_id))
            if workflow:
                print(f"✓ Retrieved workflow: {workflow['name']}")
            else:
                print("✗ Failed to retrieve workflow")
                return False
            
            # Delete workflow
            await unified_db_service.delete_comfy_workflow(int(workflow_id))
            print("✓ Deleted workflow")
        
        return True
        
    except Exception as e:
        print(f"✗ Workflow operations failed: {e}")
        return False

async def test_database_version():
    """Test database version operations"""
    print("\nTesting database version operations...")
    
    try:
        # Get current version
        version = await unified_db_service.get_db_version()
        print(f"✓ Current database version: {version}")
        
        # Set version (just set it to the same value)
        await unified_db_service.set_db_version(version)
        print("✓ Set database version")
        
        return True
        
    except Exception as e:
        print(f"✗ Database version operations failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("Database System Test Suite")
    print("=" * 40)
    
    tests = [
        test_canvas_operations,
        test_chat_operations,
        test_file_operations,
        test_workflow_operations,
        test_database_version
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if await test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 40)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Database system is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
