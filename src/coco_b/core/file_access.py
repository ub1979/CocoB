# =============================================================================
'''
    File Name : file_access.py

    Description : Password-protected file access manager for sandboxed file
                  operations. Restricts bot file writes to skills/ and data/user/
                  directories only, with per-action password verification.

    Created on 2026-02-21

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : coco B - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import hashlib
import hmac
import os
from pathlib import Path
from typing import Optional, Dict, Any


# =============================================================================
'''
    FileAccessManager : Manages password-protected, sandboxed file operations.

    - Password stored as PBKDF2-HMAC-SHA256 hash with random salt
    - Auth file: data/.file_access_auth (permissions 0600)
    - Sandbox: only skills/ and data/user/ are writable
    - Pending actions: stores one action awaiting password confirmation
'''
# =============================================================================
class FileAccessManager:
    """Password-protected sandboxed file access for bot operations."""

    ITERATIONS = 600_000
    SALT_BYTES = 32

    # =========================================================================
    # Function __init__ -> Optional[Path] to None
    # =========================================================================
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the file access manager.

        Args:
            project_root: Project root directory (defaults to PROJECT_ROOT)
        """
        if project_root is None:
            from coco_b import PROJECT_ROOT
            project_root = project_root or PROJECT_ROOT

        self._project_root = Path(project_root).resolve()
        self._auth_file = self._project_root / "data" / ".file_access_auth"

        # Allowed directories (resolved absolute paths)
        self._allowed_dirs = [
            self._project_root / "skills",
            self._project_root / "data" / "user",
        ]

        # Pending action awaiting password confirmation (in-memory, per session)
        self._pending_actions: Dict[str, Dict[str, Any]] = {}

    # =========================================================================
    # Password Management
    # =========================================================================

    def is_password_set(self) -> bool:
        """Check if a password has been configured."""
        return self._auth_file.exists()

    def setup_password(self, password: str) -> bool:
        """
        Set up the file access password (first-time only).

        Args:
            password: Password to set (min 8 characters)

        Returns:
            True if password was set successfully
        """
        if self.is_password_set():
            return False

        if len(password) < 8:
            return False

        salt = os.urandom(self.SALT_BYTES)
        pw_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, self.ITERATIONS
        )

        # Ensure data directory exists
        self._auth_file.parent.mkdir(parents=True, exist_ok=True)

        # Write salt:hash in hex format
        self._auth_file.write_text(
            f"{salt.hex()}:{pw_hash.hex()}", encoding="utf-8"
        )

        # Restrict file permissions (owner read/write only)
        try:
            os.chmod(self._auth_file, 0o600)
        except OSError:
            pass  # Windows doesn't support Unix permissions

        return True

    def verify_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.

        Args:
            password: Password to verify

        Returns:
            True if password matches
        """
        if not self.is_password_set():
            return False

        try:
            content = self._auth_file.read_text(encoding="utf-8").strip()
            salt_hex, hash_hex = content.split(":", 1)
            salt = bytes.fromhex(salt_hex)
            stored_hash = bytes.fromhex(hash_hex)
        except (ValueError, OSError):
            return False

        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, self.ITERATIONS
        )
        
        # ==================================
        # Security: Use constant-time comparison to prevent timing attacks
        # hmac.compare_digest takes constant time regardless of match position,
        # preventing attackers from guessing the password byte-by-byte
        # ==================================
        return hmac.compare_digest(computed, stored_hash)

    # =========================================================================
    # Sandbox Enforcement
    # =========================================================================

    def is_path_allowed(self, path: str) -> bool:
        """
        Check if a path is inside the allowed sandbox directories.

        Resolves symlinks and prevents directory traversal attacks.

        Args:
            path: File path to check

        Returns:
            True if path is within skills/ or data/user/
        """
        try:
            resolved = Path(path).resolve()
        except (ValueError, OSError):
            return False

        for allowed_dir in self._allowed_dirs:
            allowed_resolved = allowed_dir.resolve()
            try:
                resolved.relative_to(allowed_resolved)
                return True
            except ValueError:
                continue

        return False

    # =========================================================================
    # Sandboxed File Operations
    # =========================================================================

    def write_file(self, path: str, content: str) -> bool:
        """
        Write a file within the sandbox.

        Args:
            path: File path (must be inside allowed directories)
            content: File content to write

        Returns:
            True if write succeeded
        """
        if not self.is_path_allowed(path):
            return False

        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return True
        except OSError:
            return False

    def read_file(self, path: str) -> Optional[str]:
        """
        Read a file within the sandbox.

        Args:
            path: File path (must be inside allowed directories)

        Returns:
            File content or None if not allowed/not found
        """
        if not self.is_path_allowed(path):
            return None

        try:
            return Path(path).read_text(encoding="utf-8")
        except OSError:
            return None

    def list_dir(self, path: str) -> Optional[list]:
        """
        List directory contents within the sandbox.

        Args:
            path: Directory path (must be inside allowed directories)

        Returns:
            List of filenames or None if not allowed/not found
        """
        if not self.is_path_allowed(path):
            return None

        try:
            dir_path = Path(path)
            if not dir_path.is_dir():
                return None
            return [p.name for p in sorted(dir_path.iterdir())]
        except OSError:
            return None

    # =========================================================================
    # Pending Action Management
    # =========================================================================

    def request_auth(self, session_key: str, action: str, details: Dict[str, Any]) -> str:
        """
        Store a pending action and return a password prompt message.

        Args:
            session_key: Session identifier
            action: Action type (e.g., "create_skill", "delete_skill")
            details: Action details (name, content, etc.)

        Returns:
            Message prompting user for password
        """
        self._pending_actions[session_key] = {
            "action": action,
            "details": details,
        }
        return "This action requires authorization. Please reply with `/unlock <password>` to proceed."

    def get_pending_action(self, session_key: str) -> Optional[Dict[str, Any]]:
        """
        Get the pending action for a session.

        Args:
            session_key: Session identifier

        Returns:
            Pending action dict or None
        """
        return self._pending_actions.get(session_key)

    def clear_pending_action(self, session_key: str):
        """
        Clear the pending action for a session.

        Args:
            session_key: Session identifier
        """
        self._pending_actions.pop(session_key, None)


# =============================================================================
'''
    End of File : file_access.py

    Project : coco B - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
