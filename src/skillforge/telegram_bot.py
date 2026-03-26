#!/usr/bin/env python3
"""
SkillForge - Telegram Bot

Run SkillForge as a Telegram bot with persistent memory, skills, and MCP tools.

Usage:
    1. Set your Telegram bot token:
       export TELEGRAM_BOT_TOKEN="your_token_here"

    2. Run the bot:
       python telegram_bot.py

To get a bot token:
    1. Open Telegram and search for @BotFather
    2. Send /newbot and follow the instructions
    3. Copy the token

See TELEGRAM_SETUP.md for detailed instructions.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

from skillforge import PROJECT_ROOT

import config
from skillforge.core.sessions import SessionManager
from skillforge.core.router import MessageRouter
from skillforge.core.llm import LLMProviderFactory
from skillforge.core.skills import SkillsManager
from skillforge.channels.telegram import TelegramChannel, TelegramConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("skillforge_telegram")


class SkillForgeTelegramBot:
    """SkillForge Telegram Bot with full feature support."""

    def __init__(self):
        self.session_manager = None
        self.llm = None
        self.router = None
        self.skills_manager = None
        self.telegram = None
        self.mcp_manager = None
        self.current_provider = None

    def _get_saved_provider(self) -> str:
        """Get saved provider from secure storage (synced with desktop)."""
        try:
            storage_file = Path.home() / ".skillforge" / "secure_config.json"
            if storage_file.exists():
                import json
                with open(storage_file, 'r') as f:
                    data = json.load(f)
                    return data.get('current_provider', '')
        except Exception:
            pass
        return ''

    def _save_provider(self, provider_name: str):
        """Save provider to secure storage (syncs with desktop)."""
        try:
            storage_dir = Path.home() / ".skillforge"
            storage_dir.mkdir(parents=True, exist_ok=True)
            storage_file = storage_dir / "secure_config.json"

            data = {}
            if storage_file.exists():
                import json
                with open(storage_file, 'r') as f:
                    data = json.load(f)

            data['current_provider'] = provider_name
            import json
            with open(storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save provider: {e}")

    def switch_provider(self, provider_name: str) -> tuple:
        """Switch to a different LLM provider."""
        if provider_name not in config.LLM_PROVIDERS:
            available = ", ".join(config.LLM_PROVIDERS.keys())
            return False, f"Unknown provider: {provider_name}\nAvailable: {available}"

        try:
            provider_config = config.LLM_PROVIDERS[provider_name]
            new_llm = LLMProviderFactory.from_dict(provider_config)
            self.llm = new_llm
            self.router.llm = new_llm
            self.current_provider = provider_name
            self._save_provider(provider_name)
            return True, f"Switched to {new_llm.provider_name}: {new_llm.model_name}"
        except Exception as e:
            return False, f"Failed to switch: {str(e)}"

    def initialize(self):
        """Initialize all bot components."""
        logger.info("Initializing SkillForge Telegram bot...")

        # Initialize session manager
        self.session_manager = SessionManager(config.SESSION_DATA_DIR)
        logger.info("Session manager initialized")

        # Initialize LLM provider (use saved provider from desktop if available)
        saved_provider = self._get_saved_provider()
        provider_name = saved_provider or config.LLM_PROVIDER
        provider_config = config.LLM_PROVIDERS.get(provider_name, {})
        self.llm = LLMProviderFactory.from_dict(provider_config)
        self.current_provider = provider_name
        logger.info(f"LLM provider initialized: {provider_name}")

        # Initialize skills manager
        self.skills_manager = SkillsManager()
        skills = self.skills_manager.load_all_skills()
        logger.info(f"Skills loaded: {len(skills)} skills")

        # Initialize MCP manager first (needed by router for skills)
        mcp_manager = None
        try:
            from skillforge.core.mcp_client import MCPManager
            mcp_manager = MCPManager()
            mcp_manager.load_config()

            # Auto-connect enabled MCP servers for Telegram
            # (Unlike GUI where user manually connects)
            mcp_manager.connect_all_sync(timeout=30.0)
            connected_count = sum(1 for name in mcp_manager._server_configs if mcp_manager.is_connected(name))
            logger.info(f"MCP manager initialized: {connected_count} servers connected")
        except Exception as e:
            logger.warning(f"MCP not available: {e}")

        # Store MCP manager reference
        self.mcp_manager = mcp_manager

        # Initialize message router with MCP
        self.router = MessageRouter(
            session_manager=self.session_manager,
            llm_provider=self.llm,
            mcp_manager=mcp_manager,
        )
        logger.info("Message router initialized")

        return True

    async def handle_message(
        self,
        channel: str,
        user_id: str,
        user_message: str,
        chat_id: str = None,
        user_name: str = None,
        is_skill: bool = False,
        skill_name: str = None,
        skill_args: str = None,
        **kwargs
    ) -> str:
        """Handle incoming Telegram messages."""
        try:
            # Handle /provider command to switch LLM
            if user_message.lower().startswith("/provider"):
                parts = user_message.split(maxsplit=1)
                if len(parts) > 1:
                    provider_name = parts[1].strip()
                    success, msg = self.switch_provider(provider_name)
                    return f"{'✅' if success else '❌'} {msg}"
                else:
                    available = ", ".join(config.LLM_PROVIDERS.keys())
                    return f"📡 Current: {self.current_provider}\n\nAvailable: {available}\n\nUsage: /provider <name>"

            # Handle /status command
            if user_message.lower() == "/status":
                mcp_status = "No servers" if not self.mcp_manager else \
                    ", ".join([n for n in self.mcp_manager._server_configs if self.mcp_manager.is_connected(n)]) or "No servers"
                return (f"📊 **SkillForge Status**\n\n"
                       f"**LLM:** {self.current_provider}\n"
                       f"**MCP:** {mcp_status}\n"
                       f"**Skills:** {len(self.skills_manager.load_all_skills())}")

            # Handle the message through the router
            response = await self.router.handle_message(
                channel=channel,
                user_id=user_id,
                user_message=user_message,
                chat_id=chat_id,
                user_name=user_name,
            )
            return response
        except Exception as e:
            logger.error(f"Message handling error: {e}", exc_info=True)
            return "Sorry, something went wrong. Please try again."

    async def start(self):
        """Start the Telegram bot."""
        # Check for bot token
        bot_token = config.TELEGRAM_BOT_TOKEN
        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not set!")
            print("\n" + "=" * 60)
            print("ERROR: Telegram bot token not configured")
            print("=" * 60)
            print("\nTo set up your Telegram bot:")
            print("1. Open Telegram and search for @BotFather")
            print("2. Send /newbot and follow the instructions")
            print("3. Copy the token and set it:")
            print("\n   export TELEGRAM_BOT_TOKEN='your_token_here'")
            print("\nThen run this script again.")
            print("=" * 60 + "\n")
            return

        # Initialize components
        self.initialize()

        # Create Telegram channel
        tg_config = TelegramConfig(
            bot_token=bot_token,
            allowed_users=config.TELEGRAM_ALLOWED_USERS,
            webhook_url=config.TELEGRAM_WEBHOOK_URL,
            webhook_port=config.TELEGRAM_WEBHOOK_PORT,
        )

        self.telegram = TelegramChannel(
            config=tg_config,
            message_handler=self.handle_message,
        )

        # Initialize and get bot info
        await self.telegram.initialize()
        bot_info = await self.telegram.get_bot_info()

        if bot_info:
            print("\n" + "=" * 60)
            print("  SkillForge - Telegram Bot")
            print("=" * 60)
            print(f"  Bot: @{bot_info['username']}")
            print(f"  Name: {bot_info['first_name']}")
            print(f"  LLM: {config.LLM_PROVIDER}")
            print(f"  Skills: {len(self.skills_manager.load_all_skills())}")

            # Show MCP status
            if self.mcp_manager:
                connected = [name for name in self.mcp_manager._server_configs if self.mcp_manager.is_connected(name)]
                if connected:
                    print(f"  MCP: {', '.join(connected)}")
                else:
                    print("  MCP: No servers connected")
            else:
                print("  MCP: Not available")

            print("=" * 60)
            print("\n  Bot is running! Send a message to @" + bot_info['username'])
            print("  Press Ctrl+C to stop.\n")

        # Start polling or webhook
        if config.TELEGRAM_WEBHOOK_URL:
            await self.telegram.start_webhook()
        else:
            await self.telegram.start_polling()

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            await self.telegram.stop()
            print("Bot stopped.")

    async def stop(self):
        """Stop the bot gracefully."""
        if self.telegram:
            await self.telegram.stop()


async def main():
    """Main entry point."""
    bot = SkillForgeTelegramBot()
    await bot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
