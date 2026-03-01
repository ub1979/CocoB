# =============================================================================
'''
    File Name : handlers.py
    
    Description : Chat Message Handlers - Handles chat messages with streaming 
                  support. Supports skill invocations via /skill-name commands.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Imports
# =============================================================================

from typing import AsyncIterator, TYPE_CHECKING

if TYPE_CHECKING:
    from coco_b.ui.settings.state import AppState

# =============================================================================
'''
    chat_with_bot : Main chat handler function with streaming support
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function chat_with_bot -> str, list, str, AppState to AsyncIterator[list]
# =========================================================================
# =============================================================================
async def chat_with_bot(
    message: str,
    history: list,
    user_id: str,
    app_state: "AppState"
) -> AsyncIterator[list]:
    """
    Handle chat messages with streaming.

    Args:
        message: User's message text
        history: Chat history (Gradio format)
        user_id: Current user identifier
        app_state: Shared application state

    Yields:
        Updated history with streaming response
    """
    # ==================================
    if not message.strip():
        yield history
        return

    # ==================================
    if history is None:
        history = []

    # Check if it's a skill invocation
    is_skill, skill_name, remaining = app_state.router.is_skill_invocation(message)

    # Handle built-in commands (non-streaming)
    # ==================================
    if message.startswith("/") and not is_skill:
        session_key = app_state.session_manager.get_session_key("gradio", user_id)
        response = app_state.router.handle_command(message, session_key)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        yield history
        return

    # Add user message to history
    history.append({"role": "user", "content": message})

    # If it's a skill invocation, prepare the skill context
    skill_context = ""
    # ==================================
    if is_skill:
        skill_context = app_state.router.get_skill_context(skill_name)
        # The actual user request is in 'remaining'
        effective_message = remaining if remaining else f"Execute the {skill_name} skill"
    else:
        effective_message = message

    # Stream AI response
    current_response = ""

    try:
        async for chunk in app_state.router.handle_message_stream(
            channel="gradio",
            user_id=user_id,
            user_message=effective_message,
            user_name="Web User",
            skill_context=skill_context
        ):
            current_response += chunk
            # Create fresh list with new assistant message to trigger Gradio update
            yield history + [{"role": "assistant", "content": current_response}]

        # Final history with complete response
        history.append({"role": "assistant", "content": current_response})

    except Exception as e:
        # ==================================
        # Provide helpful error messages for common issues
        # ==================================
        error_msg = str(e)

        if "Connection refused" in error_msg or "ConnectionError" in error_msg:
            provider_info = app_state.get_current_provider_info()
            base_url = provider_info.get("base_url", "")

            if "8080" in base_url:
                error_response = (
                    "❌ **MLX server not running!**\n\n"
                    "Start it in a terminal:\n"
                    "```\n"
                    "mlx_lm.server --model mlx-community/Mistral-7B-Instruct-v0.3-4bit --port 8080\n"
                    "```"
                )
            elif "11434" in base_url:
                error_response = (
                    "❌ **Ollama not running!**\n\n"
                    "Start it in a terminal:\n"
                    "```\n"
                    "ollama serve\n"
                    "```"
                )
            elif "1234" in base_url:
                error_response = (
                    "❌ **LM Studio server not running!**\n\n"
                    "Open LM Studio → Start Server"
                )
            else:
                error_response = f"❌ **Cannot connect to AI provider**\n\n{error_msg}"
        else:
            error_response = f"❌ **AI error:** {error_msg}"

        history.append({"role": "assistant", "content": error_response})
        yield history

# =============================================================================
# End of File
# =============================================================================
# Project : mr_bot - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# =============================================================================
