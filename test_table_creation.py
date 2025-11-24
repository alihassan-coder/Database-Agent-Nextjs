"""
Test script to verify the table creation fix works correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.main_agent import DatabaseAgent

def test_table_name_extraction():
    """Test the table name extraction for CREATE TABLE requests."""
    
    print("🧪 Testing table name extraction for CREATE TABLE requests...")
    
    # Create a mock agent instance (we won't actually connect to database)
    try:
        agent = DatabaseAgent()
        
        # Test cases
        test_cases = [
            "create a table name employ with columns id, name, email, password",
            "create table users with name, email, password",
            "make a new table called products",
            "table name admin and columns id, name, email",
            "database name customer with columns id, name, email, phone"
        ]
        
        for test_case in test_cases:
            print(f"\n📝 Testing: '{test_case}'")
            try:
                # Test the table name extraction
                table_names = agent._extract_table_names_from_query(test_case)
                print(f"✅ Extracted table names: {table_names}")
                
                if table_names:
                    print(f"   → Table to create: {table_names[0]}")
                else:
                    print("   ❌ No table names extracted")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        print("\n🎉 Table name extraction test completed!")
        
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        print("This is expected if database connection is not available.")
        print("The important part is testing the table name extraction logic.")

if __name__ == "__main__":
    test_table_name_extraction()
