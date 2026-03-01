"""
SecureStorage — encrypted local storage for tokens and sensitive settings.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Optional


class SecureStorage:
    """Simple encrypted storage for sensitive data like API tokens."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path.home() / ".coco_b"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.storage_dir / "secure_config.json"
        self._data = self._load()

    def _get_machine_key(self) -> bytes:
        """Generate a machine-specific key for encryption."""
        import platform
        machine_info = f"{platform.node()}-{platform.machine()}-{os.getlogin() if hasattr(os, 'getlogin') else 'user'}"
        return hashlib.sha256(machine_info.encode()).digest()

    def _encrypt(self, plaintext: str) -> str:
        """Simple XOR encryption with base64 encoding."""
        key = self._get_machine_key()
        encrypted = bytes([ord(c) ^ key[i % len(key)] for i, c in enumerate(plaintext)])
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt XOR encrypted data."""
        try:
            key = self._get_machine_key()
            encrypted = base64.b64decode(ciphertext.encode())
            decrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(encrypted)])
            return decrypted.decode()
        except Exception:
            return ""

    def _load(self) -> dict:
        """Load encrypted config from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self):
        """Save encrypted config to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self._data, f, indent=2)

    def set_token(self, key: str, token: str):
        """Store an encrypted token."""
        self._data[key] = self._encrypt(token)
        self._save()

    def get_token(self, key: str) -> str:
        """Retrieve and decrypt a token."""
        encrypted = self._data.get(key, "")
        if encrypted:
            return self._decrypt(encrypted)
        return ""

    def set_setting(self, key: str, value):
        """Store a non-sensitive setting."""
        self._data[key] = value
        self._save()

    def get_setting(self, key: str, default=None):
        """Get a non-sensitive setting."""
        return self._data.get(key, default)

    def set_password_hash(self, password: str):
        """Store password as a hash for verification."""
        salt = os.urandom(16)
        pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        self._data['_password_salt'] = base64.b64encode(salt).decode()
        self._data['_password_hash'] = base64.b64encode(pw_hash).decode()
        self._save()

    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        if '_password_hash' not in self._data:
            return True  # No password set
        salt = base64.b64decode(self._data['_password_salt'].encode())
        stored_hash = base64.b64decode(self._data['_password_hash'].encode())
        pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return pw_hash == stored_hash

    def has_password(self) -> bool:
        """Check if a password is set."""
        return '_password_hash' in self._data

    def clear_password(self):
        """Remove password protection."""
        self._data.pop('_password_hash', None)
        self._data.pop('_password_salt', None)
        self._save()


# Global secure storage instance
secure_storage = SecureStorage()
