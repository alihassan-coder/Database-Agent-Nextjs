"""
Database Agent Package

This package contains the LLM-driven database agent with intelligent decision making.
The agent uses LangGraph for conversation management and provides real-time database operations.
"""

from .main_agent import DatabaseAgent
from .system_prompts import SYSTEM_PROMPT, HELP_TEXT
from .config import DatabaseConfig, AgentConfig
from .tools import DatabaseTools

__version__ = "1.0.0"
__author__ = "Database Agent Team"

__all__ = [
    "DatabaseAgent",
    "DatabaseConfig", 
    "AgentConfig",
    "DatabaseTools",
    "SYSTEM_PROMPT",
    "HELP_TEXT"
]
