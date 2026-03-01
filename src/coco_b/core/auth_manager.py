# =============================================================================
'''
    File Name : auth_manager.py
    
    Description : Tiered authentication system for agentic features.
                  Provides multiple security levels from no-auth (GREEN) 
                  to password+confirm (RED) with session management.
    
    Security Levels:
        - GREEN (0): No auth needed (read-only, heartbeats)
        - YELLOW (1): PIN auth (routine tasks, 30 min session)
        - ORANGE (2): Password auth (skill creation, 1 hour session)
        - RED (3): Password + confirm (dangerous ops, per-action)
    
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
import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, NamedTuple
from pathlib import Path
import json


# =============================================================================
'''
    SecurityLevel : Enumeration of authentication security levels
'''
# =============================================================================
class SecurityLevel(Enum):
    """Security levels for agentic features"""
    GREEN = 0   # No auth needed (read-only, heartbeats)
    YELLOW = 1  # PIN auth (routine tasks, 30 min session)
    ORANGE = 2  # Password auth (skill creation, 1 hour session)
    RED = 3     # Password + confirm (dangerous ops, per-action)


# =============================================================================
'''
    AuthResult : Result of an authentication check
'''
# =============================================================================
class AuthResult(NamedTuple):
    """Result of authentication check"""
    allowed: bool
    method: str
    message: Optional[str] = None
    expires_in: Optional[timedelta] = None


# =============================================================================
'''
    AuthSession : Represents an authenticated user session
'''
# =============================================================================
class AuthSession:
    """Represents an authenticated session for a user"""
    
    def __init__(self, level: SecurityLevel, expires_at: datetime, 
                 created_at: Optional[datetime] = None):
        self.level = level
        self.expires_at = expires_at
        self.created_at = created_at or datetime.now()
        self.last_activity = datetime.now()
    
    def is_valid(self) -> bool:
        """Check if session is still valid (not expired)"""
        return datetime.now() < self.expires_at
    
    def time_remaining(self) -> timedelta:
        """Get time remaining in session"""
        remaining = self.expires_at - datetime.now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()


# =============================================================================
'''
    AuthManager : Manages tiered authentication for agentic features
    
    Features:
        - Multiple security levels (GREEN to RED)
        - PIN and Password authentication
        - Session management with auto-expiry
        - Persistent credential storage
        - Constant-time comparison for security
'''
# =============================================================================
class AuthManager:
    """
    Manages tiered authentication for agentic features.
    
    Security:
        - Passwords stored with PBKDF2-HMAC-SHA256
        - PINs stored with same method (treated as short passwords)
        - Constant-time comparison to prevent timing attacks
        - Sessions auto-expire for security
    """
    
    # ==================================
    # Session duration constants
    # ==================================
    PIN_SESSION_MINUTES = 30
    PASSWORD_SESSION_MINUTES = 60
    
    # ==================================
    # Password hashing constants
    # ==================================
    ITERATIONS = 600_000
    SALT_BYTES = 32
    
    # =========================================================================
    # Function __init__ -> Optional[Path] to None
    # =========================================================================
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the authentication manager.
        
        Args:
            data_dir: Directory to store auth data (default: data/auth/)
        """
        # ==================================
        # Set up data directory
        # ==================================
        if data_dir is None:
            from coco_b import PROJECT_ROOT
            self._data_dir = Path(PROJECT_ROOT) / "data" / "auth"
        else:
            self._data_dir = Path(data_dir)
        
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # ==================================
        # Auth file paths
        # ==================================
        self._password_file = self._data_dir / ".master_password"
        self._pin_file = self._data_dir / ".pin"
        self._sessions_file = self._data_dir / "sessions.json"
        
        # ==================================
        # In-memory session storage
        # ==================================
        self._sessions: Dict[str, AuthSession] = {}
        
        # ==================================
        # Load existing credentials and sessions
        # ==================================
        self._load_credentials()
        self._load_sessions()
    
    # =========================================================================
    # Private: Credential Storage
    # =========================================================================
    
    def _hash_credential(self, credential: str, salt: Optional[bytes] = None) -> tuple:
        """
        Hash a credential (password or PIN) with PBKDF2.
        
        Args:
            credential: The credential to hash
            salt: Optional salt (generated if not provided)
            
        Returns:
            Tuple of (salt_hex, hash_hex)
        """
        if salt is None:
            salt = os.urandom(self.SALT_BYTES)
        
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            credential.encode('utf-8'),
            salt,
            self.ITERATIONS
        )
        
        return salt.hex(), hashed.hex()
    
    def _verify_credential(self, credential: str, salt_hex: str, hash_hex: str) -> bool:
        """
        Verify a credential against stored hash using constant-time comparison.
        
        Security:
            Uses hmac.compare_digest to prevent timing attacks.
        """
        try:
            salt = bytes.fromhex(salt_hex)
            stored_hash = bytes.fromhex(hash_hex)
        except ValueError:
            return False
        
        computed = hashlib.pbkdf2_hmac(
            'sha256',
            credential.encode('utf-8'),
            salt,
            self.ITERATIONS
        )
        
        return hmac.compare_digest(computed, stored_hash)
    
    def _load_credentials(self):
        """Load stored credentials from disk"""
        # Password is loaded on demand via is_password_set()
        # PIN is loaded on demand via is_pin_set()
        pass
    
    def _load_sessions(self):
        """Load sessions from disk (optional persistence)"""
        if self._sessions_file.exists():
            try:
                with open(self._sessions_file, 'r') as f:
                    data = json.load(f)
                # Convert loaded data to AuthSession objects
                for user_id, session_data in data.items():
                    try:
                        level = SecurityLevel(session_data['level'])
                        expires_at = datetime.fromisoformat(session_data['expires_at'])
                        created_at = datetime.fromisoformat(session_data['created_at'])
                        
                        # Only restore if not expired
                        if datetime.now() < expires_at:
                            self._sessions[user_id] = AuthSession(
                                level=level,
                                expires_at=expires_at,
                                created_at=created_at
                            )
                    except (KeyError, ValueError):
                        continue
            except (json.JSONDecodeError, IOError):
                pass
    
    def _save_sessions(self):
        """Save active sessions to disk"""
        data = {}
        for user_id, session in self._sessions.items():
            if session.is_valid():
                data[user_id] = {
                    'level': session.level.value,
                    'expires_at': session.expires_at.isoformat(),
                    'created_at': session.created_at.isoformat()
                }
        
        try:
            with open(self._sessions_file, 'w') as f:
                json.dump(data, f)
        except IOError:
            pass
    
    # =========================================================================
    # Public: Setup Methods
    # =========================================================================
    
    def is_password_set(self) -> bool:
        """Check if master password has been configured"""
        return self._password_file.exists()
    
    def is_pin_set(self) -> bool:
        """Check if PIN has been configured"""
        return self._pin_file.exists()
    
    def setup_password(self, password: str) -> bool:
        """
        Set up master password (one-time setup).
        
        Args:
            password: Master password (min 8 characters)
            
        Returns:
            True if password was set successfully
        """
        # ==================================
        # Validate password strength
        # ==================================
        if len(password) < 8:
            return False
        
        # ==================================
        # Check if already set
        # ==================================
        if self.is_password_set():
            return False
        
        # ==================================
        # Hash and store
        # ==================================
        salt_hex, hash_hex = self._hash_credential(password)
        
        try:
            self._password_file.write_text(
                f"{salt_hex}:{hash_hex}",
                encoding='utf-8'
            )
            # Restrict permissions
            os.chmod(self._password_file, 0o600)
            return True
        except OSError:
            return False
    
    def setup_pin(self, pin: str) -> bool:
        """
        Set up 4-digit PIN for quick authentication.
        
        Args:
            pin: 4-digit PIN code
            
        Returns:
            True if PIN was set successfully
        """
        # ==================================
        # Validate PIN format
        # ==================================
        if not pin.isdigit() or len(pin) != 4:
            return False
        
        # ==================================
        # Check if password is set first (PIN requires password)
        # ==================================
        if not self.is_password_set():
            return False
        
        # ==================================
        # Hash and store
        # ==================================
        salt_hex, hash_hex = self._hash_credential(pin)
        
        try:
            self._pin_file.write_text(
                f"{salt_hex}:{hash_hex}",
                encoding='utf-8'
            )
            os.chmod(self._pin_file, 0o600)
            return True
        except OSError:
            return False
    
    def change_pin(self, old_pin: str, new_pin: str) -> bool:
        """
        Change existing PIN.
        
        Args:
            old_pin: Current PIN
            new_pin: New 4-digit PIN
            
        Returns:
            True if PIN was changed successfully
        """
        # Verify old PIN
        if not self.verify_pin(old_pin):
            return False
        
        # Validate new PIN
        if not new_pin.isdigit() or len(new_pin) != 4:
            return False
        
        # Remove old PIN file
        try:
            self._pin_file.unlink()
        except OSError:
            pass
        
        # Set new PIN
        return self.setup_pin(new_pin)
    
    # =========================================================================
    # Public: Verification Methods
    # =========================================================================
    
    def verify_pin(self, pin: str) -> bool:
        """
        Verify PIN against stored hash.
        
        Args:
            pin: PIN to verify
            
        Returns:
            True if PIN is correct
        """
        if not self.is_pin_set():
            return False
        
        try:
            content = self._pin_file.read_text(encoding='utf-8').strip()
            salt_hex, hash_hex = content.split(':', 1)
        except (ValueError, OSError):
            return False
        
        return self._verify_credential(pin, salt_hex, hash_hex)
    
    def verify_password(self, password: str) -> bool:
        """
        Verify master password against stored hash.
        
        Args:
            password: Password to verify
            
        Returns:
            True if password is correct
        """
        if not self.is_password_set():
            return False
        
        try:
            content = self._password_file.read_text(encoding='utf-8').strip()
            salt_hex, hash_hex = content.split(':', 1)
        except (ValueError, OSError):
            return False
        
        return self._verify_credential(password, salt_hex, hash_hex)
    
    # =========================================================================
    # Public: Session Management
    # =========================================================================
    
    def authenticate_pin(self, user_id: str, pin: str) -> bool:
        """
        Authenticate user with PIN and create YELLOW session.
        
        Args:
            user_id: User identifier
            pin: 4-digit PIN
            
        Returns:
            True if authentication successful
        """
        if not self.verify_pin(pin):
            return False
        
        # Create 30-minute YELLOW session
        self._sessions[user_id] = AuthSession(
            level=SecurityLevel.YELLOW,
            expires_at=datetime.now() + timedelta(minutes=self.PIN_SESSION_MINUTES)
        )
        
        self._save_sessions()
        return True
    
    def authenticate_password(self, user_id: str, password: str) -> bool:
        """
        Authenticate user with password and create ORANGE session.
        
        Args:
            user_id: User identifier
            password: Master password
            
        Returns:
            True if authentication successful
        """
        if not self.verify_password(password):
            return False
        
        # Create 1-hour ORANGE session
        self._sessions[user_id] = AuthSession(
            level=SecurityLevel.ORANGE,
            expires_at=datetime.now() + timedelta(minutes=self.PASSWORD_SESSION_MINUTES)
        )
        
        self._save_sessions()
        return True
    
    def check_access(self, user_id: str, required_level: SecurityLevel) -> AuthResult:
        """
        Check if user has required access level.
        
        Args:
            user_id: User identifier
            required_level: Minimum SecurityLevel required
            
        Returns:
            AuthResult with status and instructions
        """
        # ==================================
        # GREEN level - always allowed
        # ==================================
        if required_level == SecurityLevel.GREEN:
            return AuthResult(allowed=True, method="none")
        
        # ==================================
        # Check for active session
        # ==================================
        session = self._sessions.get(user_id)
        
        if session and session.is_valid():
            # Update activity
            session.update_activity()
            
            # Check if session level is sufficient
            if session.level.value >= required_level.value:
                return AuthResult(
                    allowed=True,
                    method="session",
                    expires_in=session.time_remaining()
                )
        
        # ==================================
        # No valid session - require authentication
        # ==================================
        if required_level == SecurityLevel.YELLOW:
            if not self.is_pin_set():
                # Fall back to password if PIN not set
                return AuthResult(
                    allowed=False,
                    method="password",
                    message="🔐 Enter your password (PIN not set):"
                )
            
            return AuthResult(
                allowed=False,
                method="pin",
                message="🔐 Enter your 4-digit PIN:"
            )
        
        elif required_level == SecurityLevel.ORANGE:
            return AuthResult(
                allowed=False,
                method="password",
                message="🔐 Enter your password (1-hour session):"
            )
        
        elif required_level == SecurityLevel.RED:
            return AuthResult(
                allowed=False,
                method="password+confirm",
                message="🔐 This is a sensitive operation. Enter password:"
            )
        
        return AuthResult(allowed=False, method="unknown", message="Unknown security level")
    
    def extend_session(self, user_id: str, minutes: Optional[int] = None) -> bool:
        """
        Extend current session on user activity.
        
        Args:
            user_id: User identifier
            minutes: Minutes to extend (default: based on session level)
            
        Returns:
            True if session was extended
        """
        session = self._sessions.get(user_id)
        
        if not session or not session.is_valid():
            return False
        
        # Determine extension time based on level
        if minutes is None:
            if session.level == SecurityLevel.YELLOW:
                minutes = self.PIN_SESSION_MINUTES
            else:
                minutes = self.PASSWORD_SESSION_MINUTES
        
        # Extend from current time (not from expiry)
        session.expires_at = datetime.now() + timedelta(minutes=minutes)
        session.update_activity()
        
        self._save_sessions()
        return True
    
    def clear_session(self, user_id: str):
        """
        Clear user session (logout).
        
        Args:
            user_id: User identifier
        """
        self._sessions.pop(user_id, None)
        self._save_sessions()
    
    def get_session_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current session status for display.
        
        Args:
            user_id: User identifier
            
        Returns:
            Session status dict or None if no active session
        """
        session = self._sessions.get(user_id)
        
        if not session or not session.is_valid():
            return None
        
        remaining = session.time_remaining()
        
        return {
            "level": session.level.name,
            "level_value": session.level.value,
            "expires_in_minutes": remaining.seconds // 60,
            "expires_at": session.expires_at.isoformat(),
            "created_at": session.created_at.isoformat(),
            "is_valid": True
        }
    
    def clear_all_sessions(self):
        """Clear all sessions (admin/reset use)"""
        self._sessions.clear()
        self._save_sessions()
    
    # =========================================================================
    # Public: Utility Methods
    # =========================================================================
    
    def get_auth_summary(self) -> Dict[str, Any]:
        """
        Get summary of authentication status.
        
        Returns:
            Dict with auth configuration status
        """
        return {
            "password_set": self.is_password_set(),
            "pin_set": self.is_pin_set(),
            "active_sessions": len([s for s in self._sessions.values() if s.is_valid()]),
            "pin_session_minutes": self.PIN_SESSION_MINUTES,
            "password_session_minutes": self.PASSWORD_SESSION_MINUTES
        }


# =============================================================================
'''
    End of File : auth_manager.py
    
    Project : coco B - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
