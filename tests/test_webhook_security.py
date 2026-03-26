# =============================================================================
# test_webhook_security.py — Tests for webhook signature verification
# =============================================================================

import pytest
import hmac
import hashlib
import time
from unittest.mock import patch


# =============================================================================
# Import webhook security module directly
# =============================================================================
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from skillforge.core.webhook_security import (
    WebhookSecurityError,
    verify_whatsapp_signature,
    verify_telegram_secret,
    verify_slack_signature,
    verify_ms_teams_token,
    get_whatsapp_app_secret,
    get_telegram_webhook_secret,
    get_slack_signing_secret,
)


class TestWebhookSecurityError:
    """Test WebhookSecurityError exception."""

    def test_is_exception_subclass(self):
        """WebhookSecurityError should be an Exception subclass."""
        assert issubclass(WebhookSecurityError, Exception)

    def test_can_be_raised_with_message(self):
        """WebhookSecurityError can be raised with a custom message."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            raise WebhookSecurityError("Test error message")
        assert str(exc_info.value) == "Test error message"


class TestVerifyWhatsAppSignature:
    """Test WhatsApp webhook signature verification."""

    def test_valid_signature(self):
        """Valid signature should pass verification."""
        app_secret = "test_secret"
        payload = b'{"test": "data"}'
        
        # Compute valid signature
        computed = hmac.new(
            app_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        signature = f"sha256={computed}"
        
        # Should not raise
        result = verify_whatsapp_signature(payload, signature, app_secret)
        assert result is True

    def test_missing_signature(self):
        """Missing signature should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_whatsapp_signature(b'{"test": "data"}', None, "secret")
        assert "Missing X-Hub-Signature-256" in str(exc_info.value)

    def test_missing_app_secret(self):
        """Missing app secret should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_whatsapp_signature(b'{"test": "data"}', "sha256=abc", "")
        assert "not configured" in str(exc_info.value)

    def test_invalid_signature_format(self):
        """Invalid signature format should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_whatsapp_signature(b'{"test": "data"}', "invalid_format", "secret")
        assert "Invalid signature format" in str(exc_info.value)

    def test_invalid_signature(self):
        """Invalid signature should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_whatsapp_signature(
                b'{"test": "data"}',
                "sha256=wrong_signature",
                "secret"
            )
        assert "Invalid WhatsApp signature" in str(exc_info.value)

    def test_timing_attack_protection(self):
        """Verification should use constant-time comparison."""
        app_secret = "test_secret"
        payload = b'{"test": "data"}'
        
        # Compute valid signature
        computed = hmac.new(
            app_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Slightly different signature
        wrong_signature = f"sha256={computed[:-1]}0"
        
        with pytest.raises(WebhookSecurityError):
            verify_whatsapp_signature(payload, wrong_signature, app_secret)


class TestVerifyTelegramSecret:
    """Test Telegram webhook secret verification."""

    def test_valid_secret(self):
        """Valid secret should pass verification."""
        expected_secret = "my_webhook_secret"
        request_secret = "my_webhook_secret"
        
        result = verify_telegram_secret(request_secret, expected_secret)
        assert result is True

    def test_missing_expected_secret(self):
        """Missing expected secret should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_telegram_secret("request_secret", "")
        assert "not configured" in str(exc_info.value)

    def test_missing_request_secret(self):
        """Missing request secret should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_telegram_secret(None, "expected_secret")
        assert "Missing X-Telegram-Bot-Api-Secret-Token" in str(exc_info.value)

    def test_invalid_secret(self):
        """Invalid secret should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_telegram_secret("wrong_secret", "expected_secret")
        assert "Invalid Telegram webhook secret" in str(exc_info.value)

    def test_timing_attack_protection(self):
        """Verification should use constant-time comparison."""
        expected = "secret123"
        request = "secret124"  # One character different
        
        with pytest.raises(WebhookSecurityError):
            verify_telegram_secret(request, expected)


class TestVerifySlackSignature:
    """Test Slack webhook signature verification."""

    def test_valid_signature(self):
        """Valid signature should pass verification."""
        signing_secret = "test_secret"
        timestamp = str(int(time.time()))
        payload = b'{"test": "data"}'
        
        # Compute valid signature
        base_string = f"v0:{timestamp}:{payload.decode('utf-8')}"
        computed = hmac.new(
            signing_secret.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        signature = f"v0={computed}"
        
        # Should not raise
        result = verify_slack_signature(payload, signature, timestamp, signing_secret)
        assert result is True

    def test_missing_signing_secret(self):
        """Missing signing secret should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_slack_signature(b'{}', "sig", "123", "")
        assert "not configured" in str(exc_info.value)

    def test_missing_signature(self):
        """Missing signature should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_slack_signature(b'{}', None, "123", "secret")
        assert "Missing X-Slack-Signature" in str(exc_info.value)

    def test_missing_timestamp(self):
        """Missing timestamp should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_slack_signature(b'{}', "v0=sig", None, "secret")
        assert "Missing X-Slack-Request-Timestamp" in str(exc_info.value)

    def test_old_timestamp(self):
        """Old timestamp should raise error (replay attack protection)."""
        old_timestamp = str(int(time.time()) - 1000)  # 1000 seconds ago
        
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_slack_signature(b'{}', "v0=sig", old_timestamp, "secret")
        assert "timestamp too old" in str(exc_info.value).lower()

    def test_future_timestamp(self):
        """Future timestamp should raise error."""
        future_timestamp = str(int(time.time()) + 1000)  # 1000 seconds in future
        
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_slack_signature(b'{}', "v0=sig", future_timestamp, "secret")
        assert "timestamp too old" in str(exc_info.value).lower()

    def test_invalid_timestamp_format(self):
        """Invalid timestamp format should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_slack_signature(b'{}', "v0=sig", "not_a_number", "secret")
        assert "Invalid timestamp format" in str(exc_info.value)

    def test_invalid_signature(self):
        """Invalid signature should raise error."""
        timestamp = str(int(time.time()))
        
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_slack_signature(b'{}', "v0=wrong_sig", timestamp, "secret")
        assert "Invalid Slack signature" in str(exc_info.value)

    def test_custom_max_age(self):
        """Custom max age should be respected."""
        # Timestamp 200 seconds ago with max_age of 300 should pass
        timestamp = str(int(time.time()) - 200)
        signing_secret = "test_secret"
        payload = b'{"test": "data"}'
        
        base_string = f"v0:{timestamp}:{payload.decode('utf-8')}"
        computed = hmac.new(
            signing_secret.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        signature = f"v0={computed}"
        
        # Should pass with 300 second max age
        result = verify_slack_signature(
            payload, signature, timestamp, signing_secret, max_age_seconds=300
        )
        assert result is True


class TestVerifyMSTeamsToken:
    """Test MS Teams token verification (simplified)."""

    def test_valid_bearer_token(self):
        """Valid Bearer token format should pass."""
        result = verify_ms_teams_token(
            "Bearer eyJ0eXAiOiJKV1QiLCJhbGc...",
            "test_app_id",
            "test_password"
        )
        assert result is True

    def test_missing_app_id(self):
        """Missing app ID should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_ms_teams_token("Bearer token", "", "password")
        assert "app ID not configured" in str(exc_info.value)

    def test_placeholder_app_id(self):
        """Placeholder app ID should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_ms_teams_token("Bearer token", "YOUR_APP_ID_HERE", "password")
        assert "app ID not configured" in str(exc_info.value)

    def test_missing_app_password(self):
        """Missing app password should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_ms_teams_token("Bearer token", "app_id", "")
        assert "app password not configured" in str(exc_info.value)

    def test_placeholder_app_password(self):
        """Placeholder app password should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_ms_teams_token("Bearer token", "app_id", "YOUR_APP_PASSWORD_HERE")
        assert "app password not configured" in str(exc_info.value)

    def test_missing_auth_header(self):
        """Missing Authorization header should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_ms_teams_token(None, "app_id", "password")
        assert "Missing Authorization header" in str(exc_info.value)

    def test_invalid_auth_format(self):
        """Invalid Authorization format should raise error."""
        with pytest.raises(WebhookSecurityError) as exc_info:
            verify_ms_teams_token("Basic dXNlcjpwYXNz", "app_id", "password")
        assert "Invalid Authorization format" in str(exc_info.value)


class TestEnvironmentFunctions:
    """Test environment variable helper functions."""

    def test_get_whatsapp_app_secret_from_env(self):
        """get_whatsapp_app_secret should read from environment."""
        with patch.dict(os.environ, {'WHATSAPP_APP_SECRET': 'test_secret'}):
            assert get_whatsapp_app_secret() == 'test_secret'

    def test_get_whatsapp_app_secret_missing(self):
        """get_whatsapp_app_secret should return None if not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_whatsapp_app_secret() is None

    def test_get_telegram_webhook_secret_from_env(self):
        """get_telegram_webhook_secret should read from environment."""
        with patch.dict(os.environ, {'TELEGRAM_WEBHOOK_SECRET': 'test_secret'}):
            assert get_telegram_webhook_secret() == 'test_secret'

    def test_get_telegram_webhook_secret_missing(self):
        """get_telegram_webhook_secret should return None if not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_telegram_webhook_secret() is None

    def test_get_slack_signing_secret_from_env(self):
        """get_slack_signing_secret should read from environment."""
        with patch.dict(os.environ, {'SLACK_SIGNING_SECRET': 'test_secret'}):
            assert get_slack_signing_secret() == 'test_secret'

    def test_get_slack_signing_secret_missing(self):
        """get_slack_signing_secret should return None if not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_slack_signing_secret() is None


# Import os for the environment tests
import os
