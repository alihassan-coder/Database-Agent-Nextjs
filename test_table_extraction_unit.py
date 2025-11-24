#!/usr/bin/env python3
"""
Unit test for table name extraction without requiring database connection.
"""

import re

def test_table_name_extraction_patterns():
    """Test the regex patterns used in table name extraction."""
    
    print("🧪 Testing table name extraction patterns...")
    
    # Test cases and expected results
    test_cases = [
        ("create a table name employ with columns id, name, email, password", "employ"),
        ("create table users with name, email, password", "users"),
        ("make a new table called products", "products"),
        ("table name admin and columns id, name, email", "admin"),
        ("database name customer with columns id, name, email, phone", "customer"),
        ("add table employees with columns", "employees"),
        ("new table called orders", "orders")
    ]
    
    # Patterns from the fallback extraction
    patterns = [
        r'table\s+name\s+(\w+)',
        r'database\s+name\s+(\w+)',
        r'create\s+table\s+(\w+)',
        r'new\s+table\s+called?\s+(\w+)',
        r'make\s+table\s+(\w+)',
        r'add\s+table\s+(\w+)'
    ]
    
    success_count = 0
    total_count = len(test_cases)
    
    for test_input, expected in test_cases:
        print(f"\n📝 Testing: '{test_input}'")
        print(f"   Expected: '{expected}'")
        
        found = False
        for pattern in patterns:
            match = re.search(pattern, test_input.lower())
            if match:
                extracted = match.group(1)
                print(f"   ✅ Extracted: '{extracted}' (pattern: {pattern})")
                if extracted == expected:
                    success_count += 1
                    print(f"   ✅ MATCH!")
                else:
                    print(f"   ❌ MISMATCH! Expected '{expected}', got '{extracted}'")
                found = True
                break
        
        if not found:
            print(f"   ❌ No pattern matched")
    
    print(f"\n📊 Results: {success_count}/{total_count} tests passed")
    
    if success_count == total_count:
        print("🎉 All tests passed!")
    else:
        print("⚠️ Some tests failed. Check the patterns.")

def test_sql_extraction_patterns():
    """Test the SQL extraction patterns."""
    
    print("\n🧪 Testing SQL extraction patterns...")
    
    # Test cases for CREATE TABLE SQL extraction
    test_cases = [
        ("CREATE TABLE employ (id SERIAL PRIMARY KEY, name VARCHAR(255), email VARCHAR(255), password VARCHAR(255));", "CREATE TABLE employ (id SERIAL PRIMARY KEY, name VARCHAR(255), email VARCHAR(255), password VARCHAR(255));"),
        ("```sql\nCREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);\n```", "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);"),
        ("Here's the SQL:\nCREATE TABLE products (\n  id SERIAL PRIMARY KEY,\n  name VARCHAR(255)\n);", "CREATE TABLE products (\n  id SERIAL PRIMARY KEY,\n  name VARCHAR(255)\n);"),
    ]
    
    # CREATE TABLE pattern from the code
    create_pattern = r'(CREATE\s+TABLE\s+.*?)(?=\n\n|\n$|$|;)'
    
    success_count = 0
    total_count = len(test_cases)
    
    for test_input, expected in test_cases:
        print(f"\n📝 Testing SQL extraction:")
        print(f"   Input: {test_input[:50]}...")
        print(f"   Expected: {expected[:50]}...")
        
        matches = re.findall(create_pattern, test_input, re.DOTALL | re.IGNORECASE)
        if matches:
            extracted = matches[0].strip()
            if not extracted.endswith(';'):
                extracted += ';'
            print(f"   ✅ Extracted: {extracted[:50]}...")
            if extracted.strip() == expected.strip():
                success_count += 1
                print(f"   ✅ MATCH!")
            else:
                print(f"   ❌ MISMATCH!")
        else:
            print(f"   ❌ No CREATE TABLE pattern matched")
    
    print(f"\n📊 SQL Extraction Results: {success_count}/{total_count} tests passed")

if __name__ == "__main__":
    test_table_name_extraction_patterns()
    test_sql_extraction_patterns()
