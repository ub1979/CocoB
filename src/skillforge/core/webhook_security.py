# =============================================================================
'''
    File Name : webhook_security.py
    
    Description : Webhook signature verification for all channel integrations.
                  Provides security functions to verify that incoming webhooks
                  are genuinely from the claimed platform (WhatsApp, Telegram,
                  Slack, MS Teams) and not from attackers.
    
    Security:
        - HMAC-SHA256 signature verification
        - Timestamp validation to prevent replay attacks
        - Constant-time comparison to prevent timing attacks
        
    Supported Platforms:
        - WhatsApp (Meta): X-Hub-Signature-256 header
        - Telegram: X-Telegram-Bot-Api-Secret-Token header
        - Slack: X-Slack-Signature header with timestamp
        - MS Teams: JWT token validation (Bot Framework)
    
    Created on 2026-02-21
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import hmac
import hashlib
import time
import json
from typing import Optional, Dict, Any


# =============================================================================
'''
    WebhookSecurityError : Exception raised when webhook verification fails
'''
# =============================================================================
class WebhookSecurityError(Exception):
    """Raised when webhook signature verification fails"""
    pass


# =============================================================================
'''
    verify_whatsapp_signature : Verify WhatsApp webhook signature
    
    WhatsApp uses HMAC-SHA256 with the app secret to sign payloads.
    The signature is sent in the X-Hub-Signature-256 header.
    
    Args:
        payload: Raw request body bytes
        signature: Signature from X-Hub-Signature-256 header (e.g., "sha256=abc123...")
        app_secret: WhatsApp app secret from developer dashboard
        
    Returns:
        True if signature is valid
        
    Raises:
        WebhookSecurityError: If signature is invalid or missing
        
    Reference:
        https://developers.facebook.com/docs/graph-api/webhooks/getting-started
'''
# =============================================================================
def verify_whatsapp_signature(
    payload: bytes,
    signature: Optional[str],
    app_secret: str
) -> bool:
    """
    Verify WhatsApp webhook signature using HMAC-SHA256.
    
    Security:
        - Uses constant-time comparison to prevent timing attacks
        - Validates signature format before comparison
    """
    # ==================================
    # Check if signature is provided
    # ==================================
    if not signature:
        raise WebhookSecurityError(
            "Missing X-Hub-Signature-256 header. "
            "This webhook may not be from WhatsApp."
        )
    
    # ==================================
    # Check if app secret is configured
    # ==================================
    if not app_secret:
        raise WebhookSecurityError(
            "WhatsApp app secret not configured. "
            "Set WHATSAPP_APP_SECRET environment variable."
        )
    
    # ==================================
    # Extract signature value (format: "sha256=<hash>")
    # ==================================
    if not signature.startswith('sha256='):
        raise WebhookSecurityError(
            f"Invalid signature format. Expected 'sha256=...', got '{signature[:20]}...'"
        )
    
    expected_signature = signature[7:]  # Remove 'sha256=' prefix
    
    # ==================================
    # Compute HMAC-SHA256 of payload
    # ==================================
    computed = hmac.new(
        app_secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # ==================================
    # Constant-time comparison to prevent timing attacks
    # ==================================
    if not hmac.compare_digest(computed, expected_signature):
        raise WebhookSecurityError(
            "Invalid WhatsApp signature. "
            "This request may be spoofed or the app secret is incorrect."
        )
    
    return True


# =============================================================================
'''
    verify_telegram_secret : Verify Telegram webhook secret token
    
    Telegram sends a secret token in the X-Telegram-Bot-Api-Secret-Token header
    when webhooks are configured with a secret_token parameter.
    
    Args:
        request_secret: Secret from X-Telegram-Bot-Api-Secret-Token header
        expected_secret: The secret token configured in webhook
        
    Returns:
        True if secret matches
        
    Raises:
        WebhookSecurityError: If secret is invalid or missing
        
    Reference:
        https://core.telegram.org/bots/api#setwebhook
'''
# =============================================================================
def verify_telegram_secret(
    request_secret: Optional[str],
    expected_secret: str
) -> bool:
    """
    Verify Telegram webhook secret token.
    
    Security:
        - Uses constant-time comparison to prevent timing attacks
        - Validates that secret is configured
    """
    # ==================================
    # Check if expected secret is configured
    # ==================================
    if not expected_secret:
        raise WebhookSecurityError(
            "Telegram webhook secret not configured. "
            "Set TELEGRAM_WEBHOOK_SECRET environment variable."
        )
    
    # ==================================
    # Check if request has secret header
    # ==================================
    if not request_secret:
        raise WebhookSecurityError(
            "Missing X-Telegram-Bot-Api-Secret-Token header. "
            "This webhook may not be from Telegram."
        )
    
    # ==================================
    # Constant-time comparison
    # ==================================
    if not hmac.compare_digest(request_secret, expected_secret):
        raise WebhookSecurityError(
            "Invalid Telegram webhook secret. "
            "This request may be spoofed."
        )
    
    return True


# =============================================================================
'''
    verify_slack_signature : Verify Slack webhook signature
    
    Slack uses HMAC-SHA256 with a signing secret. The signature includes
    a timestamp to prevent replay attacks.
    
    Args:
        payload: Raw request body bytes
        signature: Signature from X-Slack-Signature header (e.g., "v0=abc123...")
        timestamp: Timestamp from X-Slack-Request-Timestamp header
        signing_secret: Slack signing secret from app dashboard
        max_age_seconds: Maximum age of request (default: 300 seconds)
        
    Returns:
        True if signature is valid and not expired
        
    Raises:
        WebhookSecurityError: If signature is invalid, expired, or missing
        
    Reference:
        https://api.slack.com/authentication/verifying-requests-from-slack
'''
# =============================================================================
def verify_slack_signature(
    payload: bytes,
    signature: Optional[str],
    timestamp: Optional[str],
    signing_secret: str,
    max_age_seconds: int = 300
) -> bool:
    """
    Verify Slack webhook signature with replay attack protection.
    
    Security:
        - Validates timestamp to prevent replay attacks
        - Uses constant-time comparison
        - Rejects requests older than max_age_seconds
    """
    # ==================================
    # Check if signing secret is configured
    # ==================================
    if not signing_secret:
        raise WebhookSecurityError(
            "Slack signing secret not configured. "
            "Set SLACK_SIGNING_SECRET environment variable."
        )
    
    # ==================================
    # Check required headers
    # ==================================
    if not signature:
        raise WebhookSecurityError(
            "Missing X-Slack-Signature header. "
            "This webhook may not be from Slack."
        )
    
    if not timestamp:
        raise WebhookSecurityError(
            "Missing X-Slack-Request-Timestamp header."
        )
    
    # ==================================
    # Validate timestamp to prevent replay attacks
    # ==================================
    try:
        request_time = int(timestamp)
        current_time = int(time.time())
        
        if abs(current_time - request_time) > max_age_seconds:
            raise WebhookSecurityError(
                f"Request timestamp too old. "
                f"Age: {current_time - request_time}s, max: {max_age_seconds}s. "
                f"This may be a replay attack."
            )
    except ValueError:
        raise WebhookSecurityError(f"Invalid timestamp format: {timestamp}")
    
    # ==================================
    # Construct base string: v0:timestamp:payload
    # ==================================
    base_string = f"v0:{timestamp}:{payload.decode('utf-8')}"
    
    # ==================================
    # Compute HMAC-SHA256
    # ==================================
    computed = hmac.new(
        signing_secret.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # ==================================
    # Compare signatures (format: "v0=<hash>")
    # ==================================
    expected_signature = f"v0={computed}"
    
    if not hmac.compare_digest(expected_signature, signature):
        raise WebhookSecurityError(
            "Invalid Slack signature. "
            "This request may be spoofed or the signing secret is incorrect."
        )
    
    return True


# =============================================================================
'''
    verify_ms_teams_token : Verify MS Teams JWT token (simplified)
    
    MS Teams uses JWT tokens from the Bot Framework. Full validation requires
    fetching signing keys from Microsoft and validating the JWT.
    
    This simplified version checks the Authorization header format.
    For production, use the Bot Framework SDK for full validation.
    
    Args:
        auth_header: Authorization header from request
        app_id: MS Teams app ID
        app_password: MS Teams app password
        
    Returns:
        True if token appears valid (simplified check)
        
    Raises:
        WebhookSecurityError: If token is missing or malformed
        
    Reference:
        https://docs.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-authentication
'''
# =============================================================================
def verify_ms_teams_token(
    auth_header: Optional[str],
    app_id: str,
    app_password: str
) -> bool:
    """
    Simplified MS Teams token validation.
    
    Note:
        This is a simplified check. For production, use the Bot Framework
        Connector SDK which handles full JWT validation including key rotation.
    
    Security:
        - Checks for Authorization header presence
        - Validates Bearer token format
        - Full JWT validation should be added for production
    """
    # ==================================
    # Check if credentials are configured
    # ==================================
    if not app_id or app_id == "YOUR_APP_ID_HERE":
        raise WebhookSecurityError(
            "MS Teams app ID not configured. "
            "Set MSTEAMS_APP_ID in config.py or environment."
        )
    
    if not app_password or app_password == "YOUR_APP_PASSWORD_HERE":
        raise WebhookSecurityError(
            "MS Teams app password not configured. "
            "Set MSTEAMS_APP_PASSWORD in config.py or environment."
        )
    
    # ==================================
    # Check for Authorization header
    # ==================================
    if not auth_header:
        raise WebhookSecurityError(
            "Missing Authorization header. "
            "This webhook may not be from MS Teams."
        )
    
    # ==================================
    # Validate Bearer token format
    # ==================================
    if not auth_header.startswith("Bearer "):
        raise WebhookSecurityError(
            f"Invalid Authorization format. Expected 'Bearer <token>', "
            f"got '{auth_header[:20]}...'"
        )
    
    # ==================================
    # Note: Full JWT validation requires Bot Framework SDK
    # For production, use: botbuilder-core for proper validation
    # ==================================
    # TODO: Add full JWT validation using Bot Framework SDK
    # This simplified version trusts the token format for now
    
    return True


# =============================================================================
'''
    Optional: Get secrets from environment or config
    
    These helper functions retrieve webhook secrets from environment variables
    or config, with clear error messages if not set.
'''
# =============================================================================

def get_whatsapp_app_secret() -> Optional[str]:
    """Get WhatsApp app secret from environment."""
    import os
    return os.environ.get('WHATSAPP_APP_SECRET')


def get_telegram_webhook_secret() -> Optional[str]:
    """Get Telegram webhook secret from environment."""
    import os
    return os.environ.get('TELEGRAM_WEBHOOK_SECRET')


def get_slack_signing_secret() -> Optional[str]:
    """Get Slack signing secret from environment."""
    import os
    return os.environ.get('SLACK_SIGNING_SECRET')


# =============================================================================
'''
    End of File : webhook_security.py
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
