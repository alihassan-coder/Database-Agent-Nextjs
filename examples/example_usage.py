"""
Enhanced example usage of the Database Agent with LangGraph workflow
This script demonstrates how to use the enhanced DatabaseAgent class programmatically.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.database_agent import DatabaseAgent

def enhanced_example_usage():
    """Example of how to use the Enhanced Database Agent with conversation history."""
    print("🤖 Enhanced Database Agent Example Usage")
    print("=" * 60)
    
    try:
        # Initialize the enhanced agent
        agent = DatabaseAgent()
        print("✅ Enhanced Database Agent initialized successfully!")
        print("✅ LangGraph workflow active")
        print("✅ Conversation history enabled")
        
        # Example 1: Get database structure
        print("\n📊 Getting database structure...")
        response = agent.chat("Show me the database structure")
        print(response)
        
        # Example 2: Context-aware follow-up
        print("\n🧠 Testing conversation memory...")
        response = agent.chat("Tell me more about the first table you mentioned")
        print(response)
        
        # Example 3: Query data
        print("\n🔍 Querying data...")
        response = agent.chat("SELECT * FROM todos LIMIT 5")
        print(response)
        
        # Example 4: Natural language query with context
        print("\n💬 Natural language query with context...")
        response = agent.chat("How many columns are in that table?")
        print(response)
        
        # Example 5: Show conversation history
        print("\n📚 Conversation History:")
        history = agent.get_conversation_history()
        for i, entry in enumerate(history[-6:], 1):  # Show last 6 entries
            print(f"{i}. {entry['role'].title()}: {entry['content'][:80]}...")
        
        # Example 6: Clear history and start fresh
        print("\n🧹 Clearing conversation history...")
        agent.clear_conversation_history()
        print("✅ History cleared!")
        
        # Example 7: Fresh conversation
        print("\n🆕 Fresh conversation test...")
        response = agent.chat("What can you help me with?")
        print(response)
        
        # Example 8: Get help
        print("\n❓ Getting help...")
        help_text = agent.get_help()
        print(help_text[:200] + "...")
        
        print("\n🎉 Enhanced features demonstrated successfully!")
        print("\n🚀 Key Features Shown:")
        print("   - 🧠 Conversation memory and context awareness")
        print("   - 🔄 LangGraph workflow for intelligent routing")
        print("   - 📊 Comprehensive database analysis")
        print("   - 🛡️ Advanced safety features")
        print("   - 💬 Context-aware responses")
        print("   - 📚 Conversation history management")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("Make sure your database is running and .env file is configured correctly.")
        print("Required environment variables:")
        print("- DATABASE_URL")
        print("- OPENAI_API_KEY")

if __name__ == "__main__":
    enhanced_example_usage()
