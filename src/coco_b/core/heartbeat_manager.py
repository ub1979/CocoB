# =============================================================================
'''
    File Name : heartbeat_manager.py
    
    Description : Proactive heartbeat system for agentic features.
                  Sends periodic check-ins to users with useful information
                  like morning briefings, deadline reminders, and alerts.
    
    Security Levels:
        - GREEN: All heartbeats are read-only, no authentication required
    
    Heartbeat Types:
        - morning_brief: Daily summary (emails, calendar, weather)
        - deadline_watch: Upcoming deadline reminders
        - unusual_activity: Important alerts and notifications
        - daily_summary: End-of-day recap
    
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
import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from coco_b.core.router import MessageRouter

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("heartbeat")


# =============================================================================
'''
    HeartbeatType : Types of proactive heartbeats available
'''
# =============================================================================
class HeartbeatType:
    """Available heartbeat types with their default configurations"""
    
    MORNING_BRIEF = "morning_brief"
    DEADLINE_WATCH = "deadline_watch"
    UNUSUAL_ACTIVITY = "unusual_activity"
    DAILY_SUMMARY = "daily_summary"
    
    # Default configurations for each heartbeat type
    DEFAULTS = {
        MORNING_BRIEF: {
            "enabled_by_default": False,
            "default_time": "09:00",
            "description": "Daily morning summary with emails, calendar, and reminders",
            "content": ["emails", "calendar", "reminders"],
            "security_level": "GREEN"  # No auth required
        },
        DEADLINE_WATCH: {
            "enabled_by_default": False,
            "check_interval_minutes": 60,
            "description": "Reminders for upcoming deadlines and due dates",
            "content": ["upcoming_deadlines", "overdue_items"],
            "security_level": "GREEN"
        },
        UNUSUAL_ACTIVITY: {
            "enabled_by_default": True,
            "description": "Alerts for important emails, calendar changes, and notifications",
            "content": ["important_emails", "calendar_changes", "mentions"],
            "security_level": "GREEN"
        },
        DAILY_SUMMARY: {
            "enabled_by_default": False,
            "default_time": "18:00",
            "description": "End-of-day recap of what happened today",
            "content": ["emails_sent", "meetings_attended", "tasks_completed"],
            "security_level": "GREEN"
        }
    }


# =============================================================================
'''
    HeartbeatConfig : Configuration for a user's heartbeat
'''
# =============================================================================
@dataclass
class HeartbeatConfig:
    """Configuration for a heartbeat type"""
    heartbeat_type: str
    enabled: bool = False
    schedule_time: Optional[str] = None  # HH:MM format for daily heartbeats
    check_interval_minutes: Optional[int] = None  # For interval-based heartbeats
    last_sent: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HeartbeatConfig":
        """Create from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
'''
    HeartbeatManager : Manages proactive heartbeats for users
    
    Features:
        - Schedule-based heartbeats (morning brief, daily summary)
        - Interval-based heartbeats (deadline watch)
        - Event-triggered heartbeats (unusual activity)
        - Per-user configuration
        - GREEN security level - no authentication required
'''
# =============================================================================
class HeartbeatManager:
    """
    Manages proactive heartbeat messages to users.
    All heartbeats are GREEN level (read-only, no auth required).
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize heartbeat manager.
        
        Args:
            data_dir: Directory to store heartbeat configurations
        """
        # ==================================
        # Setup data directory
        # ==================================
        if data_dir is None:
            from coco_b import PROJECT_ROOT
            self._data_dir = Path(PROJECT_ROOT) / "data" / "heartbeats"
        else:
            self._data_dir = Path(data_dir)
        
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # ==================================
        # User configurations storage
        # ==================================
        self._configs: Dict[str, Dict[str, HeartbeatConfig]] = {}
        
        # ==================================
        # Message handler (set later)
        # ==================================
        self._message_handler: Optional[Callable] = None
        self._router: Optional["MessageRouter"] = None
        
        # ==================================
        # Running state
        # ==================================
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # ==================================
        # Load existing configurations
        # ==================================
        self._load_configs()
    
    # =========================================================================
    # Configuration Management
    # =========================================================================
    
    def _get_user_config_file(self, user_id: str) -> Path:
        """Get config file path for a user"""
        return self._data_dir / f"{user_id}.json"
    
    def _load_configs(self):
        """Load all heartbeat configurations from disk"""
        if not self._data_dir.exists():
            return
        
        for config_file in self._data_dir.glob("*.json"):
            user_id = config_file.stem
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                
                self._configs[user_id] = {}
                for heartbeat_type, config_data in data.items():
                    self._configs[user_id][heartbeat_type] = HeartbeatConfig.from_dict(config_data)
                    
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load heartbeat config for {user_id}: {e}")
    
    def _save_user_config(self, user_id: str):
        """Save a user's heartbeat configuration to disk"""
        config_file = self._get_user_config_file(user_id)
        
        try:
            data = {
                hb_type: config.to_dict()
                for hb_type, config in self._configs.get(user_id, {}).items()
            }
            
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except IOError as e:
            logger.error(f"Failed to save heartbeat config for {user_id}: {e}")
    
    # =========================================================================
    # Public: Configuration Methods
    # =========================================================================
    
    def get_user_config(self, user_id: str, heartbeat_type: str) -> HeartbeatConfig:
        """
        Get configuration for a user's heartbeat.
        
        Args:
            user_id: User identifier
            heartbeat_type: Type of heartbeat
            
        Returns:
            HeartbeatConfig (creates default if not exists)
        """
        if user_id not in self._configs:
            self._configs[user_id] = {}
        
        if heartbeat_type not in self._configs[user_id]:
            # Create default config
            defaults = HeartbeatType.DEFAULTS.get(heartbeat_type, {})
            self._configs[user_id][heartbeat_type] = HeartbeatConfig(
                heartbeat_type=heartbeat_type,
                enabled=defaults.get("enabled_by_default", False),
                schedule_time=defaults.get("default_time"),
                check_interval_minutes=defaults.get("check_interval_minutes")
            )
        
        return self._configs[user_id][heartbeat_type]
    
    def enable_heartbeat(self, user_id: str, heartbeat_type: str, 
                         schedule_time: Optional[str] = None) -> bool:
        """
        Enable a heartbeat for a user.
        
        Args:
            user_id: User identifier
            heartbeat_type: Type of heartbeat to enable
            schedule_time: Optional custom time (HH:MM)
            
        Returns:
            True if enabled successfully
        """
        config = self.get_user_config(user_id, heartbeat_type)
        config.enabled = True
        
        if schedule_time:
            config.schedule_time = schedule_time
        
        self._save_user_config(user_id)
        logger.info(f"Enabled {heartbeat_type} for user {user_id}")
        return True
    
    def disable_heartbeat(self, user_id: str, heartbeat_type: str) -> bool:
        """
        Disable a heartbeat for a user.
        
        Args:
            user_id: User identifier
            heartbeat_type: Type of heartbeat to disable
            
        Returns:
            True if disabled successfully
        """
        config = self.get_user_config(user_id, heartbeat_type)
        config.enabled = False
        
        self._save_user_config(user_id)
        logger.info(f"Disabled {heartbeat_type} for user {user_id}")
        return True
    
    def get_enabled_heartbeats(self, user_id: str) -> List[str]:
        """
        Get list of enabled heartbeat types for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of enabled heartbeat type names
        """
        enabled = []
        for heartbeat_type in HeartbeatType.DEFAULTS.keys():
            config = self.get_user_config(user_id, heartbeat_type)
            if config.enabled:
                enabled.append(heartbeat_type)
        return enabled
    
    # =========================================================================
    # Public: Heartbeat Generation
    # =========================================================================
    
    async def generate_morning_brief(self, user_id: str, channel: str) -> str:
        """
        Generate morning brief heartbeat content.
        
        Args:
            user_id: User identifier
            channel: Channel to send to (for context)
            
        Returns:
            Formatted morning brief message
        """
        lines = ["🌅 **Good Morning!**"]
        
        # This would integrate with actual services in production
        # For now, provide a template that shows what's possible
        lines.extend([
            "",
            "📧 **Emails**: Check with `/email inbox`",
            "📅 **Calendar**: Check with `/calendar today`",
            "⏰ **Reminders**: You have pending tasks",
            "",
            "_Reply for details or use commands above_"
        ])
        
        return "\n".join(lines)
    
    async def generate_deadline_watch(self, user_id: str, channel: str) -> Optional[str]:
        """
        Generate deadline watch heartbeat (only if deadlines approaching).
        
        Args:
            user_id: User identifier
            channel: Channel to send to
            
        Returns:
            Message if deadlines found, None otherwise
        """
        # This would check actual deadlines in production
        # Return None if no urgent deadlines
        return None  # Placeholder - would check todo/scheduler
    
    async def generate_unusual_activity(self, user_id: str, channel: str) -> Optional[str]:
        """
        Generate unusual activity alert (only if activity detected).
        
        Args:
            user_id: User identifier
            channel: Channel to send to
            
        Returns:
            Message if unusual activity, None otherwise
        """
        # This would check for important emails, mentions, etc.
        return None  # Placeholder
    
    async def generate_daily_summary(self, user_id: str, channel: str) -> str:
        """
        Generate end-of-day summary.
        
        Args:
            user_id: User identifier
            channel: Channel to send to
            
        Returns:
            Formatted daily summary
        """
        lines = ["📊 **Daily Summary**"]
        
        lines.extend([
            "",
            "📧 Emails: _Check with /email_",
            "✅ Tasks: _Check with /todo list_",
            "📅 Tomorrow: _Check with /calendar tomorrow_",
            "",
            "_Have a great evening!_"
        ])
        
        return "\n".join(lines)
    
    # =========================================================================
    # Public: Sending Heartbeats
    # =========================================================================
    
    async def send_heartbeat(self, user_id: str, channel: str, 
                            heartbeat_type: str) -> bool:
        """
        Send a heartbeat to a user.
        
        Args:
            user_id: User identifier
            channel: Channel to send on
            heartbeat_type: Type of heartbeat to send
            
        Returns:
            True if sent successfully
        """
        if not self._message_handler:
            logger.warning("No message handler configured for heartbeats")
            return False
        
        # Generate content based on type
        content = None
        
        if heartbeat_type == HeartbeatType.MORNING_BRIEF:
            content = await self.generate_morning_brief(user_id, channel)
        
        elif heartbeat_type == HeartbeatType.DEADLINE_WATCH:
            content = await self.generate_deadline_watch(user_id, channel)
        
        elif heartbeat_type == HeartbeatType.UNUSUAL_ACTIVITY:
            content = await self.generate_unusual_activity(user_id, channel)
        
        elif heartbeat_type == HeartbeatType.DAILY_SUMMARY:
            content = await self.generate_daily_summary(user_id, channel)
        
        # Don't send if no content (e.g., no deadlines to report)
        if not content:
            return False
        
        try:
            # Send via message handler
            await self._message_handler(
                channel=channel,
                user_id=user_id,
                message=content,
                is_heartbeat=True
            )
            
            # Update last sent time
            config = self.get_user_config(user_id, heartbeat_type)
            config.last_sent = datetime.now().isoformat()
            self._save_user_config(user_id)
            
            logger.info(f"Sent {heartbeat_type} to user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send {heartbeat_type} to {user_id}: {e}")
            return False
    
    # =========================================================================
    # Scheduler Loop
    # =========================================================================
    
    async def start(self):
        """Start the heartbeat scheduler loop"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Heartbeat manager started")
    
    async def stop(self):
        """Stop the heartbeat scheduler loop"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat manager stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop - checks and sends heartbeats"""
        while self._running:
            try:
                await self._check_and_send_heartbeats()
                # Check every minute
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat scheduler: {e}")
                await asyncio.sleep(60)
    
    async def _check_and_send_heartbeats(self):
        """Check all users and send due heartbeats"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        
        for user_id, configs in self._configs.items():
            for heartbeat_type, config in configs.items():
                if not config.enabled:
                    continue
                
                should_send = False
                
                # Check schedule-based heartbeats
                if config.schedule_time:
                    if config.schedule_time == current_time:
                        # Check if already sent today
                        if config.last_sent:
                            last_sent = datetime.fromisoformat(config.last_sent)
                            if last_sent.date() == now.date():
                                continue  # Already sent today
                        should_send = True
                
                # Check interval-based heartbeats
                elif config.check_interval_minutes:
                    if config.last_sent:
                        last_sent = datetime.fromisoformat(config.last_sent)
                        minutes_since = (now - last_sent).total_seconds() / 60
                        if minutes_since >= config.check_interval_minutes:
                            should_send = True
                    else:
                        should_send = True  # Never sent, send now
                
                if should_send:
                    # Determine channel (default to first available or config)
                    channel = "telegram"  # Would be user-configured
                    await self.send_heartbeat(user_id, channel, heartbeat_type)
    
    # =========================================================================
    # Integration Methods
    # =========================================================================
    
    def set_message_handler(self, handler: Callable):
        """
        Set the message handler for sending heartbeats.
        
        Args:
            handler: Async function to handle messages
        """
        self._message_handler = handler
    
    def set_router(self, router: "MessageRouter"):
        """
        Set the message router for integration.
        
        Args:
            router: MessageRouter instance
        """
        self._router = router
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get heartbeat manager status"""
        return {
            "running": self._running,
            "configured_users": len(self._configs),
            "total_heartbeats_enabled": sum(
                1 for user_configs in self._configs.values()
                for config in user_configs.values()
                if config.enabled
            )
        }


# =============================================================================
'''
    End of File : heartbeat_manager.py
    
    Project : coco B - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
