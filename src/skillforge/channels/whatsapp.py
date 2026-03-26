# =============================================================================
'''
    File Name : whatsapp.py
    
    Description : WhatsApp Integration via Baileys Service. A secure Python 
                  client that communicates with the Baileys Node.js service.
                  This approach avoids unsafe/outdated Python WhatsApp libraries.
    
    Architecture:
        SkillForge (Python) → HTTP API → Baileys Service (Node.js) → WhatsApp Web
    
    Modifying it on 2026-02-07
    
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
import aiohttp
import base64
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from skillforge import PROJECT_ROOT
from skillforge.core.image_handler import ImageHandler, Attachment, EXTENSION_TO_MIME


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
    # Function send_image -> str, str, Optional[str] to bool
    # =========================================================================
    # =========================================================================
    async def send_image(self, to: str, image_path: str, caption: Optional[str] = None) -> bool:
        """
        Send an image via WhatsApp through the Baileys service.

        For local file paths the image is base64-encoded and sent via the
        ``/send-media`` endpoint.  For HTTP(S) URLs the URL is passed
        directly and the Baileys service downloads it server-side.

        Args:
            to: Phone number or chat ID (JID).
            image_path: Local file path or HTTP(S) URL.
            caption: Optional text caption.

        Returns:
            True if sent successfully.
        """
        if not self.is_connected:
            status = await self.check_status()
            if not status.get("connected"):
                self.logger.error("WhatsApp not connected — cannot send image")
                return False

        try:
            session = await self._get_session()

            is_url = image_path.startswith(("http://", "https://"))

            payload: dict = {}
            # Determine recipient format
            if "@" in to:
                payload["chatId"] = to
            else:
                payload["to"] = to

            if is_url:
                payload["imageUrl"] = image_path
            else:
                p = Path(image_path)
                if not p.is_file():
                    self.logger.warning(f"Image file not found, skipping: {image_path}")
                    return False
                image_data = base64.b64encode(p.read_bytes()).decode("ascii")
                # Determine mimetype from extension
                ext_map = {v: k for k, v in EXTENSION_TO_MIME.items()}
                mime_to_ext = {k: v for k, v in EXTENSION_TO_MIME.items()}
                mimetype = mime_to_ext.get(p.suffix.lower(), "image/png")
                payload["image"] = image_data
                payload["mimetype"] = mimetype

            if caption:
                payload["caption"] = caption

            async with session.post(
                f"{self.config.service_url}/send-media",
                json=payload,
            ) as resp:
                if resp.status == 200:
                    self.logger.info(f"Image sent to {to}")
                    return True
                else:
                    error = await resp.text()
                    self.logger.error(f"Send image failed: {error}")
                    return False

        except Exception as e:
            self.logger.error(f"Send image error: {e}")
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
            # Check if this is an image message and download media
            attachments: List[Attachment] = []
            message_type = data.get("messageType", "text")

            if message_type == "image":
                try:
                    attachment = await self._download_image_from_webhook(data)
                    if attachment:
                        attachments.append(attachment)
                except Exception as e:
                    self.logger.error(f"Image download error: {e}", exc_info=True)

            # ==================================
            # Build kwargs, only include attachments if present
            kwargs = dict(
                channel="whatsapp",
                user_id=data.get("senderId", ""),
                user_message=data.get("content", ""),
                chat_id=data.get("chatId"),
                user_name=data.get("senderName"),
            )
            if attachments:
                kwargs["attachments"] = attachments

            # ==================================
            # Call message handler with extracted data
            response = await self.message_handler(**kwargs)

            # ==================================
            # Auto-reply if handler returns a response (E-005: outbound images)
            if response and data.get("chatId"):
                chat_id = data["chatId"]
                # Check for outbound images in the response
                try:
                    from skillforge.core.router import MessageRouter
                    cleaned_text, image_paths = MessageRouter.extract_outbound_images(response)
                except Exception:
                    cleaned_text, image_paths = response, []

                if image_paths:
                    # Send text first (if any)
                    if cleaned_text:
                        await self.send_message(chat_id, cleaned_text)
                    # Then send each image natively
                    for img_path in image_paths:
                        await self.send_image(chat_id, img_path)
                else:
                    await self.send_message(chat_id, response)

            return response
        except Exception as e:
            self.logger.error(f"Message handler error: {e}", exc_info=True)
            return None

    # =========================================================================
    # =========================================================================
    # Function _download_image_from_webhook -> Dict[str, Any] to Optional[Attachment]
    # =========================================================================
    # =========================================================================
    async def _download_image_from_webhook(
        self, data: Dict[str, Any]
    ) -> Optional[Attachment]:
        """
        Download image media from a WhatsApp message via the Baileys service.

        Args:
            data: Webhook payload containing raw message and image metadata.

        Returns:
            Attachment object if download succeeds, None otherwise.
        """
        raw_message = data.get("raw")
        if not raw_message:
            self.logger.warning("No raw message in webhook data for image download")
            return None

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.config.service_url}/download-media",
                json={
                    "messageKey": raw_message.get("key", {}),
                    "messageType": "image",
                    "rawMessage": raw_message,
                },
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    self.logger.error(f"Media download failed: {error_text}")
                    return None

                result = await resp.json()
                if not result.get("success") or not result.get("data"):
                    return None

                # Decode base64 data and save to temp file
                image_bytes = base64.b64decode(result["data"])
                mimetype = result.get("mimetype", data.get("imageMimetype", "image/jpeg"))

                # Determine file extension from MIME type
                ext_map = {v: k for k, v in EXTENSION_TO_MIME.items()}
                file_ext = ext_map.get(mimetype, ".jpg")

                tmp_dir = PROJECT_ROOT / "data" / "images" / "whatsapp_tmp"
                tmp_dir.mkdir(parents=True, exist_ok=True)

                msg_id = data.get("messageId", "unknown")
                safe_id = ImageHandler.sanitize_filename(msg_id)
                temp_path = tmp_dir / f"wa_{safe_id}{file_ext}"
                temp_path.write_bytes(image_bytes)

                return Attachment(
                    file_path=str(temp_path),
                    original_filename=f"whatsapp_image_{safe_id}{file_ext}",
                    mime_type=mimetype,
                    size_bytes=len(image_bytes),
                )

        except Exception as e:
            self.logger.error(f"Image download error: {e}", exc_info=True)
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
        from skillforge.channels.whatsapp import WhatsAppChannel, create_webhook_blueprint

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
    from skillforge.core.webhook_security import verify_whatsapp_signature, get_whatsapp_app_secret

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
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
