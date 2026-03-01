# =============================================================================
# test_auth_manager.py — Tests for tiered authentication system
# =============================================================================

import pytest
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import patch


class TestSecurityLevel:
    """Test SecurityLevel enumeration."""

    def test_security_level_values(self):
        """Security levels should have correct integer values."""
        from coco_b.core.auth_manager import SecurityLevel
        
        assert SecurityLevel.GREEN.value == 0
        assert SecurityLevel.YELLOW.value == 1
        assert SecurityLevel.ORANGE.value == 2
        assert SecurityLevel.RED.value == 3

    def test_security_level_ordering(self):
        """Higher levels should have higher values."""
        from coco_b.core.auth_manager import SecurityLevel
        
        assert SecurityLevel.GREEN.value < SecurityLevel.YELLOW.value
        assert SecurityLevel.YELLOW.value < SecurityLevel.ORANGE.value
        assert SecurityLevel.ORANGE.value < SecurityLevel.RED.value


class TestAuthSession:
    """Test AuthSession class."""

    def test_session_creation(self):
        """AuthSession should store level and expiry correctly."""
        from coco_b.core.auth_manager import AuthSession, SecurityLevel
        
        expires = datetime.now() + timedelta(minutes=30)
        session = AuthSession(SecurityLevel.YELLOW, expires)
        
        assert session.level == SecurityLevel.YELLOW
        assert session.expires_at == expires
        assert session.is_valid() is True

    def test_session_expiry(self):
        """Expired session should return is_valid=False."""
        from coco_b.core.auth_manager import AuthSession, SecurityLevel
        
        expires = datetime.now() - timedelta(minutes=1)  # Already expired
        session = AuthSession(SecurityLevel.YELLOW, expires)
        
        assert session.is_valid() is False

    def test_time_remaining(self):
        """time_remaining should return correct timedelta."""
        from coco_b.core.auth_manager import AuthSession, SecurityLevel
        
        expires = datetime.now() + timedelta(minutes=30)
        session = AuthSession(SecurityLevel.YELLOW, expires)
        
        remaining = session.time_remaining()
        assert 29 <= remaining.seconds // 60 <= 30  # Allow 1 second variance

    def test_time_remaining_expired(self):
        """time_remaining should return 0 for expired session."""
        from coco_b.core.auth_manager import AuthSession, SecurityLevel
        
        expires = datetime.now() - timedelta(minutes=1)
        session = AuthSession(SecurityLevel.YELLOW, expires)
        
        assert session.time_remaining() == timedelta(0)

    def test_update_activity(self):
        """update_activity should update last_activity timestamp."""
        from coco_b.core.auth_manager import AuthSession, SecurityLevel
        
        expires = datetime.now() + timedelta(minutes=30)
        session = AuthSession(SecurityLevel.YELLOW, expires)
        
        old_activity = session.last_activity
        time.sleep(0.01)  # Small delay
        session.update_activity()
        
        assert session.last_activity > old_activity


class TestAuthManagerSetup:
    """Test AuthManager setup and credential configuration."""

    def test_initialization(self):
        """AuthManager should initialize with empty state."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            
            assert auth.is_password_set() is False
            assert auth.is_pin_set() is False
            assert auth.get_auth_summary()["active_sessions"] == 0

    def test_setup_password_success(self):
        """Setting up password should work with valid input."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            
            assert auth.setup_password("securepass123") is True
            assert auth.is_password_set() is True

    def test_setup_password_too_short(self):
        """Password shorter than 8 chars should be rejected."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            
            assert auth.setup_password("short") is False
            assert auth.is_password_set() is False

    def test_setup_password_already_set(self):
        """Setting password twice should fail."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            
            auth.setup_password("securepass123")
            assert auth.setup_password("anotherpass456") is False

    def test_setup_pin_success(self):
        """Setting up PIN should work with valid 4-digit input."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")  # PIN requires password first
            
            assert auth.setup_pin("1234") is True
            assert auth.is_pin_set() is True

    def test_setup_pin_invalid_format(self):
        """PIN must be exactly 4 digits."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            
            assert auth.setup_pin("123") is False      # Too short
            assert auth.setup_pin("12345") is False    # Too long
            assert auth.setup_pin("abcd") is False     # Not digits
            assert auth.setup_pin("12a4") is False     # Mixed

    def test_setup_pin_without_password(self):
        """PIN setup should fail if password not set."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            
            assert auth.setup_pin("1234") is False

    def test_change_pin_success(self):
        """Changing PIN should work with correct old PIN."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            
            assert auth.change_pin("1234", "5678") is True
            assert auth.verify_pin("5678") is True
            assert auth.verify_pin("1234") is False

    def test_change_pin_wrong_old_pin(self):
        """Changing PIN should fail with wrong old PIN."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            
            assert auth.change_pin("0000", "5678") is False
            assert auth.verify_pin("1234") is True  # Unchanged


class TestAuthManagerVerification:
    """Test password and PIN verification."""

    def test_verify_password_correct(self):
        """Correct password should verify successfully."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            
            assert auth.verify_password("securepass123") is True

    def test_verify_password_incorrect(self):
        """Incorrect password should fail verification."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            
            assert auth.verify_password("wrongpass") is False

    def test_verify_password_not_set(self):
        """Verifying password when not set should fail."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            
            assert auth.verify_password("anypass") is False

    def test_verify_pin_correct(self):
        """Correct PIN should verify successfully."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            
            assert auth.verify_pin("1234") is True

    def test_verify_pin_incorrect(self):
        """Incorrect PIN should fail verification."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            
            assert auth.verify_pin("0000") is False

    def test_verify_pin_not_set(self):
        """Verifying PIN when not set should fail."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            
            assert auth.verify_pin("1234") is False

    def test_timing_attack_protection_password(self):
        """Password verification should use constant-time comparison."""
        from coco_b.core.auth_manager import AuthManager
        import time
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("testpassword123")
            
            # Measure time for correct password
            times_correct = []
            for _ in range(5):
                start = time.perf_counter()
                auth.verify_password("testpassword123")
                times_correct.append(time.perf_counter() - start)
            
            # Measure time for wrong password
            times_wrong = []
            for _ in range(5):
                start = time.perf_counter()
                auth.verify_password("wrongpassword456")
                times_wrong.append(time.perf_counter() - start)
            
            # Times should be similar (no more than 10x difference)
            avg_correct = sum(times_correct) / len(times_correct)
            avg_wrong = sum(times_wrong) / len(times_wrong)
            
            ratio = max(avg_correct, avg_wrong) / min(avg_correct, avg_wrong)
            assert ratio < 10, f"Timing ratio {ratio} suggests non-constant-time comparison"


class TestAuthManagerSessions:
    """Test session management."""

    def test_authenticate_pin_creates_session(self):
        """Successful PIN auth should create YELLOW session."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            
            assert auth.authenticate_pin("user1", "1234") is True
            
            status = auth.get_session_status("user1")
            assert status is not None
            assert status["level"] == "YELLOW"
            assert status["is_valid"] is True

    def test_authenticate_password_creates_session(self):
        """Successful password auth should create ORANGE session."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            
            assert auth.authenticate_password("user1", "securepass123") is True
            
            status = auth.get_session_status("user1")
            assert status is not None
            assert status["level"] == "ORANGE"

    def test_authenticate_wrong_credentials_no_session(self):
        """Failed auth should not create session."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            
            assert auth.authenticate_pin("user1", "0000") is False
            assert auth.get_session_status("user1") is None

    def test_session_expiry(self):
        """Session should expire after configured time."""
        from coco_b.core.auth_manager import AuthManager, AuthSession, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            
            # Authenticate with PIN (30 min session)
            auth.authenticate_pin("user1", "1234")
            assert auth.get_session_status("user1") is not None
            
            # Manually expire session by creating an expired session
            expired_time = datetime.now() - timedelta(minutes=1)
            auth._sessions["user1"] = AuthSession(
                level=SecurityLevel.YELLOW,
                expires_at=expired_time
            )
            
            assert auth.get_session_status("user1") is None

    def test_clear_session(self):
        """Clear session should remove it."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.authenticate_password("user1", "securepass123")
            
            assert auth.get_session_status("user1") is not None
            auth.clear_session("user1")
            assert auth.get_session_status("user1") is None

    def test_extend_session(self):
        """Extend session should increase expiry time."""
        from coco_b.core.auth_manager import AuthManager, AuthSession, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            
            # Create a session that expires soon
            near_expiry = datetime.now() + timedelta(minutes=5)
            auth._sessions["user1"] = AuthSession(
                level=SecurityLevel.YELLOW,
                expires_at=near_expiry
            )
            
            old_status = auth.get_session_status("user1")
            old_expires = datetime.fromisoformat(old_status["expires_at"])
            
            # Extend the session
            auth.extend_session("user1", minutes=30)
            
            new_status = auth.get_session_status("user1")
            new_expires = datetime.fromisoformat(new_status["expires_at"])
            
            # New expiry should be later than old
            assert new_expires > old_expires
            
            # Should be roughly 30 minutes from now
            expected_expiry = datetime.now() + timedelta(minutes=30)
            time_diff = abs((new_expires - expected_expiry).total_seconds())
            assert time_diff < 5  # Within 5 seconds


class TestAuthManagerAccessControl:
    """Test access control with security levels."""

    def test_green_level_always_allowed(self):
        """GREEN level should always be allowed without auth."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            
            result = auth.check_access("user1", SecurityLevel.GREEN)
            assert result.allowed is True
            assert result.method == "none"

    def test_yellow_level_requires_pin(self):
        """YELLOW level should require PIN when no session."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            
            result = auth.check_access("user1", SecurityLevel.YELLOW)
            assert result.allowed is False
            assert result.method == "pin"
            assert "PIN" in result.message

    def test_yellow_level_with_active_session(self):
        """YELLOW level should be allowed with YELLOW session."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            auth.authenticate_pin("user1", "1234")
            
            result = auth.check_access("user1", SecurityLevel.YELLOW)
            assert result.allowed is True
            assert result.method == "session"

    def test_orange_level_requires_password(self):
        """ORANGE level should require password when no session."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            
            result = auth.check_access("user1", SecurityLevel.ORANGE)
            assert result.allowed is False
            assert result.method == "password"

    def test_orange_level_with_orange_session(self):
        """ORANGE level should be allowed with ORANGE session."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.authenticate_password("user1", "securepass123")
            
            result = auth.check_access("user1", SecurityLevel.ORANGE)
            assert result.allowed is True

    def test_orange_session_covers_yellow(self):
        """ORANGE session should satisfy YELLOW requirements."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.authenticate_password("user1", "securepass123")  # ORANGE session
            
            result = auth.check_access("user1", SecurityLevel.YELLOW)
            assert result.allowed is True

    def test_yellow_session_does_not_cover_orange(self):
        """YELLOW session should not satisfy ORANGE requirements."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            auth.authenticate_pin("user1", "1234")  # YELLOW session
            
            result = auth.check_access("user1", SecurityLevel.ORANGE)
            assert result.allowed is False
            assert result.method == "password"

    def test_red_level_requires_password_confirm(self):
        """RED level should require password+confirm."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            
            result = auth.check_access("user1", SecurityLevel.RED)
            assert result.allowed is False
            assert result.method == "password+confirm"
            assert "sensitive" in result.message.lower()

    def test_yellow_fallback_to_password_if_no_pin(self):
        """YELLOW should fallback to password if PIN not set."""
        from coco_b.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            # No PIN set
            
            result = auth.check_access("user1", SecurityLevel.YELLOW)
            assert result.allowed is False
            assert result.method == "password"


class TestAuthManagerPersistence:
    """Test session persistence across instances."""

    def test_sessions_persist_to_disk(self):
        """Sessions should be saved and loaded from disk."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create first instance and authenticate
            auth1 = AuthManager(data_dir=tmpdir)
            auth1.setup_password("securepass123")
            auth1.authenticate_password("user1", "securepass123")
            
            # Create second instance (simulating restart)
            auth2 = AuthManager(data_dir=tmpdir)
            
            # Session should be loaded
            status = auth2.get_session_status("user1")
            assert status is not None
            assert status["level"] == "ORANGE"

    def test_expired_sessions_not_loaded(self):
        """Expired sessions should not be loaded from disk."""
        from coco_b.core.auth_manager import AuthManager
        import json
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth1 = AuthManager(data_dir=tmpdir)
            auth1.setup_password("securepass123")
            auth1.authenticate_password("user1", "securepass123")
            
            # Manually modify the sessions file to make session expired
            sessions_file = Path(tmpdir) / "sessions.json"
            with open(sessions_file, 'r') as f:
                data = json.load(f)
            
            # Set expiry to past
            for user_data in data.values():
                user_data['expires_at'] = (datetime.now() - timedelta(hours=1)).isoformat()
            
            with open(sessions_file, 'w') as f:
                json.dump(data, f)
            
            # Create new instance - should not load expired session
            auth2 = AuthManager(data_dir=tmpdir)
            assert auth2.get_session_status("user1") is None


class TestAuthManagerUtilities:
    """Test utility methods."""

    def test_get_auth_summary(self):
        """get_auth_summary should return correct status."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            
            summary = auth.get_auth_summary()
            assert summary["password_set"] is False
            assert summary["pin_set"] is False
            assert summary["active_sessions"] == 0
            assert summary["pin_session_minutes"] == 30
            assert summary["password_session_minutes"] == 60
            
            # After setup
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            auth.authenticate_pin("user1", "1234")
            
            summary = auth.get_auth_summary()
            assert summary["password_set"] is True
            assert summary["pin_set"] is True
            assert summary["active_sessions"] == 1

    def test_clear_all_sessions(self):
        """clear_all_sessions should remove all sessions."""
        from coco_b.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = AuthManager(data_dir=tmpdir)
            auth.setup_password("securepass123")
            auth.setup_pin("1234")
            
            auth.authenticate_pin("user1", "1234")
            auth.authenticate_pin("user2", "1234")
            auth.authenticate_password("user3", "securepass123")
            
            assert auth.get_auth_summary()["active_sessions"] == 3
            
            auth.clear_all_sessions()
            
            assert auth.get_auth_summary()["active_sessions"] == 0
            assert auth.get_session_status("user1") is None
            assert auth.get_session_status("user2") is None
            assert auth.get_session_status("user3") is None


# Import datetime for the tests
from datetime import datetime
from pathlib import Path
