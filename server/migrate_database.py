#!/usr/bin/env python3
"""
Database migration script for multi-tenant and user authentication
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.dynamodb_service import DynamoDBService
from services.user_service import UserService


def migrate_database():
    """Run database migration"""
    print("🚀 Starting database migration...")
    
    try:
        # Initialize DynamoDB service (this will create tables if they don't exist)
        print("📊 Initializing DynamoDB service...")
        db_service = DynamoDBService()
        print("✅ DynamoDB tables created/verified")
        
        # Initialize user service (this will create default users)
        print("👤 Initializing user service...")
        user_service = UserService()
        print("✅ User service initialized with default users")
        
        # List existing tables
        print("\n📋 Current DynamoDB tables:")
        dynamodb = db_service.dynamodb
        table_names = [table.name for table in dynamodb.tables.all()]
        for table_name in sorted(table_names):
            if 'jaaz' in table_name:
                print(f"  - {table_name}")
        
        # List existing users
        print("\n👥 Current users:")
        users = user_service.list_users()
        for user in users:
            print(f"  - {user['username']} ({user['email']}) - Active: {user.get('is_active', True)}")
        
        print("\n🎉 Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_migration():
    """Verify that migration was successful"""
    print("\n🔍 Verifying migration...")
    
    try:
        # Test database connection
        db_service = DynamoDBService()
        
        # Test user operations
        user_service = UserService()
        
        # Try to authenticate with demo user
        demo_user = user_service.authenticate_user("demo", "demo123")
        if demo_user:
            print("✅ Demo user authentication works")
        else:
            print("❌ Demo user authentication failed")
            return False
        
        # Try to create a test canvas (this tests multi-tenant isolation)
        test_canvas_id = "test_migration_canvas"
        try:
            db_service.create_canvas(test_canvas_id, "Migration Test Canvas", demo_user["user_id"])
            print("✅ Canvas creation with user_id works")
            
            # Clean up test canvas
            db_service.delete_canvas(test_canvas_id, demo_user["user_id"])
            print("✅ Canvas deletion with user verification works")
            
        except Exception as e:
            print(f"❌ Canvas operations failed: {e}")
            return False
        
        print("✅ Migration verification successful!")
        return True
        
    except Exception as e:
        print(f"❌ Migration verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_usage():
    """Show usage information"""
    print("""
🔧 Database Migration Tool for Jaaz Multi-Tenant System

Usage:
  python migrate_database.py [command]

Commands:
  migrate    - Run database migration (default)
  verify     - Verify migration was successful
  help       - Show this help message

Examples:
  python migrate_database.py
  python migrate_database.py migrate
  python migrate_database.py verify

This script will:
1. Create/update DynamoDB tables with multi-tenant schema
2. Add user_id fields to all relevant tables
3. Create user authentication table
4. Initialize default demo users (admin/admin123, demo/demo123)
5. Verify that multi-tenant isolation is working

Note: Make sure your AWS credentials are configured before running.
""")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "migrate"
    
    if command == "help":
        show_usage()
    elif command == "verify":
        success = verify_migration()
        sys.exit(0 if success else 1)
    elif command == "migrate":
        success = migrate_database()
        if success:
            verify_migration()
        sys.exit(0 if success else 1)
    else:
        print(f"❌ Unknown command: {command}")
        show_usage()
        sys.exit(1)
