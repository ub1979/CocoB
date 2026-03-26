# =============================================================================
'''
    File Name : slack_channel.py

    Description : Slack Integration using slack-bolt library.
                  Provides a safe, async channel for SkillForge to communicate
                  via Slack with support for commands, skills, DMs, mentions,
                  and conversation context using Socket Mode.

    Architecture:
        SkillForge (Python) -> slack-bolt -> Slack API (Socket Mode)

    Modifying it on 2026-02-09

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient

# =============================================================================
# Setup logging
# =============================================================================
logging.basicConfig(level=logging.INFO)


# =============================================================================
'''
    SlackConfig : Configuration dataclass for Slack bot settings
                  Stores all connection parameters and behavior options
'''
# =============================================================================
@dataclass
class SlackConfig:
    """Configuration for Slack bot connection"""
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-... (for socket mode)
    signing_secret: str = ""
    max_message_length: int = 4000  # Slack's recommended limit
    respond_to_mentions: bool = True
    respond_to_dms: bool = True
    allowed_channels: List[str] = field(default_factory=list)  # Empty = allow all
    allowed_users: List[str] = field(default_factory=list)  # Empty = allow all


# =============================================================================
'''
    SlackChannel : Main Slack channel integration class.
                   Uses slack-bolt library for async communication
                   with Slack API via Socket Mode.
'''
# =============================================================================
class SlackChannel:
    """
    Slack channel integration using slack-bolt.

    Features:
    - Async message handling via Socket Mode
    - Command support (/reset, /stats, /help)
    - Skill invocation via /skill-name
    - DM and mention support
    - Chunked message sending for long responses
    - Channel/User allowlists (optional)
    """

    # =========================================================================
    # Function __init__ -> Optional[SlackConfig], Optional[Callable] to None
    # =========================================================================
    def __init__(
        self,
        config: Optional[SlackConfig] = None,
        message_handler: Optional[Callable] = None,
    ):
        """
        Initialize Slack channel.

        Args:
            config: Slack bot configuration
            message_handler: Async function to handle incoming messages
        """
        self.config = config or SlackConfig()
        self.message_handler = message_handler
        self.is_running = False

        # Setup logging
        self.logger = logging.getLogger("slack_channel")

        # Validate tokens
        if not self.config.bot_token:
            self.logger.warning("No bot token provided. Set SLACK_BOT_TOKEN env var.")
        if not self.config.app_token:
            self.logger.warning("No app token provided. Set SLACK_APP_TOKEN env var.")

        # Create Slack app
        self.app = AsyncApp(
            token=self.config.bot_token,
            signing_secret=self.config.signing_secret or "placeholder",
        )

        # Store client reference
        self.client: Optional[AsyncWebClient] = None

        # Socket mode handler
        self._socket_handler: Optional[AsyncSocketModeHandler] = None

        # Bot user ID (set on startup)
        self.bot_user_id: Optional[str] = None

        # Setup event handlers
        self._setup_handlers()

    # =========================================================================
    # Function _setup_handlers -> None to None
    # =========================================================================
    def _setup_handlers(self):
        """Setup Slack event handlers"""

        # Handle app mentions
        @self.app.event("app_mention")
        async def handle_app_mention(event, say, client):
            if self.config.respond_to_mentions:
                await self._handle_mention(event, say, client)

        # Handle direct messages
        @self.app.event("message")
        async def handle_message(event, say, client):
            # Ignore bot messages
            if event.get("bot_id"):
                return

            # Ignore message subtypes (edits, deletions, etc.)
            if event.get("subtype"):
                return

            # Check if it's a DM
            channel_type = event.get("channel_type", "")
            is_dm = channel_type == "im"

            if is_dm and self.config.respond_to_dms:
                await self._handle_dm(event, say, client)

        # Handle slash commands
        @self.app.command("/mrbot")
        async def handle_slash_command(ack, command, say):
            await ack()
            await self._handle_slash_command(command, say)

        @self.app.command("/mrbot_reset")
        async def handle_reset_command(ack, command, say):
            await ack()
            await self._handle_reset(command, say)

        @self.app.command("/mrbot_stats")
        async def handle_stats_command(ack, command, say):
            await ack()
            await self._handle_stats(command, say)

        @self.app.command("/mrbot_help")
        async def handle_help_command(ack, command, say):
            await ack()
            await self._handle_help(command, say)

    # =========================================================================
    # Function _is_allowed -> Dict[str, Any] to bool
    # =========================================================================
    def _is_allowed(self, event: Dict[str, Any]) -> bool:
        """
        Check if message should be processed based on allowlists.

        Args:
            event: Slack event data

        Returns:
            True if allowed
        """
        # Check user allowlist
        if self.config.allowed_users:
            user_id = event.get("user", "")
            if user_id not in self.config.allowed_users:
                return False

        # Check channel allowlist
        if self.config.allowed_channels:
            channel_id = event.get("channel", "")
            if channel_id not in self.config.allowed_channels:
                return False

        return True

    # =========================================================================
    # Function _clean_message -> str to str
    # =========================================================================
    def _clean_message(self, text: str) -> str:
        """
        Clean message text by removing bot mentions and formatting.

        Args:
            text: Raw message text

        Returns:
            Cleaned message text
        """
        # Remove bot mention
        if self.bot_user_id:
            text = re.sub(f'<@{self.bot_user_id}>', '', text)

        # Clean up extra whitespace
        text = ' '.join(text.split())

        return text.strip()

    # =========================================================================
    # Function _handle_mention -> Dict[str, Any], Callable, AsyncWebClient to None
    # =========================================================================
    async def _handle_mention(
        self,
        event: Dict[str, Any],
        say: Callable,
        client: AsyncWebClient,
    ):
        """
        Handle app mention events.

        Args:
            event: Slack event data
            say: Function to send messages
            client: Slack web client
        """
        if not self._is_allowed(event):
            return

        text = self._clean_message(event.get("text", ""))
        await self._process_message(event, say, client, text)

    # =========================================================================
    # Function _handle_dm -> Dict[str, Any], Callable, AsyncWebClient to None
    # =========================================================================
    async def _handle_dm(
        self,
        event: Dict[str, Any],
        say: Callable,
        client: AsyncWebClient,
    ):
        """
        Handle direct message events.

        Args:
            event: Slack event data
            say: Function to send messages
            client: Slack web client
        """
        if not self._is_allowed(event):
            return

        text = event.get("text", "")

        # Check for command-like messages
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command = parts[0][1:].lower()
            args = parts[1] if len(parts) > 1 else ""

            if command == "reset":
                await self._handle_reset_dm(event, say)
                return
            elif command == "stats":
                await self._handle_stats_dm(event, say)
                return
            elif command == "help":
                await self._handle_help_dm(event, say)
                return
            else:
                # Treat as skill invocation
                await self._process_message(
                    event, say, client, text,
                    is_skill=True,
                    skill_name=command,
                    skill_args=args,
                )
                return

        await self._process_message(event, say, client, text)

    # =========================================================================
    # Function _process_message -> Dict[str, Any], Callable, AsyncWebClient, str, bool, Optional[str], Optional[str] to None
    # =========================================================================
    async def _process_message(
        self,
        event: Dict[str, Any],
        say: Callable,
        client: AsyncWebClient,
        user_message: str,
        is_skill: bool = False,
        skill_name: Optional[str] = None,
        skill_args: Optional[str] = None,
    ):
        """
        Process a message and send response.

        Args:
            event: Slack event data
            say: Function to send messages
            client: Slack web client
            user_message: The message text
            is_skill: Whether this is a skill invocation
            skill_name: Name of the skill if applicable
            skill_args: Arguments for the skill
        """
        if not self.message_handler:
            await say("Sorry, the bot is not fully configured yet.")
            return

        user_id = event.get("user", "")
        channel_id = event.get("channel", "")

        # Get user info for display name
        user_name = user_id
        try:
            user_info = await client.users_info(user=user_id)
            if user_info.get("ok"):
                user_name = user_info["user"].get("real_name", user_id)
        except Exception:
            pass

        try:
            response = await self.message_handler(
                channel="slack",
                user_id=user_id,
                user_message=user_message,
                chat_id=channel_id,
                user_name=user_name,
                is_skill=is_skill,
                skill_name=skill_name,
                skill_args=skill_args,
            )

            if response:
                await self.send_message(channel_id, response, say=say)

        except Exception as e:
            self.logger.error(f"Message handler error: {e}", exc_info=True)
            await say("Sorry, something went wrong. Please try again.")

    # =========================================================================
    # Function _handle_slash_command -> Dict[str, Any], Callable to None
    # =========================================================================
    async def _handle_slash_command(
        self,
        command: Dict[str, Any],
        say: Callable,
    ):
        """
        Handle /mrbot slash command.

        Args:
            command: Slack command data
            say: Function to send messages
        """
        text = command.get("text", "").strip()
        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")
        user_name = command.get("user_name", user_id)

        if not text:
            await say(
                f"Usage: `/mrbot <message>` - Chat with the bot\n"
                f"Other commands: `/mrbot_help`, `/mrbot_reset`, `/mrbot_stats`"
            )
            return

        if not self.message_handler:
            await say("Sorry, the bot is not fully configured yet.")
            return

        try:
            response = await self.message_handler(
                channel="slack",
                user_id=user_id,
                user_message=text,
                chat_id=channel_id,
                user_name=user_name,
            )

            if response:
                await self.send_message(channel_id, response, say=say)

        except Exception as e:
            self.logger.error(f"Slash command error: {e}", exc_info=True)
            await say("Sorry, something went wrong. Please try again.")

    # =========================================================================
    # Function _handle_reset -> Dict[str, Any], Callable to None
    # =========================================================================
    async def _handle_reset(
        self,
        command: Dict[str, Any],
        say: Callable,
    ):
        """Handle /mrbot_reset slash command"""
        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")
        user_name = command.get("user_name", user_id)

        if self.message_handler:
            try:
                await self.message_handler(
                    channel="slack",
                    user_id=user_id,
                    user_message="/reset",
                    chat_id=channel_id,
                    user_name=user_name,
                    is_command=True,
                    command="reset",
                )
            except Exception as e:
                self.logger.error(f"Reset handler error: {e}")

        await say("Conversation reset! Starting fresh.")

    # =========================================================================
    # Function _handle_reset_dm -> Dict[str, Any], Callable to None
    # =========================================================================
    async def _handle_reset_dm(
        self,
        event: Dict[str, Any],
        say: Callable,
    ):
        """Handle /reset in DM"""
        user_id = event.get("user", "")
        channel_id = event.get("channel", "")

        if self.message_handler:
            try:
                await self.message_handler(
                    channel="slack",
                    user_id=user_id,
                    user_message="/reset",
                    chat_id=channel_id,
                    user_name=user_id,
                    is_command=True,
                    command="reset",
                )
            except Exception as e:
                self.logger.error(f"Reset handler error: {e}")

        await say("Conversation reset! Starting fresh.")

    # =========================================================================
    # Function _handle_stats -> Dict[str, Any], Callable to None
    # =========================================================================
    async def _handle_stats(
        self,
        command: Dict[str, Any],
        say: Callable,
    ):
        """Handle /mrbot_stats slash command"""
        user_id = command.get("user_id", "")
        channel_id = command.get("channel_id", "")

        stats_message = (
            "*Session Statistics*\n\n"
            f"- User ID: `{user_id}`\n"
            f"- Channel ID: `{channel_id}`\n"
            "- Channel: Slack"
        )

        await say(stats_message)

    # =========================================================================
    # Function _handle_stats_dm -> Dict[str, Any], Callable to None
    # =========================================================================
    async def _handle_stats_dm(
        self,
        event: Dict[str, Any],
        say: Callable,
    ):
        """Handle /stats in DM"""
        user_id = event.get("user", "")
        channel_id = event.get("channel", "")

        stats_message = (
            "*Session Statistics*\n\n"
            f"- User ID: `{user_id}`\n"
            f"- Channel ID: `{channel_id}`\n"
            "- Channel: Slack"
        )

        await say(stats_message)

    # =========================================================================
    # Function _handle_help -> Dict[str, Any], Callable to None
    # =========================================================================
    async def _handle_help(
        self,
        command: Dict[str, Any],
        say: Callable,
    ):
        """Handle /mrbot_help slash command"""
        help_message = (
            "*Available Commands*\n\n"
            "- `/mrbot <message>` - Chat with the bot\n"
            "- `/mrbot_help` - Show this help message\n"
            "- `/mrbot_reset` - Reset conversation history\n"
            "- `/mrbot_stats` - Show session statistics\n\n"
            "*Other ways to chat:*\n"
            "- Mention @skillforge in a channel\n"
            "- Send a direct message\n\n"
            "*Skills (in DM):*\n"
            "- `/commit` - Help with git commits\n"
            "- `/search` - Search the web\n"
            "- `/explain` - Explain code"
        )

        await say(help_message)

    # =========================================================================
    # Function _handle_help_dm -> Dict[str, Any], Callable to None
    # =========================================================================
    async def _handle_help_dm(
        self,
        event: Dict[str, Any],
        say: Callable,
    ):
        """Handle /help in DM"""
        help_message = (
            "*Available Commands*\n\n"
            "- `/help` - Show this help message\n"
            "- `/reset` - Reset conversation history\n"
            "- `/stats` - Show session statistics\n"
            "- `/memory` - Show what I remember about you\n"
            "- `/forget` - Clear all my memories of you\n"
            "- `/forget [topic]` - Forget specific memories\n\n"
            "*Skills:*\n"
            "- `/commit` - Help with git commits\n"
            "- `/search` - Search the web\n"
            "- `/explain` - Explain code\n\n"
            "Just type a message to start chatting!"
        )

        await say(help_message)

    # =========================================================================
    # Function send_message -> str, str, Optional[Callable] to bool
    # =========================================================================
    async def send_message(
        self,
        channel_id: str,
        text: str,
        say: Optional[Callable] = None,
    ) -> bool:
        """
        Send a message to a channel.

        Args:
            channel_id: Target channel ID
            text: Message text
            say: Optional say function from event handler

        Returns:
            True if successful
        """
        try:
            # Split long messages
            if len(text) > self.config.max_message_length:
                return await self.send_chunked_message(channel_id, text, say)

            if say:
                await say(text)
            elif self.client:
                await self.client.chat_postMessage(
                    channel=channel_id,
                    text=text,
                )
            else:
                self.logger.error("No client or say function available")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Send error: {e}")
            return False

    # =========================================================================
    # Function send_chunked_message -> str, str, Optional[Callable] to bool
    # =========================================================================
    async def send_chunked_message(
        self,
        channel_id: str,
        text: str,
        say: Optional[Callable] = None,
    ) -> bool:
        """
        Send a long message in chunks.

        Args:
            channel_id: Target channel ID
            text: Long message text
            say: Optional say function from event handler

        Returns:
            True if all chunks sent successfully
        """
        max_len = self.config.max_message_length - 20  # Leave room for chunk indicator
        chunks = []

        # Split by paragraphs first for cleaner breaks
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_len:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Handle single paragraph longer than max
                if len(para) > max_len:
                    for i in range(0, len(para), max_len):
                        chunks.append(para[i:i + max_len])
                    current_chunk = ""
                else:
                    current_chunk = para + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # Send each chunk
        for i, chunk in enumerate(chunks):
            prefix = f"[{i + 1}/{len(chunks)}]\n" if len(chunks) > 1 else ""

            try:
                if say:
                    await say(prefix + chunk)
                elif self.client:
                    await self.client.chat_postMessage(
                        channel=channel_id,
                        text=prefix + chunk,
                    )

                # Small delay between chunks
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.error(f"Chunk send error: {e}")
                return False

        return True

    # =========================================================================
    # Function start -> None to None
    # =========================================================================
    async def start(self):
        """Start the Slack bot using Socket Mode"""
        if not self.config.bot_token:
            raise ValueError("Bot token is required")
        if not self.config.app_token:
            raise ValueError("App token is required for Socket Mode")

        self.logger.info("Starting Slack bot in Socket Mode...")

        # Create socket mode handler
        self._socket_handler = AsyncSocketModeHandler(
            self.app,
            self.config.app_token,
        )

        # Get bot user ID
        self.client = self.app.client
        try:
            auth_response = await self.client.auth_test()
            self.bot_user_id = auth_response.get("user_id")
            bot_name = auth_response.get("user")
            self.logger.info(f"Authenticated as {bot_name} ({self.bot_user_id})")
        except Exception as e:
            self.logger.error(f"Auth test failed: {e}")

        self.is_running = True
        await self._socket_handler.start_async()

    # =========================================================================
    # Function stop -> None to None
    # =========================================================================
    async def stop(self):
        """Stop the Slack bot gracefully"""
        if self._socket_handler and self.is_running:
            self.logger.info("Stopping Slack bot...")
            await self._socket_handler.close_async()
            self.is_running = False
            self.logger.info("Slack bot stopped")

    # =========================================================================
    # Function get_status -> None to Dict[str, Any]
    # =========================================================================
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        return {
            "running": self.is_running,
            "has_bot_token": bool(self.config.bot_token),
            "has_app_token": bool(self.config.app_token),
            "bot_user_id": self.bot_user_id,
        }

    # =========================================================================
    # Function get_bot_info -> None to Optional[Dict[str, Any]]
    # =========================================================================
    async def get_bot_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the bot"""
        if not self.client:
            return None

        try:
            auth_response = await self.client.auth_test()
            return {
                "user_id": auth_response.get("user_id"),
                "user": auth_response.get("user"),
                "team_id": auth_response.get("team_id"),
                "team": auth_response.get("team"),
                "url": auth_response.get("url"),
            }
        except Exception as e:
            self.logger.error(f"Get bot info error: {e}")
            return None


# =============================================================================
# Factory Function
# =============================================================================

def create_slack_channel(
    bot_token: str,
    app_token: str,
    message_handler: Optional[Callable] = None,
    signing_secret: str = "",
    allowed_users: Optional[List[str]] = None,
    allowed_channels: Optional[List[str]] = None,
) -> SlackChannel:
    """
    Create a configured SlackChannel instance.

    Args:
        bot_token: Slack bot token (xoxb-...)
        app_token: Slack app token (xapp-...) for Socket Mode
        message_handler: Async function to handle messages
        signing_secret: Slack signing secret
        allowed_users: List of allowed user IDs
        allowed_channels: List of allowed channel IDs

    Returns:
        Configured SlackChannel
    """
    config = SlackConfig(
        bot_token=bot_token,
        app_token=app_token,
        signing_secret=signing_secret,
        allowed_users=allowed_users or [],
        allowed_channels=allowed_channels or [],
    )

    return SlackChannel(config=config, message_handler=message_handler)


# =============================================================================
# Standalone Test Section
# =============================================================================
async def main():
    """Test Slack bot connection"""
    import os

    print("Slack Channel Test")
    print("=" * 40)

    # Get tokens from environment
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")

    if not bot_token:
        print("\nError: SLACK_BOT_TOKEN environment variable not set")
        print("\nTo get tokens:")
        print("1. Go to https://api.slack.com/apps")
        print("2. Create a new app from scratch")
        print("3. Go to 'OAuth & Permissions' and add scopes:")
        print("   - app_mentions:read")
        print("   - chat:write")
        print("   - im:read")
        print("   - im:write")
        print("   - im:history")
        print("4. Install app to workspace and copy Bot Token")
        print("5. Go to 'Socket Mode' and enable it")
        print("6. Generate and copy App Token with connections:write scope")
        return

    if not app_token:
        print("\nError: SLACK_APP_TOKEN environment variable not set")
        print("Enable Socket Mode in your Slack app settings.")
        return

    async def test_handler(
        channel: str,
        user_id: str,
        user_message: str,
        chat_id: str = None,
        user_name: str = None,
        **kwargs,
    ) -> str:
        """Simple echo handler for testing"""
        print(f"Received from {user_name or user_id}: {user_message}")
        return f"Echo: {user_message}"

    # Create and start bot
    slack_bot = create_slack_channel(
        bot_token=bot_token,
        app_token=app_token,
        message_handler=test_handler,
    )

    print("\nStarting bot in Socket Mode...")
    print("Mention the bot or DM it to test.")
    print("Press Ctrl+C to exit.\n")

    try:
        await slack_bot.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await slack_bot.stop()


if __name__ == "__main__":
    asyncio.run(main())


# =============================================================================
'''
    End of File : slack_channel.py

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
