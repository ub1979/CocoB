#!/usr/bin/env python3
# =============================================================================
'''
    File Name : run_discord.py

    Description : Standalone entry point for running the Discord bot.
                  Initializes all required components and starts the bot
                  in standalone mode.

    Usage:
        python run_discord.py

    Environment Variables:
        DISCORD_BOT_TOKEN - Your Discord bot token (required)

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
import os
import sys
import signal
from pathlib import Path

from skillforge import PROJECT_ROOT

import config
from skillforge.core.sessions import SessionManager
from skillforge.core.llm import LLMProviderFactory
from skillforge.core.router import MessageRouter
from skillforge.core.skills import SkillsManager
from skillforge.channels.discord_channel import DiscordChannel, DiscordConfig

# =============================================================================
# Global state for signal handling
# =============================================================================
discord_channel = None


# =============================================================================
# Signal Handler
# =============================================================================
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print("\nReceived shutdown signal. Stopping bot...")
    if discord_channel:
        asyncio.create_task(discord_channel.stop())
    sys.exit(0)


# =============================================================================
# Main Function
# =============================================================================
async def main():
    """Main entry point for Discord bot"""
    global discord_channel

    print("=" * 60)
    print("SkillForge - Discord Bot")
    print("=" * 60)

    # =========================================================================
    # Check for bot token
    # =========================================================================
    bot_token = os.environ.get("DISCORD_BOT_TOKEN", config.DISCORD_BOT_TOKEN if hasattr(config, 'DISCORD_BOT_TOKEN') else "")

    if not bot_token:
        print("\nError: DISCORD_BOT_TOKEN not set!")
        print("\nTo get a Discord bot token:")
        print("1. Go to https://discord.com/developers/applications")
        print("2. Create a new application")
        print("3. Go to the Bot section and create a bot")
        print("4. Copy the token")
        print("5. Enable 'Message Content Intent' in Bot settings")
        print("\nThen set the environment variable:")
        print("  export DISCORD_BOT_TOKEN='your-token-here'")
        print("\nOr add to config.py:")
        print("  DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN', '')")
        return

    # =========================================================================
    # Initialize components
    # =========================================================================
    print("\nInitializing components...")

    # Session Manager
    session_manager = SessionManager(config.SESSION_DATA_DIR)
    print(f"  Session Manager: {config.SESSION_DATA_DIR}")

    # LLM Provider
    llm_config = config.LLM_PROVIDERS.get(config.LLM_PROVIDER, {})
    if not llm_config:
        print(f"  Error: LLM provider '{config.LLM_PROVIDER}' not found in config")
        return

    llm_provider = LLMProviderFactory.from_dict(llm_config)
    print(f"  LLM Provider: {llm_provider.provider_name}")
    print(f"  Model: {llm_provider.model_name}")

    # Message Router
    router = MessageRouter(session_manager, llm_provider)
    print("  Message Router: initialized")

    # Skills Manager (optional)
    skills_manager = None
    try:
        skills_manager = SkillsManager()
        skills_manager.load_all_skills()
        skill_count = len(skills_manager.get_all_skills())
        print(f"  Skills Manager: {skill_count} skills loaded")
        router.personality.skills_manager = skills_manager
    except Exception as e:
        print(f"  Skills Manager: not available ({e})")

    # =========================================================================
    # Create message handler
    # =========================================================================
    async def message_handler(
        channel: str,
        user_id: str,
        user_message: str,
        chat_id: str = None,
        user_name: str = None,
        is_skill: bool = False,
        skill_name: str = None,
        skill_args: str = None,
        is_command: bool = False,
        command: str = None,
        **kwargs,
    ) -> str:
        """
        Handle messages from Discord and route to AI.

        Args:
            channel: Channel name (discord)
            user_id: Discord user ID
            user_message: Message text
            chat_id: Discord channel ID
            user_name: User's display name
            is_skill: Whether this is a skill invocation
            skill_name: Name of skill to invoke
            skill_args: Arguments for skill
            is_command: Whether this is a built-in command
            command: Command name if is_command

        Returns:
            AI response text
        """
        # Handle reset command
        if is_command and command == "reset":
            session_key = session_manager.get_session_key("discord", user_id, chat_id)
            session_manager.reset_session(session_key)
            return None  # Response handled by channel

        # Handle built-in commands
        if user_message.startswith("/"):
            cmd = user_message.split()[0].lower()
            session_key = session_manager.get_session_key("discord", user_id, chat_id)

            if cmd in ["/reset", "/new"]:
                return router.handle_command(cmd, session_key)
            elif cmd in ["/stats", "/help", "/skills"]:
                return router.handle_command(cmd, session_key)

        # Check for skill invocation
        skill_context = None
        if is_skill and skill_name:
            skill_context = router.get_skill_context(skill_name)
            if skill_args:
                user_message = skill_args  # Use args as the actual message

        # Route to AI
        response = ""
        async for chunk in router.handle_message_stream(
            channel="discord",
            user_id=user_id,
            user_message=user_message,
            chat_id=chat_id,
            user_name=user_name,
            skill_context=skill_context,
        ):
            response += chunk

        return response

    # =========================================================================
    # Create Discord channel
    # =========================================================================
    discord_config = DiscordConfig(
        bot_token=bot_token,
        command_prefix=getattr(config, 'DISCORD_COMMAND_PREFIX', '!'),
        respond_to_mentions=True,
        respond_to_dms=True,
    )

    discord_channel = DiscordChannel(
        config=discord_config,
        message_handler=message_handler,
    )

    # =========================================================================
    # Setup signal handlers
    # =========================================================================
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # =========================================================================
    # Start bot
    # =========================================================================
    print("\n" + "=" * 60)
    print("Starting Discord bot...")
    print("=" * 60)
    print("\nBot is starting. Use Ctrl+C to stop.")
    print("\nTo invite the bot to your server:")
    print("1. Go to Discord Developer Portal")
    print("2. Select your application -> OAuth2 -> URL Generator")
    print("3. Select 'bot' and 'applications.commands' scopes")
    print("4. Select permissions: Send Messages, Read Message History")
    print("5. Copy the URL and open it to invite the bot")
    print("\n" + "=" * 60)

    try:
        await discord_channel.start()
    except Exception as e:
        print(f"\nError starting bot: {e}")
        print("\nCommon issues:")
        print("- Invalid bot token")
        print("- Missing 'Message Content Intent' in Discord settings")
        print("- Network connectivity issues")


# =============================================================================
# Entry Point
# =============================================================================
if __name__ == "__main__":
    asyncio.run(main())


# =============================================================================
'''
    End of File : run_discord.py

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
