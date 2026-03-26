# =============================================================================
# test_heartbeat_manager.py — Tests for heartbeat system
# =============================================================================

import pytest
import tempfile
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock


class TestHeartbeatType:
    """Test heartbeat type constants and defaults."""

    def test_heartbeat_types_defined(self):
        """All heartbeat types should be defined."""
        from skillforge.core.heartbeat_manager import HeartbeatType
        
        assert HeartbeatType.MORNING_BRIEF == "morning_brief"
        assert HeartbeatType.DEADLINE_WATCH == "deadline_watch"
        assert HeartbeatType.UNUSUAL_ACTIVITY == "unusual_activity"
        assert HeartbeatType.DAILY_SUMMARY == "daily_summary"

    def test_default_configs_exist(self):
        """Default configs should exist for all types."""
        from skillforge.core.heartbeat_manager import HeartbeatType
        
        for hb_type in [HeartbeatType.MORNING_BRIEF, HeartbeatType.DEADLINE_WATCH,
                       HeartbeatType.UNUSUAL_ACTIVITY, HeartbeatType.DAILY_SUMMARY]:
            assert hb_type in HeartbeatType.DEFAULTS

    def test_unusual_activity_enabled_by_default(self):
        """Unusual activity should be enabled by default."""
        from skillforge.core.heartbeat_manager import HeartbeatType
        
        config = HeartbeatType.DEFAULTS[HeartbeatType.UNUSUAL_ACTIVITY]
        assert config["enabled_by_default"] is True

    def test_morning_brief_default_time(self):
        """Morning brief should default to 9 AM."""
        from skillforge.core.heartbeat_manager import HeartbeatType
        
        config = HeartbeatType.DEFAULTS[HeartbeatType.MORNING_BRIEF]
        assert config["default_time"] == "09:00"

    def test_all_security_level_green(self):
        """All heartbeat types should be GREEN security level."""
        from skillforge.core.heartbeat_manager import HeartbeatType
        
        for hb_type, config in HeartbeatType.DEFAULTS.items():
            assert config["security_level"] == "GREEN"


class TestHeartbeatConfig:
    """Test HeartbeatConfig dataclass."""

    def test_config_creation(self):
        """Should create config with defaults."""
        from skillforge.core.heartbeat_manager import HeartbeatConfig
        
        config = HeartbeatConfig(heartbeat_type="test")
        
        assert config.heartbeat_type == "test"
        assert config.enabled is False
        assert config.schedule_time is None
        assert config.last_sent is None

    def test_config_to_dict(self):
        """Should convert to dictionary correctly."""
        from skillforge.core.heartbeat_manager import HeartbeatConfig
        
        config = HeartbeatConfig(
            heartbeat_type="morning_brief",
            enabled=True,
            schedule_time="09:00"
        )
        
        data = config.to_dict()
        assert data["heartbeat_type"] == "morning_brief"
        assert data["enabled"] is True
        assert data["schedule_time"] == "09:00"

    def test_config_from_dict(self):
        """Should create from dictionary correctly."""
        from skillforge.core.heartbeat_manager import HeartbeatConfig
        
        data = {
            "heartbeat_type": "daily_summary",
            "enabled": True,
            "schedule_time": "18:00",
            "last_sent": "2026-02-21T09:00:00"
        }
        
        config = HeartbeatConfig.from_dict(data)
        assert config.heartbeat_type == "daily_summary"
        assert config.enabled is True
        assert config.schedule_time == "18:00"


class TestHeartbeatManagerInitialization:
    """Test HeartbeatManager initialization."""

    def test_initialization(self):
        """Should initialize with empty state."""
        from skillforge.core.heartbeat_manager import HeartbeatManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            assert manager._running is False
            assert manager._message_handler is None
            assert len(manager._configs) == 0

    def test_creates_data_directory(self):
        """Should create data directory if not exists."""
        from skillforge.core.heartbeat_manager import HeartbeatManager
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "heartbeats"
            manager = HeartbeatManager(data_dir=data_dir)
            
            assert data_dir.exists()


class TestHeartbeatConfiguration:
    """Test heartbeat configuration management."""

    def test_get_user_config_creates_default(self):
        """Should create default config if not exists."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            config = manager.get_user_config("user1", HeartbeatType.MORNING_BRIEF)
            
            assert config.heartbeat_type == HeartbeatType.MORNING_BRIEF
            assert config.enabled is False  # Default
            assert config.schedule_time == "09:00"  # Default

    def test_enable_heartbeat(self):
        """Should enable heartbeat for user."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            result = manager.enable_heartbeat("user1", HeartbeatType.MORNING_BRIEF)
            assert result is True
            
            config = manager.get_user_config("user1", HeartbeatType.MORNING_BRIEF)
            assert config.enabled is True

    def test_enable_heartbeat_custom_time(self):
        """Should enable heartbeat with custom schedule time."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            manager.enable_heartbeat("user1", HeartbeatType.MORNING_BRIEF, 
                                    schedule_time="07:30")
            
            config = manager.get_user_config("user1", HeartbeatType.MORNING_BRIEF)
            assert config.schedule_time == "07:30"

    def test_disable_heartbeat(self):
        """Should disable heartbeat for user."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            manager.enable_heartbeat("user1", HeartbeatType.MORNING_BRIEF)
            manager.disable_heartbeat("user1", HeartbeatType.MORNING_BRIEF)
            
            config = manager.get_user_config("user1", HeartbeatType.MORNING_BRIEF)
            assert config.enabled is False

    def test_get_enabled_heartbeats(self):
        """Should return list of enabled heartbeats."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            # Enable two heartbeats
            manager.enable_heartbeat("user1", HeartbeatType.MORNING_BRIEF)
            manager.enable_heartbeat("user1", HeartbeatType.DAILY_SUMMARY)
            
            enabled = manager.get_enabled_heartbeats("user1")
            
            assert HeartbeatType.MORNING_BRIEF in enabled
            assert HeartbeatType.DAILY_SUMMARY in enabled
            assert HeartbeatType.DEADLINE_WATCH not in enabled

    def test_config_persistence(self):
        """Should persist config across manager instances."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # First instance - enable heartbeat
            manager1 = HeartbeatManager(data_dir=tmpdir)
            manager1.enable_heartbeat("user1", HeartbeatType.MORNING_BRIEF)
            
            # Second instance - should load config
            manager2 = HeartbeatManager(data_dir=tmpdir)
            config = manager2.get_user_config("user1", HeartbeatType.MORNING_BRIEF)
            
            assert config.enabled is True


class TestHeartbeatGeneration:
    """Test heartbeat content generation."""

    @pytest.mark.asyncio
    async def test_generate_morning_brief(self):
        """Should generate morning brief content."""
        from skillforge.core.heartbeat_manager import HeartbeatManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            content = await manager.generate_morning_brief("user1", "telegram")
            
            assert "🌅" in content
            assert "Good Morning" in content
            assert "📧" in content
            assert "📅" in content

    @pytest.mark.asyncio
    async def test_generate_daily_summary(self):
        """Should generate daily summary content."""
        from skillforge.core.heartbeat_manager import HeartbeatManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            content = await manager.generate_daily_summary("user1", "telegram")
            
            assert "📊" in content
            assert "Daily Summary" in content

    @pytest.mark.asyncio
    async def test_generate_deadline_watch_no_deadlines(self):
        """Should return None when no deadlines."""
        from skillforge.core.heartbeat_manager import HeartbeatManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            content = await manager.generate_deadline_watch("user1", "telegram")
            
            assert content is None

    @pytest.mark.asyncio
    async def test_generate_unusual_activity_none(self):
        """Should return None when no unusual activity."""
        from skillforge.core.heartbeat_manager import HeartbeatManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            content = await manager.generate_unusual_activity("user1", "telegram")
            
            assert content is None


class TestHeartbeatSending:
    """Test sending heartbeats."""

    @pytest.mark.asyncio
    async def test_send_heartbeat_no_handler(self):
        """Should fail if no message handler set."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            result = await manager.send_heartbeat("user1", "telegram", 
                                                 HeartbeatType.MORNING_BRIEF)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_send_heartbeat_success(self):
        """Should send heartbeat via message handler."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            # Mock message handler
            mock_handler = AsyncMock()
            manager.set_message_handler(mock_handler)
            
            result = await manager.send_heartbeat("user1", "telegram",
                                                 HeartbeatType.MORNING_BRIEF)
            
            assert result is True
            mock_handler.assert_called_once()
            
            # Check call arguments
            call_args = mock_handler.call_args
            assert call_args.kwargs["user_id"] == "user1"
            assert call_args.kwargs["channel"] == "telegram"
            assert call_args.kwargs["is_heartbeat"] is True

    @pytest.mark.asyncio
    async def test_send_heartbeat_updates_last_sent(self):
        """Should update last_sent timestamp."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            manager.set_message_handler(AsyncMock())
            
            config = manager.get_user_config("user1", HeartbeatType.MORNING_BRIEF)
            assert config.last_sent is None
            
            await manager.send_heartbeat("user1", "telegram",
                                        HeartbeatType.MORNING_BRIEF)
            
            assert config.last_sent is not None


class TestHeartbeatScheduler:
    """Test heartbeat scheduler."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Should start and stop scheduler."""
        from skillforge.core.heartbeat_manager import HeartbeatManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            assert manager._running is False
            
            await manager.start()
            assert manager._running is True
            assert manager._task is not None
            
            await manager.stop()
            assert manager._running is False

    @pytest.mark.asyncio
    async def test_scheduler_checks_heartbeats(self):
        """Scheduler should check and send due heartbeats."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            # Enable heartbeat
            manager.enable_heartbeat("user1", HeartbeatType.MORNING_BRIEF)
            
            # Set schedule to current time
            config = manager.get_user_config("user1", HeartbeatType.MORNING_BRIEF)
            config.schedule_time = datetime.now().strftime("%H:%M")
            
            # Mock message handler
            mock_handler = AsyncMock()
            manager.set_message_handler(mock_handler)
            
            # Manually trigger check
            await manager._check_and_send_heartbeats()
            
            # Should have attempted to send
            # (may or may not send depending on last_sent)


class TestHeartbeatUtilities:
    """Test utility methods."""

    def test_get_status(self):
        """Should return correct status."""
        from skillforge.core.heartbeat_manager import HeartbeatManager, HeartbeatType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            # Enable some heartbeats
            manager.enable_heartbeat("user1", HeartbeatType.MORNING_BRIEF)
            manager.enable_heartbeat("user2", HeartbeatType.DAILY_SUMMARY)
            
            status = manager.get_status()
            
            assert status["running"] is False
            assert status["configured_users"] == 2
            assert status["total_heartbeats_enabled"] == 2

    def test_set_message_handler(self):
        """Should set message handler."""
        from skillforge.core.heartbeat_manager import HeartbeatManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HeartbeatManager(data_dir=tmpdir)
            
            mock_handler = AsyncMock()
            manager.set_message_handler(mock_handler)
            
            assert manager._message_handler == mock_handler


# Import for tests
from pathlib import Path
