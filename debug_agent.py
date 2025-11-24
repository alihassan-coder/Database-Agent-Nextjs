#!/usr/bin/env python3
"""
Debug script to test the agent's database info method
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_agent_database_info():
    """Test the agent's get_database_info method"""
    print("🔍 Testing Agent Database Info Method...")
    
    try:
        from agent.main_agent import DatabaseAgent
        
        # Initialize agent
        print("📡 Initializing Database Agent...")
        agent = DatabaseAgent()
        print("✅ Agent initialized successfully")
        
        # Test get_database_info method
        print("📊 Getting database info from agent...")
        db_info = agent.get_database_info()
        
        print(f"📋 Database Info Result:")
        print(f"  Total tables: {db_info.get('total_tables', 0)}")
        print(f"  Table names: {list(db_info.get('tables', {}).keys())}")
        print(f"  Database URL: {db_info.get('database_url', 'Unknown')}")
        
        if 'error' in db_info:
            print(f"❌ Error in database info: {db_info['error']}")
            return False
        
        # Check if tables are detected
        if db_info.get('total_tables', 0) == 0:
            print("⚠️  Agent reports 0 tables - this is the issue!")
            return False
        else:
            print(f"✅ Agent correctly detected {db_info.get('total_tables', 0)} tables")
            
            # Show table details
            tables = db_info.get('tables', {})
            for table_name, table_info in tables.items():
                columns = table_info.get('columns', [])
                column_names = [col.get('name', 'unknown') for col in columns]
                print(f"  📋 {table_name}: {column_names}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error testing agent: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_agent_database_info()
    if success:
        print("\n✅ Agent database info test passed!")
    else:
        print("\n❌ Agent database info test failed!")
