"""
Database utility tools and helper functions.

This module contains utility functions for database operations,
table management, and SQL query processing.
"""

import re
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError


class DatabaseTools:
    """Utility class for database operations and helper functions."""
    
    def __init__(self, engine, db_type: str):
        """
        Initialize database tools.
        
        Args:
            engine: SQLAlchemy engine instance
            db_type: Type of database (postgresql, mysql, sqlite)
        """
        self.engine = engine
        self.db_type = db_type
    
    def extract_table_name_from_create(self, sql_query: str) -> Optional[str]:
        """
        Extract table name from CREATE TABLE SQL query.
        
        Args:
            sql_query: SQL CREATE TABLE query
            
        Returns:
            Table name if found, None otherwise
        """
        try:
            pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)'
            match = re.search(pattern, sql_query, re.IGNORECASE)
            return match.group(1) if match else None
        except Exception:
            return None
    
    def extract_table_name_from_drop(self, sql_query: str) -> Optional[str]:
        """
        Extract table name from DROP TABLE SQL query.
        
        Args:
            sql_query: SQL DROP TABLE query
            
        Returns:
            Table name if found, None otherwise
        """
        try:
            pattern = r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)'
            match = re.search(pattern, sql_query, re.IGNORECASE)
            return match.group(1) if match else None
        except Exception:
            return None
    
    def extract_table_name_from_message(self, message: str) -> Optional[str]:
        """
        Extract table name from user message using simple string parsing.
        
        Args:
            message: User message
            
        Returns:
            Table name if found, None otherwise
        """
        try:
            message_lower = message.lower()
            
            # Simple keyword-based extraction - much more reliable than regex
            # Order matters! More specific patterns first
            keywords = [
                "database name",  # "database name admin" - MUST be first
                "table name",     # "table name admin" - MUST be second
                "create table",   # "create table admin"
                "make table",     # "make table admin"
                "add table",      # "add table admin"
                "new table",      # "new table admin" - least specific, last
                "name table"      # "name admin table"
            ]
            
            for keyword in keywords:
                if keyword in message_lower:
                    # Find the word after the keyword
                    keyword_pos = message_lower.find(keyword)
                    after_keyword = message[keyword_pos + len(keyword):].strip()
                    
                    # Get the first word after the keyword
                    words = after_keyword.split()
                    if words:
                        # Clean the word (remove punctuation)
                        table_name = words[0].strip(".,!?;:")
                        if table_name and len(table_name) > 0:
                            return table_name
            
            # Special case: look for "database name X" pattern
            if "database name" in message_lower:
                parts = message_lower.split("database name")
                if len(parts) > 1:
                    after_db_name = parts[1].strip()
                    words = after_db_name.split()
                    if words:
                        table_name = words[0].strip(".,!?;:")
                        if table_name and len(table_name) > 0:
                            return table_name
            
            # Special case: look for "table name X" pattern  
            if "table name" in message_lower:
                parts = message_lower.split("table name")
                if len(parts) > 1:
                    after_table_name = parts[1].strip()
                    words = after_table_name.split()
                    if words:
                        table_name = words[0].strip(".,!?;:")
                        if table_name and len(table_name) > 0:
                            return table_name
            
            return None
        except Exception:
            return None
    
    def extract_columns_from_message(self, message: str) -> List[str]:
        """
        Extract column names from user message using simple string parsing.
        
        Args:
            message: User message
            
        Returns:
            List of column names
        """
        try:
            message_lower = message.lower()
            
            # Look for column keywords
            column_keywords = [
                "add colom", "add column", "columns", "with columns", "add col", "coloms"
            ]
            
            for keyword in column_keywords:
                if keyword in message_lower:
                    # Find the text after the keyword
                    keyword_pos = message_lower.find(keyword)
                    after_keyword = message[keyword_pos + len(keyword):].strip()
                    
                    # Look for comma-separated values
                    if ',' in after_keyword:
                        # Split by comma and clean up
                        columns = []
                        for col in after_keyword.split(','):
                            col = col.strip().replace(' ', '_').lower()
                            if col and len(col) > 0:
                                columns.append(col)
                        if columns:
                            return columns
                    else:
                        # Single column or space-separated
                        words = after_keyword.split()
                        if words:
                            columns = []
                            for word in words:
                                col = word.strip(".,!?;:").replace(' ', '_').lower()
                                if col and len(col) > 0:
                                    columns.append(col)
                            if columns:
                                return columns
            
            # Special handling for "coloms" (user's typo)
            if "coloms" in message_lower:
                coloms_pos = message_lower.find("coloms")
                after_coloms = message[coloms_pos + len("coloms"):].strip()
                
                # Extract columns after "coloms" - handle multi-word columns
                words = after_coloms.split()
                if words:
                    columns = []
                    i = 0
                    while i < len(words):
                        word = words[i].strip(".,!?;:").lower()
                        if word and len(word) > 0:
                            # Check if this is part of a multi-word column
                            if word in ['created', 'updated'] and i + 1 < len(words) and words[i + 1].lower() == 'at':
                                # Handle "created at" and "updated at" as single columns
                                columns.append(f"{word}_at")
                                i += 2  # Skip the next word
                            else:
                                columns.append(word)
                                i += 1
                        else:
                            i += 1
                    if columns:
                        return columns
            
            # Default columns if none specified
            return ['id', 'name', 'email', 'phone', 'address']
        except Exception:
            return ['id', 'name', 'email', 'phone', 'address']
    
    def build_create_table_sql(self, table_name: str, columns: List[str]) -> str:
        """
        Build CREATE TABLE SQL statement with simple, reliable logic.
        
        Args:
            table_name: Name of the table
            columns: List of column names
            
        Returns:
            SQL CREATE TABLE statement
        """
        try:
            # Always start with id as primary key
            sql_parts = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
            
            # Track which columns we've already added to avoid duplicates
            added_columns = {"id"}
            
            # Add other columns with simple logic
            for col in columns:
                col_lower = col.lower().strip()
                if col_lower and col_lower not in added_columns and col_lower != 'id':
                    # Simple column type assignment
                    if 'name' in col_lower:
                        sql_parts.append(f"{col} TEXT NOT NULL")
                    elif 'email' in col_lower:
                        sql_parts.append(f"{col} TEXT UNIQUE")
                    elif 'password' in col_lower:
                        sql_parts.append(f"{col} TEXT")
                    elif 'phone' in col_lower:
                        sql_parts.append(f"{col} TEXT")
                    elif 'address' in col_lower:
                        sql_parts.append(f"{col} TEXT")
                    elif 'created_at' in col_lower or 'created' in col_lower:
                        sql_parts.append(f"{col} TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    elif 'updated_at' in col_lower or 'updated' in col_lower:
                        sql_parts.append(f"{col} TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    else:
                        # Default to TEXT for any other column
                        sql_parts.append(f"{col} TEXT")
                    
                    added_columns.add(col_lower)
            
            # Add default timestamps if not already present
            if 'created_at' not in added_columns and 'created' not in added_columns:
                sql_parts.append("created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            if 'updated_at' not in added_columns and 'updated' not in added_columns:
                sql_parts.append("updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            
            return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(sql_parts)})"
        except Exception:
            # Fallback to simple table
            return f"""CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
    
    def get_table_exists_query(self, table_name: str) -> str:
        """
        Get database-specific query to check if a table exists.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            SQL query to check table existence
        """
        if self.db_type == 'postgresql':
            return f"""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = '{table_name}'
                ) AS table_exists
            """
        elif self.db_type == 'mysql':
            return f"""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = '{table_name}'
                ) AS table_exists
            """
        else:  # SQLite
            return f"""
                SELECT EXISTS(
                    SELECT 1 FROM sqlite_master 
                    WHERE type='table' AND name='{table_name}'
                ) AS table_exists
            """
    
    def verify_table_exists(self, table_name: str) -> bool:
        """
        Verify that a table exists in the database.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                if self.db_type == 'postgresql':
                    # PostgreSQL-specific query
                    result = conn.execute(text(f"""
                        SELECT EXISTS(
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = '{table_name}'
                        ) AS table_exists
                    """))
                elif self.db_type == 'mysql':
                    # MySQL-specific query
                    result = conn.execute(text(f"""
                        SELECT EXISTS(
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = '{table_name}'
                        ) AS table_exists
                    """))
                else:
                    # SQLite-specific query (default)
                    result = conn.execute(text(f"""
                        SELECT EXISTS(
                            SELECT 1 FROM sqlite_master 
                            WHERE type='table' AND name='{table_name}'
                        ) AS table_exists
                    """))
                row = result.fetchone()
                return bool(row[0]) if row else False
        except Exception:
            return False
    
    def get_all_table_names(self) -> List[str]:
        """
        Get all table names from the database.
        
        Returns:
            List of table names
        """
        try:
            inspector = inspect(self.engine)
            return inspector.get_table_names()
        except Exception:
            return []
    
    def get_example_create_sql(self, table_name: str, columns: List[str]) -> str:
        """
        Generate example CREATE TABLE SQL for the current database type.
        
        Args:
            table_name: Name of the table
            columns: List of column names
            
        Returns:
            Example CREATE TABLE SQL statement
        """
        if self.db_type == 'postgresql':
            # PostgreSQL syntax
            sql_parts = ["id SERIAL PRIMARY KEY"]
            for col in columns:
                if col.lower() == 'name':
                    sql_parts.append(f"{col} VARCHAR(255) NOT NULL")
                elif col.lower() == 'email':
                    sql_parts.append(f"{col} VARCHAR(255) UNIQUE")
                elif 'created_at' in col.lower() or 'updated_at' in col.lower():
                    sql_parts.append(f"{col} TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                else:
                    sql_parts.append(f"{col} VARCHAR(255)")
            return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(sql_parts)})"
        
        elif self.db_type == 'mysql':
            # MySQL syntax
            sql_parts = ["id INT AUTO_INCREMENT PRIMARY KEY"]
            for col in columns:
                if col.lower() == 'name':
                    sql_parts.append(f"{col} VARCHAR(255) NOT NULL")
                elif col.lower() == 'email':
                    sql_parts.append(f"{col} VARCHAR(255) UNIQUE")
                elif 'created_at' in col.lower() or 'updated_at' in col.lower():
                    sql_parts.append(f"{col} TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                else:
                    sql_parts.append(f"{col} VARCHAR(255)")
            return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(sql_parts)})"
        
        else:  # SQLite
            # SQLite syntax
            sql_parts = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
            for col in columns:
                if col.lower() == 'name':
                    sql_parts.append(f"{col} TEXT NOT NULL")
                elif col.lower() == 'email':
                    sql_parts.append(f"{col} TEXT UNIQUE")
                elif 'created_at' in col.lower() or 'updated_at' in col.lower():
                    sql_parts.append(f"{col} TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                else:
                    sql_parts.append(f"{col} TEXT")
            return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(sql_parts)})"
