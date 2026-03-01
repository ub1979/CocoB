# =============================================================================
'''
    File Name : discord_channel.py

    Description : Discord Integration using discord.py library.
                  Provides a safe, async channel for mr_bot to communicate
                  via Discord with support for commands, skills, DMs, mentions,
                  and conversation context.

    Architecture:
        mr_bot (Python) -> discord.py -> Discord API

    Modifying it on 2026-02-09

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List

import discord
from discord.ext import commands

# =============================================================================
# Setup logging
# =============================================================================
logging.basicConfig(level=logging.INFO)


# =============================================================================
'''
    DiscordConfig : Configuration dataclass for Discord bot settings
                    Stores all connection parameters and behavior options
'''
# =============================================================================
@dataclass
class DiscordConfig:
    """Configuration for Discord bot connection"""
    bot_token: str = ""
    command_prefix: str = "!"
    max_message_length: int = 2000  # Discord's limit
    respond_to_mentions: bool = True
    respond_to_dms: bool = True
    allowed_guilds: List[int] = field(default_factory=list)  # Empty = allow all
    allowed_users: List[int] = field(default_factory=list)  # Empty = allow all
    allowed_channels: List[int] = field(default_factory=list)  # Empty = allow all


# =============================================================================
'''
    DiscordChannel : Main Discord channel integration class.
                     Uses discord.py library for async communication
                     with Discord API.
'''
# =============================================================================
class DiscordChannel:
    """
    Discord channel integration using discord.py.

    Features:
    - Async message handling
    - Command support (/start, /help, /reset, /stats)
    - Skill invocation via /skill-name
    - DM and mention support
    - Chunked message sending for long responses
    - Guild/User/Channel allowlists (optional)
    """

    # =========================================================================
    # Function __init__ -> Optional[DiscordConfig], Optional[Callable] to None
    # =========================================================================
    def __init__(
        self,
        config: Optional[DiscordConfig] = None,
        message_handler: Optional[Callable] = None,
    ):
        """
        Initialize Discord channel.

        Args:
            config: Discord bot configuration
            message_handler: Async function to handle incoming messages
        """
        self.config = config or DiscordConfig()
        self.message_handler = message_handler
        self.is_running = False

        # Setup logging
        self.logger = logging.getLogger("discord_channel")

        # Validate token
        if not self.config.bot_token:
            self.logger.warning("No bot token provided. Set DISCORD_BOT_TOKEN env var.")

        # Setup intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        intents.guild_messages = True

        # Create bot instance
        self.bot = commands.Bot(
            command_prefix=self.config.command_prefix,
            intents=intents,
            help_command=None,  # We'll provide our own help
        )

        # Register event handlers
        self._setup_handlers()

    # =========================================================================
    # Function _setup_handlers -> None to None
    # =========================================================================
    def _setup_handlers(self):
        """Setup Discord event handlers"""

        @self.bot.event
        async def on_ready():
            self.is_running = True
            self.logger.info(f"Discord bot connected as {self.bot.user.name} ({self.bot.user.id})")
            self.logger.info(f"Connected to {len(self.bot.guilds)} guilds")

        @self.bot.event
        async def on_message(message: discord.Message):
            # Ignore own messages
            if message.author == self.bot.user:
                return

            # Ignore bots
            if message.author.bot:
                return

            # Check if this is a DM
            is_dm = isinstance(message.channel, discord.DMChannel)

            # Check if bot is mentioned
            is_mentioned = self.bot.user in message.mentions

            # Process commands first
            await self.bot.process_commands(message)

            # Handle message if:
            # 1. It's a DM and we respond to DMs
            # 2. Bot is mentioned and we respond to mentions
            # 3. Message starts with command prefix (handled by commands)
            should_respond = (
                (is_dm and self.config.respond_to_dms) or
                (is_mentioned and self.config.respond_to_mentions)
            )

            if should_respond and not message.content.startswith(self.config.command_prefix):
                await self._handle_message(message)

        @self.bot.event
        async def on_command_error(ctx: commands.Context, error):
            if isinstance(error, commands.CommandNotFound):
                # Check if it might be a skill invocation
                command_name = ctx.message.content.split()[0][len(self.config.command_prefix):]
                await self._handle_skill_command(ctx.message, command_name)
            else:
                self.logger.error(f"Command error: {error}")

        # Register built-in commands
        @self.bot.command(name="start")
        async def cmd_start(ctx: commands.Context):
            await self._handle_start(ctx)

        @self.bot.command(name="help")
        async def cmd_help(ctx: commands.Context):
            await self._handle_help(ctx)

        @self.bot.command(name="reset")
        async def cmd_reset(ctx: commands.Context):
            await self._handle_reset(ctx)

        @self.bot.command(name="stats")
        async def cmd_stats(ctx: commands.Context):
            await self._handle_stats(ctx)

    # =========================================================================
    # Function _is_allowed -> discord.Message to bool
    # =========================================================================
    def _is_allowed(self, message: discord.Message) -> bool:
        """
        Check if message should be processed based on allowlists.

        Args:
            message: Discord message

        Returns:
            True if allowed
        """
        # Check user allowlist
        if self.config.allowed_users:
            if message.author.id not in self.config.allowed_users:
                return False

        # Check guild allowlist (skip for DMs)
        if self.config.allowed_guilds and message.guild:
            if message.guild.id not in self.config.allowed_guilds:
                return False

        # Check channel allowlist (skip for DMs)
        if self.config.allowed_channels and not isinstance(message.channel, discord.DMChannel):
            if message.channel.id not in self.config.allowed_channels:
                return False

        return True

    # =========================================================================
    # Function _handle_start -> commands.Context to None
    # =========================================================================
    async def _handle_start(self, ctx: commands.Context):
        """Handle !start command"""
        if not self._is_allowed(ctx.message):
            return

        welcome_message = (
            f"Hello {ctx.author.display_name}!\n\n"
            "I'm your AI assistant with persistent memory.\n\n"
            "**Commands:**\n"
            f"- `{self.config.command_prefix}help` - Show available commands\n"
            f"- `{self.config.command_prefix}reset` - Reset conversation\n"
            f"- `{self.config.command_prefix}stats` - Show session stats\n\n"
            "You can also use skills like `!commit`, `!search`, `!explain`\n\n"
            "Just mention me or DM me to start chatting!"
        )

        await ctx.send(welcome_message)

    # =========================================================================
    # Function _handle_help -> commands.Context to None
    # =========================================================================
    async def _handle_help(self, ctx: commands.Context):
        """Handle !help command"""
        if not self._is_allowed(ctx.message):
            return

        help_message = (
            "**Available Commands:**\n\n"
            f"- `{self.config.command_prefix}start` - Start the bot\n"
            f"- `{self.config.command_prefix}help` - Show this help message\n"
            f"- `{self.config.command_prefix}reset` - Reset conversation history\n"
            f"- `{self.config.command_prefix}stats` - Show session statistics\n"
            f"- `{self.config.command_prefix}memory` - Show what I remember about you\n"
            f"- `{self.config.command_prefix}forget` - Clear all my memories of you\n"
            f"- `{self.config.command_prefix}forget [topic]` - Forget specific memories\n\n"
            "**Skills:**\n"
            f"- `{self.config.command_prefix}commit` - Help with git commits\n"
            f"- `{self.config.command_prefix}search` - Search the web\n"
            f"- `{self.config.command_prefix}explain` - Explain code\n\n"
            "Just mention me or DM me to chat!"
        )

        await ctx.send(help_message)

    # =========================================================================
    # Function _handle_reset -> commands.Context to None
    # =========================================================================
    async def _handle_reset(self, ctx: commands.Context):
        """Handle !reset command"""
        if not self._is_allowed(ctx.message):
            return

        user_id = str(ctx.author.id)

        if self.message_handler:
            try:
                await self.message_handler(
                    channel="discord",
                    user_id=user_id,
                    user_message="/reset",
                    chat_id=str(ctx.channel.id),
                    user_name=ctx.author.display_name,
                    is_command=True,
                    command="reset",
                )
            except Exception as e:
                self.logger.error(f"Reset handler error: {e}")

        await ctx.send("Conversation reset! Starting fresh.")

    # =========================================================================
    # Function _handle_stats -> commands.Context to None
    # =========================================================================
    async def _handle_stats(self, ctx: commands.Context):
        """Handle !stats command"""
        if not self._is_allowed(ctx.message):
            return

        user_id = str(ctx.author.id)

        stats_message = (
            "**Session Statistics**\n\n"
            f"- User ID: `{user_id}`\n"
            f"- Channel ID: `{ctx.channel.id}`\n"
            f"- Guild: {ctx.guild.name if ctx.guild else 'DM'}\n"
            "- Channel: Discord"
        )

        await ctx.send(stats_message)

    # =========================================================================
    # Function _handle_skill_command -> discord.Message, str to None
    # =========================================================================
    async def _handle_skill_command(
        self,
        message: discord.Message,
        command_name: str,
    ):
        """
        Handle skill commands like !commit, !search, etc.

        Args:
            message: Discord message
            command_name: Command name without prefix
        """
        if not self._is_allowed(message):
            return

        # Extract arguments
        parts = message.content.split(maxsplit=1)
        args = parts[1] if len(parts) > 1 else ""

        # Pass to message handler as skill invocation
        await self._process_message(
            message=message,
            user_message=message.content,
            is_skill=True,
            skill_name=command_name,
            skill_args=args,
        )

    # =========================================================================
    # Function _handle_message -> discord.Message to None
    # =========================================================================
    async def _handle_message(self, message: discord.Message):
        """
        Handle regular text messages.

        Args:
            message: Discord message
        """
        if not self._is_allowed(message):
            return

        # Remove bot mention from message content
        content = message.content
        if self.bot.user.mentioned_in(message):
            content = content.replace(f'<@{self.bot.user.id}>', '').strip()
            content = content.replace(f'<@!{self.bot.user.id}>', '').strip()

        await self._process_message(message=message, user_message=content)

    # =========================================================================
    # Function _process_message -> discord.Message, str, bool, Optional[str], Optional[str] to None
    # =========================================================================
    async def _process_message(
        self,
        message: discord.Message,
        user_message: str,
        is_skill: bool = False,
        skill_name: Optional[str] = None,
        skill_args: Optional[str] = None,
    ):
        """
        Process a message and send response.

        Args:
            message: Discord message
            user_message: The message text
            is_skill: Whether this is a skill invocation
            skill_name: Name of the skill if applicable
            skill_args: Arguments for the skill
        """
        if not self.message_handler:
            await message.channel.send("Sorry, the bot is not fully configured yet.")
            return

        user_id = str(message.author.id)
        chat_id = str(message.channel.id)
        user_name = message.author.display_name

        # Show typing indicator
        async with message.channel.typing():
            try:
                response = await self.message_handler(
                    channel="discord",
                    user_id=user_id,
                    user_message=user_message,
                    chat_id=chat_id,
                    user_name=user_name,
                    is_skill=is_skill,
                    skill_name=skill_name,
                    skill_args=skill_args,
                )

                if response:
                    await self.send_message(chat_id, response, message=message)

            except Exception as e:
                self.logger.error(f"Message handler error: {e}", exc_info=True)
                await message.channel.send("Sorry, something went wrong. Please try again.")

    # =========================================================================
    # Function send_message -> str, str, Optional[discord.Message] to bool
    # =========================================================================
    async def send_message(
        self,
        channel_id: str,
        text: str,
        message: Optional[discord.Message] = None,
    ) -> bool:
        """
        Send a message to a channel.

        Args:
            channel_id: Target channel ID
            text: Message text
            message: Optional message to reply to

        Returns:
            True if successful
        """
        try:
            # Split long messages
            if len(text) > self.config.max_message_length:
                return await self.send_chunked_message(channel_id, text, message)

            # Send via reply or to channel
            if message:
                await message.reply(text)
            else:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(text)
                else:
                    self.logger.error(f"Channel {channel_id} not found")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Send error: {e}")
            return False

    # =========================================================================
    # Function send_chunked_message -> str, str, Optional[discord.Message] to bool
    # =========================================================================
    async def send_chunked_message(
        self,
        channel_id: str,
        text: str,
        message: Optional[discord.Message] = None,
    ) -> bool:
        """
        Send a long message in chunks.

        Args:
            channel_id: Target channel ID
            text: Long message text
            message: Optional message to reply to

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

        # Get channel if needed
        channel = None
        if not message:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                self.logger.error(f"Channel {channel_id} not found")
                return False

        # Send each chunk
        for i, chunk in enumerate(chunks):
            prefix = f"[{i + 1}/{len(chunks)}]\n" if len(chunks) > 1 else ""

            try:
                if i == 0 and message:
                    await message.reply(prefix + chunk)
                elif channel:
                    await channel.send(prefix + chunk)
                elif message:
                    await message.channel.send(prefix + chunk)

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
        """Start the Discord bot"""
        if not self.config.bot_token:
            raise ValueError("Bot token is required")

        self.logger.info("Starting Discord bot...")
        await self.bot.start(self.config.bot_token)

    # =========================================================================
    # Function stop -> None to None
    # =========================================================================
    async def stop(self):
        """Stop the Discord bot gracefully"""
        if self.is_running:
            self.logger.info("Stopping Discord bot...")
            await self.bot.close()
            self.is_running = False
            self.logger.info("Discord bot stopped")

    # =========================================================================
    # Function get_status -> None to Dict[str, Any]
    # =========================================================================
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        return {
            "running": self.is_running,
            "has_token": bool(self.config.bot_token),
            "guilds": len(self.bot.guilds) if self.is_running else 0,
            "user": str(self.bot.user) if self.bot.user else None,
        }

    # =========================================================================
    # Function get_bot_info -> None to Optional[Dict[str, Any]]
    # =========================================================================
    async def get_bot_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the bot"""
        if not self.bot.user:
            return None

        return {
            "id": self.bot.user.id,
            "name": self.bot.user.name,
            "discriminator": self.bot.user.discriminator,
            "guilds": [{"id": g.id, "name": g.name} for g in self.bot.guilds],
        }


# =============================================================================
# Factory Function
# =============================================================================

def create_discord_channel(
    bot_token: str,
    message_handler: Optional[Callable] = None,
    command_prefix: str = "!",
    allowed_users: Optional[List[int]] = None,
    allowed_guilds: Optional[List[int]] = None,
) -> DiscordChannel:
    """
    Create a configured DiscordChannel instance.

    Args:
        bot_token: Discord bot token
        message_handler: Async function to handle messages
        command_prefix: Command prefix (default: !)
        allowed_users: List of allowed user IDs
        allowed_guilds: List of allowed guild IDs

    Returns:
        Configured DiscordChannel
    """
    config = DiscordConfig(
        bot_token=bot_token,
        command_prefix=command_prefix,
        allowed_users=allowed_users or [],
        allowed_guilds=allowed_guilds or [],
    )

    return DiscordChannel(config=config, message_handler=message_handler)


# =============================================================================
# Standalone Test Section
# =============================================================================
async def main():
    """Test Discord bot connection"""
    import os

    print("Discord Channel Test")
    print("=" * 40)

    # Get token from environment
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("\nError: DISCORD_BOT_TOKEN environment variable not set")
        print("\nTo get a token:")
        print("1. Go to https://discord.com/developers/applications")
        print("2. Create a new application")
        print("3. Go to Bot section and create a bot")
        print("4. Copy the token and set it as DISCORD_BOT_TOKEN")
        print("5. Enable 'Message Content Intent' in Bot settings")
        print("6. Invite bot with: OAuth2 -> URL Generator -> bot + applications.commands")
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
    discord_bot = create_discord_channel(
        bot_token=token,
        message_handler=test_handler,
    )

    print("\nStarting bot...")
    print("Mention the bot or DM it to test.")
    print("Press Ctrl+C to exit.\n")

    try:
        await discord_bot.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await discord_bot.stop()


if __name__ == "__main__":
    asyncio.run(main())


# =============================================================================
'''
    End of File : discord_channel.py

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
