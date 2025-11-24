#!/usr/bin/env python3
"""
Debug script to test database connection and table detection
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

# Load environment variables
load_dotenv()

def test_database_connection():
    """Test database connection and table detection"""
    print("🔍 Testing Database Connection...")
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    print(f"📊 Database URL: {database_url.split('@')[-1] if '@' in database_url else 'Local database'}")
    
    try:
        # Create engine
        engine = create_engine(database_url, echo=False)
        print("✅ Engine created successfully")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
        
        # Get table information
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"📋 Found {len(tables)} tables:")
        for i, table in enumerate(tables, 1):
            print(f"  {i}. {table}")
            
            # Get column info for each table
            try:
                columns = inspector.get_columns(table)
                print(f"     Columns: {[col['name'] for col in columns]}")
            except Exception as e:
                print(f"     Error getting columns: {e}")
        
        if len(tables) == 0:
            print("⚠️  No tables found! This might be the issue.")
            print("💡 Try running: SHOW TABLES; or SELECT * FROM information_schema.tables;")
            
            # Try alternative methods to detect tables
            print("\n🔍 Trying alternative table detection methods...")
            
            with engine.connect() as conn:
                # Method 1: Direct SQL query
                try:
                    result = conn.execute(text("SHOW TABLES"))
                    tables_alt = [row[0] for row in result.fetchall()]
                    print(f"SHOW TABLES found: {tables_alt}")
                except Exception as e:
                    print(f"SHOW TABLES failed: {e}")
                
                # Method 2: Information schema
                try:
                    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
                    tables_alt = [row[0] for row in result.fetchall()]
                    print(f"Information schema found: {tables_alt}")
                except Exception as e:
                    print(f"Information schema failed: {e}")
                
                # Method 3: SQLite specific
                try:
                    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                    tables_alt = [row[0] for row in result.fetchall()]
                    print(f"SQLite master found: {tables_alt}")
                except Exception as e:
                    print(f"SQLite master failed: {e}")
        
        return len(tables)
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return 0

if __name__ == "__main__":
    table_count = test_database_connection()
    print(f"\n📊 Total tables detected: {table_count}")
