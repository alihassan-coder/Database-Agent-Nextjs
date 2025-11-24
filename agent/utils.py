from sqlalchemy import inspect, text
import json

def get_full_database_schema(engine):
    """
    Extracts and returns a complete database schema with enhanced information:
    - Table names
    - Column names, datatypes, and constraints
    - Primary keys and their relationships
    - Foreign keys and their relationships
    - Example row data (if available)
    - Index information
    - Table comments/descriptions

    Args:
        engine: SQLAlchemy engine instance

    Returns:
        dict: Complete schema information optimized for LLM consumption
    """
    print("<=== get_full_database_schema ===>")
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        schema_info = {
            "total_tables": len(tables),
            "database_type": str(engine.dialect.name),
            "tables": {}
        }

        for table_name in tables:
            columns = inspector.get_columns(table_name)
            primary_keys = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            # Get indexes for better understanding of table structure
            indexes = inspector.get_indexes(table_name)
            
            # Get table comment/description if available
            table_comment = None
            try:
                # Try to get table comment (database-specific)
                if hasattr(inspector, 'get_table_comment'):
                    table_comment = inspector.get_table_comment(table_name)
            except Exception:
                pass

            fk_info = [
                {
                    "column": fk["constrained_columns"][0],
                    "ref_table": fk["referred_table"],
                    "ref_column": fk["referred_columns"][0],
                    "on_delete": fk.get("options", {}).get("ondelete", "RESTRICT"),
                    "on_update": fk.get("options", {}).get("onupdate", "RESTRICT")
                }
                for fk in foreign_keys if fk.get("constrained_columns")
            ]

            # Enhanced column information
            column_info = []
            for col in columns:
                col_data = {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                    "primary_key": col["name"] in primary_keys,
                    "default": col.get("default"),
                    "comment": col.get("comment")
                }
                column_info.append(col_data)

            # Try to fetch sample data for better context
            example_rows = []
            row_count = 0
            try:
                with engine.connect() as conn:
                    # Get row count
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    row_count = count_result.scalar()
                    
                    # Get up to 3 sample rows for better understanding
                    if row_count > 0:
                        result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 3"))
                        example_rows = [dict(row._mapping) for row in result]
            except Exception:
                pass  # Ignore if access denied or no rows

            schema_info["tables"][table_name] = {
                "columns": column_info,
                "primary_keys": primary_keys,
                "foreign_keys": fk_info,
                "indexes": [
                    {
                        "name": idx["name"],
                        "columns": idx["column_names"],
                        "unique": idx["unique"]
                    }
                    for idx in indexes
                ],
                "row_count": row_count,
                "example_rows": example_rows,
                "comment": table_comment
            }

        # Pretty print the schema
        print(json.dumps(schema_info, indent=2))
        return schema_info

    except Exception as e:
        print(f"❌ Error fetching schema: {str(e)}")
        return {"error": str(e)}







def get_table_schema(engine, table_name: str):
    """
    Retrieve the schema of a specific database table using SQLAlchemy Inspector.

    Args:
        engine: SQLAlchemy engine instance
        table_name (str): Name of the table to inspect

    Returns:
        list[dict]: A list of dictionaries with 'column_name' and 'data_type' keys.
                    Example:
                    [
                        {"column_name": "id", "data_type": "INTEGER"},
                        {"column_name": "email", "data_type": "VARCHAR"},
                    ]

    Raises:
        Exception: If table not found or database error occurs.
    """
    print(f"<=== get_table_schema: {table_name} ===>")

    try:
        inspector = inspect(engine)

        # Get all available tables
        tables = inspector.get_table_names()
        if table_name not in tables:
            raise ValueError(f"❌ Table '{table_name}' not found in the database.")

        # Get column info for the specific table
        columns = inspector.get_columns(table_name)

        schema = []
        for col in columns:
            col_name = col.get("name")
            col_type = str(col.get("type"))
            schema.append({
                "column_name": col_name,
                "data_type": col_type
            })

        # Nicely log the schema
        print(f"==> ✅ Table '{table_name}' Schema:")
        for col in schema:
            print(f"   - {col['column_name']} ({col['data_type']})")

        return schema

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Database error while getting schema for '{table_name}': {error_msg}")
        
        # Provide more specific error messages
        if "no such table" in error_msg.lower() or "table" in error_msg.lower() and "not found" in error_msg.lower():
            return {"error": f"Table '{table_name}' does not exist in the database"}
        elif "permission" in error_msg.lower() or "access" in error_msg.lower():
            return {"error": f"Access denied to table '{table_name}'. Check your database permissions"}
        elif "connection" in error_msg.lower():
            return {"error": f"Database connection error while accessing table '{table_name}'"}
        else:
            return {"error": f"Error accessing table '{table_name}': {error_msg}"}

