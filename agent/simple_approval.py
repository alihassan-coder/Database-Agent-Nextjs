"""
Simple and Performant Human Approval System

This module provides a streamlined approach to human approval for dangerous
database operations with minimal overhead and maximum performance.
"""

import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import re


class ApprovalStatus(Enum):
    """Approval status enumeration"""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class SimpleApprovalManager:
    """
    Simple and performant human approval manager for dangerous database operations.
    
    Key features:
    - Fast dangerous operation detection using regex patterns
    - In-memory storage with automatic cleanup
    - Simple API with minimal overhead
    - Built-in timeout handling
    """
    
    def __init__(self, timeout_minutes: int = 5):
        """
        Initialize the simple approval manager.
        
        Args:
            timeout_minutes: Approval timeout in minutes (default: 5)
        """
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        self.timeout_seconds = timeout_minutes * 60
        
        # Pre-compiled regex patterns for fast detection
        self.dangerous_patterns = [
            re.compile(r'^\s*DROP\s+', re.IGNORECASE),
            re.compile(r'^\s*DELETE\s+FROM\s+', re.IGNORECASE),
            re.compile(r'^\s*ALTER\s+TABLE\s+', re.IGNORECASE),
            re.compile(r'^\s*TRUNCATE\s+TABLE\s+', re.IGNORECASE),
            re.compile(r'^\s*UPDATE\s+.*\s+SET\s+.*\s+WHERE\s+1\s*=\s*1', re.IGNORECASE),  # Mass updates
        ]
        
        # Safe operations that don't need approval
        self.safe_patterns = [
            re.compile(r'^\s*SELECT\s+', re.IGNORECASE),
            re.compile(r'^\s*INSERT\s+INTO\s+', re.IGNORECASE),
            re.compile(r'^\s*CREATE\s+TABLE\s+', re.IGNORECASE),
            re.compile(r'^\s*SHOW\s+', re.IGNORECASE),
            re.compile(r'^\s*DESCRIBE\s+', re.IGNORECASE),
        ]
    
    def is_dangerous_operation(self, sql_query: str) -> bool:
        """
        Fast detection of dangerous operations using pre-compiled regex patterns.
        
        Args:
            sql_query: SQL query to check
            
        Returns:
            True if the operation is dangerous and requires approval
        """
        if not sql_query or not sql_query.strip():
            return False
        
        # Check safe patterns first (faster for common operations)
        for pattern in self.safe_patterns:
            if pattern.match(sql_query):
                return False
        
        # Check dangerous patterns
        for pattern in self.dangerous_patterns:
            if pattern.match(sql_query):
                return True
        
        return False
    
    def get_operation_info(self, sql_query: str) -> Dict[str, Any]:
        """
        Extract operation information from SQL query.
        
        Args:
            sql_query: SQL query to analyze
            
        Returns:
            Dictionary with operation details
        """
        query_upper = sql_query.upper().strip()
        
        # Determine operation type
        if query_upper.startswith('DROP'):
            operation_type = 'DROP'
        elif query_upper.startswith('DELETE'):
            operation_type = 'DELETE'
        elif query_upper.startswith('ALTER'):
            operation_type = 'ALTER'
        elif query_upper.startswith('TRUNCATE'):
            operation_type = 'TRUNCATE'
        elif query_upper.startswith('UPDATE'):
            operation_type = 'UPDATE'
        else:
            operation_type = 'UNKNOWN'
        
        # Extract table name
        table_name = self._extract_table_name(sql_query)
        
        # Generate description
        description = f"{operation_type} operation"
        if table_name:
            description += f" on table '{table_name}'"
        
        return {
            'operation_type': operation_type,
            'table_name': table_name,
            'description': description
        }
    
    def _extract_table_name(self, sql_query: str) -> Optional[str]:
        """
        Extract table name from SQL query using regex.
        
        Args:
            sql_query: SQL query to analyze
            
        Returns:
            Table name if found, None otherwise
        """
        patterns = [
            r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)',
            r'DELETE\s+FROM\s+(\w+)',
            r'ALTER\s+TABLE\s+(\w+)',
            r'TRUNCATE\s+TABLE\s+(\w+)',
            r'UPDATE\s+(\w+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sql_query, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def create_approval_request(self, sql_query: str) -> Dict[str, Any]:
        """
        Create a new approval request for a dangerous operation.
        
        Args:
            sql_query: SQL query that needs approval
            
        Returns:
            Dictionary containing approval request details
        """
        approval_id = str(uuid.uuid4())
        timestamp = datetime.now()
        expires_at = timestamp + timedelta(seconds=self.timeout_seconds)
        
        # Get operation info
        operation_info = self.get_operation_info(sql_query)
        
        approval_request = {
            "id": approval_id,
            "sql_query": sql_query,
            "operation_type": operation_info['operation_type'],
            "table_name": operation_info['table_name'],
            "description": operation_info['description'],
            "status": ApprovalStatus.PENDING.value,
            "created_at": timestamp.isoformat(),
            "expires_at": expires_at.isoformat(),
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


# Global instance for the application
simple_approval_manager = SimpleApprovalManager()
