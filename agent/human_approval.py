"""
Human Approval System for Database Operations

This module handles human approval for dangerous database operations
in a web-based environment, replacing console-based input with
proper API endpoints and state management.
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ApprovalStatus(Enum):
    """Approval status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class HumanApprovalManager:
    """
    Manages human approval for dangerous database operations.
    
    This class handles approval requests, tracks their status,
    and provides a web-compatible interface for human approval.
    """
    
    def __init__(self):
        """Initialize the approval manager with empty storage."""
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        self.approval_timeout = 300  # 5 minutes timeout
    
    def create_approval_request(self, sql_query: str, operation_type: str, 
                               table_name: Optional[str] = None, 
                               description: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new approval request for a dangerous database operation.
        
        Args:
            sql_query: The SQL query that needs approval
            operation_type: Type of operation (DROP, DELETE, ALTER, etc.)
            table_name: Name of the table being affected (optional)
            description: Human-readable description of the operation
            
        Returns:
            Dictionary containing approval request details
        """
        approval_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        approval_request = {
            "id": approval_id,
            "sql_query": sql_query,
            "operation_type": operation_type,
            "table_name": table_name,
            "description": description or f"{operation_type} operation on database",
            "status": ApprovalStatus.PENDING.value,
            "created_at": timestamp.isoformat(),
            "expires_at": datetime.fromtimestamp(timestamp.timestamp() + self.approval_timeout).isoformat(),
            "approved_at": None,
            "denied_at": None,
            "approved_by": None
        }
        
        self.pending_approvals[approval_id] = approval_request
        
        return {
            "approval_id": approval_id,
            "requires_approval": True,
            "approval_request": approval_request
        }
    
    def get_approval_status(self, approval_id: str) -> Dict[str, Any]:
        """
        Get the current status of an approval request.
        
        Args:
            approval_id: ID of the approval request
            
        Returns:
            Dictionary containing approval status and details
        """
        if approval_id not in self.pending_approvals:
            return {
                "error": "Approval request not found",
                "requires_approval": False
            }
        
        approval = self.pending_approvals[approval_id]
        
        # Check if approval has expired
        if self._is_expired(approval):
            approval["status"] = ApprovalStatus.EXPIRED.value
            return {
                "approval_id": approval_id,
                "status": ApprovalStatus.EXPIRED.value,
                "requires_approval": False,
                "message": "Approval request has expired"
            }
        
        return {
            "approval_id": approval_id,
            "status": approval["status"],
            "requires_approval": approval["status"] == ApprovalStatus.PENDING.value,
            "approval_request": approval
        }
    
    def approve_operation(self, approval_id: str, approved_by: str = "user") -> Dict[str, Any]:
        """
        Approve a pending database operation.
        
        Args:
            approval_id: ID of the approval request
            approved_by: Identifier of who approved the operation
            
        Returns:
            Dictionary containing approval result
        """
        if approval_id not in self.pending_approvals:
            return {
                "success": False,
                "error": "Approval request not found"
            }
        
        approval = self.pending_approvals[approval_id]
        
        if approval["status"] != ApprovalStatus.PENDING.value:
            return {
                "success": False,
                "error": f"Approval request is not pending (current status: {approval['status']})"
            }
        
        if self._is_expired(approval):
            approval["status"] = ApprovalStatus.EXPIRED.value
            return {
                "success": False,
                "error": "Approval request has expired"
            }
        
        # Update approval status
        approval["status"] = ApprovalStatus.APPROVED.value
        approval["approved_at"] = datetime.now().isoformat()
        approval["approved_by"] = approved_by
        
        return {
            "success": True,
            "approval_id": approval_id,
            "status": ApprovalStatus.APPROVED.value,
            "sql_query": approval["sql_query"],
            "message": "Operation approved successfully"
        }
    
    def deny_operation(self, approval_id: str, denied_by: str = "user") -> Dict[str, Any]:
        """
        Deny a pending database operation.
        
        Args:
            approval_id: ID of the approval request
            denied_by: Identifier of who denied the operation
            
        Returns:
            Dictionary containing denial result
        """
        if approval_id not in self.pending_approvals:
            return {
                "success": False,
                "error": "Approval request not found"
            }
        
        approval = self.pending_approvals[approval_id]
        
        if approval["status"] != ApprovalStatus.PENDING.value:
            return {
                "success": False,
                "error": f"Approval request is not pending (current status: {approval['status']})"
            }
        
        # Update approval status
        approval["status"] = ApprovalStatus.DENIED.value
        approval["denied_at"] = datetime.now().isoformat()
        approval["approved_by"] = denied_by
        
        return {
            "success": True,
            "approval_id": approval_id,
            "status": ApprovalStatus.DENIED.value,
            "message": "Operation denied successfully"
        }
    
    def get_pending_approvals(self) -> Dict[str, Any]:
        """
        Get all pending approval requests.
        
        Returns:
            Dictionary containing list of pending approvals
        """
        pending = []
        expired_ids = []
        
        for approval_id, approval in self.pending_approvals.items():
            if self._is_expired(approval):
                approval["status"] = ApprovalStatus.EXPIRED.value
                expired_ids.append(approval_id)
            elif approval["status"] == ApprovalStatus.PENDING.value:
                pending.append(approval)
        
        # Clean up expired approvals
        for approval_id in expired_ids:
            del self.pending_approvals[approval_id]
        
        return {
            "pending_approvals": pending,
            "count": len(pending)
        }
    
    def cleanup_expired_approvals(self) -> int:
        """
        Clean up expired approval requests.
        
        Returns:
            Number of expired approvals cleaned up
        """
        expired_ids = []
        
        for approval_id, approval in self.pending_approvals.items():
            if self._is_expired(approval):
                expired_ids.append(approval_id)
        
        for approval_id in expired_ids:
            del self.pending_approvals[approval_id]
        
        return len(expired_ids)
    
    def _is_expired(self, approval: Dict[str, Any]) -> bool:
        """
        Check if an approval request has expired.
        
        Args:
            approval: Approval request dictionary
            
        Returns:
            True if expired, False otherwise
        """
        try:
            expires_at = datetime.fromisoformat(approval["expires_at"])
            return datetime.now() > expires_at
        except (ValueError, KeyError):
            return True
    
    def is_dangerous_operation(self, sql_query: str) -> bool:
        """
        Check if a SQL query represents a dangerous operation that requires approval.
        
        Args:
            sql_query: SQL query to check
            
        Returns:
            True if the operation is dangerous and requires approval
        """
        dangerous_operations = ['DROP', 'DELETE', 'ALTER', 'TRUNCATE']
        query_upper = sql_query.upper().strip()
        
        for op in dangerous_operations:
            if query_upper.startswith(op):
                return True
        
        return False
    
    def get_operation_type(self, sql_query: str) -> str:
        """
        Determine the type of operation from a SQL query.
        
        Args:
            sql_query: SQL query to analyze
            
        Returns:
            Operation type (DROP, DELETE, ALTER, etc.)
        """
        query_upper = sql_query.upper().strip()
        
        if query_upper.startswith('DROP'):
            return 'DROP'
        elif query_upper.startswith('DELETE'):
            return 'DELETE'
        elif query_upper.startswith('ALTER'):
            return 'ALTER'
        elif query_upper.startswith('TRUNCATE'):
            return 'TRUNCATE'
        else:
            return 'UNKNOWN'
    
    def extract_table_name(self, sql_query: str) -> Optional[str]:
        """
        Extract table name from a SQL query.
        
        Args:
            sql_query: SQL query to analyze
            
        Returns:
            Table name if found, None otherwise
        """
        import re
        
        # Pattern for DROP TABLE
        drop_pattern = r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)'
        match = re.search(drop_pattern, sql_query, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Pattern for DELETE FROM
        delete_pattern = r'DELETE\s+FROM\s+(\w+)'
        match = re.search(delete_pattern, sql_query, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Pattern for ALTER TABLE
        alter_pattern = r'ALTER\s+TABLE\s+(\w+)'
        match = re.search(alter_pattern, sql_query, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None


# Global instance for the application
approval_manager = HumanApprovalManager()
