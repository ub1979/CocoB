#!/usr/bin/env python3
# =============================================================================
'''
    File Name : run_slack.py

    Description : Standalone entry point for running the Slack bot.
                  Initializes all required components and starts the bot
                  in Socket Mode for real-time communication.

    Usage:
        python run_slack.py

    Environment Variables:
        SLACK_BOT_TOKEN - Your Slack bot token (xoxb-...) (required)
        SLACK_APP_TOKEN - Your Slack app token (xapp-...) (required)
        SLACK_SIGNING_SECRET - Your Slack signing secret (optional)

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
import os
import sys
import signal
from pathlib import Path

from coco_b import PROJECT_ROOT

import config
from coco_b.core.sessions import SessionManager
from coco_b.core.llm import LLMProviderFactory
from coco_b.core.router import MessageRouter
from coco_b.core.skills import SkillsManager
from coco_b.channels.slack_channel import SlackChannel, SlackConfig

# =============================================================================
# Global state for signal handling
# =============================================================================
slack_channel = None


# =============================================================================
# Signal Handler
# =============================================================================
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print("\nReceived shutdown signal. Stopping bot...")
    if slack_channel:
        asyncio.create_task(slack_channel.stop())
    sys.exit(0)


# =============================================================================
# Main Function
# =============================================================================
async def main():
    """Main entry point for Slack bot"""
    global slack_channel

    print("=" * 60)
    print("coco B - Slack Bot")
    print("=" * 60)

    # =========================================================================
    # Check for required tokens
    # =========================================================================
    bot_token = os.environ.get("SLACK_BOT_TOKEN", config.SLACK_BOT_TOKEN if hasattr(config, 'SLACK_BOT_TOKEN') else "")
    app_token = os.environ.get("SLACK_APP_TOKEN", config.SLACK_APP_TOKEN if hasattr(config, 'SLACK_APP_TOKEN') else "")
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", config.SLACK_SIGNING_SECRET if hasattr(config, 'SLACK_SIGNING_SECRET') else "")

    if not bot_token:
        print("\nError: SLACK_BOT_TOKEN not set!")
        print("\nTo get Slack tokens:")
        print("1. Go to https://api.slack.com/apps")
        print("2. Create a new app 'From scratch'")
        print("3. Go to 'OAuth & Permissions' and add these Bot Token Scopes:")
        print("   - app_mentions:read")
        print("   - chat:write")
        print("   - im:read")
        print("   - im:write")
        print("   - im:history")
        print("4. Install app to your workspace")
        print("5. Copy the 'Bot User OAuth Token' (starts with xoxb-)")
        print("\nThen set the environment variable:")
        print("  export SLACK_BOT_TOKEN='xoxb-your-token-here'")
        return

    if not app_token:
        print("\nError: SLACK_APP_TOKEN not set!")
        print("\nTo enable Socket Mode:")
        print("1. Go to your Slack app settings")
        print("2. Go to 'Socket Mode' and enable it")
        print("3. Generate an App-Level Token with 'connections:write' scope")
        print("4. Copy the token (starts with xapp-)")
        print("\nThen set the environment variable:")
        print("  export SLACK_APP_TOKEN='xapp-your-token-here'")
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
        Handle messages from Slack and route to AI.

        Args:
            channel: Channel name (slack)
            user_id: Slack user ID
            user_message: Message text
            chat_id: Slack channel ID
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
            session_key = session_manager.get_session_key("slack", user_id, chat_id)
            session_manager.reset_session(session_key)
            return None  # Response handled by channel

        # Handle built-in commands
        if user_message.startswith("/"):
            cmd = user_message.split()[0].lower()
            session_key = session_manager.get_session_key("slack", user_id, chat_id)

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
            channel="slack",
            user_id=user_id,
            user_message=user_message,
            chat_id=chat_id,
            user_name=user_name,
            skill_context=skill_context,
        ):
            response += chunk

        return response

    # =========================================================================
    # Create Slack channel
    # =========================================================================
    slack_config = SlackConfig(
        bot_token=bot_token,
        app_token=app_token,
        signing_secret=signing_secret,
        respond_to_mentions=True,
        respond_to_dms=True,
    )

    slack_channel = SlackChannel(
        config=slack_config,
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
    print("Starting Slack bot in Socket Mode...")
    print("=" * 60)
    print("\nBot is starting. Use Ctrl+C to stop.")
    print("\nTo use the bot:")
    print("1. Invite the bot to a channel: /invite @bot_name")
    print("2. Mention the bot: @bot_name hello!")
    print("3. Or send a direct message to the bot")
    print("\nSlash commands (if registered):")
    print("  /mrbot <message> - Chat with the bot")
    print("  /mrbot_help - Show help")
    print("  /mrbot_reset - Reset conversation")
    print("  /mrbot_stats - Show statistics")
    print("\n" + "=" * 60)

    try:
        await slack_channel.start()
    except Exception as e:
        print(f"\nError starting bot: {e}")
        print("\nCommon issues:")
        print("- Invalid bot token or app token")
        print("- Missing OAuth scopes")
        print("- Socket Mode not enabled")
        print("- Network connectivity issues")


# =============================================================================
# Entry Point
# =============================================================================
if __name__ == "__main__":
    asyncio.run(main())


# =============================================================================
'''
    End of File : run_slack.py

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
