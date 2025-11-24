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
# setup for google genai
# from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import os
from dotenv import load_dotenv
import json
import re
from datetime import datetime

load_dotenv()




class ConversationState(TypedDict):
    """State for the LangGraph conversation workflow."""
    messages: Annotated[List[Any], add_messages]
    next_action: Optional[str]
    context: Optional[Dict[str, Any]]
    pending_query: Optional[str]
    human_approval: Optional[bool]


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
        # openrouter
        self.llm = ChatOpenAI(model="openai/gpt-oss-20b:free",
         api_key=os.getenv("OPENROUTER_API_KEY05"),
         base_url="https://openrouter.ai/api/v1"

         )

        
        # Initialize database connection with error handling
        self.database_url = os.getenv("DATABASE_URL")

        if not self.database_url:
            raise ValueError("DATABASE_URL not found in environment variables. Please check your .env file.")
        
        try:
            self.engine = create_engine(self.database_url, echo=False)
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {str(e)}. Please check your DATABASE_URL in .env file.")
        
        # Conversation history
        self.conversation_history: List[Dict[str, Any]] = []
        
        # System prompt for the AI
        self.system_prompt = """You are an intelligent database assistant that executes operations in real-time. You can:
1. Understand user queries in natural language
2. Execute SQL queries and database operations immediately
3. Perform real-time database modifications (ALTER, DROP, INSERT, UPDATE, DELETE)
4. Provide database insights and analysis
5. Remember conversation context for better responses

IMPORTANT: When users request database operations, execute them immediately in real-time.
Do not just talk about what you would do - actually perform the operations.
Be helpful, accurate, and explain what you've done after execution."""

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
                "response": "response"
            }
        )
        
        workflow.add_edge("response", END)
        
        self.workflow = workflow.compile()
    
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
        
        # Get conversation history for context
        history_context = ""
        if self.conversation_history:
            recent_history = self.conversation_history[-3:]  # Last 3 exchanges
            history_context = "\n".join([
                f"{entry['role']}: {entry['content']}" 
                for entry in recent_history
            ])
        
        router_prompt = f"""
You are a database assistant router. Based on the user's message, decide what action to take.

User message: {last_message}

Recent conversation:
{history_context}

Available actions:
- "database_operation": If the user wants to query, insert, update, delete, or get database info
- "response": If the user is asking for help, explanation, or general conversation
- "end": If the user wants to quit or end the conversation

Respond with ONLY the action name (database_operation, response, or end).
"""
        
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
            state["next_action"] = "response"  # Default to response on error
        
        return state
    
    def _should_continue(self, state: ConversationState) -> str:
        """Return the next action based on LLM decision."""
        return state.get("next_action", "response")
    
    def _needs_human_approval(self, state: ConversationState) -> str:
        """
        Determine if the database operation needs human approval.
        
        Args:
            state: Current conversation state
            
        Returns:
            Next action based on whether human approval is needed
        """
        context = state.get("context", {})
        sql_query = context.get("sql_executed")
        
        if sql_query:
            # Check if it's a dangerous operation that needs approval
            dangerous_operations = ['DROP', 'DELETE', 'ALTER', 'TRUNCATE']
            query_upper = sql_query.upper().strip()
            
            for op in dangerous_operations:
                if query_upper.startswith(op):
                    # Store the pending query for human approval
                    state["pending_query"] = sql_query
                    return "human_approval"
        
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
        pending_query = state.get("pending_query", "")
        
        if not pending_query:
            state["human_approval"] = False
            return state
        
        print(f"\n⚠️  DANGEROUS OPERATION DETECTED ⚠️")
        print(f"SQL Query: {pending_query}")
        print(f"\nThis operation could modify or delete data in your database.")
        
        while True:
            user_input = input("\n🤔 Do you want to allow me to run this query? (yes/no): ").strip().lower()
            
            if user_input in ['yes', 'y', 'allow', 'ok']:
                state["human_approval"] = True
                print("✅ Query approved! Executing...")
                break
            elif user_input in ['no', 'n', 'deny', 'cancel']:
                state["human_approval"] = False
                print("❌ Query denied! Operation cancelled.")
                break
            else:
                print("Please enter 'yes' or 'no'.")
        
        return state
    
    def _handle_human_decision(self, state: ConversationState) -> str:
        """
        Handle the human approval decision.
        
        Args:
            state: Current conversation state
            
        Returns:
            Next action based on human decision
        """
        if state.get("human_approval", False):
            # Human approved, execute the query
            return "database_operation"
        else:
            # Human denied, go to response
            return "response"
    
    def _database_operation(self, state: ConversationState) -> ConversationState:
        """
        Handle database operations using LLM to understand and execute in real-time.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with operation results
        """
        print("<=== _database_operation ===>")
        messages = state["messages"]
        last_message = messages[-1].content if messages else ""
        
        # Check if this is a retry after human approval
        if state.get("human_approval") is True and state.get("pending_query"):
            # Execute the approved query
            sql_query = state["pending_query"]
            result = self.execute_sql_query(sql_query)
            
            if result.get("success"):
                operation_result = f"✅ Successfully executed approved SQL query:\n```sql\n{sql_query}\n```\n\nResult: {json.dumps(result, indent=2)}"
            else:
                operation_result = f"❌ Error executing approved SQL query:\n```sql\n{sql_query}\n```\n\nError: {result.get('error', 'Unknown error')}"
            
            # Clear the pending query and approval
            state["pending_query"] = None
            state["human_approval"] = None
            
            state["context"] = {
                "operation_result": operation_result,
                "sql_executed": sql_query
            }
            return state
        
        # Check if human denied the operation
        if state.get("human_approval") is False:
            operation_result = "❌ Operation cancelled by user. No changes were made to the database."
            state["context"] = {
                "operation_result": operation_result,
                "sql_executed": None
            }
            # Clear the pending query and approval
            state["pending_query"] = None
            state["human_approval"] = None
            return state
        
        # Get lightweight database info for context
        db_info = self.get_database_info()
        
        # Create a simplified database summary for the LLM
        db_summary = {
            "total_tables": db_info.get("total_tables", 0),
            "table_names": list(db_info.get("tables", {}).keys()),
            "table_columns": {
                table: [col["name"] for col in info.get("columns", [])]
                for table, info in db_info.get("tables", {}).items()
            }
        }
        
        operation_prompt = f"""
You are a database assistant. The user wants to perform a database operation.

User message: {last_message}

Database summary:
- Total tables: {db_summary['total_tables']}
- Table names: {db_summary['table_names']}
- Table columns: {db_summary['table_columns']}

Based on the user's request, you need to:
1. If it's a direct SQL query, execute it immediately
2. If it's a natural language request, convert it to SQL and execute it
3. If it's a request for database info, provide the information

IMPORTANT: You must actually execute SQL commands, not just talk about them.
For dangerous operations like DROP, ALTER, DELETE - execute them if the user confirms.

Respond with the actual results of the operation.
"""
        
        try:
            # First, let LLM analyze what needs to be done
            analysis_response = self.llm.invoke([
                SystemMessage(content="You are a database assistant. Analyze the user's request and determine what SQL operation to perform. Respond with ONLY the SQL query to execute, or 'INFO' if it's just a request for information."),
                HumanMessage(content=f"User request: {last_message}\nDatabase summary: {json.dumps(db_summary, indent=2)}")
            ])
            
            sql_query = analysis_response.content.strip()
            
            # Check if it's a SQL query or info request
            if sql_query.upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'ALTER', 'DROP', 'CREATE')):
                # Execute the SQL query
                result = self.execute_sql_query(sql_query)
                
                if result.get("success"):
                    operation_result = f"✅ Successfully executed SQL query:\n```sql\n{sql_query}\n```\n\nResult: {json.dumps(result, indent=2)}"
                else:
                    operation_result = f"❌ Error executing SQL query:\n```sql\n{sql_query}\n```\n\nError: {result.get('error', 'Unknown error')}"
                    
            elif sql_query.upper() == 'INFO':
                # Provide database information
                operation_result = f"📊 Database Information:\n{json.dumps(db_info, indent=2)}"
            else:
                # Let LLM handle other cases
                response = self.llm.invoke([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=operation_prompt)
                ])
                operation_result = response.content
            
            # Store the operation result in context
            state["context"] = {
                "operation_result": operation_result,
                "database_info": db_summary,
                "sql_executed": sql_query if sql_query.upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'ALTER', 'DROP', 'CREATE')) else None
            }
            
        except Exception as e:
            state["context"] = {
                "operation_result": f"❌ Error processing database operation: {str(e)}",
                "database_info": db_summary
            }
        
        return state
    
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
        
        # Add conversation history
        if self.conversation_history:
            history_text = "\n".join([
                f"{entry['role']}: {entry['content']}" 
                for entry in self.conversation_history[-5:]
            ])
            context_parts.append(f"Recent Conversation:\n{history_text}")
        
        full_context = "\n\n".join(context_parts) if context_parts else "No additional context available."
        
        response_prompt = f"""
Context Information:
{full_context}

Current User Message: {last_message}

Provide a helpful, accurate, and context-aware response. 
If database operations were performed, explain the results clearly.
If a human approval was involved, acknowledge their decision.
Use conversation history to provide better context.
"""
        
        try:
            response = self.llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=response_prompt)
            ])
            
            ai_response = response.content
            
            # Add AI response to state
            state["messages"].append(AIMessage(content=ai_response))
            
        except Exception as e:
            error_response = f"Error generating response: {str(e)}"
            state["messages"].append(AIMessage(content=error_response))
        
        return state
    
    def _add_to_history(self, role: str, content: str) -> None:
        """
        Add message to conversation history.
        
        Args:
            role: Role of the speaker ('user' or 'assistant')
            content: Message content
        """
        print("<=== _add_to_history ===>")
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
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
                "database_url": self.database_url.split('@')[-1] if '@' in self.database_url else "Local database"
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
            print("<=== execute_sql_query ===>")
            query_upper = query.upper().strip()
            
            with self.engine.connect() as conn:
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
                    conn.commit()
                    
                    return {
                        "success": True,
                        "message": "Query executed successfully",
                        "affected_rows": result.rowcount if hasattr(result, 'rowcount') else 0,
                        "query_type": query_upper.split()[0] if query_upper.split() else "UNKNOWN"
                    }
                        
        except SQLAlchemyError as e:
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "query": query
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "query": query
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
    
    def chat(self, user_input: str) -> str:
        """
        Main chat interface using LLM-driven workflow.
        
        Args:
            user_input: User's message or query
            
        Returns:
            Agent's response
        """
        try:
            print("<=== chat ===>")
            # Create initial state
            initial_state = ConversationState(
                messages=[HumanMessage(content=user_input)],
                next_action=None,
                context=None
            )
            
            # Run through the workflow
            final_state = self.workflow.invoke(initial_state)
            
            # Get the last AI message
            ai_messages = [msg for msg in final_state["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                ai_response = ai_messages[-1].content
                # Add to conversation history only once at the end
                self._add_to_history("user", user_input)
                self._add_to_history("assistant", ai_response)
                return ai_response
            else:
                error_response = "I'm sorry, I couldn't process your request. Please try again."
                self._add_to_history("user", user_input)
                self._add_to_history("assistant", error_response)
                return error_response
                
        except Exception as e:
            error_response = f"❌ Error: {str(e)}"
            self._add_to_history("user", user_input)
            self._add_to_history("assistant", error_response)
            return error_response
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get the conversation history.
        
        Returns:
            List of conversation entries with role, content, and timestamp
        """
        print("<=== get_conversation_history ===>")
        return self.conversation_history.copy()
    
    def clear_conversation_history(self) -> None:
        """Clear the conversation history."""
        print("<=== clear_conversation_history ===>")
        self.conversation_history.clear()
    
    def get_help(self) -> str:
        """
        Get help information for the database agent.
        
        Returns:
            Formatted help text with available commands and examples
        """
        print("<=== get_help ===>")
        return """
==> **Real-Time Database Agent with Human-in-the-Loop Help**

**How it works:**
- The AI executes database operations immediately in real-time
- No hardcoded rules - everything is dynamically determined by the LLM
- Natural language understanding with instant execution
- **Human approval required for dangerous operations** (DROP, DELETE, ALTER, TRUNCATE)

**You can ask:**
- "Show me the database structure" → Gets real database info
- "What tables do I have?" → Queries database immediately
- "SELECT * FROM todos" → Executes SQL instantly
- "Remove the priority column" → **Asks for approval** before dropping
- "Add a new table" → Creates table in real-time

**Safety Features:**
- ==> **Human approval for dangerous operations**
- ==> Real-time SQL execution
- ==> Natural language understanding
- ==> Dynamic workflow routing
- ==> Live database analysis
- ==> Instant operation execution
- ==> Conversation memory

**Examples:**
- "What's in my database?" → Shows actual database structure
- "Delete all completed tasks" → **Asks for approval** before deleting
- "Add a new column" → **Asks for approval** before modifying table

**Human-in-the-Loop:**
When you request dangerous operations like DROP, DELETE, ALTER, or TRUNCATE,
the agent will show you the exact SQL query and ask for your approval before executing.

The AI executes your requests immediately - with your approval for safety!
"""


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