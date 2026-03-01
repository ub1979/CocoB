# =============================================================================
'''
    File Name : telegram.py

    Description : Telegram Integration using python-telegram-bot library.
                  Provides a safe, async channel for mr_bot to communicate
                  via Telegram with support for commands, skills, and
                  conversation context.

    Architecture:
        mr_bot (Python) → python-telegram-bot → Telegram Bot API

    Modifying it on 2026-02-07

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

from telegram import Update, Bot
from telegram.error import Conflict
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode, ChatAction


# =============================================================================
'''
    TelegramConfig : Configuration dataclass for Telegram bot settings
                     Stores all connection parameters and behavior options
'''
# =============================================================================
@dataclass
class TelegramConfig:
    """Configuration for Telegram bot connection"""
    bot_token: str = ""
    webhook_url: Optional[str] = None  # None = use polling
    webhook_port: int = 8443
    allowed_users: List[str] = field(default_factory=list)  # Empty = allow all
    max_message_length: int = 4096  # Telegram's limit
    send_typing_indicator: bool = True
    parse_mode: str = "Markdown"


# =============================================================================
'''
    TelegramChannel : Main Telegram channel integration class.
                      Uses python-telegram-bot library for safe, async
                      communication with Telegram Bot API.
'''
# =============================================================================
class TelegramChannel:
    """
    Telegram channel integration using python-telegram-bot.

    Features:
    - Async message handling
    - Command support (/start, /help, /reset, /stats)
    - Skill invocation via /skill-name
    - Typing indicators
    - User allowlist (optional)
    - Chunked message sending for long responses
    """

    # =========================================================================
    # =========================================================================
    # Function __init__ -> Optional[TelegramConfig], Optional[Callable] to None
    # =========================================================================
    # =========================================================================
    def __init__(
        self,
        config: Optional[TelegramConfig] = None,
        message_handler: Optional[Callable] = None,
    ):
        """
        Initialize Telegram channel.

        Args:
            config: Telegram bot configuration
            message_handler: Async function to handle incoming messages
        """
        # ==================================
        # Initialize configuration
        self.config = config or TelegramConfig()
        self.message_handler = message_handler
        self.application: Optional[Application] = None
        self.is_running = False

        # ==================================
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("telegram")

        # ==================================
        # Validate token
        if not self.config.bot_token:
            self.logger.warning("No bot token provided. Set TELEGRAM_BOT_TOKEN env var.")

    # =========================================================================
    # =========================================================================
    # Function initialize -> None to Application
    # =========================================================================
    # =========================================================================
    async def initialize(self) -> Application:
        """
        Initialize the Telegram application with handlers.

        Returns:
            Configured Application instance
        """
        if not self.config.bot_token:
            raise ValueError("Bot token is required")

        # ==================================
        # Build application
        self.application = (
            Application.builder()
            .token(self.config.bot_token)
            .build()
        )

        # ==================================
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        self.application.add_handler(CommandHandler("reset", self._handle_reset))
        self.application.add_handler(CommandHandler("stats", self._handle_stats))

        # ==================================
        # Add message handler for regular text
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # ==================================
        # Add catch-all for skill commands (e.g., /commit, /search)
        self.application.add_handler(
            MessageHandler(filters.COMMAND, self._handle_skill_command)
        )

        self.logger.info("Telegram application initialized")
        return self.application

    # =========================================================================
    # =========================================================================
    # Function start_polling -> None to None
    # =========================================================================
    # =========================================================================
    async def start_polling(self):
        """
        Start the bot in polling mode.

        Use this for development or when webhooks aren't available.
        """
        if self.is_running:
            self.logger.warning("Telegram bot is already running — skipping duplicate start")
            return

        if not self.application:
            await self.initialize()

        self.logger.info("Starting Telegram bot in polling mode...")
        self.is_running = True

        # ==================================
        # Initialize and start polling
        try:
            await self.application.initialize()
            # Clear any stale webhook/polling sessions before starting
            try:
                await self.application.bot.delete_webhook(drop_pending_updates=True)
            except Exception:
                pass
            await self.application.start()
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
        except Conflict:
            self.is_running = False
            self.logger.error(
                "Another bot instance is already polling with this token. "
                "Stop the other instance first."
            )
            raise RuntimeError(
                "Another Telegram bot instance is already running with this token. "
                "Only one polling connection is allowed per bot token."
            )

        self.logger.info("Telegram bot is running (polling mode)")

    # =========================================================================
    # =========================================================================
    # Function start_webhook -> Optional[str], Optional[int] to None
    # =========================================================================
    # =========================================================================
    async def start_webhook(
        self,
        webhook_url: Optional[str] = None,
        port: Optional[int] = None,
    ):
        """
        Start the bot in webhook mode.

        Args:
            webhook_url: Public URL for webhook
            port: Port to listen on
        """
        if not self.application:
            await self.initialize()

        url = webhook_url or self.config.webhook_url
        listen_port = port or self.config.webhook_port

        if not url:
            raise ValueError("Webhook URL is required for webhook mode")

        self.logger.info(f"Starting Telegram bot in webhook mode on port {listen_port}...")
        self.is_running = True

        # ==================================
        # Initialize and start webhook
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_webhook(
            listen="0.0.0.0",
            port=listen_port,
            url_path="telegram",
            webhook_url=f"{url}/telegram",
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

        self.logger.info(f"Telegram bot is running (webhook mode at {url})")

    # =========================================================================
    # =========================================================================
    # Function stop -> None to None
    # =========================================================================
    # =========================================================================
    async def stop(self):
        """Stop the Telegram bot gracefully."""
        if self.application and self.is_running:
            self.logger.info("Stopping Telegram bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            self.is_running = False
            self.logger.info("Telegram bot stopped")

    # =========================================================================
    # =========================================================================
    # Function _is_user_allowed -> Update to bool
    # =========================================================================
    # =========================================================================
    def _is_user_allowed(self, update: Update) -> bool:
        """Check if user is allowed to use the bot."""
        # ==================================
        # Allow all if no allowlist configured
        if not self.config.allowed_users:
            return True

        # ==================================
        # Check username and user ID
        user = update.effective_user
        if not user:
            return False

        user_id = str(user.id)
        username = user.username or ""

        return (
            user_id in self.config.allowed_users or
            username in self.config.allowed_users or
            f"@{username}" in self.config.allowed_users
        )

    # =========================================================================
    # =========================================================================
    # Function _handle_start -> Update, ContextTypes.DEFAULT_TYPE to None
    # =========================================================================
    # =========================================================================
    async def _handle_start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle /start command."""
        if not self._is_user_allowed(update):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        user = update.effective_user
        welcome_message = (
            f"Hello {user.first_name}! 👋\n\n"
            "I'm your AI assistant with persistent memory.\n\n"
            "**Commands:**\n"
            "• /help - Show available commands\n"
            "• /reset - Reset conversation\n"
            "• /stats - Show session stats\n"
            "• /memory - Show what I remember about you\n"
            "• /forget - Clear my memories of you\n\n"
            "You can also use skills like /commit, /search, /explain\n\n"
            "Just send me a message to start chatting!"
        )

        await update.message.reply_text(
            welcome_message,
            parse_mode=ParseMode.MARKDOWN,
        )

    # =========================================================================
    # =========================================================================
    # Function _handle_help -> Update, ContextTypes.DEFAULT_TYPE to None
    # =========================================================================
    # =========================================================================
    async def _handle_help(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle /help command."""
        if not self._is_user_allowed(update):
            return

        help_message = (
            "**Available Commands:**\n\n"
            "• /start - Start the bot\n"
            "• /help - Show this help message\n"
            "• /reset - Reset conversation history\n"
            "• /stats - Show session statistics\n"
            "• /memory - Show what I remember about you\n"
            "• /forget - Clear all my memories of you\n"
            "• /forget [topic] - Forget specific memories\n\n"
            "**Skills:**\n"
            "• /commit - Help with git commits\n"
            "• /search - Search the web\n"
            "• /explain - Explain code\n\n"
            "Just type any message to chat with me!"
        )

        await update.message.reply_text(
            help_message,
            parse_mode=ParseMode.MARKDOWN,
        )

    # =========================================================================
    # =========================================================================
    # Function _handle_reset -> Update, ContextTypes.DEFAULT_TYPE to None
    # =========================================================================
    # =========================================================================
    async def _handle_reset(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle /reset command - reset conversation."""
        if not self._is_user_allowed(update):
            return

        user_id = str(update.effective_user.id)

        # ==================================
        # Call message handler with reset command
        if self.message_handler:
            try:
                await self.message_handler(
                    channel="telegram",
                    user_id=user_id,
                    user_message="/reset",
                    chat_id=str(update.effective_chat.id),
                    user_name=update.effective_user.first_name,
                    is_command=True,
                    command="reset",
                )
            except Exception as e:
                self.logger.error(f"Reset handler error: {e}")

        await update.message.reply_text(
            "✨ Conversation reset! Starting fresh.",
            parse_mode=ParseMode.MARKDOWN,
        )

    # =========================================================================
    # =========================================================================
    # Function _handle_stats -> Update, ContextTypes.DEFAULT_TYPE to None
    # =========================================================================
    # =========================================================================
    async def _handle_stats(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle /stats command - show session stats."""
        if not self._is_user_allowed(update):
            return

        user_id = str(update.effective_user.id)

        # ==================================
        # Get stats from message handler if available
        stats_message = "📊 **Session Statistics**\n\n"
        stats_message += f"• User ID: `{user_id}`\n"
        stats_message += f"• Chat ID: `{update.effective_chat.id}`\n"
        stats_message += "• Channel: Telegram\n"

        await update.message.reply_text(
            stats_message,
            parse_mode=ParseMode.MARKDOWN,
        )

    # =========================================================================
    # =========================================================================
    # Function _handle_skill_command -> Update, ContextTypes.DEFAULT_TYPE to None
    # =========================================================================
    # =========================================================================
    async def _handle_skill_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle skill commands like /commit, /search, etc."""
        if not self._is_user_allowed(update):
            return

        # ==================================
        # Extract command and arguments
        message_text = update.message.text
        parts = message_text.split(maxsplit=1)
        command = parts[0][1:]  # Remove leading /
        args = parts[1] if len(parts) > 1 else ""

        # ==================================
        # Pass to message handler as skill invocation
        await self._process_message(
            update=update,
            user_message=message_text,
            is_skill=True,
            skill_name=command,
            skill_args=args,
        )

    # =========================================================================
    # =========================================================================
    # Function _handle_message -> Update, ContextTypes.DEFAULT_TYPE to None
    # =========================================================================
    # =========================================================================
    async def _handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle regular text messages."""
        if not self._is_user_allowed(update):
            await update.message.reply_text("Sorry, you're not authorized to use this bot.")
            return

        await self._process_message(update=update, user_message=update.message.text)

    # =========================================================================
    # =========================================================================
    # Function _process_message -> Update, str, bool, Optional[str], Optional[str] to None
    # =========================================================================
    # =========================================================================
    async def _process_message(
        self,
        update: Update,
        user_message: str,
        is_skill: bool = False,
        skill_name: Optional[str] = None,
        skill_args: Optional[str] = None,
    ):
        """
        Process a message and send response.

        Args:
            update: Telegram update object
            user_message: The message text
            is_skill: Whether this is a skill invocation
            skill_name: Name of the skill if applicable
            skill_args: Arguments for the skill
        """
        if not self.message_handler:
            await update.message.reply_text(
                "Sorry, the bot is not fully configured yet."
            )
            return

        user = update.effective_user
        chat_id = str(update.effective_chat.id)
        user_id = str(user.id)

        # ==================================
        # Send typing indicator
        if self.config.send_typing_indicator:
            await update.effective_chat.send_action(ChatAction.TYPING)

        try:
            # ==================================
            # Call the message handler
            response = await self.message_handler(
                channel="telegram",
                user_id=user_id,
                user_message=user_message,
                chat_id=chat_id,
                user_name=user.first_name,
                is_skill=is_skill,
                skill_name=skill_name,
                skill_args=skill_args,
            )

            # ==================================
            # Send response if we got one
            if response:
                await self.send_message(chat_id, response, update=update)

        except Exception as e:
            self.logger.error(f"Message handler error: {e}", exc_info=True)
            await update.message.reply_text(
                "Sorry, something went wrong. Please try again."
            )

    # =========================================================================
    # =========================================================================
    # Function send_message -> str, str, Optional[Update] to bool
    # =========================================================================
    # =========================================================================
    async def send_message(
        self,
        chat_id: str,
        message: str,
        update: Optional[Update] = None,
    ) -> bool:
        """
        Send a message to a chat.

        Args:
            chat_id: Target chat ID
            message: Message text
            update: Optional update to reply to

        Returns:
            True if successful
        """
        try:
            # ==================================
            # Split long messages
            if len(message) > self.config.max_message_length:
                return await self.send_chunked_message(chat_id, message, update)

            # ==================================
            # Send via update reply or direct
            if update and update.message:
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN,
                )
            elif self.application:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                self.logger.error("No application available to send message")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Send error: {e}")
            # ==================================
            # Retry without markdown if parsing failed
            try:
                if update and update.message:
                    await update.message.reply_text(message)
                elif self.application:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                    )
                return True
            except Exception as e2:
                self.logger.error(f"Send retry error: {e2}")
                return False

    # =========================================================================
    # =========================================================================
    # Function send_chunked_message -> str, str, Optional[Update] to bool
    # =========================================================================
    # =========================================================================
    async def send_chunked_message(
        self,
        chat_id: str,
        message: str,
        update: Optional[Update] = None,
    ) -> bool:
        """
        Send a long message in chunks.

        Args:
            chat_id: Target chat ID
            message: Long message text
            update: Optional update to reply to

        Returns:
            True if all chunks sent successfully
        """
        max_len = self.config.max_message_length - 20  # Leave room for chunk indicator
        chunks = []

        # ==================================
        # Split by paragraphs first for cleaner breaks
        paragraphs = message.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_len:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # ==================================
                # Handle single paragraph longer than max
                if len(para) > max_len:
                    for i in range(0, len(para), max_len):
                        chunks.append(para[i:i + max_len])
                    current_chunk = ""
                else:
                    current_chunk = para + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # ==================================
        # Send each chunk
        for i, chunk in enumerate(chunks):
            prefix = f"[{i + 1}/{len(chunks)}]\n" if len(chunks) > 1 else ""

            try:
                if i == 0 and update and update.message:
                    await update.message.reply_text(
                        prefix + chunk,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                elif self.application:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=prefix + chunk,
                        parse_mode=ParseMode.MARKDOWN,
                    )

                # ==================================
                # Small delay between chunks
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.error(f"Chunk send error: {e}")
                # ==================================
                # Try without markdown
                try:
                    if self.application:
                        await self.application.bot.send_message(
                            chat_id=chat_id,
                            text=prefix + chunk,
                        )
                except Exception:
                    return False

        return True

    # =========================================================================
    # =========================================================================
    # Function get_status -> None to Dict[str, Any]
    # =========================================================================
    # =========================================================================
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        return {
            "running": self.is_running,
            "has_token": bool(self.config.bot_token),
            "webhook_mode": bool(self.config.webhook_url),
            "allowed_users_count": len(self.config.allowed_users),
        }

    # =========================================================================
    # =========================================================================
    # Function get_bot_info -> None to Optional[Dict[str, Any]]
    # =========================================================================
    # =========================================================================
    async def get_bot_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the bot from Telegram."""
        if not self.application:
            return None

        try:
            bot_info = await self.application.bot.get_me()
            return {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "can_join_groups": bot_info.can_join_groups,
                "can_read_all_group_messages": bot_info.can_read_all_group_messages,
            }
        except Exception as e:
            self.logger.error(f"Get bot info error: {e}")
            return None


# =============================================================================
# Factory Function
# =============================================================================

# =========================================================================
# =========================================================================
# Function create_telegram_channel -> str, Optional[Callable], Optional[List[str]] to TelegramChannel
# =========================================================================
# =========================================================================
def create_telegram_channel(
    bot_token: str,
    message_handler: Optional[Callable] = None,
    allowed_users: Optional[List[str]] = None,
) -> TelegramChannel:
    """
    Create a configured TelegramChannel instance.

    Args:
        bot_token: Telegram bot token from BotFather
        message_handler: Async function to handle messages
        allowed_users: List of allowed user IDs/usernames

    Returns:
        Configured TelegramChannel
    """
    config = TelegramConfig(
        bot_token=bot_token,
        allowed_users=allowed_users or [],
    )

    return TelegramChannel(config=config, message_handler=message_handler)


# =============================================================================
# Standalone Test Section
# =============================================================================

# =========================================================================
# =========================================================================
# Function main -> None to None
# =========================================================================
# =========================================================================
async def main():
    """Test Telegram bot connection."""
    import os

    print("Telegram Channel Test")
    print("=" * 40)

    # ==================================
    # Get token from environment
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("\nError: TELEGRAM_BOT_TOKEN environment variable not set")
        print("\nTo get a token:")
        print("1. Open Telegram and search for @BotFather")
        print("2. Send /newbot and follow the instructions")
        print("3. Copy the token and set it as TELEGRAM_BOT_TOKEN")
        return

    # =========================================================================
    # =========================================================================
    # Function test_handler -> ... to str
    # =========================================================================
    # =========================================================================
    async def test_handler(
        channel: str,
        user_id: str,
        user_message: str,
        chat_id: str = None,
        user_name: str = None,
        **kwargs,
    ) -> str:
        """Simple echo handler for testing."""
        print(f"Received from {user_name or user_id}: {user_message}")
        return f"Echo: {user_message}"

    # ==================================
    # Create and start bot
    tg = create_telegram_channel(
        bot_token=token,
        message_handler=test_handler,
    )

    await tg.initialize()

    # ==================================
    # Get bot info
    info = await tg.get_bot_info()
    if info:
        print(f"\nBot: @{info['username']} ({info['first_name']})")

    print("\nStarting bot in polling mode...")
    print("Send a message to the bot to test.")
    print("Press Ctrl+C to exit.\n")

    await tg.start_polling()

    try:
        # ==================================
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        await tg.stop()


# =========================================================================
# =========================================================================
# Entry Point
# =========================================================================
# =========================================================================
if __name__ == "__main__":
    asyncio.run(main())


# =============================================================================
'''
    End of File : telegram.py

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
