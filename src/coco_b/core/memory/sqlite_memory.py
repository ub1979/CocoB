# =============================================================================
'''
    File Name : sqlite_memory.py

    Description : SQLite FTS5 memory engine for coco B. Replaces ChromaDB with
                  a zero-dependency, instant-startup memory system using SQLite
                  full-text search. Stores user facts and conversation summaries.

    Created on 2026-02-17

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

import sqlite3
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# Fact extraction patterns: (regex, template)
# =============================================================================
FACT_PATTERNS = [
    (re.compile(r"\bmy name is (\w+(?:\s(?!and\b|but\b|so\b|because\b|I\b)\w+)?)\b", re.IGNORECASE), "User's name is {0}", "info"),
    (re.compile(r"\bcall me (\w+)\b", re.IGNORECASE), "User wants to be called {0}", "preference"),
    (re.compile(r"\bi (?:like|love|enjoy|prefer) ((?:\w+(?:\s(?!and\b|but\b|so\b|because\b)\w+){0,3}))", re.IGNORECASE), "User likes {0}", "preference"),
    (re.compile(r"\bi (?:hate|dislike|don'?t like) ((?:\w+(?:\s(?!and\b|but\b|so\b|because\b)\w+){0,3}))", re.IGNORECASE), "User dislikes {0}", "preference"),
    (re.compile(r"\bi am (?:a |an )?((?:\w+(?:\s(?!and\b|but\b|so\b)\w+){0,2}))\b", re.IGNORECASE), "User is {0}", "trait"),
    (re.compile(r"\bi work (?:at|for|in) ((?:\w+(?:\s(?!and\b|but\b|so\b)\w+){0,3}))", re.IGNORECASE), "User works at {0}", "info"),
    (re.compile(r"\bi live in ((?:\w+(?:\s(?!and\b|but\b|so\b)\w+){0,3}))", re.IGNORECASE), "User lives in {0}", "info"),
    (re.compile(r"\bi(?:'m| am) from ((?:\w+(?:\s(?!and\b|but\b|so\b)\w+){0,3}))", re.IGNORECASE), "User is from {0}", "info"),
    (re.compile(r"\bmy (?:fav(?:ou?rite)?|fav) (\w+) is ((?:\w+(?:\s(?!and\b|but\b|so\b)\w+){0,3}))", re.IGNORECASE), "User's favorite {0} is {1}", "preference"),
    (re.compile(r"\bi speak (\w+(?:\s+and\s+\w+)*)", re.IGNORECASE), "User speaks {0}", "info"),
    (re.compile(r"\bi(?:'m| am) learning ((?:\w+(?:\s(?!and\b|but\b|so\b)\w+){0,3}))", re.IGNORECASE), "User is learning {0}", "info"),
    (re.compile(r"\bi(?:'m| am) (\d+)\s*(?:years? old|yo)\b", re.IGNORECASE), "User is {0} years old", "info"),
]


# =============================================================================
'''
    SQLiteMemory : Zero-dependency memory using SQLite FTS5
'''
# =============================================================================
class SQLiteMemory:
    """SQLite FTS5 memory engine — instant startup, zero dependencies."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            from coco_b import PROJECT_ROOT
            db_path = str(PROJECT_ROOT / "data" / "memory.db")

        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        # Delete empty/corrupt db file so it recreates cleanly
        if db_file.exists() and db_file.stat().st_size == 0:
            db_file.unlink()
            logger.info("Removed empty memory.db, will recreate")

        self._db_path = db_path
        self._init_db()
        self._verify_db()

    # =========================================================================
    # Database initialization
    # =========================================================================
    def _init_db(self):
        """Create tables and FTS5 virtual tables if they don't exist."""
        conn = self._connect()
        try:
            # ==================================
            # Enable WAL mode for better concurrency
            # WAL (Write-Ahead Logging) allows readers to not block writers
            # and improves performance under concurrent access
            # ==================================
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")  # Balance safety and speed
            conn.execute("PRAGMA temp_store=MEMORY")   # Store temp tables in memory
            
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    category TEXT DEFAULT 'info',
                    source_session TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT,
                    session_key TEXT,
                    user_message TEXT,
                    assistant_response TEXT,
                    summary TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
                    fact, category, user_id, content=facts, content_rowid=id
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                    user_message, assistant_response, summary, user_id,
                    content=conversations, content_rowid=id
                );
            """)

            # Create triggers to keep FTS in sync
            for trigger_sql in [
                """CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
                    INSERT INTO facts_fts(rowid, fact, category, user_id)
                    VALUES (new.id, new.fact, new.category, new.user_id);
                END;""",
                """CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
                    INSERT INTO facts_fts(facts_fts, rowid, fact, category, user_id)
                    VALUES ('delete', old.id, old.fact, old.category, old.user_id);
                END;""",
                """CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
                    INSERT INTO facts_fts(facts_fts, rowid, fact, category, user_id)
                    VALUES ('delete', old.id, old.fact, old.category, old.user_id);
                    INSERT INTO facts_fts(rowid, fact, category, user_id)
                    VALUES (new.id, new.fact, new.category, new.user_id);
                END;""",
                """CREATE TRIGGER IF NOT EXISTS convos_ai AFTER INSERT ON conversations BEGIN
                    INSERT INTO conversations_fts(rowid, user_message, assistant_response, summary, user_id)
                    VALUES (new.id, new.user_message, new.assistant_response, new.summary, new.user_id);
                END;""",
                """CREATE TRIGGER IF NOT EXISTS convos_ad AFTER DELETE ON conversations BEGIN
                    INSERT INTO conversations_fts(conversations_fts, rowid, user_message, assistant_response, summary, user_id)
                    VALUES ('delete', old.id, old.user_message, old.assistant_response, old.summary, old.user_id);
                END;""",
            ]:
                try:
                    conn.execute(trigger_sql)
                except sqlite3.OperationalError as e:
                    if "already exists" not in str(e):
                        logger.warning(f"Trigger creation issue: {e}")

            conn.commit()
        finally:
            conn.close()

    def _verify_db(self):
        """Confirm all required tables exist after initialization."""
        conn = self._connect()
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()}
            required = {"facts", "conversations", "facts_fts", "conversations_fts"}
            missing = required - tables
            if missing:
                logger.error(f"Memory DB missing tables: {missing}")
                raise RuntimeError(f"Memory DB initialization failed, missing: {missing}")
            logger.info(f"Memory DB verified: {len(tables)} tables at {self._db_path}")
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        """
        Create a database connection with timeout.
        
        The timeout prevents "database is locked" errors by waiting
        up to 30 seconds for locks to be released instead of failing immediately.
        """
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # Core operations
    # =========================================================================
    def add_fact(self, user_id: str, fact: str, category: str = "info",
                 source_session: str = None) -> int:
        """Store a fact about a user. Deduplicates by checking existing facts."""
        conn = self._connect()
        try:
            # Check for duplicate/similar fact
            existing = conn.execute(
                "SELECT id FROM facts WHERE user_id = ? AND fact = ?",
                (user_id, fact)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE facts SET updated_at = datetime('now') WHERE id = ?",
                    (existing["id"],)
                )
                conn.commit()
                return existing["id"]

            cursor = conn.execute(
                "INSERT INTO facts (user_id, fact, category, source_session) VALUES (?, ?, ?, ?)",
                (user_id, fact, category, source_session)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_conversation(self, user_id: str, channel: str, session_key: str,
                         user_msg: str, assistant_msg: str) -> int:
        """Store a conversation turn with auto-generated summary."""
        summary = self._make_summary(user_msg, assistant_msg)
        conn = self._connect()
        try:
            cursor = conn.execute(
                """INSERT INTO conversations
                   (user_id, channel, session_key, user_message, assistant_response, summary)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, channel, session_key, user_msg, assistant_msg, summary)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def search(self, query: str, user_id: str = None, limit: int = 5) -> List[Dict]:
        """Search both facts and conversations via FTS5."""
        results = []
        fts_query = self._to_fts_query(query)
        if not fts_query:
            return results

        conn = self._connect()
        try:
            # Search facts
            fact_filter = "AND f.user_id = ?" if user_id else ""
            params = [fts_query] + ([user_id] if user_id else [])

            rows = conn.execute(f"""
                SELECT f.fact, f.category, f.user_id, f.created_at
                FROM facts_fts
                JOIN facts f ON facts_fts.rowid = f.id
                WHERE facts_fts MATCH ? {fact_filter}
                ORDER BY facts_fts.rank
                LIMIT ?
            """, params + [limit]).fetchall()

            for row in rows:
                results.append({
                    "type": "fact",
                    "content": row["fact"],
                    "category": row["category"],
                    "user_id": row["user_id"],
                    "created_at": row["created_at"],
                })

            # Search conversations
            convo_filter = "AND c.user_id = ?" if user_id else ""
            rows = conn.execute(f"""
                SELECT c.user_message, c.assistant_response, c.summary,
                       c.user_id, c.channel, c.created_at
                FROM conversations_fts
                JOIN conversations c ON conversations_fts.rowid = c.id
                WHERE conversations_fts MATCH ? {convo_filter}
                ORDER BY conversations_fts.rank
                LIMIT ?
            """, params + [limit]).fetchall()

            for row in rows:
                results.append({
                    "type": "conversation",
                    "summary": row["summary"],
                    "user_message": row["user_message"],
                    "user_id": row["user_id"],
                    "channel": row["channel"],
                    "created_at": row["created_at"],
                })
        finally:
            conn.close()

        return results

    def get_user_facts(self, user_id: str) -> List[Dict]:
        """Get all known facts about a user."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT fact, category, created_at, updated_at FROM facts WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_relevant_context(self, query: str, user_id: str, max_chars: int = 1500) -> str:
        """Build a formatted context string for the LLM system prompt.
        Capped to ~500 tokens (~1500 chars) to avoid prompt bloat."""
        parts = []
        char_budget = max_chars

        # Get user facts (prioritize these)
        facts = self.get_user_facts(user_id)
        if facts:
            fact_lines = []
            for f in facts[:10]:
                line = f"- {f['fact']}"
                if sum(len(l) for l in fact_lines) + len(line) > char_budget * 0.6:
                    break
                fact_lines.append(line)
            if fact_lines:
                block = "**What I know about this user:**\n" + "\n".join(fact_lines)
                parts.append(block)
                char_budget -= len(block)

        # Search for relevant past conversations
        if char_budget > 200:
            search_results = self.search(query, user_id=user_id, limit=3)
            convos = [r for r in search_results if r["type"] == "conversation"]
            if convos:
                convo_lines = []
                for c in convos:
                    line = f"- {c['summary']}"
                    if sum(len(l) for l in convo_lines) + len(line) > char_budget:
                        break
                    convo_lines.append(line)
                if convo_lines:
                    parts.append("**Relevant past conversations:**\n" + "\n".join(convo_lines))

        if not parts:
            return ""

        return "## Long-term Memory\n\n" + "\n\n".join(parts)

    # =========================================================================
    # Fact extraction
    # =========================================================================
    def extract_and_store_facts(self, user_id: str, user_message: str,
                                session_key: str = None) -> List[str]:
        """Extract facts from a user message and store them. Returns list of extracted facts."""
        extracted = []
        for pattern, template, category in FACT_PATTERNS:
            match = pattern.search(user_message)
            if match:
                groups = match.groups()
                fact = template.format(*groups).strip()
                # Clean up trailing whitespace/punctuation
                fact = fact.rstrip(" ,;")
                if len(fact) > 5:
                    self.add_fact(user_id, fact, category, session_key)
                    extracted.append(fact)
        return extracted

    def extract_facts_via_llm(self, user_id: str, user_message: str,
                              assistant_message: str, llm_provider,
                              session_key: str = None) -> List[str]:
        """Use the LLM to extract facts from the conversation turn.
        Called as an optional second-pass after regex extraction.
        Non-blocking — caller should wrap in try/except."""
        prompt = (
            "Extract personal facts about the user from this conversation turn. "
            "Return ONLY a JSON list of short fact strings, or [] if none found.\n"
            "Examples: [\"User's name is John\", \"User likes hiking\", \"User works at Google\"]\n\n"
            f"User: {user_message[:500]}\n"
            f"Assistant: {assistant_message[:500]}\n\n"
            "Facts (JSON list):"
        )
        try:
            response = llm_provider.chat([
                {"role": "system", "content": "You extract personal facts. Reply ONLY with a JSON list."},
                {"role": "user", "content": prompt},
            ])
            # Parse the JSON list from response
            import json
            # Find JSON array in response
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if not match:
                return []
            facts = json.loads(match.group())
            stored = []
            for fact in facts:
                if isinstance(fact, str) and 5 < len(fact) < 200:
                    self.add_fact(user_id, fact, "llm_extracted", session_key)
                    stored.append(fact)
            return stored
        except Exception as e:
            logger.debug(f"LLM fact extraction failed: {e}")
            return []

    # =========================================================================
    # Delete operations
    # =========================================================================
    def delete_user_facts(self, user_id: str) -> int:
        """Delete all facts for a user. Returns count of deleted facts."""
        conn = self._connect()
        try:
            cursor = conn.execute("DELETE FROM facts WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def delete_facts_matching(self, user_id: str, keyword: str) -> int:
        """Delete facts matching a keyword for a user. Returns count deleted."""
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM facts WHERE user_id = ? AND fact LIKE ?",
                (user_id, f"%{keyword}%")
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # =========================================================================
    # Utilities
    # =========================================================================
    def _make_summary(self, user_msg: str, assistant_msg: str) -> str:
        """Create a short summary of a conversation turn."""
        user_short = user_msg[:100].strip()
        assistant_short = assistant_msg[:100].strip()
        if len(user_msg) > 100:
            user_short += "..."
        if len(assistant_msg) > 100:
            assistant_short += "..."
        return f"User asked: {user_short} | Bot replied: {assistant_short}"

    def _to_fts_query(self, query: str) -> str:
        """Convert a natural language query to FTS5 query syntax."""
        # Remove special FTS characters, keep words
        words = re.findall(r'\w+', query.lower())
        if not words:
            return ""
        # Use OR for broader matching
        return " OR ".join(words)

    def get_stats(self) -> Dict:
        """Get memory statistics."""
        conn = self._connect()
        try:
            fact_count = conn.execute("SELECT COUNT(*) as c FROM facts").fetchone()["c"]
            convo_count = conn.execute("SELECT COUNT(*) as c FROM conversations").fetchone()["c"]
            user_count = conn.execute("SELECT COUNT(DISTINCT user_id) as c FROM facts").fetchone()["c"]
            return {
                "facts": fact_count,
                "conversations": convo_count,
                "users": user_count,
                "db_path": self._db_path,
            }
        finally:
            conn.close()


# =============================================================================
'''
    End of File : sqlite_memory.py
'''
# =============================================================================
