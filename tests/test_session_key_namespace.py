# =============================================================================
# test_session_key_namespace.py — Tests for session key namespacing
# =============================================================================

import pytest
import tempfile


class TestSessionKeyNamespace:
    """Test that session keys are properly namespaced by channel."""

    def test_different_channels_same_user_id(self):
        """Same user ID on different channels should produce different session keys."""
        from coco_b.core.sessions import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(str(tmpdir))
            
            # Same user ID across different channels
            user_id = "12345"
            
            whatsapp_key = sm.get_session_key("whatsapp", user_id)
            telegram_key = sm.get_session_key("telegram", user_id)
            slack_key = sm.get_session_key("slack", user_id)
            msteams_key = sm.get_session_key("msteams", user_id)
            
            # All keys should be different
            keys = [whatsapp_key, telegram_key, slack_key, msteams_key]
            assert len(set(keys)) == 4, f"Session keys should be unique per channel: {keys}"
    
    def test_session_key_contains_channel(self):
        """Session key should contain the channel name."""
        from coco_b.core.sessions import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(str(tmpdir))
            
            key = sm.get_session_key("whatsapp", "user123")
            
            assert key.startswith("whatsapp:"), f"Session key should start with channel: {key}"
    
    def test_session_key_contains_chat_type(self):
        """Session key should contain chat type (direct or group)."""
        from coco_b.core.sessions import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(str(tmpdir))
            
            direct_key = sm.get_session_key("whatsapp", "user123")
            group_key = sm.get_session_key("whatsapp", "user123", chat_id="group456")
            
            assert ":direct:" in direct_key, f"Direct chat key should contain 'direct': {direct_key}"
            assert ":group:" in group_key, f"Group chat key should contain 'group': {group_key}"
    
    def test_session_key_contains_user_id(self):
        """Session key should contain the user ID."""
        from coco_b.core.sessions import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(str(tmpdir))
            
            key = sm.get_session_key("whatsapp", "user123")
            
            assert "user123" in key, f"Session key should contain user ID: {key}"
    
    def test_group_chat_includes_chat_id(self):
        """Group chat session key should include chat ID."""
        from coco_b.core.sessions import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(str(tmpdir))
            
            key = sm.get_session_key("whatsapp", "user123", chat_id="group456")
            
            assert "group456" in key, f"Group key should contain chat ID: {key}"
    
    def test_no_collision_between_platforms(self):
        """Ensure no collision between different messaging platforms."""
        from coco_b.core.sessions import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(str(tmpdir))
            
            # These could be the same person using same ID on different platforms
            platforms = ["whatsapp", "telegram", "slack", "discord", "msteams"]
            user_id = "123456789"
            
            keys = [sm.get_session_key(p, user_id) for p in platforms]
            
            # All should be unique
            assert len(set(keys)) == len(platforms), \
                f"Session keys should be unique across platforms: {keys}"
    
    def test_session_isolation(self):
        """Sessions for same user on different channels should be isolated."""
        from coco_b.core.sessions import SessionManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = SessionManager(str(tmpdir))
            
            # Create sessions for same user on different channels
            whatsapp_key = sm.get_session_key("whatsapp", "user123")
            telegram_key = sm.get_session_key("telegram", "user123")
            
            whatsapp_session = sm.get_or_create_session(whatsapp_key, "whatsapp", "user123")
            telegram_session = sm.get_or_create_session(telegram_key, "telegram", "user123")
            
            # Sessions should have different IDs
            assert whatsapp_session["sessionId"] != telegram_session["sessionId"], \
                "Sessions should be isolated by channel"
            
            # Add message to WhatsApp session
            sm.add_message(whatsapp_key, "user", "Hello from WhatsApp")
            
            # Telegram session should not see WhatsApp messages
            whatsapp_history = sm.get_conversation_history(whatsapp_key)
            telegram_history = sm.get_conversation_history(telegram_key)
            
            assert len(whatsapp_history) == 1, "WhatsApp should have 1 message"
            assert len(telegram_history) == 0, "Telegram should have 0 messages"
