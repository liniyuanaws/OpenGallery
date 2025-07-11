#!/usr/bin/env python3
"""
Test script to verify startup dependencies and configuration
"""
import sys
import os
import subprocess

def test_python_dependencies():
    """Test if all Python dependencies are available"""
    print("🐍 Testing Python dependencies...")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'boto3',
        'PyJWT',
        'anthropic',
        'strands-agents'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r server/requirements.txt")
        return False
    else:
        print("✅ All Python dependencies are available")
        return True

def test_aws_credentials():
    """Test AWS credentials for DynamoDB"""
    print("\n🔑 Testing AWS credentials...")
    
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, ClientError
        
        # Try to create a DynamoDB client
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        
        # Try to list tables (this will fail if no credentials)
        try:
            list(dynamodb.tables.all())
            print("✅ AWS credentials are configured")
            return True
        except NoCredentialsError:
            print("❌ AWS credentials not found")
            print("Configure with: aws configure")
            return False
        except ClientError as e:
            if 'UnrecognizedClientException' in str(e):
                print("❌ Invalid AWS credentials")
                return False
            else:
                print("✅ AWS credentials are configured (access may be limited)")
                return True
                
    except ImportError:
        print("❌ boto3 not installed")
        return False

def test_database_connection():
    """Test database connection and table creation"""
    print("\n🗄️ Testing database connection...")
    
    try:
        # Add server directory to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))
        
        from services.dynamodb_service import DynamoDBService
        
        # Try to initialize database service
        db_service = DynamoDBService()
        print("✅ Database service initialized")
        
        # Check if tables exist
        tables = db_service.tables
        print(f"✅ Configured tables: {list(tables.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_user_service():
    """Test user service initialization"""
    print("\n👤 Testing user service...")
    
    try:
        # Add server directory to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))
        
        from services.user_service import UserService
        
        # Try to initialize user service
        user_service = UserService()
        print("✅ User service initialized")
        
        # Test password hashing
        test_hash = user_service.hash_password("test123")
        if user_service.verify_password("test123", test_hash):
            print("✅ Password hashing works")
        else:
            print("❌ Password hashing failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ User service failed: {e}")
        return False

def test_frontend_dependencies():
    """Test if frontend dependencies are available"""
    print("\n📦 Testing frontend dependencies...")
    
    react_dir = os.path.join(os.path.dirname(__file__), 'react')
    
    if not os.path.exists(os.path.join(react_dir, 'package.json')):
        print("❌ Frontend package.json not found")
        return False
    
    if not os.path.exists(os.path.join(react_dir, 'node_modules')):
        print("⚠️ Frontend node_modules not found")
        print("Run: cd react && npm install")
        return False
    
    print("✅ Frontend dependencies appear to be installed")
    return True

def main():
    """Run all startup tests"""
    print("🚀 Jaaz Startup Test Suite")
    print("=" * 50)
    
    tests = [
        ("Python Dependencies", test_python_dependencies),
        ("AWS Credentials", test_aws_credentials),
        ("Database Connection", test_database_connection),
        ("User Service", test_user_service),
        ("Frontend Dependencies", test_frontend_dependencies),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        if result:
            print(f"  ✅ {test_name}")
            passed += 1
        else:
            print(f"  ❌ {test_name}")
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All tests passed! You can start the application with:")
        print("  ./start-simple.sh")
        return True
    else:
        print(f"\n⚠️ {failed} test(s) failed. Please fix the issues above before starting.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
