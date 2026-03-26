# =============================================================================
'''
    File Name : sessions.py
    
    Description : Session Manager for Persistent Memory AI Chatbot.
                  This module implements a Persistent Memory-style session 
                  architecture with two-tier storage: sessions.json (index) 
                  and JSONL files (transcripts). It provides full conversation 
                  history preservation, context window management with 
                  compaction, and session continuity across restarts.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Contact : Idrak AI Ltd - Building AI Solutions for the Community
'''
# =============================================================================

# =============================================================================
# Importing the libraries
# =============================================================================
import json
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import uuid
import logging

# =============================================================================
# Setup logging for security events
# =============================================================================
logger = logging.getLogger(__name__)
# =============================================================================

# =============================================================================
# Security Constants for Input Validation
# =============================================================================
# Valid roles for messages to prevent injection
VALID_ROLES = {"user", "assistant", "system"}

# Maximum lengths to prevent DoS via oversized inputs
MAX_SESSION_KEY_LENGTH = 512
MAX_USER_ID_LENGTH = 256
MAX_CHANNEL_LENGTH = 64
MAX_CONTENT_LENGTH = 100000  # 100KB per message
# =============================================================================


# =============================================================================
'''
    SessionManager : Manages conversation sessions with persistent JSONL storage.
                     Handles session creation, message storage, conversation 
                     history retrieval, and context compaction for long-running
                     conversations across multiple chat channels.
'''
# =============================================================================
class SessionManager:
    
    # =========================================================================
    # =========================================================================
    # Function __init__ -> str to None
    # =========================================================================
    # =========================================================================
    def __init__(self, data_dir: str = "data/sessions"):
        # ==================================
        # Initialize the data directory path
        # ==================================
        self.data_dir = Path(data_dir)
        
        # ==================================
        # Create the data directory if it doesn't exist
        # ==================================
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # ==================================
        # Define the sessions index file path
        # ==================================
        self.sessions_file = self.data_dir / "sessions.json"
        
        # ==================================
        # Load existing sessions or initialize empty dictionary
        # ==================================
        self.sessions: Dict[str, Dict] = self._load_sessions_index()

        # ==================================
        # Batched index writes: defer _save_sessions_index to reduce I/O
        # ==================================
        self._index_dirty = False
        self._last_index_save = time.time()
    
    # =========================================================================
    # =========================================================================
    # Function _load_sessions_index -> None to Dict[str, Dict]
    # =========================================================================
    # =========================================================================
    def _load_sessions_index(self) -> Dict[str, Dict]:
        # ==================================
        # Check if the sessions index file exists
        # ==================================
        if self.sessions_file.exists():
            # ==================================
            # Open and load the JSON index file
            # ==================================
            with open(self.sessions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        # ==================================
        # Return empty dictionary if no index exists
        # ==================================
        return {}
    
    # =========================================================================
    # =========================================================================
    # Function _save_sessions_index -> None to None
    # =========================================================================
    # =========================================================================
    def _save_sessions_index(self):
        """Mark index as dirty; actually write at most once per second."""
        now = time.time()
        if now - self._last_index_save >= 1.0:
            self._flush_sessions_index()
        else:
            self._index_dirty = True

    def _flush_sessions_index(self):
        """Write sessions index to disk immediately."""
        with open(self.sessions_file, 'w', encoding='utf-8') as f:
            json.dump(self.sessions, f, indent=2, ensure_ascii=False)
        self._index_dirty = False
        self._last_index_save = time.time()

    def flush(self):
        """Public method to force-write any pending index changes."""
        if self._index_dirty:
            self._flush_sessions_index()
    
    # =========================================================================
    # =========================================================================
    # Function _validate_input -> str, str, max_length to bool
    # =========================================================================
    # =========================================================================
    def _validate_input(self, value: str, field_name: str, max_length: int) -> bool:
        """
        Validate input string for security constraints
        
        Args:
            value: The input string to validate
            field_name: Name of the field for error messages
            max_length: Maximum allowed length
            
        Returns:
            bool: True if valid, False otherwise
            
        Security:
            Prevents path traversal and injection attacks by validating
            that inputs don't contain dangerous characters.
        """
        # ==================================
        # Check if value is a string
        # ==================================
        if not isinstance(value, str):
            logger.warning(f"Invalid type for {field_name}: expected str, got {type(value)}")
            return False
        
        # ==================================
        # Check for empty string
        # ==================================
        if not value:
            logger.warning(f"Empty value for {field_name}")
            return False
        
        # ==================================
        # Check maximum length to prevent DoS
        # ==================================
        if len(value) > max_length:
            logger.warning(f"{field_name} exceeds maximum length: {len(value)} > {max_length}")
            return False
        
        # ==================================
        # Check for path traversal attempts
        # ==================================
        if ".." in value or "//" in value:
            logger.warning(f"Path traversal attempt detected in {field_name}: {value}")
            return False
        
        # ==================================
        # Check for null bytes (injection attempt)
        # ==================================
        if "\x00" in value:
            logger.warning(f"Null byte detected in {field_name}")
            return False
        
        return True
    
    # =========================================================================
    # =========================================================================
    # Function get_session_key -> str, str, Optional[str] to str
    # =========================================================================
    # =========================================================================
    def get_session_key(self, channel: str, user_id: str, chat_id: Optional[str] = None) -> str:
        """
        Generate a unique session key for a conversation
        
        Security Note:
            Validates all inputs to prevent injection attacks and ensure
            the session key is safe for use in file paths.
        """
        # ==================================
        # Validate channel input
        # ==================================
        if not self._validate_input(channel, "channel", MAX_CHANNEL_LENGTH):
            raise ValueError(f"Invalid channel: {channel}")
        
        # ==================================
        # Validate user_id input
        # ==================================
        if not self._validate_input(user_id, "user_id", MAX_USER_ID_LENGTH):
            raise ValueError(f"Invalid user_id: {user_id}")
        
        # ==================================
        # Validate chat_id if provided
        # ==================================
        if chat_id is not None and not self._validate_input(chat_id, "chat_id", MAX_USER_ID_LENGTH):
            raise ValueError(f"Invalid chat_id: {chat_id}")
        
        # ==================================
        # Determine chat type based on presence of chat_id
        # ==================================
        chat_type = "group" if chat_id else "direct"
        
        # ==================================
        # Generate session key with chat_id for group chats
        # ==================================
        if chat_id:
            session_key = f"{channel}:{chat_type}:{user_id}:{chat_id}"
        # ==================================
        # Generate session key without chat_id for direct chats
        # ==================================
        else:
            session_key = f"{channel}:{chat_type}:{user_id}"
        
        # ==================================
        # Validate the generated session key length
        # ==================================
        if len(session_key) > MAX_SESSION_KEY_LENGTH:
            raise ValueError(f"Generated session key too long: {len(session_key)} > {MAX_SESSION_KEY_LENGTH}")
        
        return session_key
    
    # =========================================================================
    # =========================================================================
    # Function get_or_create_session -> str, str, str to Dict
    # =========================================================================
    # =========================================================================
    def get_or_create_session(self, session_key: str, channel: str, user_id: str) -> Dict:
        # ==================================
        # Check if session already exists in the index
        # ==================================
        if session_key in self.sessions:
            # ==================================
            # Retrieve existing session
            # ==================================
            session = self.sessions[session_key]
            # ==================================
            # Update the last modified timestamp
            # ==================================
            session['updatedAt'] = datetime.now().timestamp()
            # ==================================
            # Persist the updated index
            # ==================================
            self._save_sessions_index()
            return session
        
        # ==================================
        # Generate unique session ID with timestamp and UUID
        # ==================================
        session_id = f"sess-{datetime.now().strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}"
        
        # ==================================
        # Define the JSONL transcript file path
        # ==================================
        session_file = self.data_dir / f"{session_id}.jsonl"
        
        # ==================================
        # Create session metadata dictionary
        # ==================================
        session = {
            "sessionId": session_id,
            "sessionFile": str(session_file),
            "createdAt": datetime.now().timestamp(),
            "updatedAt": datetime.now().timestamp(),
            "channel": channel,
            "userId": user_id,
            "chatType": "group" if ":" in session_key.split(":")[-1] else "direct",
            "messageCount": 0,
            "tokenCount": 0
        }
        
        # ==================================
        # Initialize JSONL file with session header entry
        # ==================================
        self._append_to_jsonl(session_file, {
            "type": "session",
            "id": session_id,
            "timestamp": datetime.now().isoformat(),
            "channel": channel,
            "userId": user_id
        })
        
        # ==================================
        # Add new session to the index
        # ==================================
        self.sessions[session_key] = session
        # ==================================
        # Persist immediately for new sessions (important)
        # ==================================
        self._flush_sessions_index()

        return session
    
    # =========================================================================
    # =========================================================================
    # Function _append_to_jsonl -> Path, Dict to None
    # =========================================================================
    # =========================================================================
    def _append_to_jsonl(self, file_path: Path, entry: Dict):
        # ==================================
        # Open the JSONL file in append mode
        # ==================================
        with open(file_path, 'a', encoding='utf-8') as f:
            # ==================================
            # Write the JSON entry as a single line
            # ==================================
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    # =========================================================================
    # =========================================================================
    # Function add_message -> str, str, str, Optional[Dict] to str
    # =========================================================================
    # =========================================================================
    def add_message(self, session_key: str, role: str, content: str, metadata: Optional[Dict] = None) -> str:
        """
        Add a message to a conversation session
        
        Security Note:
            Validates role and content to prevent injection attacks.
            Only accepts valid roles (user, assistant, system).
            Content length is limited to prevent DoS.
        """
        # ==================================
        # Validate session_key format
        # ==================================
        if not isinstance(session_key, str) or len(session_key) > MAX_SESSION_KEY_LENGTH:
            raise ValueError(f"Invalid session_key: {session_key}")
        
        # ==================================
        # Validate role is one of allowed values
        # ==================================
        if role not in VALID_ROLES:
            logger.warning(f"Invalid role attempted: {role}")
            raise ValueError(f"Invalid role: {role}. Must be one of: {VALID_ROLES}")
        
        # ==================================
        # Validate content is a string
        # ==================================
        if not isinstance(content, str):
            raise ValueError(f"Content must be a string, got: {type(content)}")
        
        # ==================================
        # Check content length to prevent DoS
        # ==================================
        if len(content) > MAX_CONTENT_LENGTH:
            logger.warning(f"Content too long: {len(content)} > {MAX_CONTENT_LENGTH}")
            raise ValueError(f"Content exceeds maximum length of {MAX_CONTENT_LENGTH} characters")
        
        # ==================================
        # Retrieve the session from the index
        # ==================================
        session = self.sessions.get(session_key)
        
        # ==================================
        # Validate that the session exists
        # ==================================
        if not session:
            raise ValueError(f"Session not found: {session_key}")
        
        # ==================================
        # Generate unique message identifier
        # ==================================
        message_id = f"msg-{uuid.uuid4().hex[:8]}"
        
        # ==================================
        # Construct the message entry dictionary
        # ==================================
        message = {
            "type": "message",
            "id": message_id,
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        }
        
        # ==================================
        # Add optional metadata if provided
        # ==================================
        if metadata:
            message["metadata"] = metadata
        
        # ==================================
        # Get the session's JSONL file path
        # ==================================
        session_file = Path(session["sessionFile"])
        
        # ==================================
        # Append the message to the transcript
        # ==================================
        self._append_to_jsonl(session_file, message)
        
        # ==================================
        # Update session statistics
        # ==================================
        session["messageCount"] += 1
        session["updatedAt"] = datetime.now().timestamp()
        
        # ==================================
        # Persist the updated sessions index
        # ==================================
        self._save_sessions_index()
        
        return message_id
    
    # =========================================================================
    # =========================================================================
    # Function get_conversation_history -> str, Optional[int] to List[Dict]
    # =========================================================================
    # =========================================================================
    def get_conversation_history(self, session_key: str, max_messages: Optional[int] = None) -> List[Dict]:
        # ==================================
        # Retrieve the session from the index
        # ==================================
        session = self.sessions.get(session_key)

        # ==================================
        # Return empty list if session not found
        # ==================================
        if not session:
            return []

        # ==================================
        # Get the session's JSONL file path
        # ==================================
        session_file = Path(session["sessionFile"])

        # ==================================
        # Return empty list if transcript file doesn't exist
        # ==================================
        if not session_file.exists():
            return []

        # ==================================
        # Fast path: read only tail of file when max_messages is set
        # Reads backwards to find enough lines, avoiding full file parse
        # ==================================
        if max_messages:
            lines = self._read_tail_lines(session_file, max_messages * 3 + 5)
        else:
            with open(session_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

        # ==================================
        # Parse lines into messages
        # ==================================
        messages = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") == "message":
                msg = {
                    "role": entry["role"],
                    "content": entry["content"],
                }
                # Propagate attachment references if present in metadata
                metadata = entry.get("metadata") or {}
                if metadata.get("attachments"):
                    msg["_attachments"] = metadata["attachments"]
                messages.append(msg)
            elif entry.get("type") == "compaction":
                messages = [{
                    "role": "system",
                    "content": f"[Previous conversation summary]\n{entry['summary']}"
                }]

        # ==================================
        # Limit to most recent messages if max_messages specified
        # ==================================
        if max_messages and len(messages) > max_messages:
            return messages[-max_messages:]

        return messages

    def _read_tail_lines(self, file_path: Path, num_lines: int) -> List[str]:
        """Read approximately the last N lines from a file efficiently."""
        try:
            file_size = file_path.stat().st_size
            if file_size == 0:
                return []
            # Estimate ~200 bytes per line, read enough from the end
            chunk_size = min(file_size, num_lines * 200)
            with open(file_path, 'rb') as f:
                f.seek(max(0, file_size - chunk_size))
                if f.tell() > 0:
                    f.readline()  # Skip partial first line
                data = f.read().decode('utf-8', errors='replace')
            lines = data.splitlines()
            return lines[-num_lines:] if len(lines) > num_lines else lines
        except Exception:
            # Fallback to full read
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.readlines()
    
    # =========================================================================
    # =========================================================================
    # Function add_compaction -> str, str, int to None
    # =========================================================================
    # =========================================================================
    def add_compaction(self, session_key: str, summary: str, tokens_before: int):
        # ==================================
        # Retrieve the session from the index
        # ==================================
        session = self.sessions.get(session_key)
        
        # ==================================
        # Validate that the session exists
        # ==================================
        if not session:
            raise ValueError(f"Session not found: {session_key}")
        
        # ==================================
        # Construct the compaction entry dictionary
        # ==================================
        compaction = {
            "type": "compaction",
            "id": f"comp-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "tokensBefore": tokens_before,
            "tokensAfter": len(summary.split())  # Rough estimate
        }
        
        # ==================================
        # Get the session's JSONL file path
        # ==================================
        session_file = Path(session["sessionFile"])
        
        # ==================================
        # Append the compaction entry to the transcript
        # ==================================
        self._append_to_jsonl(session_file, compaction)
        
        # ==================================
        # Update the session's last modified timestamp
        # ==================================
        session["updatedAt"] = datetime.now().timestamp()
        
        # ==================================
        # Persist the updated sessions index
        # ==================================
        self._save_sessions_index()
    
    # =========================================================================
    # =========================================================================
    # Function reset_session -> str to None
    # =========================================================================
    # =========================================================================
    def reset_session(self, session_key: str):
        # ==================================
        # Check if the session exists in the index
        # ==================================
        if session_key in self.sessions:
            # ==================================
            # Remove the session entry from the index
            # ==================================
            del self.sessions[session_key]
            # ==================================
            # Persist immediately for session deletion (important)
            # ==================================
            self._flush_sessions_index()
    
    # =========================================================================
    # =========================================================================
    # Function list_sessions -> None to List[Dict]
    # =========================================================================
    # =========================================================================
    def list_sessions(self) -> List[Dict]:
        # ==================================
        # Return list of all sessions with their keys
        # ==================================
        return [
            {
                "key": key,
                **session
            }
            for key, session in self.sessions.items()
        ]
    
    # =========================================================================
    # =========================================================================
    # Function get_session_stats -> str to Optional[Dict]
    # =========================================================================
    # =========================================================================
    def get_session_stats(self, session_key: str) -> Optional[Dict]:
        # ==================================
        # Return the session metadata or None if not found
        # ==================================
        return self.sessions.get(session_key)


# =============================================================================
# =========================================================================
# Example Usage and Testing
# =========================================================================
# =============================================================================
# ==================================
# Run example usage when script is executed directly
# ==================================
if __name__ == "__main__":
    # ==================================
    # Initialize the session manager
    # ==================================
    sm = SessionManager()
    
    # ==================================
    # Create/get session for MS Teams user
    # ==================================
    session_key = sm.get_session_key("msteams", "user-123")
    session = sm.get_or_create_session(session_key, "msteams", "user-123")
    print(f"Session created: {session['sessionId']}")
    
    # ==================================
    # Add sample messages to the session
    # ==================================
    sm.add_message(session_key, "user", "Hello, how are you?")
    sm.add_message(session_key, "assistant", "I'm doing great! How can I help you today?")
    sm.add_message(session_key, "user", "What's the weather like?")
    sm.add_message(session_key, "assistant", "I don't have real-time weather data, but I can help you find it!")
    
    # ==================================
    # Retrieve and display conversation history
    # ==================================
    history = sm.get_conversation_history(session_key)
    print("\nConversation history:")
    for msg in history:
        print(f"{msg['role']}: {msg['content']}")
    
    # ==================================
    # Display session statistics
    # ==================================
    stats = sm.get_session_stats(session_key)
    print(f"\nSession stats: {stats['messageCount']} messages")


# =============================================================================
'''
    End of File - sessions.py
    
    Part of SkillForge - Persistent Memory AI Chatbot
    
    Idrak AI Ltd - Building AI Solutions for the Community
    Making AI Useful for Everyone
    
    Open Source - Safe Open Community Project
'''
# =============================================================================
