# =============================================================================
'''
    File Name : __init__.py

    Description : Memory module for mr_bot. Provides long-term memory storage
                  using ChromaDB for semantic search across years of conversations.

    Modifying it on 2026-02-08

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

from .sqlite_memory import SQLiteMemory

# Legacy import — ChromaDB replaced by SQLite FTS5
try:
    from .chroma_store import MemoryStore
except ImportError:
    MemoryStore = None

__all__ = ["SQLiteMemory", "MemoryStore"]

# =============================================================================
'''
    End of File : __init__.py
'''
# =============================================================================
