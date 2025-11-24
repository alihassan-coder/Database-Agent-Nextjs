"""
Configuration management for the Database Agent.

This module handles all configuration settings, environment variables,
and database connection setup.
"""


import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables
load_dotenv()


class DatabaseConfig:
    """Configuration class for database and AI model settings."""
    
    def __init__(self):
        """Initialize configuration with environment variables."""
        # AI Model Configuration
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY02")
        self.model_name = "openai/gpt-oss-20b:free"
        self.base_url = "https://openrouter.ai/api/v1"
        
        # Database Configuration
        self.database_url = os.getenv("DATABASE_URL")
        
        # Validate required environment variables
        self._validate_config()
    
    def _validate_config(self):
        """Validate that required environment variables are set."""
        if not self.database_url:
            raise ValueError("DATABASE_URL not found in environment variables. Please check your .env file.")
        
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY06 not found in environment variables. Please check your .env file.")
        
        # Debug: Print configuration (without exposing the full API key)
        print(f"🔧 Configuration loaded:")
        print(f"   - Database URL: {self.database_url[:50]}..." if self.database_url else "   - Database URL: Not set")
        print(f"   - API Key: {self.openrouter_api_key[:20]}..." if self.openrouter_api_key else "   - API Key: Not set")
        print(f"   - Model: {self.model_name}")
        print(f"   - Base URL: {self.base_url}")
    
    def get_llm_config(self):
        """Get LLM configuration dictionary."""
        return {
            "model": self.model_name,
            "api_key": self.openrouter_api_key,
            "base_url": self.base_url
        }
    
    def create_database_engine(self):
        """
        Create and test database engine connection.
        
        Returns:
            SQLAlchemy engine instance
            
        Raises:
            ConnectionError: If database connection fails
        """
        try:
            engine = create_engine(self.database_url, echo=False)
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {str(e)}. Please check your DATABASE_URL in .env file.")
    
    def create_session_factory(self, engine):
        """
        Create session factory for database operations.
        
        Args:
            engine: SQLAlchemy engine instance
            
        Returns:
            Session factory
        """
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)
    
    def detect_database_type(self, engine):
        """
        Detect the database type from the connection URL.
        
        Args:
            engine: SQLAlchemy engine instance
            
        Returns:
            Database type ('postgresql', 'mysql', 'sqlite', etc.)
        """
        try:
            if 'postgresql' in self.database_url.lower() or 'postgres' in self.database_url.lower():
                return 'postgresql'
            elif 'mysql' in self.database_url.lower():
                return 'mysql'
            elif 'sqlite' in self.database_url.lower():
                return 'sqlite'
            else:
                # Try to detect from the driver
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT version()"))
                    version = result.fetchone()[0].lower()
                    if 'postgresql' in version:
                        return 'postgresql'
                    elif 'mysql' in version:
                        return 'mysql'
                    else:
                        return 'unknown'
        except Exception:
            return 'unknown'


class AgentConfig:
    """Configuration for agent behavior and settings."""
    
    # Response settings
    MAX_RESPONSE_LENGTH = 50  # words
    MAX_TABLE_ROWS_DISPLAY = 10
    
    # Safety settings
    DANGEROUS_OPERATIONS = ['DROP', 'DELETE', 'ALTER', 'TRUNCATE']
    REQUIRE_HUMAN_APPROVAL = True
    
    # Database operation settings
    AUTO_COMMIT = True
    ECHO_SQL = False
    
    # Thread management
    DEFAULT_THREAD_TIMEOUT = 3600  # 1 hour in seconds
    
    @classmethod
    def get_safety_settings(cls):
        """Get safety configuration settings."""
        return {
            "dangerous_operations": cls.DANGEROUS_OPERATIONS,
            "require_human_approval": cls.REQUIRE_HUMAN_APPROVAL,
            "auto_commit": cls.AUTO_COMMIT
        }
    
    @classmethod
    def get_display_settings(cls):
        """Get display configuration settings."""
        return {
            "max_response_length": cls.MAX_RESPONSE_LENGTH,
            "max_table_rows": cls.MAX_TABLE_ROWS_DISPLAY,
            "echo_sql": cls.ECHO_SQL
        }
