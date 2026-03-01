# =============================================================================
'''
    File Name : whatsapp.py
    
    Description : WhatsApp Integration via Baileys Service. A secure Python 
                  client that communicates with the Baileys Node.js service.
                  This approach avoids unsafe/outdated Python WhatsApp libraries.
    
    Architecture:
        mr_bot (Python) → HTTP API → Baileys Service (Node.js) → WhatsApp Web
    
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
import aiohttp
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass


# =============================================================================
'''
    WhatsAppConfig : Configuration dataclass for WhatsApp service connection
                     Stores all connection parameters and retry settings
'''
# =============================================================================
@dataclass
class WhatsAppConfig:
    """Configuration for WhatsApp service connection"""
    service_url: str = "http://localhost:3979"
    webhook_path: str = "/whatsapp/incoming"
    bot_port: int = 3978
    retry_interval: int = 5
    max_retries: int = 3


# =============================================================================
'''
    WhatsAppChannel : Main WhatsApp channel integration class via Baileys HTTP service.
                      This client communicates with the Node.js Baileys service,
                      which handles the actual WhatsApp Web connection.
'''
# =============================================================================
class WhatsAppChannel:
    """
    WhatsApp channel integration via Baileys HTTP service.

    This client communicates with the Node.js Baileys service,
    which handles the actual WhatsApp Web connection.
    """

    # =========================================================================
    # =========================================================================
    # Function __init__ -> Optional[WhatsAppConfig], Optional[Callable] to None
    # =========================================================================
    # =========================================================================
    def __init__(
        self,
        config: Optional[WhatsAppConfig] = None,
        message_handler: Optional[Callable] = None,
    ):
        """
        Initialize WhatsApp channel.

        Args:
            config: WhatsApp service configuration
            message_handler: Async function to handle incoming messages
        """
        # ==================================
        # Initialize configuration with defaults if not provided
        self.config = config or WhatsAppConfig()
        self.message_handler = message_handler
        self.is_connected = False
        self._session: Optional[aiohttp.ClientSession] = None

        # ==================================
        # Setup logging for WhatsApp operations
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("whatsapp")

    # =========================================================================
    # =========================================================================
    # Function _get_session -> None to aiohttp.ClientSession
    # =========================================================================
    # =========================================================================
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        # ==================================
        # Create new session if none exists or current is closed
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    # =========================================================================
    # =========================================================================
    # Function check_status -> None to Dict[str, Any]
    # =========================================================================
    # =========================================================================
    async def check_status(self) -> Dict[str, Any]:
        """
        Check WhatsApp service connection status.

        Returns:
            Status dict with 'connected', 'status', 'hasQr', etc.
        """
        try:
            # ==================================
            # Make HTTP GET request to status endpoint
            session = await self._get_session()
            async with session.get(f"{self.config.service_url}/status") as resp:
                # ==================================
                # Parse successful response
                if resp.status == 200:
                    data = await resp.json()
                    self.is_connected = data.get("connected", False)
                    return data
                else:
                    return {"connected": False, "error": f"HTTP {resp.status}"}
        except aiohttp.ClientError as e:
            # ==================================
            # Handle connection errors gracefully
            self.logger.error(f"Status check failed: {e}")
            return {"connected": False, "error": str(e)}

    # =========================================================================
    # =========================================================================
    # Function get_qr_code -> None to Optional[str]
    # =========================================================================
    # =========================================================================
    async def get_qr_code(self) -> Optional[str]:
        """
        Get QR code for WhatsApp authentication.

        Returns:
            QR code string if available, None otherwise
        """
        try:
            # ==================================
            # Request QR code from Baileys service
            session = await self._get_session()
            async with session.get(f"{self.config.service_url}/qr") as resp:
                # ==================================
                # Handle already connected case
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("connected"):
                        self.logger.info("Already connected to WhatsApp")
                        return None
                    return data.get("qr")
                # ==================================
                # QR not ready yet
                elif resp.status == 404:
                    self.logger.debug("No QR code available yet")
                    return None
                else:
                    self.logger.warning(f"QR fetch failed: HTTP {resp.status}")
                    return None
        except aiohttp.ClientError as e:
            self.logger.error(f"QR fetch error: {e}")
            return None

    # =========================================================================
    # =========================================================================
    # Function display_qr -> str to None
    # =========================================================================
    # =========================================================================
    def display_qr(self, qr_text: str):
        """Display QR code in terminal using ASCII"""
        try:
            # ==================================
            # Import and generate QR code display
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=1, border=1)
            qr.add_data(qr_text)
            qr.make(fit=True)

            # ==================================
            # Print formatted QR code instructions
            print("\n" + "=" * 60)
            print("  SCAN THIS QR CODE WITH WHATSAPP")
            print("=" * 60)
            print("Open WhatsApp -> Settings -> Linked Devices -> Link a Device")
            print("=" * 60 + "\n")

            qr.print_ascii(invert=True)

            print("\n" + "=" * 60)
            print("Waiting for QR scan...")
            print("=" * 60 + "\n")
        except ImportError:
            # ==================================
            # Fallback if qrcode package not installed
            print(f"\nQR Code (install qrcode package for visual display):\n{qr_text}\n")

    # =========================================================================
    # =========================================================================
    # Function wait_for_connection -> int to bool
    # =========================================================================
    # =========================================================================
    async def wait_for_connection(self, timeout: int = 120) -> bool:
        """
        Wait for WhatsApp connection (QR scan).

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if connected, False if timeout
        """
        self.logger.info("Waiting for WhatsApp connection...")

        # ==================================
        # Initialize timing and display tracking
        start_time = asyncio.get_event_loop().time()
        qr_displayed = False

        # ==================================
        # Poll for connection status until timeout
        while asyncio.get_event_loop().time() - start_time < timeout:
            status = await self.check_status()

            # ==================================
            # Connection established successfully
            if status.get("connected"):
                self.is_connected = True
                self.logger.info("Connected to WhatsApp!")
                return True

            # ==================================
            # Display QR if available and not yet shown
            if status.get("hasQr") and not qr_displayed:
                qr = await self.get_qr_code()
                if qr:
                    self.display_qr(qr)
                    qr_displayed = True

            await asyncio.sleep(2)

        # ==================================
        # Timeout reached without connection
        self.logger.warning("Connection timeout")
        return False

    # =========================================================================
    # =========================================================================
    # Function configure_webhook -> Optional[str] to bool
    # =========================================================================
    # =========================================================================
    async def configure_webhook(self, webhook_url: Optional[str] = None) -> bool:
        """
        Configure webhook URL for incoming messages.

        Args:
            webhook_url: Full webhook URL, or None to use default

        Returns:
            True if successful
        """
        # ==================================
        # Use default webhook URL if none provided
        if webhook_url is None:
            webhook_url = f"http://localhost:{self.config.bot_port}{self.config.webhook_path}"

        try:
            # ==================================
            # POST webhook configuration to Baileys service
            session = await self._get_session()
            async with session.post(
                f"{self.config.service_url}/webhook",
                json={"url": webhook_url}
            ) as resp:
                if resp.status == 200:
                    self.logger.info(f"Webhook configured: {webhook_url}")
                    return True
                else:
                    self.logger.error(f"Webhook config failed: HTTP {resp.status}")
                    return False
        except aiohttp.ClientError as e:
            self.logger.error(f"Webhook config error: {e}")
            return False

    # =========================================================================
    # =========================================================================
    # Function send_message -> str, str to bool
    # =========================================================================
    # =========================================================================
    async def send_message(self, to: str, message: str) -> bool:
        """
        Send a WhatsApp message.

        Args:
            to: Phone number (e.g., "1234567890") or chat ID
            message: Message text

        Returns:
            True if sent successfully
        """
        # ==================================
        # Verify connection before sending
        if not self.is_connected:
            status = await self.check_status()
            if not status.get("connected"):
                raise ConnectionError("WhatsApp not connected")

        try:
            session = await self._get_session()

            # ==================================
            # Determine if 'to' is a phone number or chat ID
            payload = {"message": message}
            if "@" in to:
                payload["chatId"] = to
            else:
                payload["to"] = to

            # ==================================
            # Send message via Baileys service
            async with session.post(
                f"{self.config.service_url}/send",
                json=payload
            ) as resp:
                if resp.status == 200:
                    self.logger.info(f"Message sent to {to}")
                    return True
                else:
                    error = await resp.text()
                    self.logger.error(f"Send failed: {error}")
                    return False
        except aiohttp.ClientError as e:
            self.logger.error(f"Send error: {e}")
            return False

    # =========================================================================
    # =========================================================================
    # Function send_chunked_message -> str, str, int to bool
    # =========================================================================
    # =========================================================================
    async def send_chunked_message(self, to: str, message: str, max_length: int = 4000) -> bool:
        """
        Send a long message in chunks.

        Args:
            to: Recipient phone/chat ID
            message: Message text (can be longer than WhatsApp limit)
            max_length: Maximum characters per message

        Returns:
            True if all chunks sent successfully
        """
        # ==================================
        # Send as single message if within limit
        if len(message) <= max_length:
            return await self.send_message(to, message)

        # ==================================
        # Split message into chunks
        chunks = [message[i:i + max_length] for i in range(0, len(message), max_length)]

        # ==================================
        # Send each chunk with progress indicator
        for i, chunk in enumerate(chunks):
            prefix = f"[{i + 1}/{len(chunks)}]\n" if len(chunks) > 1 else ""
            success = await self.send_message(to, prefix + chunk)
            if not success:
                return False
            # ==================================
            # Small delay between chunks to avoid rate limiting
            if i < len(chunks) - 1:
                await asyncio.sleep(0.5)

        return True

    # =========================================================================
    # =========================================================================
    # Function disconnect -> bool to bool
    # =========================================================================
    # =========================================================================
    async def disconnect(self, logout: bool = False) -> bool:
        """
        Disconnect from WhatsApp.

        Args:
            logout: If True, also logout (requires re-scan of QR)

        Returns:
            True if successful
        """
        try:
            # ==================================
            # Send disconnect request to Baileys service
            session = await self._get_session()
            async with session.post(
                f"{self.config.service_url}/disconnect",
                json={"logout": logout}
            ) as resp:
                self.is_connected = False
                if resp.status == 200:
                    self.logger.info(f"Disconnected (logout={logout})")
                    return True
                return False
        except aiohttp.ClientError as e:
            self.logger.error(f"Disconnect error: {e}")
            return False

    # =========================================================================
    # =========================================================================
    # Function reconnect -> None to bool
    # =========================================================================
    # =========================================================================
    async def reconnect(self) -> bool:
        """
        Reconnect to WhatsApp.

        Returns:
            True if reconnection initiated
        """
        try:
            # ==================================
            # Send reconnect request to Baileys service
            session = await self._get_session()
            async with session.post(f"{self.config.service_url}/reconnect") as resp:
                if resp.status == 200:
                    self.logger.info("Reconnecting...")
                    return True
                return False
        except aiohttp.ClientError as e:
            self.logger.error(f"Reconnect error: {e}")
            return False

    # =========================================================================
    # =========================================================================
    # Function handle_incoming_webhook -> Dict[str, Any] to Optional[str]
    # =========================================================================
    # =========================================================================
    async def handle_incoming_webhook(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Handle incoming message from webhook.

        This should be called by your webhook endpoint.

        Args:
            data: Message data from Baileys service

        Returns:
            Response message if handler provided
        """
        # ==================================
        # Check if message handler is configured
        if not self.message_handler:
            self.logger.warning("No message handler configured")
            return None

        try:
            # ==================================
            # Call message handler with extracted data
            response = await self.message_handler(
                channel="whatsapp",
                user_id=data.get("senderId", ""),
                user_message=data.get("content", ""),
                chat_id=data.get("chatId"),
                user_name=data.get("senderName")
            )

            # ==================================
            # Auto-reply if handler returns a response
            if response and data.get("chatId"):
                await self.send_message(data["chatId"], response)

            return response
        except Exception as e:
            self.logger.error(f"Message handler error: {e}", exc_info=True)
            return None

    # =========================================================================
    # =========================================================================
    # Function get_status -> None to Dict[str, Any]
    # =========================================================================
    # =========================================================================
    def get_status(self) -> Dict[str, Any]:
        """Get current connection status (sync wrapper)"""
        return {
            "connected": self.is_connected,
            "service_url": self.config.service_url,
        }

    # =========================================================================
    # =========================================================================
    # Function close -> None to None
    # =========================================================================
    # =========================================================================
    async def close(self):
        """Close the HTTP session"""
        # ==================================
        # Clean up aiohttp session
        if self._session and not self._session.closed:
            await self._session.close()


# =============================================================================
# Flask Webhook Example Section
# =============================================================================

# =========================================================================
# =========================================================================
# Function create_webhook_blueprint -> WhatsAppChannel to Blueprint
# =========================================================================
# =========================================================================
def create_webhook_blueprint(whatsapp_channel: WhatsAppChannel, app_secret: Optional[str] = None):
    """
    Create Flask blueprint for WhatsApp webhook with signature verification.

    Usage:
        from flask import Flask
        from coco_b.channels.whatsapp import WhatsAppChannel, create_webhook_blueprint

        app = Flask(__name__)
        wa = WhatsAppChannel(message_handler=my_handler)
        app.register_blueprint(create_webhook_blueprint(wa, app_secret="your_secret"))

    Security:
        Verifies X-Hub-Signature-256 header to ensure webhooks are genuinely
        from WhatsApp/Meta and not spoofed by attackers.

    Args:
        whatsapp_channel: Configured WhatsAppChannel instance
        app_secret: WhatsApp app secret for signature verification.
                    If None, will try to load from WHATSAPP_APP_SECRET env var.
    """
    from flask import Blueprint, request, jsonify
    from coco_b.core.webhook_security import verify_whatsapp_signature, get_whatsapp_app_secret

    bp = Blueprint("whatsapp", __name__, url_prefix="/whatsapp")

    # ==================================
    # Get app secret from parameter or environment
    # ==================================
    _app_secret = app_secret or get_whatsapp_app_secret()

    # =========================================================================
    # =========================================================================
    # Function incoming_message -> None to jsonify
    # =========================================================================
    # =========================================================================
    @bp.route("/incoming", methods=["POST"])
    async def incoming_message():
        """
        Handle incoming WhatsApp message with signature verification.
        
        Security:
            - Verifies X-Hub-Signature-256 header
            - Rejects requests with invalid or missing signatures
            - Returns 401 Unauthorized for failed verification
        """
        # ==================================
        # Security: Verify webhook signature
        # ==================================
        if _app_secret:
            try:
                signature = request.headers.get('X-Hub-Signature-256')
                verify_whatsapp_signature(request.data, signature, _app_secret)
            except Exception as e:
                whatsapp_channel.logger.warning(f"WhatsApp webhook verification failed: {e}")
                return jsonify({"error": "Unauthorized", "message": str(e)}), 401
        else:
            whatsapp_channel.logger.warning(
                "WhatsApp app secret not configured. "
                "Webhook verification is disabled. "
                "Set WHATSAPP_APP_SECRET for security."
            )
        
        # ==================================
        # Process the verified webhook
        # ==================================
        data = request.get_json()
        await whatsapp_channel.handle_incoming_webhook(data)
        return jsonify({"ok": True})

    # =========================================================================
    # =========================================================================
    # Function status -> None to jsonify
    # =========================================================================
    # =========================================================================
    @bp.route("/status", methods=["GET"])
    async def status():
        status = await whatsapp_channel.check_status()
        return jsonify(status)

    return bp


# =============================================================================
# Standalone Test Section
# =============================================================================

# =========================================================================
# =========================================================================
# Function main -> None to None
# =========================================================================
# =========================================================================
async def main():
    """Test WhatsApp connection"""
    print("WhatsApp Channel Test")
    print("=" * 40)

    # =========================================================================
    # =========================================================================
    # Function test_handler -> str, str, str, Optional[str], Optional[str] to str
    # =========================================================================
    # =========================================================================
    async def test_handler(channel, user_id, user_message, chat_id=None, user_name=None):
        print(f"Received from {user_name or user_id}: {user_message}")
        return f"Echo: {user_message}"

    wa = WhatsAppChannel(message_handler=test_handler)

    # ==================================
    # Check initial connection status
    status = await wa.check_status()
    print(f"Status: {status}")

    # ==================================
    # Handle not connected state
    if not status.get("connected"):
        print("\nWhatsApp not connected.")
        print("Make sure the Baileys service is running:")
        print("  cd whatsapp_service && npm start")
        print("\nThen scan the QR code with WhatsApp.")

        # ==================================
        # Wait for QR scan and connection
        connected = await wa.wait_for_connection(timeout=60)
        if not connected:
            print("Connection timeout. Exiting.")
            await wa.close()
            return

    # ==================================
    # Configure webhook for incoming messages
    await wa.configure_webhook()

    print("\nWhatsApp ready! Listening for messages...")
    print("Press Ctrl+C to exit.\n")

    try:
        # ==================================
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        await wa.close()


# =========================================================================
# =========================================================================
# Entry Point - Run main when executed directly
# =========================================================================
# =========================================================================
if __name__ == "__main__":
    asyncio.run(main())


# =============================================================================
'''
    End of File : whatsapp.py
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
