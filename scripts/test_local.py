# =============================================================================
'''
    File Name : test_local.py
    
    Description : Test script to see the session manager in action.
                  No MS Teams credentials needed! This script tests the
                  conversation handling, memory persistence, and command
                  processing capabilities of the mr_bot system.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import sys
from coco_b import PROJECT_ROOT
sys.path.insert(0, str(PROJECT_ROOT))

from coco_b.core.sessions import SessionManager
from coco_b.core.llm import LLMProviderFactory
from coco_b.core.router import MessageRouter
import asyncio
import config


# =========================================================================
# =========================================================================
# Function test_conversations -> None to None
# =========================================================================
# =========================================================================
async def test_conversations():
    """Main test function for conversation handling and memory persistence"""
    print("Testing Session Manager (coco B-style)\n")
    print("=" * 60)

    # ==================================
    # Initialize components with new LLM framework
    session_manager = SessionManager("data/sessions")

    # ==================================
    # Create LLM provider from config
    llm_config = config.LLM_PROVIDERS[config.LLM_PROVIDER]
    llm_provider = LLMProviderFactory.from_dict(llm_config)

    # ==================================
    # Display configuration information
    print(f"\nProvider: {llm_provider.provider_name}")
    print(f"Model: {llm_provider.model_name}")
    print(f"Endpoint: {llm_provider.config.base_url}")
    print("=" * 60)

    # ==================================
    # Initialize message router with session and LLM
    router = MessageRouter(session_manager, llm_provider)

    # ==================================
    # Simulate Alice's first conversation
    print("\nConversation 1: Alice sends first message")
    print("-" * 60)
    response1 = await router.handle_message(
        channel="test",
        user_id="alice-123",
        user_message="Hello! My name is Alice and I like pizza.",
        user_name="Alice"
    )
    print(f"Bot: {response1}\n")

    # ==================================
    # Alice continues conversation - test memory
    print("Conversation 1: Alice sends second message")
    print("-" * 60)
    response2 = await router.handle_message(
        channel="test",
        user_id="alice-123",
        user_message="What did I just tell you I like?",
        user_name="Alice"
    )
    print(f"Bot: {response2}\n")

    # ==================================
    # Bob's separate conversation - test isolation
    print("Conversation 2: Bob sends message (different user)")
    print("-" * 60)
    response3 = await router.handle_message(
        channel="test",
        user_id="bob-456",
        user_message="Hi, what's your name?",
        user_name="Bob"
    )
    print(f"Bot: {response3}\n")

    # ==================================
    # Check session files created during testing
    print("=" * 60)
    print("Session Files Created:")
    print("-" * 60)

    sessions = session_manager.list_sessions()
    for session in sessions:
        print(f"\nSession Key: {session['key']}")
        print(f"   Session ID: {session['sessionId']}")
        print(f"   Messages: {session['messageCount']}")
        print(f"   File: {session['sessionFile']}")

    # ==================================
    # Show that history is preserved
    print("\n" + "=" * 60)
    print("Testing Memory Persistence")
    print("-" * 60)

    alice_key = session_manager.get_session_key("test", "alice-123")
    alice_history = session_manager.get_conversation_history(alice_key)

    print(f"\nAlice's conversation history ({len(alice_history)} messages):")
    for i, msg in enumerate(alice_history, 1):
        print(f"  {i}. {msg['role']}: {msg['content'][:60]}...")

    # ==================================
    # Show commands functionality
    print("\n" + "=" * 60)
    print("Testing Commands")
    print("-" * 60)

    stats_response = router.handle_command("/stats", alice_key)
    print(f"\n{stats_response}")

    # ==================================
    # Test complete - show summary
    print("\nTest Complete!")
    print("=" * 60)
    print("\nCheck these folders:")
    print("   - data/sessions/sessions.json (session index)")
    print("   - data/sessions/sess-*.jsonl (full conversations)")
    print("\nYou can open them in a text editor to see the data!")


# =========================================================================
# =========================================================================
# Entry Point - Run test when executed directly
# =========================================================================
# =========================================================================
if __name__ == "__main__":
    asyncio.run(test_conversations())


# =============================================================================
'''
    End of File : test_local.py
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
