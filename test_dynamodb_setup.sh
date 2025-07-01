#!/bin/bash

# Quick test script for DynamoDB setup
# This script helps verify that the DynamoDB migration is working correctly

echo "🚀 Testing DynamoDB Setup for Jaaz"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "server/services/unified_db_service.py" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Check if AWS credentials are configured
echo "🔍 Checking AWS credentials..."
if aws sts get-caller-identity >/dev/null 2>&1; then
    echo "✅ AWS credentials are configured"
    aws sts get-caller-identity --query 'Account' --output text | sed 's/^/   Account: /'
else
    echo "❌ AWS credentials not found or not configured"
    echo "   Please configure AWS credentials using one of these methods:"
    echo "   1. aws configure"
    echo "   2. Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
    echo "   3. Use IAM role (if running on EC2)"
    exit 1
fi

# Check if boto3 is installed
echo ""
echo "🔍 Checking Python dependencies..."
cd server
if python -c "import boto3" 2>/dev/null; then
    echo "✅ boto3 is installed"
else
    echo "❌ boto3 is not installed"
    echo "   Installing boto3..."
    pip install boto3
    if [ $? -eq 0 ]; then
        echo "✅ boto3 installed successfully"
    else
        echo "❌ Failed to install boto3"
        exit 1
    fi
fi

# Test database system
echo ""
echo "🧪 Running database system tests..."
python tools/test_database_system.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Database system test passed!"
    echo ""
    echo "Next steps:"
    echo "1. If you have existing SQLite data, run the migration:"
    echo "   cd server && python tools/migrate_to_dynamodb.py"
    echo ""
    echo "2. Update your config file (user_data/config.toml):"
    echo "   [database]"
    echo "   type = \"dynamodb\""
    echo ""
    echo "3. Restart your Jaaz application"
    echo ""
    echo "📖 For detailed instructions, see DATABASE_MIGRATION_GUIDE.md"
else
    echo ""
    echo "❌ Database system test failed!"
    echo "   Please check the error messages above and ensure:"
    echo "   1. AWS credentials are properly configured"
    echo "   2. You have DynamoDB permissions"
    echo "   3. Your AWS region is accessible"
    echo ""
    echo "📖 For troubleshooting, see DATABASE_MIGRATION_GUIDE.md"
    exit 1
fi
