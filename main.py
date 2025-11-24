"""
Simple FastAPI API for Database Agent with Human-in-the-Loop
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
import asyncio
from datetime import datetime
from agent.main_agent import DatabaseAgent
from agent.simple_approval import simple_approval_manager
from fastapi.middleware.cors import CORSMiddleware
import threading
import uuid
from fastapi import Query


# Initialize FastAPI app
app = FastAPI(
    title="Database Agent API",
    description="AI-powered database agent with human-in-the-loop functionality",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent = None

# Session management for stop functionality
active_sessions = {}
session_lock = threading.Lock()

# Simple Pydantic models
class ChatRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    thread_id: str
    timestamp: str
    operation_type: Optional[str] = None
    human_approval_required: bool = False

class ThreadInfo(BaseModel):
    thread_id: str
    created_at: str
    last_activity: str
    message_count: int

class ThreadListResponse(BaseModel):
    threads: List[ThreadInfo]
    total_threads: int

class DatabaseInfo(BaseModel):
    total_tables: int
    table_names: list
    tables: Dict[str, Any]

class StopRequest(BaseModel):
    session_id: str

class SessionInfo(BaseModel):
    session_id: str
    thread_id: str
    is_active: bool
    created_at: str

class ApprovalRequest(BaseModel):
    sql_query: str

class ApprovalResponse(BaseModel):
    approval_id: str
    requires_approval: bool
    approval_request: Optional[Dict[str, Any]] = None

class ApprovalAction(BaseModel):
    approval_id: str
    action: str  # "approve" or "deny"
    approved_by: Optional[str] = "user"

# Initialize agent on startup
@app.on_event("startup")
async def startup_event():
    global agent
    try:
        agent = DatabaseAgent()
        print("✅ Database Agent initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {str(e)}")
        raise e

@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "message": "Database Agent API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/chat",
            "database_info": "/database-info",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_info = agent.get_database_info()
        return {
            "status": "healthy",
            "database_connected": "error" not in db_info,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/database-info")
async def get_database_info():
    """Get database information"""
    try:
        db_info = agent.get_database_info()
        return DatabaseInfo(
            total_tables=db_info.get("total_tables", 0),
            table_names=list(db_info.get("tables", {}).keys()),
            tables=db_info.get("tables", {})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat with the database agent using thread-based conversation"""
    try:
        # Get agent response with thread support
        response = agent.chat(request.query, request.thread_id)
        
        # Get the thread ID that was used (either provided or newly created)
        thread_id = request.thread_id or "default"
        
        # Determine if human approval was required
        human_approval_required = False
        operation_type = None
        
        # Check if the response indicates human approval was needed
        if "DANGEROUS OPERATION DETECTED" in response or "approved" in response.lower():
            human_approval_required = True
        
        # Try to extract operation type from response
        if "SELECT" in response.upper():
            operation_type = "SELECT"
        elif "INSERT" in response.upper():
            operation_type = "INSERT"
        elif "UPDATE" in response.upper():
            operation_type = "UPDATE"
        elif "DELETE" in response.upper():
            operation_type = "DELETE"
        elif "DROP" in response.upper():
            operation_type = "DROP"
        elif "ALTER" in response.upper():
            operation_type = "ALTER"
        
        return ChatResponse(
            response=response,
            thread_id=thread_id,
            timestamp=datetime.now().isoformat(),
            operation_type=operation_type,
            human_approval_required=human_approval_required
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")



@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response from the database agent with realistic typing speed and stop functionality"""
    
    # Generate unique session ID for this request
    session_id = str(uuid.uuid4())
    thread_id = request.thread_id or "default"
    
    # Register session as active
    with session_lock:
        active_sessions[session_id] = {
            "thread_id": thread_id,
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "query": request.query
        }
    
    async def generate_stream():
        try:
            # Get the full response from the agent with thread support
            response = agent.chat(request.query, thread_id)
            
            # Check if this is a human approval request
            if "DANGEROUS OPERATION DETECTED" in response or "⚠️" in response or "**Approval ID:**" in response or "Dangerous operation detected" in response:
                # This is a human approval request - send it immediately without streaming
                approval_data = {
                    "chunk": response,
                    "chunk_type": "human_approval",
                    "is_final": True,
                    "thread_id": thread_id,
                    "session_id": session_id,
                    "requires_approval": True,
                    "timestamp": datetime.now().isoformat()
                }
                yield f"data: {json.dumps(approval_data)}\n\n"
                return
            
            # Split response into words for streaming effect
            words = response.split()
            
            # Send words in chunks with realistic typing speed
            for i in range(0, len(words), 2):  # Send 2 words at a time
                # Check if session was stopped BEFORE each chunk
                with session_lock:
                    if session_id not in active_sessions or not active_sessions[session_id]["is_active"]:
                        # Session was stopped, send stop signal
                        stop_data = {
                            "chunk": "",
                            "chunk_type": "stopped",
                            "is_final": True,
                            "thread_id": thread_id,
                            "session_id": session_id,
                            "timestamp": datetime.now().isoformat()
                        }
                        yield f"data: {json.dumps(stop_data)}\n\n"
                        return
                
                chunk = " ".join(words[i:i + 2])
                if i + 2 < len(words):
                    chunk += " "
                
                # Create streaming chunk
                stream_data = {
                    "chunk": chunk,
                    "chunk_type": "text",
                    "is_final": i + 2 >= len(words),
                    "thread_id": thread_id,
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                yield f"data: {json.dumps(stream_data)}\n\n"
                
                # Check again after sending chunk
                with session_lock:
                    if session_id not in active_sessions or not active_sessions[session_id]["is_active"]:
                        # Session was stopped, send stop signal
                        stop_data = {
                            "chunk": "",
                            "chunk_type": "stopped",
                            "is_final": True,
                            "thread_id": thread_id,
                            "session_id": session_id,
                            "timestamp": datetime.now().isoformat()
                        }
                        yield f"data: {json.dumps(stop_data)}\n\n"
                        return
                
                await asyncio.sleep(0.02)  # Very fast streaming - 20ms delay
            
            # Mark session as completed
            with session_lock:
                if session_id in active_sessions:
                    active_sessions[session_id]["is_active"] = False
                
        except Exception as e:
            error_data = {
                "chunk": f"Error: {str(e)}",
                "chunk_type": "error",
                "is_final": True,
                "thread_id": thread_id,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            # Clean up session
            with session_lock:
                if session_id in active_sessions:
                    del active_sessions[session_id]
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Session-ID": session_id
        }
    )

@app.get("/table-data/{table_name}")
async def get_table_data(table_name: str, limit: int = 10):
    """Get table data directly without going through chat"""
    try:
        # Validate table name to prevent SQL injection
        if not table_name.replace('_', '').replace('-', '').isalnum():
            raise HTTPException(status_code=400, detail="Invalid table name")
        
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        result = agent.execute_sql_query(query)
        
        if result.get("success"):
            return {
                "success": True,
                "data": result.get("data", []),
                "columns": result.get("columns", []),
                "row_count": result.get("row_count", 0),
                "table_name": table_name,
                "limit": limit,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "data": [],
                "table_name": table_name,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": [],
            "table_name": table_name,
            "timestamp": datetime.now().isoformat()
        }

@app.get("/conversation-history")
async def get_conversation_history(thread_id: Optional[str] = None):
    """Get conversation history for a specific thread or all threads"""
    try:
        history = agent.get_conversation_history(thread_id)
        return {
            "history": history,
            "total_messages": len(history),
            "thread_id": thread_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/conversation-history")
async def clear_conversation_history(thread_id: Optional[str] = None):
    """Clear conversation history for a specific thread or all threads"""
    try:
        agent.clear_conversation_history(thread_id)
        return {
            "message": f"Conversation history cleared for {'all threads' if thread_id is None else f'thread {thread_id}'}",
            "thread_id": thread_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/threads/new")
async def create_new_thread():
    """Create a new conversation thread"""
    try:
        thread_id = agent.create_new_thread()
        return {
            "thread_id": thread_id,
            "message": "New thread created",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/threads")
async def list_threads():
    """List all conversation threads"""
    try:
        threads = agent.list_threads()
        return ThreadListResponse(
            threads=threads,
            total_threads=len(threads)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/threads/{thread_id}")
async def get_thread_info(thread_id: str):
    """Get information about a specific thread"""
    try:
        thread_info = agent.get_thread_info(thread_id)
        if "error" in thread_info:
            raise HTTPException(status_code=404, detail=thread_info["error"])
        return thread_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a specific thread"""
    try:
        if thread_id in agent.threads:
            del agent.threads[thread_id]
            return {
                "message": f"Thread {thread_id} deleted",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="Thread not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop")
async def stop_generation(request: StopRequest):
    """Stop the current generation for a specific session"""
    try:
        with session_lock:
            if request.session_id in active_sessions:
                active_sessions[request.session_id]["is_active"] = False
                return {
                    "message": "Generation stopped successfully",
                    "session_id": request.session_id,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=404, detail="Session not found or already completed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions")
async def get_active_sessions():
    """Get all active sessions"""
    try:
        with session_lock:
            sessions = []
            for session_id, session_data in active_sessions.items():
                if session_data["is_active"]:
                    sessions.append(SessionInfo(
                        session_id=session_id,
                        thread_id=session_data["thread_id"],
                        is_active=session_data["is_active"],
                        created_at=session_data["created_at"]
                    ))
            return {
                "sessions": sessions,
                "total_active": len(sessions),
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Human Approval Endpoints
@app.post("/approval/request")
async def create_approval_request(request: ApprovalRequest):
    """Create a new human approval request for a dangerous database operation"""
    try:
        result = simple_approval_manager.create_approval_request(
            sql_query=request.sql_query
        )
        return ApprovalResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/approval/{approval_id}")
async def get_approval_status(approval_id: str):
    """Get the status of a specific approval request"""
    try:
        result = simple_approval_manager.get_approval_status(approval_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approval/{approval_id}/approve")
async def approve_operation(
    approval_id: str,
    approved_by: str = Query("user", description="Name of approver")
):
    """Approve a pending database operation"""
    try:
        result = simple_approval_manager.approve_operation(approval_id, approved_by)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Approval failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approval/{approval_id}/deny")
async def deny_operation(
    approval_id: str,
    denied_by: str = Query("user", description="Name of denier")
):
    """Deny a pending database operation"""
    try:
        result = simple_approval_manager.deny_operation(approval_id, denied_by)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Denial failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/approval/pending")
async def get_pending_approvals():
    """Get all pending approval requests"""
    try:
        result = simple_approval_manager.get_pending_approvals()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approval/cleanup")
async def cleanup_expired_approvals():
    """Clean up expired approval requests"""
    try:
        cleaned_count = simple_approval_manager.cleanup_expired_approvals()
        return {
            "message": f"Cleaned up {cleaned_count} expired approvals",
            "cleaned_count": cleaned_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
