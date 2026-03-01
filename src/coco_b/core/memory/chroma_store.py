# =============================================================================
'''
    File Name : chroma_store.py

    Description : ChromaDB-based memory store for long-term semantic search.
                  Stores conversation chunks and retrieves relevant memories
                  based on semantic similarity. Works alongside JSONL storage.

    Architecture:
        JSONL (sessions.py) = Full transcript, source of truth
        ChromaDB (this file) = Semantic search index for fast retrieval

    Modifying it on 2026-02-08

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("Warning: chromadb not installed. Run: pip install chromadb")


# =============================================================================
'''
    MemoryStore : Long-term memory storage using ChromaDB

    Stores conversation chunks for semantic search across years of data.
    Each memory entry contains:
    - content: The actual text (user message + assistant response)
    - metadata: timestamp, session_id, user_id, channel
'''
# =============================================================================
class MemoryStore:
    """
    Long-term memory storage using ChromaDB for semantic search.

    Features:
    - Automatic embedding using ChromaDB's default model
    - Persistent storage to disk
    - Fast semantic search across years of conversations
    - Metadata filtering (by user, channel, date)
    """

    # =========================================================================
    # =========================================================================
    # Function __init__ -> Optional[str], Optional[str] to None
    # =========================================================================
    # =========================================================================
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "conversations"
    ):
        """
        Initialize the memory store.

        Args:
            persist_dir: Directory to persist ChromaDB data
            collection_name: Name of the collection to use
        """
        if not CHROMADB_AVAILABLE:
            self.client = None
            self.collection = None
            print("MemoryStore disabled: chromadb not installed")
            return

        # ==================================
        # Set default persist directory
        # ==================================
        if persist_dir is None:
            from coco_b import PROJECT_ROOT
            persist_dir = str(PROJECT_ROOT / "data" / "memory_db")

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # ==================================
        # Initialize ChromaDB client with persistence
        # ==================================
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # ==================================
        # Get or create collection
        # ==================================
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "mr_bot conversation memories"}
        )

        print(f"MemoryStore initialized: {self.collection.count()} memories")

    # =========================================================================
    # =========================================================================
    # Function is_available -> None to bool
    # =========================================================================
    # =========================================================================
    def is_available(self) -> bool:
        """Check if memory store is available."""
        return self.client is not None and self.collection is not None

    # =========================================================================
    # =========================================================================
    # Function _generate_id -> str to str
    # =========================================================================
    # =========================================================================
    def _generate_id(self, content: str, timestamp: str) -> str:
        """Generate a unique ID for a memory entry."""
        hash_input = f"{content}{timestamp}".encode()
        return hashlib.sha256(hash_input).hexdigest()[:16]

    # =========================================================================
    # =========================================================================
    # Function add_memory -> str, Dict[str, Any] to Optional[str]
    # =========================================================================
    # =========================================================================
    def add_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Add a memory entry to the store.

        Args:
            content: The text content to store (e.g., "User asked about pizza, I explained toppings")
            metadata: Additional metadata (user_id, session_id, channel, etc.)

        Returns:
            Memory ID if successful, None otherwise
        """
        if not self.is_available():
            return None

        # ==================================
        # Prepare metadata
        # ==================================
        meta = metadata or {}
        timestamp = meta.get("timestamp", datetime.now().isoformat())
        meta["timestamp"] = timestamp

        # ==================================
        # Generate unique ID
        # ==================================
        memory_id = self._generate_id(content, timestamp)

        # ==================================
        # Add to ChromaDB
        # ==================================
        try:
            self.collection.add(
                documents=[content],
                metadatas=[meta],
                ids=[memory_id]
            )
            return memory_id
        except Exception as e:
            print(f"Error adding memory: {e}")
            return None

    # =========================================================================
    # =========================================================================
    # Function add_conversation_turn -> str, str, Dict[str, Any] to Optional[str]
    # =========================================================================
    # =========================================================================
    def add_conversation_turn(
        self,
        user_message: str,
        assistant_response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Add a conversation turn (user + assistant) as a single memory.

        This creates a searchable memory entry combining both sides
        of the conversation for better context retrieval.

        Args:
            user_message: What the user said
            assistant_response: What the assistant replied
            metadata: Additional metadata

        Returns:
            Memory ID if successful
        """
        # ==================================
        # Combine into a single memory entry
        # ==================================
        content = f"User: {user_message}\nAssistant: {assistant_response}"

        # ==================================
        # Add summary tag for easier filtering
        # ==================================
        meta = metadata or {}
        meta["type"] = "conversation_turn"

        return self.add_memory(content, meta)

    # =========================================================================
    # =========================================================================
    # Function search -> str, int, Optional[Dict] to List[Dict]
    # =========================================================================
    # =========================================================================
    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search for relevant memories.

        Args:
            query: Search query (semantic search)
            n_results: Maximum number of results
            where: Optional metadata filter (e.g., {"user_id": "user-001"})

        Returns:
            List of memory entries with content and metadata
        """
        if not self.is_available():
            return []

        try:
            # ==================================
            # Query ChromaDB
            # ==================================
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where
            )

            # ==================================
            # Format results
            # ==================================
            memories = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    memory = {
                        "content": doc,
                        "id": results["ids"][0][i] if results["ids"] else None,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results.get("distances") else None
                    }
                    memories.append(memory)

            return memories

        except Exception as e:
            print(f"Error searching memories: {e}")
            return []

    # =========================================================================
    # =========================================================================
    # Function get_relevant_context -> str, str, int to str
    # =========================================================================
    # =========================================================================
    def get_relevant_context(
        self,
        query: str,
        user_id: Optional[str] = None,
        n_results: int = 5
    ) -> str:
        """
        Get relevant memories formatted as context for the LLM.

        Args:
            query: Current user message to find relevant context for
            user_id: Optional user ID to filter memories
            n_results: Number of memories to retrieve

        Returns:
            Formatted string of relevant memories for LLM context
        """
        # ==================================
        # Build filter
        # ==================================
        where = {"user_id": user_id} if user_id else None

        # ==================================
        # Search for relevant memories
        # ==================================
        memories = self.search(query, n_results=n_results, where=where)

        if not memories:
            return ""

        # ==================================
        # Format as concise context string (truncate aggressively)
        # ==================================
        context_parts = []

        for mem in memories:
            content = mem['content']
            # Truncate to 100 chars for speed
            if len(content) > 100:
                content = content[:100] + "..."
            context_parts.append(f"[Memory] {content}")

        return "\n".join(context_parts)

    # =========================================================================
    # =========================================================================
    # Function count -> None to int
    # =========================================================================
    # =========================================================================
    def count(self) -> int:
        """Get total number of memories stored."""
        if not self.is_available():
            return 0
        return self.collection.count()

    # =========================================================================
    # =========================================================================
    # Function clear -> None to bool
    # =========================================================================
    # =========================================================================
    def clear(self) -> bool:
        """Clear all memories. Use with caution!"""
        if not self.is_available():
            return False

        try:
            # ==================================
            # Delete and recreate collection
            # ==================================
            self.client.delete_collection(self.collection.name)
            self.collection = self.client.get_or_create_collection(
                name="conversations",
                metadata={"description": "mr_bot conversation memories"}
            )
            print("Memory store cleared")
            return True
        except Exception as e:
            print(f"Error clearing memories: {e}")
            return False

    # =========================================================================
    # =========================================================================
    # Function get_stats -> None to Dict
    # =========================================================================
    # =========================================================================
    def get_stats(self) -> Dict:
        """Get memory store statistics."""
        return {
            "available": self.is_available(),
            "count": self.count(),
            "persist_dir": str(self.persist_dir) if hasattr(self, 'persist_dir') else None
        }


# =============================================================================
# Standalone Test
# =============================================================================
if __name__ == "__main__":
    print("Testing MemoryStore...")

    store = MemoryStore()

    if store.is_available():
        # Add some test memories
        store.add_conversation_turn(
            user_message="What's my favorite food?",
            assistant_response="Based on our conversations, you love pizza, especially with pepperoni!",
            metadata={"user_id": "test-user", "channel": "test"}
        )

        store.add_conversation_turn(
            user_message="Tell me about Python",
            assistant_response="Python is a great programming language. You mentioned you're learning it.",
            metadata={"user_id": "test-user", "channel": "test"}
        )

        # Search
        print("\nSearching for 'food preferences'...")
        results = store.search("food preferences", n_results=3)
        for r in results:
            print(f"  - {r['content'][:100]}...")

        print(f"\nTotal memories: {store.count()}")
        print(f"Stats: {store.get_stats()}")
    else:
        print("MemoryStore not available")


# =============================================================================
'''
    End of File : chroma_store.py

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
