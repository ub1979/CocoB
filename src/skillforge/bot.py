# =============================================================================
'''
    File Name : bot.py
    
    Description :
        Main entry point for the SkillForge AI chatbot server.
        This Flask application provides webhook endpoints for MS Teams integration,
        session management, and testing capabilities.
        
        The server initializes the SessionManager, LLM provider, and MessageRouter
        to handle incoming messages from various channels with persistent memory.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Contact : Idrak AI Ltd - Building AI Solutions for the Community
'''
# =============================================================================

# =============================================================================
# Importing the libraries
# =============================================================================
import sys
from skillforge import PROJECT_ROOT

from flask import Flask, request, jsonify, make_response
from skillforge.core.sessions import SessionManager
from skillforge.core.llm import LLMProviderFactory
from skillforge.core.router import MessageRouter
from skillforge.core.webhook_security import verify_ms_teams_token
import asyncio
import os

# =============================================================================
# Security Imports (Rate Limiting)
# =============================================================================
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RATE_LIMITING_AVAILABLE = False
    print("Warning: flask-limiter not installed. Rate limiting disabled.")
    print("Install with: pip install flask-limiter")
# =============================================================================

# =============================================================================
'''
    Configuration Loading : Import configuration with fallback handling
    
    Attempts to import config.py, provides helpful error message if not found.
'''
# =============================================================================

# ==================================
# Try to import config, fallback to example config
# ==================================
try:
    import config
except ImportError:
    print("config.py not found! Copy config.example.py to config.py and fill in your credentials.")
    sys.exit(1)
# ==================================

# =============================================================================
'''
    Flask Application Initialization : Web server setup
    
    Creates the Flask app instance and initializes all bot components
    including session manager, LLM provider, and message router.
'''
# =============================================================================

# =============================================================================
# Initialize Flask app
# =============================================================================
app = Flask(__name__)

# =============================================================================
# Security: Initialize Rate Limiter (if available)
# =============================================================================
if RATE_LIMITING_AVAILABLE:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )
    print("Rate limiting enabled: 200 requests/day, 50 requests/hour per IP")
else:
    limiter = None
    print("Rate limiting disabled - install flask-limiter for protection")
# =============================================================================

# =============================================================================
# Security Headers Middleware
# =============================================================================
@app.after_request
def add_security_headers(response):
    """
    Add security headers to all responses
    
    Security Headers:
        - X-Content-Type-Options: Prevents MIME type sniffing
        - X-Frame-Options: Prevents clickjacking
        - X-XSS-Protection: Enables browser XSS filter
        - Strict-Transport-Security: Enforces HTTPS (when available)
        - Content-Security-Policy: Restricts resource loading
    """
    # ==================================
    # Prevent MIME type sniffing
    # ==================================
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # ==================================
    # Prevent clickjacking attacks
    # ==================================
    response.headers['X-Frame-Options'] = 'DENY'
    
    # ==================================
    # Enable XSS protection in browsers
    # ==================================
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # ==================================
    # Enforce HTTPS in production (commented out until HTTPS is configured)
    # ==================================
    # response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # ==================================
    # Basic Content Security Policy
    # ==================================
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    
    return response
# =============================================================================

# =============================================================================
# Initialize bot components
# =============================================================================
print("Initializing bot components...")
session_manager = SessionManager(config.SESSION_DATA_DIR)

# ==================================
# Create LLM provider from config
# ==================================
llm_config = config.LLM_PROVIDERS[config.LLM_PROVIDER]
llm_provider = LLMProviderFactory.from_dict(llm_config)
print(f"LLM Provider: {llm_provider.provider_name} ({llm_provider.model_name})")
# ==================================

router = MessageRouter(session_manager, llm_provider)
print("Bot ready!")
# =============================================================================

# =============================================================================
# =============================================================================
# Flask Route Definitions
# =============================================================================
# =============================================================================

# =============================================================================
'''
    HomeEndpoint : Health check and status endpoint
    
    Provides basic information about the bot's current state including
    provider, model, and active session count.
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function health_check -> None to JSON response
# =========================================================================
# =============================================================================
@app.route("/", methods=["GET"])
def home():
    # =============================================================================
    # '''
    #     Home : Health check endpoint
    #     
    #     Returns bot status, provider info, and session count
    # '''
    # =============================================================================
    return jsonify({
        "bot_name": "skillforge",
        "status": "running",
        "message": "SkillForge is alive!",
        "provider": llm_provider.provider_name,
        "model": llm_provider.model_name,
        "sessions": len(session_manager.list_sessions())
    })
# =============================================================================

# =============================================================================
'''
    MessagesEndpoint : Main webhook for MS Teams messages
    
    Receives Activity objects from Microsoft Bot Framework,
    processes messages, and returns AI responses.
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function messages -> JSON request to JSON response
# =========================================================================
# =============================================================================
@app.route("/api/messages", methods=["POST"])
# ==================================
# Apply rate limiting if available (30 requests per minute per IP)
# ==================================
@limiter.limit("30 per minute") if limiter else lambda f: f
async def messages():
    # =============================================================================
    # '''
    #     Messages : Main webhook endpoint for MS Teams
    #     
    #     Receives Activity objects from Bot Framework and processes them.
    #     Handles both regular messages and slash commands.
    #     
    #     Security:
    #         Verifies Authorization header to ensure requests are from
    #         Microsoft Bot Framework and not spoofed by attackers.
    # '''
    # =============================================================================
    
    # ==================================
    # Security: Verify MS Teams authorization
    # ==================================
    try:
        auth_header = request.headers.get('Authorization')
        verify_ms_teams_token(
            auth_header,
            config.MSTEAMS_APP_ID,
            config.MSTEAMS_APP_PASSWORD
        )
    except Exception as e:
        print(f"MS Teams webhook verification failed: {e}")
        return jsonify({"error": "Unauthorized", "message": str(e)}), 401
    
    # ==================================
    # Extract message details from request
    # ==================================
    try:
        activity = request.json
        
        message_type = activity.get("type", "")
        text = activity.get("text", "").strip()
        from_user = activity.get("from", {})
        conversation = activity.get("conversation", {})
        
        user_id = from_user.get("id", "unknown")
        user_name = from_user.get("name", "User")
        conversation_id = conversation.get("id", "")
        
        print(f"\nReceived message from {user_name}: {text}")
        # ==================================
        
        # ==================================
        # Only handle messages (not typing indicators, etc.)
        # ==================================
        if message_type != "message" or not text:
            return jsonify({"status": "ignored"}), 200
        # ==================================
        
        # ==================================
        # Check for commands vs regular messages
        # ==================================
        if text.startswith("/"):
            session_key = session_manager.get_session_key("msteams", user_id, conversation_id)
            response_text = router.handle_command(text, session_key)
        else:
            # ==================================
            # Regular message - get AI response
            # ==================================
            response_text = await router.handle_message(
                channel="msteams",
                user_id=user_id,
                user_message=text,
                chat_id=conversation_id,
                user_name=user_name
            )
            # ==================================
        # ==================================
        
        print(f"Bot response: {response_text[:100]}...")
        
        # ==================================
        # Send response back to Teams
        # ==================================
        return jsonify({
            "type": "message",
            "text": response_text
        }), 200
        # ==================================
    
    # ==================================
    # Handle errors gracefully
    # ==================================
    except Exception as e:
        print(f"Error handling message: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    # ==================================
# =============================================================================

# =============================================================================
'''
    SessionsEndpoint : Debug endpoint for session listing
    
    Returns a list of all active conversation sessions
    for debugging and monitoring purposes.
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function list_sessions -> None to JSON response
# =========================================================================
# =============================================================================
@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    # =============================================================================
    # '''
    #     ListSessions : Debug endpoint to list all sessions
    #     
    #     Returns count and details of all active conversation sessions.
    # '''
    # =============================================================================
    sessions = session_manager.list_sessions()
    return jsonify({
        "count": len(sessions),
        "sessions": sessions
    })
# =============================================================================

# =============================================================================
'''
    TestEndpoint : Testing endpoint without MS Teams
    
    Allows quick testing of the bot without setting up
    Microsoft Teams integration. Accepts POST requests
    with user_id and message fields.
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function test_message -> JSON request to JSON response
# =========================================================================
# =============================================================================
@app.route("/api/test", methods=["POST"])
# ==================================
# Apply stricter rate limiting for test endpoint (10 requests per minute)
# ==================================
@limiter.limit("10 per minute") if limiter else lambda f: f
async def test_message():
    # =============================================================================
    # '''
    #     TestMessage : Test endpoint for quick testing without MS Teams
    #     
    #     POST body: {"user_id": "test", "message": "Hello"}
    #     Returns the user message and bot response.
    # '''
    # =============================================================================
    data = request.json
    user_id = data.get("user_id", "test-user")
    message = data.get("message", "")
    
    # ==================================
    # Validate input
    # ==================================
    if not message:
        return jsonify({"error": "message required"}), 400
    # ==================================
    
    # ==================================
    # Get AI response
    # ==================================
    response = await router.handle_message(
        channel="test",
        user_id=user_id,
        user_message=message,
        user_name="Test User"
    )
    # ==================================
    
    return jsonify({
        "user": message,
        "bot": response
    })
# =============================================================================

# =============================================================================
'''
    MainFunction : Server startup and initialization
    
    Prints startup banner with configuration details and starts
    the Flask development server.
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function main -> None to None (starts server)
# =========================================================================
# =============================================================================
def main():
    # =============================================================================
    # '''
    #     Main : Start the bot server
    #     
    #     Displays startup banner with configuration and begins
    #     listening for incoming webhook requests.
    # '''
    # =============================================================================
    print(f"""
====================================================
            SkillForge Server Starting
====================================================

Webhook URL: http://{config.HOST}:{config.PORT}/api/messages
Test URL: http://{config.HOST}:{config.PORT}/api/test
Sessions URL: http://{config.HOST}:{config.PORT}/api/sessions

Bot Name: SkillForge
Provider: {llm_provider.provider_name}
Model: {llm_provider.model_name}
Endpoint: {llm_provider.config.base_url}

Waiting for messages...
""")
    
    # ==================================
    # Determine debug mode from environment (SECURITY: never hardcode debug=True)
    # ==================================
    import os
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    
    # ==================================
    # Security warning if debug mode is enabled
    # ==================================
    if debug_mode:
        print("""
    ⚠️  WARNING: Flask debug mode is enabled!
       Do NOT use debug mode in production as it exposes sensitive information.
       Set FLASK_DEBUG=false or unset the environment variable for production.
        """)
    # ==================================
    
    # ==================================
    # Start Flask server with secure configuration
    # ==================================
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=debug_mode,
        use_reloader=debug_mode  # Disable reloader in production
    )
    # ==================================
# =============================================================================

# =============================================================================
# Application Entry Point
# =============================================================================

# ==================================
# Run main function when executed directly
# ==================================
if __name__ == "__main__":
    main()
# ==================================

# =============================================================================
# =============================================================================
# End of Bot Server File
# =============================================================================
# =============================================================================

'''
    =============================================================================
    Project Information
    =============================================================================
    
    SkillForge - AI Chatbot with Persistent Memory
    
    Created by : Syed Usama Bukhari
    Organization : Idrak AI Ltd
    
    A Safe Open Community Project - Making AI Useful
    
    This project is designed to be a community-driven, open-source AI assistant
    with persistent memory capabilities. Our mission is to make AI technology
    accessible and useful for everyone.
    
    Features:
    - Persistent conversation memory
    - Multi-channel support (MS Teams, WhatsApp, Web UI)
    - Multi-provider LLM support (15+ providers)
    - Self-improving personality system
    - Extensible skills framework
    - MCP tool integration
    
    Join us in building the future of AI assistants!
    
    =============================================================================
'''
