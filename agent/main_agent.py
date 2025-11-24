"""
LLM-Driven Database Agent with Intelligent Decision Making

This module provides an intelligent database assistant that uses LLM to make decisions
about what actions to take based on user queries. It removes hardcoded logic and lets
the AI dynamically determine the best course of action for each interaction.
"""

"""
About the Project:
- this is ai agent that is crete to perform the sql queries and database operations on the database that you connected with the agent.
- this execute the sql queries and database operations on the database that you connected with the agent.
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError
import json
from datetime import datetime
import uuid

try:
    from .config import DatabaseConfig, AgentConfig
    from .utils import get_full_database_schema, get_table_schema

    from .system_prompts import (
        SYSTEM_PROMPT, HELP_TEXT, get_router_prompt, get_operation_prompt,
        get_sql_generation_prompt, get_response_prompt, get_database_rules
        )
    from .tools import DatabaseTools
    from .simple_approval import simple_approval_manager

except Exception as e:
    print(f"Error importing modules is main_agent file: {e}")
   



class ConversationState(TypedDict):
    messages: Annotated[List[Any], add_messages]
    next_action: Optional[str]
    context: Optional[Dict[str, Any]]
    pending_query: Optional[str]
    human_approval: Optional[bool]
    approval_pending: Optional[bool]
    approval_id: Optional[str]


class DatabaseAgent:
    """
    LLM-Driven Database Agent with intelligent decision making.
    
    This agent uses LLM to dynamically decide what actions to take based on user queries,
    removing hardcoded logic and making the system more flexible and intelligent.
    """
    
    def __init__(self):
        """
        Initialize the LLM-Driven Database Agent.
        
        Sets up AI model, database connection, conversation history,
        and LLM-driven workflow for intelligent decision making.
        """
        # Initialize configuration
        self.config = DatabaseConfig()
        self.agent_config = AgentConfig()
        
        # Initialize LLM with configuration
        llm_config = self.config.get_llm_config()
        self.llm = ChatOpenAI(
            model=llm_config["model"],
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"]
        )
        
        # Initialize database connection
        self.engine = self.config.create_database_engine()
        self.SessionLocal = self.config.create_session_factory(self.engine)
        self.db_type = self.config.detect_database_type(self.engine)
        print(f"Database type detected: {self.db_type}")
        
        # Initialize database tools
        self.db_tools = DatabaseTools(self.engine, self.db_type)
        
        # Initialize memory saver for LangGraph conversation history
        self.memory = MemorySaver()
        
        # System prompt for the AI
        self.system_prompt = SYSTEM_PROMPT

        # Initialize LangGraph workflow
        self._setup_workflow()
    
    def _setup_workflow(self) -> None:
        """
        Set up LangGraph workflow for conversation management with human-in-the-loop.
        
        Creates a state graph that uses LLM to decide next actions and includes
        human approval for dangerous database operations.
        """
        workflow = StateGraph(ConversationState)
        
        # Add nodes
        workflow.add_node("router", self._llm_router)
        workflow.add_node("database_operation", self._database_operation)
        workflow.add_node("human_approval", self._human_approval)
        workflow.add_node("response", self._generate_response)
        
        # Set entry point
        workflow.set_entry_point("router")
        
        # Add conditional edges based on LLM decision
        workflow.add_conditional_edges(
            "router",
            self._should_continue,
            {
                "database_operation": "database_operation",
                "response": "response",
                "end": END
            }
        )
        
        # Add conditional edges from database_operation
        workflow.add_conditional_edges(
            "database_operation",
            self._needs_human_approval,
            {
                "human_approval": "human_approval",
                "response": "response"
            }
        )
        
        # Add conditional edges from human_approval
        workflow.add_conditional_edges(
            "human_approval",
            self._handle_human_decision,
            {
                "database_operation": "database_operation",
                "response": "response",
                "human_approval": "human_approval"
            }
        )
        
        workflow.add_edge("response", END)
        
        # Compile with memory checkpointer
        self.workflow = workflow.compile(checkpointer=self.memory)
    
    def _llm_router(self, state: ConversationState) -> ConversationState:
        """
        Use LLM to decide what action to take next.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with next action decision
        """
        print("<=== _llm_router ===>")
        messages = state["messages"]
        last_message = messages[-1].content if messages else ""
        
        # LangGraph automatically manages conversation history through the state
        
        router_prompt = get_router_prompt(last_message)
        
        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a routing assistant. Respond with only the action name."),
                HumanMessage(content=router_prompt)
            ])
            
            action = response.content.strip().lower()
            if action in ["database_operation", "response", "end"]:
                state["next_action"] = action
            else:
                state["next_action"] = "response"  # Default to response
                
        except Exception as e:
            print(f"❌ LLM Router Error: {str(e)}")
            if "401" in str(e) or "User not found" in str(e):
                print("🔑 API Authentication Error: Please check your OpenRouter API key")
                print("   - Make sure OPENROUTER_API_KEY06 is set correctly in .env file")
                print("   - Verify the API key is valid and has sufficient credits")
            state["next_action"] = "response"  # Default to response on error
        
        return state
    
    def _should_continue(self, state: ConversationState) -> str:
        """Return the next action based on LLM decision."""
        return state.get("next_action", "response")
    
    def _needs_human_approval(self, state: ConversationState) -> str:
        """
        Determine if the database operation needs human approval.
        """
        context = state.get("context", {})
        sql_query = context.get("sql_query") or context.get("sql_executed")

        print(f"<=== _needs_human_approval ===> sql_query: {sql_query}, requires_approval: {context.get('requires_approval')}")

        # Check if this operation requires human approval
        if context.get("requires_approval") and sql_query:
            print(f"⚠️ Human approval needed for: {sql_query}")
            return "human_approval"

        print("✅ No human approval needed")
        return "response"

    
    def _human_approval(self, state: ConversationState) -> ConversationState:
        """
        Handle human approval for dangerous database operations.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with human approval decision
        """
        print("<=== _human_approval ===>")
        context = state.get("context", {})
        pending_query = context.get("sql_executed", "")
        
        print(f"Pending query: {pending_query}")
        print(f"State keys: {list(state.keys())}")
        print(f"Context: {context}")
        
        if not pending_query:
            print("❌ No pending query found")
            state["human_approval"] = False
            return state
        
        # Check if this is a dangerous operation that needs approval
        if not simple_approval_manager.is_dangerous_operation(pending_query):
            state["human_approval"] = True
            return state
        
        # Create approval request using the simple manager
        print(f"🔧 Creating approval request for: {pending_query}")
        approval_result = simple_approval_manager.create_approval_request(
            sql_query=pending_query
        )
        
        approval_id = approval_result["approval_id"]
        state["approval_id"] = approval_id
        print(f"🔧 Created approval with ID: {approval_id}")
        
        # Get operation info from the approval result
        approval_request = approval_result["approval_request"]
        operation_type = approval_request["operation_type"]
        table_name = approval_request["table_name"]
        
        # Create a response that will trigger the frontend approval dialog
        approval_message = f"""
⚠️ **DANGEROUS OPERATION DETECTED** ⚠️

I need your approval to execute this potentially dangerous database operation:

**Operation Type:** {operation_type}
**Table:** {table_name or 'Unknown'}
**SQL Query:**
```sql
{pending_query}
```

This operation could modify or delete data in your database. Please review the query above and confirm your decision.

**Approval ID:** {approval_id}
"""
        
        # Set the context to show the approval message
        state["context"] = {
            "operation_result": approval_message,
            "sql_executed": pending_query,
            "requires_approval": True,
            "approval_id": approval_id
        }
        
        print(f"🔧 Set context with approval message: {approval_message[:100]}...")
        
        # Set human approval as pending
        state["human_approval"] = None  # Pending approval
        state["approval_pending"] = True
        
        return state
    
    def _handle_human_decision(self, state: ConversationState) -> str:
        """
        Handle the human approval decision.

        Args:
            state: Current conversation state

        Returns:
            Next action based on human decision
        """
        approval_id = state.get("approval_id")

        if not approval_id:
            # No approval ID, treat as denied (safe default)
            state["human_approval"] = False
            return "response"

        # Query external approval manager for status
        approval_status = simple_approval_manager.get_approval_status(approval_id)

        status = approval_status.get("status", "").lower()
        if status == "approved":
            # Mark approved so _database_operation will execute pending_query
            state["human_approval"] = True
            return "database_operation"
        elif status in ("denied", "expired"):
            state["human_approval"] = False
            return "response"
        else:
            # still pending -> go to response to show approval message
            print("⏳ Approval still pending, showing approval message")
            return "response"

        
    def _database_operation(self, state: ConversationState) -> ConversationState:
        """
        Simplified database operation handler.
        Uses LLM to understand user intent and execute SQL safely in real-time.

        Focus: 
            - Uses ONLY specific table schema (not full DB schema)
            - Generates accurate SQL
            - Executes safely with optional human approval
        """
        print("<=== _database_operation ===>")

        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""
        engine = self.engine

        try:
            # --- STEP 1: Handle human approval flow --------------------------
            if state.get("human_approval") is True and state.get("context", {}).get("sql_executed"):
                sql_query = state["context"]["sql_executed"]
                result = self.execute_sql_query(sql_query)
                operation_result = (
                    f"✅ Executed approved query successfully:\n```sql\n{sql_query}\n```\n"
                    if result.get("success")
                    else f"❌ Error executing approved query:\n{result.get('error', 'Unknown error')}"
                )
                state["context"] = {"operation_result": operation_result, "sql_executed": sql_query}
                state["human_approval"] = None
                return state

            if state.get("human_approval") is False:
                state["context"] = {"operation_result": "❌ Operation cancelled by user."}
                state["human_approval"] = None
                return state

            # --- STEP 2: Check if this is a CREATE TABLE request -------------
            user_lower = last_message.lower()
            is_create_request = any(keyword in user_lower for keyword in [
                'create table', 'make table', 'add table', 'new table', 
                'create a table', 'table name', 'database name'
            ])
            
            if is_create_request:
                # --- CREATE TABLE FLOW ----------------------------------------
                print("🔨 Processing CREATE TABLE request...")
                
                # Extract table name and columns from the request
                mentioned_tables = self._extract_table_names_from_query(last_message)
                print(f"🔍 Table to create: {mentioned_tables}")
                
                if not mentioned_tables:
                    state["context"] = {
                        "operation_result": "❌ Could not detect table name in your CREATE TABLE request. Please specify the table name clearly."
                    }
                    return state
                
                table_name = mentioned_tables[0]
                
                # Generate CREATE TABLE SQL using LLM
                create_prompt = f"""
You are an expert SQL assistant for {self.db_type.upper()} database.

User Request: "{last_message}"

Database Type: {self.db_type.upper()}

Instructions:
1. Extract the table name and column names from the user's request
2. Generate a proper CREATE TABLE SQL statement
3. Use appropriate data types for {self.db_type.upper()}
4. Include common constraints (PRIMARY KEY, NOT NULL, etc.)
5. Return ONLY the SQL statement

Common data types for {self.db_type.upper()}:
- INTEGER or SERIAL (for auto-incrementing IDs)
- VARCHAR(255) or TEXT (for text fields)
- TIMESTAMP (for dates)
- BOOLEAN (for true/false values)

Examples:
- "create table users with id, name, email, password" → CREATE TABLE users (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, email VARCHAR(255) UNIQUE, password VARCHAR(255) NOT NULL);
- "table name employ with columns id, name, email, password" → CREATE TABLE employ (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, email VARCHAR(255), password VARCHAR(255) NOT NULL);

Generate the CREATE TABLE SQL for: {table_name}
"""
                
                llm_messages = [
                    SystemMessage(content="You are a SQL generation assistant. Return only the SQL statement."),
                    HumanMessage(content=create_prompt)
                ]
                
                print("🤖 Generating CREATE TABLE SQL...")
                llm_response = self.llm.invoke(llm_messages)
                raw_output = getattr(llm_response, "content", str(llm_response))
                print(f"🤖 Raw LLM output: {raw_output[:300]}")
                
                sql_query = self._extract_sql_from_text(raw_output)
                
                if not sql_query:
                    raise ValueError("No valid CREATE TABLE SQL found in LLM output.")
                
                print(f"✅ Generated CREATE TABLE SQL: {sql_query}")
                
            else:
                # --- EXISTING TABLE OPERATIONS FLOW ---------------------------
                print("🔍 Processing existing table operation...")
                
                # Extract mentioned tables
                mentioned_tables = self._extract_table_names_from_query(last_message)
                print(f"🔍 Mentioned tables: {mentioned_tables}")

                if not mentioned_tables:
                    state["context"] = {
                        "operation_result": "❌ Could not detect any table name in your request."
                    }
                    return state

                # Get schema for mentioned tables
                print("📋 Fetching table schemas...")
                schemas = {}
                for table in mentioned_tables:
                    try:
                        schema = get_table_schema(engine, table)
                        schemas[table] = schema
                        print(f"✅ Got schema for table '{table}': {len(schema)} columns")
                    except Exception as e:
                        schemas[table] = {"error": str(e)}
                        print(f"⚠️ Failed to get schema for table '{table}': {e}")

                # Prepare schema prompt for LLM
                schema_text = []
                for table, schema in schemas.items():
                    if "error" in schema:
                        schema_text.append(f"❌ Table '{table}' not found or inaccessible.")
                        continue

                    schema_text.append(f"📋 TABLE: {table}")
                    for col in schema:
                        schema_text.append(f"  • {col['column_name']} ({col['data_type']})")
                    schema_text.append("")

                formatted_schema = "\n".join(schema_text)

                schema_prompt = (
                    "You are an expert SQL assistant.\n"
                    "Follow these CRITICAL RULES:\n"
                    "1. Use ONLY the tables and columns listed below.\n"
                    "2. Do NOT invent new columns or tables.\n"
                    "3. For INSERT/UPDATE, include all NOT NULL columns.\n"
                    "4. For ALTER, use correct column names and types.\n"
                    "5. Always output VALID SQL syntax for the database type.\n\n"
                    f"{formatted_schema}\n\n"
                    "Now, based on this schema, generate a single SQL statement for the user's request."
                )

                user_context = f"User request: {last_message}"

                # Ask LLM to generate SQL
                llm_messages = [
                    SystemMessage(content=schema_prompt),
                    HumanMessage(content=user_context)
                ]

                print("🤖 Sending to LLM for SQL generation...")
                llm_response = self.llm.invoke(llm_messages)
                raw_output = getattr(llm_response, "content", str(llm_response))
                print(f"🤖 Raw LLM output: {raw_output[:300]}")

                sql_query = self._extract_sql_from_text(raw_output)

                if not sql_query:
                    raise ValueError("No valid SQL found in LLM output.")

                print(f"✅ Extracted SQL: {sql_query}")

            # --- STEP 3: Safety check (approval) ------------------------------
            if simple_approval_manager.is_dangerous_operation(sql_query):
                print(f"⚠️ Dangerous operation detected: {sql_query}")
                state["context"] = {
                    "operation_result": f"⚠️ Dangerous operation detected:\n```sql\n{sql_query}\n```",
                    "sql_executed": sql_query,
                    "requires_approval": True
                }
                return state

            # --- STEP 4: Execute SQL safely -----------------------------------
            result = self.execute_sql_query(sql_query)

            if result.get("success"):
                operation_result = f"✅ Query executed successfully!\n```sql\n{sql_query}\n```"
            else:
                operation_result = f"❌ SQL Execution Failed:\n```sql\n{sql_query}\n```\nError: {result.get('error')}"

            # --- STEP 5: Store result in state --------------------------------
            state["context"] = {
                "operation_result": operation_result,
                "sql_executed": sql_query,
                "sql_generated": sql_query,
                "execution_successful": result.get("success", False)
            }

        except Exception as e:
            print(f"❌ Error in _database_operation: {e}")
            import traceback
            traceback.print_exc()

            state["context"] = {
                "operation_result": f"❌ Error: {str(e)}",
                "sql_generated": "Error occurred",
                "execution_successful": False
            }

        return state

    def _extract_sql_from_text(self, text: str) -> str:
        """
        Extract SQL query from LLM response text.
        
        Args:
            text: Raw text from LLM response
            
        Returns:
            Extracted SQL query or empty string if not found
        """
        import re
        
        # Look for SQL code blocks first
        sql_patterns = [
            r'```sql\s*(.*?)\s*```',  # ```sql ... ```
            r'```\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH).*?```',  # ``` ... ``` with SQL keywords
        ]
        
        for pattern in sql_patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            if matches:
                sql = matches[0].strip()
                if sql:
                    return sql
        
        # Look for CREATE TABLE statements specifically (they can be multi-line)
        create_pattern = r'(CREATE\s+TABLE\s+.*?)(?=\n\n|\n$|$|;)'
        create_matches = re.findall(create_pattern, text, re.DOTALL | re.IGNORECASE)
        if create_matches:
            sql = create_matches[0].strip()
            if sql:
                # Ensure it ends with semicolon if not already
                if not sql.endswith(';'):
                    sql += ';'
                return sql
        
        # Look for other SQL statements
        other_sql_pattern = r'(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|WITH).*?(?=\n\n|\n$|$|;)'
        other_matches = re.findall(other_sql_pattern, text, re.DOTALL | re.IGNORECASE)
        if other_matches:
            sql = other_matches[0].strip()
            if sql:
                return sql
        
        # If no pattern matches, try to find any SQL-like statement in lines
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if any(keyword in line.upper() for keyword in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'WITH']):
                return line
        
        return ""

    def _extract_table_names_from_query(self, user_message: str) -> List[str]:
        """
        Extract table names from user query using LLM for intelligent parsing.
        Handles both existing tables and new table creation requests.
        
        Args:
            user_message: User's natural language query
            
        Returns:
            List of table names mentioned in the query
        """
        try:
            # Check if this is a CREATE TABLE request first
            user_lower = user_message.lower()
            is_create_request = any(keyword in user_lower for keyword in [
                'create table', 'make table', 'add table', 'new table', 
                'create a table', 'table name', 'database name'
            ])
            
            if is_create_request:
                # For CREATE TABLE requests, extract the table name to be created
                extraction_prompt = f"""
You are a database assistant. Extract table names from CREATE TABLE requests.

User Query: "{user_message}"

Instructions:
1. If this is a CREATE TABLE request, extract the table name that the user wants to create
2. Look for patterns like "create table X", "table name X", "database name X", "new table X"
3. Return ONLY the table name to be created as a JSON array
4. If no table name is specified, return an empty array []

Examples:
- "create a table name employ with columns id, name, email, password" → ["employ"]
- "create table users with name, email" → ["users"]
- "make a new table called products" → ["products"]
- "table name admin and columns id, name" → ["admin"]
- "database name customer with columns" → ["customer"]

Return format: ["table_name"] or []
"""
            else:
                # For other operations, match against existing tables
                available_tables = self.db_tools.get_all_table_names()
                extraction_prompt = f"""
You are a database assistant. Extract table names from the user's query.

User Query: "{user_message}"

Available tables in database: {', '.join(available_tables)}

Instructions:
1. Identify any table names mentioned in the user's query
2. Match them against available tables (case-insensitive)
3. Return ONLY the table names as a JSON array
4. If no specific table is mentioned, return an empty array []

Examples:
- "add 5 columns to user table" → ["user"]
- "show me data from users and orders" → ["users", "orders"]
- "insert into customer table" → ["customer"]

Return format: ["table1", "table2"] or []
"""
            
            try:
                response = self.llm.invoke([
                    SystemMessage(content="You are a table name extraction assistant. Return only JSON array."),
                    HumanMessage(content=extraction_prompt)
                ])
                
                # Parse the JSON response
                import json
                table_names = json.loads(response.content.strip())
                return table_names if isinstance(table_names, list) else []
            except Exception as llm_error:
                print(f"❌ LLM Table Extraction Error: {str(llm_error)}")
                if "401" in str(llm_error) or "User not found" in str(llm_error):
                    print("🔑 API Authentication Error during table extraction")
                    # Fall back to simple string matching
                    if is_create_request:
                        # For CREATE requests, try to extract table name using simple patterns
                        import re
                        patterns = [
                            r'table\s+name\s+(\w+)',
                            r'database\s+name\s+(\w+)',
                            r'create\s+table\s+(\w+)',
                            r'new\s+table\s+called?\s+(\w+)',
                            r'make\s+table\s+(\w+)',
                            r'add\s+table\s+(\w+)'
                        ]
                        for pattern in patterns:
                            match = re.search(pattern, user_lower)
                            if match:
                                table_name = match.group(1)
                                print(f"🔄 Fallback extraction found: [{table_name}]")
                                return [table_name]
                        return []
                    else:
                        # For other operations, match against existing tables
                        available_tables = self.db_tools.get_all_table_names()
                        extracted = []
                        for table in available_tables:
                            if table.lower() in user_lower:
                                extracted.append(table)
                        print(f"🔄 Fallback extraction found: {extracted}")
                        return extracted
                else:
                    raise llm_error
            
        except Exception as e:
            print(f"Error extracting table names: {e}")
            return []
    
    def _get_specific_table_schemas(self, table_names: List[str]) -> Dict[str, Any]:
        """
        Get detailed schema information for specific tables.
        
        Args:
            table_names: List of table names to get schemas for
            
        Returns:
            Dictionary with table schemas
        """
        table_schemas = {}
        
        for table_name in table_names:
            try:
                schema = get_table_schema(self.engine, table_name)
                if not schema.get("error"):
                    table_schemas[table_name] = schema
                else:
                    print(f"Warning: Could not get schema for table '{table_name}': {schema.get('error')}")
            except Exception as e:
                print(f"Error getting schema for table '{table_name}': {e}")
        
        return table_schemas
    
    def _format_table_schema_for_llm(self, table_name: str, schema: List[Dict]) -> str:
        """
        Format table schema information for LLM consumption.
        
        Args:
            table_name: Name of the table
            schema: Schema information from get_table_schema
            
        Returns:
            Formatted string with table schema information
        """
        if not schema or schema.get("error"):
            return f"Table '{table_name}': Schema not available"
        
        formatted = [f"📋 TABLE: {table_name}"]
        formatted.append("  Columns:")
        
        for col in schema:
            col_info = f"    • {col['column_name']} ({col['data_type']})"
            formatted.append(col_info)
        
        return "\n".join(formatted)

    def _validate_sql_against_schema(self, sql_query: str, db_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate SQL query against the database schema.
        
        Args:
            sql_query: SQL query to validate
            db_schema: Database schema information
            
        Returns:
            Dictionary with validation result and error details
        """
        try:
            sql_upper = sql_query.upper().strip()
            
            # Extract table name from SQL
            table_name = None
            if sql_upper.startswith('INSERT INTO'):
                # Extract table name from INSERT INTO table_name
                parts = sql_query.split()
                if len(parts) >= 3:
                    table_name = parts[2].strip('`"[]()')
            elif sql_upper.startswith('SELECT'):
                # For SELECT queries, try to extract table names
                # This is more complex, so we'll be more lenient
                return {"valid": True, "error": None}
            elif sql_upper.startswith('UPDATE'):
                # Extract table name from UPDATE table_name
                parts = sql_query.split()
                if len(parts) >= 2:
                    table_name = parts[1].strip('`"[]()')
            elif sql_upper.startswith('DELETE FROM'):
                # Extract table name from DELETE FROM table_name
                parts = sql_query.split()
                if len(parts) >= 3:
                    table_name = parts[2].strip('`"[]()')
            
            if not table_name:
                return {"valid": True, "error": None}  # Can't validate without table name
            
            # Get table schema
            table_schema = db_schema.get('tables', {}).get(table_name)
            if not table_schema:
                return {
                    "valid": False, 
                    "error": f"Table '{table_name}' not found in schema",
                    "available_columns": "Table not found"
                }
            
            # Get available columns
            available_columns = [col['name'] for col in table_schema.get('columns', [])]
            
            # For INSERT statements, validate columns
            if sql_upper.startswith('INSERT INTO'):
                # Extract column names from INSERT statement
                # Look for pattern: INSERT INTO table (col1, col2, ...) VALUES
                import re
                match = re.search(r'INSERT INTO\s+\w+\s*\(([^)]+)\)', sql_query, re.IGNORECASE)
                if match:
                    columns_str = match.group(1)
                    used_columns = [col.strip().strip('`"[]()') for col in columns_str.split(',')]
                    
                    # Check if all used columns exist in schema
                    invalid_columns = [col for col in used_columns if col not in available_columns]
                    if invalid_columns:
                        return {
                            "valid": False,
                            "error": f"Columns {invalid_columns} do not exist in table '{table_name}'",
                            "available_columns": ", ".join(available_columns)
                        }
            
            return {"valid": True, "error": None, "available_columns": ", ".join(available_columns)}
            
        except Exception as e:
            print(f"❌ Error validating SQL against schema: {e}")
            return {"valid": True, "error": None}  # If validation fails, allow execution
    
    def _generate_response(self, state: ConversationState) -> ConversationState:
        """
        Generate final response using LLM with all context.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with final response
        """
        print("<=== _generate_response ===>")
        messages = state["messages"]
        last_message = messages[-1].content if messages else ""
        
        # Check if this is a human approval request
        # print(f"🔧 Checking approval_pending: {state.get('approval_pending')}")
        # print(f"🔧 Checking requires_approval: {state.get('context', {}).get('requires_approval')}")
        
        if state.get("approval_pending") and state.get("context", {}).get("requires_approval"):
            # Return the approval message directly without LLM processing
            approval_message = state["context"]["operation_result"]
            print(f"🔧 Returning approval message: {approval_message[:100]}...")
            state["messages"].append(AIMessage(content=approval_message))
            return state
        
        # Build comprehensive context
        context_parts = []
        
        if state.get("context"):
            if "operation_result" in state["context"]:
                context_parts.append(f"Database Operation Result: {state['context']['operation_result']}")
            if "database_info" in state["context"]:
                context_parts.append(f"Database Summary: {json.dumps(state['context']['database_info'], indent=2)}")
        
        # Add human approval context if relevant
        if state.get("human_approval") is not None:
            if state["human_approval"]:
                context_parts.append("Human approved the database operation.")
            else:
                context_parts.append("Human denied the database operation.")
        
        # LangGraph automatically manages conversation history through the state
        
        full_context = "\n\n".join(context_parts) if context_parts else "No additional context available."
        
        response_prompt = get_response_prompt(full_context, last_message)
        
        try:
            # LangGraph automatically provides conversation history through state["messages"]
            # We can use the existing messages in the state which include the full conversation
            existing_messages = state["messages"]
            
            # Create a new message list with system prompt and existing conversation
            llm_messages = [SystemMessage(content=self.system_prompt)]
            llm_messages.extend(existing_messages)
            llm_messages.append(HumanMessage(content=response_prompt))
            
            response = self.llm.invoke(llm_messages)
            
            ai_response = response.content
            
            # Add AI response to state
            state["messages"].append(AIMessage(content=ai_response))
            
        except Exception as e:
            print(f"❌ LLM Response Generation Error: {str(e)}")
            if "401" in str(e) or "User not found" in str(e):
                print("🔑 API Authentication Error: Please check your OpenRouter API key")
                print("   - Make sure OPENROUTER_API_KEY06 is set correctly in .env file")
                print("   - Verify the API key is valid and has sufficient credits")
                error_response = f"❌ **API Authentication Error:** {str(e)}\n\nPlease check your OpenRouter API key configuration."
            else:
                error_response = f"Error generating response: {str(e)}"
            state["messages"].append(AIMessage(content=error_response))
        
        return state
    
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get lightweight database information - only table names and column headers.
        
        Returns:
            Dictionary containing basic database structure information
        """
        try:
            print("<=== get_database_info ===>")
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            database_info = {
                "tables": {},
                "total_tables": len(tables),
                "database_url": self.config.database_url.split('@')[-1] if '@' in self.config.database_url else "Local database"
            }
            
            # Get only basic info for each table - no row counts or detailed metadata
            for table_name in tables:
                columns = inspector.get_columns(table_name)
                
                database_info["tables"][table_name] = {
                    "columns": [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col["nullable"]
                        } for col in columns
                    ]
                }
            
            return database_info
            
        except Exception as e:
            return {"error": f"Failed to get database info: {str(e)}"}
    
    
    def execute_sql_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SQL query with real-time execution.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Dictionary containing query results or error information
        """
        try:
            print(f"<=== execute_sql_query ===> Executing: {query}")
            query_upper = query.upper().strip()
            
            # Use engine.begin() for proper transaction management
            with self.engine.begin() as conn:
                if query_upper.startswith('SELECT'):
                    # For SELECT queries, fetch and return data
                    result = conn.execute(text(query))
                    columns = result.keys()
                    rows = result.fetchall()
                    
                    return {
                        "success": True,
                        "columns": list(columns),
                        "data": [dict(row._mapping) for row in rows],
                        "row_count": len(rows),
                        "query_type": "SELECT"
                    }
                else:
                    # For other operations (INSERT, UPDATE, DELETE, ALTER, DROP, CREATE)
                    result = conn.execute(text(query))
                    # Transaction will be automatically committed when exiting the context
                    
                    # For CREATE TABLE operations, verify the table was actually created
                    if query_upper.startswith('CREATE'):
                        table_name = self.db_tools.extract_table_name_from_create(query)
                        if table_name:
                            # Verify table creation within the same transaction
                            verification_query = self.db_tools.get_table_exists_query(table_name)
                            verification_result = conn.execute(text(verification_query))
                            verification_row = verification_result.fetchone()
                            table_exists = bool(verification_row[0]) if verification_row else False
                            
                            if not table_exists:
                                return {
                                    "success": False,
                                    "error": f"Table '{table_name}' creation failed - table not found in database",
                                    "query_type": "CREATE"
                                }
                    
                    # For DROP TABLE operations, verify the table was actually dropped
                    elif query_upper.startswith('DROP'):
                        table_name = self.db_tools.extract_table_name_from_drop(query)
                        if table_name:
                            # Verify table deletion within the same transaction
                            verification_query = self.db_tools.get_table_exists_query(table_name)
                            verification_result = conn.execute(text(verification_query))
                            verification_row = verification_result.fetchone()
                            table_still_exists = bool(verification_row[0]) if verification_row else False
                            
                            if table_still_exists:
                                return {
                                    "success": False,
                                    "error": f"Table '{table_name}' deletion failed - table still exists in database",
                                    "query_type": "DROP"
                                }
                    
                    return {
                        "success": True,
                        "message": "Query executed successfully",
                        "affected_rows": result.rowcount if hasattr(result, 'rowcount') else 0,
                        "query_type": query_upper.split()[0] if query_upper.split() else "UNKNOWN"
                    }
                        
        except SQLAlchemyError as e:
            error_msg = str(e)
            print(f"SQLAlchemy Error: {error_msg}")
            # Provide more specific error messages
            if "syntax error" in error_msg.lower():
                return {
                    "success": False,
                    "error": f"SQL syntax error: {error_msg}\n\nGenerated SQL: {query}",
                    "query": query,
                    "error_type": "syntax_error"
                }
            elif "table already exists" in error_msg.lower():
                return {
                    "success": False,
                    "error": f"Table already exists: {error_msg}",
                    "query": query,
                    "error_type": "table_exists"
                }
            elif "no such table" in error_msg.lower():
                return {
                    "success": False,
                    "error": f"Table not found: {error_msg}",
                    "query": query,
                    "error_type": "table_not_found"
                }
            else:
                return {
                    "success": False,
                    "error": f"Database error: {error_msg}",
                    "query": query,
                    "error_type": "database_error"
                }
        except Exception as e:
            error_msg = str(e)
            print(f"Unexpected Error: {error_msg}")
            return {
                "success": False,
                "error": f"Unexpected error: {error_msg}",
                "query": query,
                "error_type": "unexpected_error"
            }
    
    def create_table(self, table_name: str, columns: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Create a new table with specified columns.
        
        Args:
            table_name: Name of the table to create
            columns: List of column definitions with name, type, and constraints
            
        Returns:
            Dictionary containing operation result
        """
        try:
            print("<=== create_table ===>")
            column_definitions = []
            for col in columns:
                col_def = f"{col['name']} {col['type']}"
                if col.get('primary_key'):
                    col_def += " PRIMARY KEY"
                if col.get('not_null'):
                    col_def += " NOT NULL"
                if col.get('unique'):
                    col_def += " UNIQUE"
                column_definitions.append(col_def)
            
            query = f"CREATE TABLE {table_name} ({', '.join(column_definitions)})"
            
            with self.engine.connect() as conn:
                conn.execute(text(query))
                conn.commit()
                
            return {
                "success": True,
                "message": f"Table '{table_name}' created successfully",
                "query": query
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create table: {str(e)}"
            }
    
    def drop_table(self, table_name: str) -> Dict[str, Any]:
        """
        Drop a table from the database.
        
        Args:
            table_name: Name of the table to drop
            
        Returns:
            Dictionary containing operation result
        """
        try:
            print("<=== drop_table ===>")
            query = f"DROP TABLE IF EXISTS {table_name}"
            
            with self.engine.connect() as conn:
                conn.execute(text(query))
                conn.commit()
                
            return {
                "success": True,
                "message": f"Table '{table_name}' dropped successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to drop table: {str(e)}"
            }
    
    def insert_data(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert data into a table.
        
        Args:
            table_name: Name of the table
            data: Dictionary of column names and values to insert
            
        Returns:
            Dictionary containing operation result
        """
        try:
            print("<=== insert_data ===>")
            columns = list(data.keys())
            placeholders = ', '.join([':' + col for col in columns])
            
            query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            
            with self.engine.connect() as conn:
                conn.execute(text(query), data)
                conn.commit()
                
            return {
                "success": True,
                "message": f"Data inserted into '{table_name}' successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to insert data: {str(e)}"
            }
    
    def update_data(self, table_name: str, data: Dict[str, Any], where_clause: str) -> Dict[str, Any]:
        """
        Update data in a table.
        
        Args:
            table_name: Name of the table
            data: Dictionary of column names and new values
            where_clause: WHERE condition for the update
            
        Returns:
            Dictionary containing operation result
        """
        try:
            print("<=== update_data ===>")
            set_clauses = ', '.join([f"{col} = :{col}" for col in data.keys()])
            query = f"UPDATE {table_name} SET {set_clauses} WHERE {where_clause}"
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query), data)
                conn.commit()
                
            return {
                "success": True,
                "message": f"Data updated in '{table_name}' successfully",
                "affected_rows": result.rowcount
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to update data: {str(e)}"
            }
    
    def delete_data(self, table_name: str, where_clause: str) -> Dict[str, Any]:
        """
        Delete data from a table.
        
        Args:
            table_name: Name of the table
            where_clause: WHERE condition for the deletion
            
        Returns:
            Dictionary containing operation result
        """
        try:
            print("<=== delete_data ===>")
            query = f"DELETE FROM {table_name} WHERE {where_clause}"
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                conn.commit()
                
            return {
                "success": True,
                "message": f"Data deleted from '{table_name}' successfully",
                "affected_rows": result.rowcount
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete data: {str(e)}"
            }
    
    def chat(self, user_input: str, thread_id: str = None) -> str:
        """
        Main chat interface using LLM-driven workflow with LangGraph thread management.
        
        Args:
            user_input: User's message or query
            thread_id: Thread ID for conversation history (creates new if None)
            
        Returns:
            Agent's response
        """
        try:
            print("<=== chat ===>")
            print(f"User input: {user_input}")
            
            # Generate new thread ID if not provided
            if thread_id is None:
                thread_id = str(uuid.uuid4())
                print(f"Created new thread: {thread_id}")
            
            # Configure thread for LangGraph
            config = {"configurable": {"thread_id": thread_id}}
            
            # Check if this is an approval continuation message
            if user_input in ['__APPROVED__', '__DENIED__']:
                print(f"🔧 Handling approval continuation: {user_input}")
                
                # Get the current state to retrieve approval_id
                current_state = self.workflow.get_state(config)
                if current_state and current_state.values:
                    approval_id = current_state.values.get("approval_id")
                    print(f"🔧 Found approval_id: {approval_id}")
                    
                    if approval_id:
                        # Check approval status
                        approval_status = simple_approval_manager.get_approval_status(approval_id)
                        status = approval_status.get("status", "").lower()
                        print(f"🔧 Approval status: {status}")
                        
                        if status == "approved":
                            # Execute the approved query
                            sql_query = current_state.values.get("context", {}).get("sql_executed")
                            if sql_query:
                                print(f"🔧 Executing approved query: {sql_query}")
                                result = self.execute_sql_query(sql_query)
                                
                                if result.get("success"):
                                    return f"✅ Successfully executed approved operation:\n```sql\n{sql_query}\n```\n\nResult: {json.dumps(result, indent=2)}"
                                else:
                                    return f"❌ Error executing approved operation:\n```sql\n{sql_query}\n```\n\nError: {result.get('error', 'Unknown error')}"
                        elif status == "denied":
                            return "❌ Operation cancelled by user. No changes were made to the database."
                
                return "⚠️ No pending approval found."
            
            # Create initial state
            initial_state = ConversationState(
                messages=[HumanMessage(content=user_input)],
                next_action=None,
                context=None,
                pending_query=None,
                human_approval=None,
                approval_pending=None,
                approval_id=None
            )
            
            # Run through the workflow with thread configuration
            final_state = self.workflow.invoke(initial_state, config=config)
            
            # Get the last AI message
            ai_messages = [msg for msg in final_state["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                ai_response = ai_messages[-1].content
                return ai_response
            else:
                error_response = "I'm sorry, I couldn't process your request. Please try again."
                return error_response
                
        except Exception as e:
            error_response = f"❌ Error: {str(e)}"
            print(f"Error in chat: {e}")
            import traceback
            traceback.print_exc()
            return error_response
    
    def get_conversation_history(self, thread_id: str = None) -> List[Dict[str, Any]]:
        """
        Get the conversation history for a specific thread using LangGraph's memory.
        
        Args:
            thread_id: Thread ID to get history for
            
        Returns:
            List of conversation entries with role, content, and timestamp
        """
        print("<=== get_conversation_history ===>")
        if not thread_id:
            return []
        
        try:
            # Get the current state for the thread
            config = {"configurable": {"thread_id": thread_id}}
            state = self.workflow.get_state(config)
            
            if state and state.values:
                messages = state.values.get("messages", [])
                history = []
                for msg in messages:
                    if isinstance(msg, HumanMessage):
                        history.append({
                            "role": "user",
                            "content": msg.content,
                            "timestamp": datetime.now().isoformat()
                        })
                    elif isinstance(msg, AIMessage):
                        history.append({
                            "role": "assistant", 
                            "content": msg.content,
                            "timestamp": datetime.now().isoformat()
                        })
                return history
            return []
        except Exception as e:
            print(f"Error getting conversation history: {e}")
            return []
    
    def clear_conversation_history(self, thread_id: str = None) -> None:
        """
        Clear the conversation history for a specific thread.
        
        Args:
            thread_id: Thread ID to clear
        """
        print("<=== clear_conversation_history ===>")
        if thread_id:
            try:
                # Clear the thread by updating it with empty state
                config = {"configurable": {"thread_id": thread_id}}
                empty_state = ConversationState(
                    messages=[],
                    next_action=None,
                    context=None
                )
                self.workflow.update_state(config, empty_state)
            except Exception as e:
                print(f"Error clearing conversation history: {e}")
    
    def create_new_thread(self) -> str:
        """
        Create a new conversation thread.
        
        Returns:
            New thread ID
        """
        thread_id = str(uuid.uuid4())
        print(f"Created new thread: {thread_id}")
        return thread_id
    
    def get_thread_info(self, thread_id: str) -> Dict[str, Any]:
        """
        Get information about a specific thread.
        
        Args:
            thread_id: Thread ID to get info for
            
        Returns:
            Thread information dictionary
        """
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.workflow.get_state(config)
            
            if state and state.values:
                messages = state.values.get("messages", [])
                return {
                    "thread_id": thread_id,
                    "message_count": len(messages),
                    "created_at": datetime.now().isoformat(),
                    "last_activity": datetime.now().isoformat()
                }
            else:
                return {"error": "Thread not found"}
        except Exception as e:
            return {"error": f"Thread not found: {str(e)}"}
    
    def list_threads(self) -> List[Dict[str, Any]]:
        """
        List all threads with basic information.
        Note: This is a simplified implementation as LangGraph's memory doesn't provide
        a direct way to list all threads.
        
        Returns:
            List of thread information dictionaries
        """
        # LangGraph's MemorySaver doesn't provide a direct way to list all threads
        # This would require additional implementation or using a different checkpointer
        return []
    
    

    def get_help(self) -> str:
        """
        Get help information for the database agent.
        
        Returns:
            Formatted help text with available commands and examples
        """
        print("<=== get_help ===>")
        return HELP_TEXT


def main():
    """
    Main function to run the LLM-driven database agent with human-in-the-loop.
    
    Initializes the agent, displays help information, and starts
    the interactive chat loop with intelligent decision making and human approval.
    """
    print(" Real-Time Database Agent with Human-in-the-Loop Starting...")
    print("=" * 60)
    
    try:
        agent = DatabaseAgent()
        print(" Database connection established")
        print(" AI model loaded")
        print(" Real-time execution enabled")
        print(" Human approval system ready")
        print(" Immediate SQL execution ready")
        print("\n" + agent.get_help())
        
        print("\n" + "=" * 60)
        print(" Chat with your real-time database agent! (Type 'quit' to exit)")
        print("The AI executes your requests immediately with human approval for safety!")
        print("=" * 60)
        
        while True:
            user_input = input("\n==> You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print(" Goodbye! Thanks for using Real-Time Database Agent!")
                break
            
            if user_input.lower() == 'history':
                history = agent.get_conversation_history()
                print("\n **Conversation History:**")
                for entry in history[-10:]:  # Show last 10 entries
                    print(f"{entry['role'].title()}: {entry['content'][:100]}...")
                continue
            
            if user_input.lower() == 'clear':
                agent.clear_conversation_history()
                print("==> Conversation history cleared!")
                continue
            
            if not user_input:
                continue
                
            print("\n==> Agent: ", end="")
            response = agent.chat(user_input)
            print(response)
            
    except Exception as e:
        print(f"❌ Failed to start Real-Time Database Agent: {str(e)}")
        print("Please check your database connection and OPENROUTER_API_KEY.")


if __name__ == "__main__":
    main()