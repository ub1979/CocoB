# =============================================================================
# test_channel_images.py -- Tests for E-004: Channel Inbound image handling
#
# Tests Telegram, WhatsApp, and Flet UI image attachment flow.
# =============================================================================

import asyncio
import base64
import os
import struct
import zlib
from pathlib import Path
from typing import Optional, List
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from skillforge.core.image_handler import Attachment, ImageHandler, EXTENSION_TO_MIME


# =============================================================================
# Helpers — minimal valid image files
# =============================================================================

def _make_png(path: Path, size_bytes: int = 100) -> Path:
    """Create a minimal valid PNG file."""
    png_header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">II", 1, 1) + b"\x08\x02\x00\x00\x00"
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    content = png_header + ihdr + iend
    if size_bytes > len(content):
        content += b"\x00" * (size_bytes - len(content))
    path.write_bytes(content)
    return path


def _make_jpeg(path: Path, size_bytes: int = 100) -> Path:
    """Create a minimal valid JPEG file."""
    jpeg_header = b"\xff\xd8\xff\xe0"
    content = jpeg_header + b"\x00" * max(0, size_bytes - len(jpeg_header))
    path.write_bytes(content)
    return path


def _sample_attachment(tmp_path: Path, name: str = "test.jpg") -> Attachment:
    """Create a sample JPEG Attachment backed by a real file."""
    img_path = _make_jpeg(tmp_path / name)
    return Attachment(
        file_path=str(img_path),
        original_filename=name,
        mime_type="image/jpeg",
        size_bytes=img_path.stat().st_size,
    )


# =============================================================================
# Telegram Channel Tests
# =============================================================================

class TestTelegramPhotoHandler:
    """Test Telegram _handle_photo creates Attachment and calls _process_message."""

    @pytest.fixture
    def tg_channel(self):
        """Create a TelegramChannel with a mock message handler."""
        from skillforge.channels.telegram import TelegramChannel, TelegramConfig

        config = TelegramConfig(bot_token="fake-token")
        handler = AsyncMock(return_value="Test response")
        channel = TelegramChannel(config=config, message_handler=handler)
        return channel

    @pytest.fixture
    def mock_update_photo(self, tmp_path):
        """Create a mock Telegram Update with a photo."""
        img_path = _make_jpeg(tmp_path / "photo.jpg")

        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.first_name = "Test"
        update.effective_user.username = "testuser"
        update.effective_chat.id = 67890
        update.effective_chat.send_action = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.message.caption = "A nice photo"

        # Mock photo object (list of PhotoSize — we want the last/largest)
        photo_obj = MagicMock()
        photo_obj.file_unique_id = "unique123"
        photo_obj.width = 800
        photo_obj.height = 600

        file_obj = MagicMock()
        file_obj.download_to_drive = AsyncMock()
        photo_obj.get_file = AsyncMock(return_value=file_obj)

        update.message.photo = [MagicMock(), photo_obj]  # [-1] is largest

        return update, img_path, file_obj

    @pytest.mark.asyncio
    async def test_handle_photo_creates_attachment(self, tg_channel, mock_update_photo, tmp_path):
        """_handle_photo should download the photo, create Attachment, call _process_message."""
        update, img_path, file_obj = mock_update_photo

        # Mock the download to actually create the file
        async def fake_download(path):
            _make_jpeg(Path(path))

        file_obj.download_to_drive = AsyncMock(side_effect=fake_download)

        # Patch PROJECT_ROOT to use tmp_path
        with patch("skillforge.channels.telegram.PROJECT_ROOT", tmp_path):
            with patch.object(tg_channel, "_process_message", new_callable=AsyncMock) as mock_process:
                context = MagicMock()
                await tg_channel._handle_photo(update, context)

                # _process_message should have been called with attachments
                mock_process.assert_called_once()
                call_kwargs = mock_process.call_args
                assert call_kwargs.kwargs.get("user_message") == "A nice photo"
                attachments = call_kwargs.kwargs.get("attachments")
                assert attachments is not None
                assert len(attachments) == 1
                assert attachments[0].mime_type == "image/jpeg"
                assert attachments[0].original_filename.startswith("photo_")

    @pytest.mark.asyncio
    async def test_handle_photo_no_caption(self, tg_channel, mock_update_photo, tmp_path):
        """_handle_photo with no caption should use '[Image]' as message."""
        update, img_path, file_obj = mock_update_photo
        update.message.caption = None

        async def fake_download(path):
            _make_jpeg(Path(path))

        file_obj.download_to_drive = AsyncMock(side_effect=fake_download)

        with patch("skillforge.channels.telegram.PROJECT_ROOT", tmp_path):
            with patch.object(tg_channel, "_process_message", new_callable=AsyncMock) as mock_process:
                context = MagicMock()
                await tg_channel._handle_photo(update, context)

                call_kwargs = mock_process.call_args
                assert call_kwargs.kwargs.get("user_message") == "[Image]"

    @pytest.mark.asyncio
    async def test_handle_photo_unauthorized_user(self, tg_channel, mock_update_photo, tmp_path):
        """Unauthorized user should get rejection, not process the photo."""
        update, _, _ = mock_update_photo
        tg_channel.config.allowed_users = ["other_user"]

        context = MagicMock()
        await tg_channel._handle_photo(update, context)

        update.message.reply_text.assert_called_once_with(
            "Sorry, you're not authorized to use this bot."
        )

    @pytest.mark.asyncio
    async def test_handle_photo_error_handling(self, tg_channel, mock_update_photo, tmp_path):
        """If photo download fails, user should get a friendly error."""
        update, _, file_obj = mock_update_photo

        # Simulate download error
        photo_obj = update.message.photo[-1]
        photo_obj.get_file = AsyncMock(side_effect=Exception("Download failed"))

        with patch("skillforge.channels.telegram.PROJECT_ROOT", tmp_path):
            context = MagicMock()
            await tg_channel._handle_photo(update, context)

            # Should reply with error message
            update.message.reply_text.assert_called_once_with(
                "Sorry, I couldn't process that image. Please try again."
            )


class TestTelegramDocumentImageHandler:
    """Test Telegram _handle_document_image for image files sent as documents."""

    @pytest.fixture
    def tg_channel(self):
        from skillforge.channels.telegram import TelegramChannel, TelegramConfig

        config = TelegramConfig(bot_token="fake-token")
        handler = AsyncMock(return_value="Test response")
        return TelegramChannel(config=config, message_handler=handler)

    @pytest.mark.asyncio
    async def test_handle_document_image(self, tg_channel, tmp_path):
        """Document image handler should create Attachment for supported MIME types."""
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.first_name = "Test"
        update.effective_user.username = "testuser"
        update.effective_chat.id = 67890
        update.effective_chat.send_action = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.message.caption = "Document image"

        doc = MagicMock()
        doc.mime_type = "image/png"
        doc.file_name = "screenshot.png"
        doc.file_unique_id = "doc_unique_456"

        file_obj = MagicMock()

        async def fake_download(path):
            _make_png(Path(path))

        file_obj.download_to_drive = AsyncMock(side_effect=fake_download)
        doc.get_file = AsyncMock(return_value=file_obj)
        update.message.document = doc

        with patch("skillforge.channels.telegram.PROJECT_ROOT", tmp_path):
            with patch.object(tg_channel, "_process_message", new_callable=AsyncMock) as mock_process:
                context = MagicMock()
                await tg_channel._handle_document_image(update, context)

                mock_process.assert_called_once()
                call_kwargs = mock_process.call_args
                attachments = call_kwargs.kwargs.get("attachments")
                assert attachments is not None
                assert len(attachments) == 1
                assert attachments[0].mime_type == "image/png"
                assert attachments[0].original_filename == "screenshot.png"

    @pytest.mark.asyncio
    async def test_handle_document_unsupported_mime(self, tg_channel, tmp_path):
        """Unsupported MIME types should be rejected with a user-friendly message."""
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.first_name = "Test"
        update.effective_user.username = "testuser"
        update.effective_chat.id = 67890
        update.message.reply_text = AsyncMock()

        doc = MagicMock()
        doc.mime_type = "image/svg+xml"
        doc.file_name = "vector.svg"
        doc.file_unique_id = "doc_svg"
        update.message.document = doc

        context = MagicMock()
        await tg_channel._handle_document_image(update, context)

        # Should reply with unsupported message
        update.message.reply_text.assert_called_once()
        args = update.message.reply_text.call_args[0][0]
        assert "Unsupported" in args


class TestTelegramProcessMessageAttachments:
    """Test _process_message forwards attachments to the router."""

    @pytest.fixture
    def tg_channel(self):
        from skillforge.channels.telegram import TelegramChannel, TelegramConfig

        config = TelegramConfig(bot_token="fake-token")
        handler = AsyncMock(return_value="Response with image analysis")
        return TelegramChannel(config=config, message_handler=handler)

    @pytest.mark.asyncio
    async def test_process_message_passes_attachments_to_router(self, tg_channel, tmp_path):
        """_process_message should forward attachments to the message handler."""
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.first_name = "Test"
        update.effective_chat.id = 67890
        update.effective_chat.send_action = AsyncMock()
        update.message.reply_text = AsyncMock()

        attachment = _sample_attachment(tmp_path)

        await tg_channel._process_message(
            update=update,
            user_message="What is in this image?",
            attachments=[attachment],
        )

        # Verify the message handler was called with attachments
        tg_channel.message_handler.assert_called_once()
        call_kwargs = tg_channel.message_handler.call_args.kwargs
        assert call_kwargs["attachments"] == [attachment]
        assert call_kwargs["user_message"] == "What is in this image?"
        assert call_kwargs["channel"] == "telegram"

    @pytest.mark.asyncio
    async def test_process_message_without_attachments(self, tg_channel, tmp_path):
        """_process_message without attachments should NOT include attachments key."""
        update = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.first_name = "Test"
        update.effective_chat.id = 67890
        update.effective_chat.send_action = AsyncMock()
        update.message.reply_text = AsyncMock()

        await tg_channel._process_message(
            update=update,
            user_message="Hello world",
        )

        tg_channel.message_handler.assert_called_once()
        call_kwargs = tg_channel.message_handler.call_args.kwargs
        assert "attachments" not in call_kwargs
        assert call_kwargs["user_message"] == "Hello world"


# =============================================================================
# WhatsApp Channel Tests
# =============================================================================

class TestWhatsAppImageWebhook:
    """Test WhatsApp handle_incoming_webhook with image messages."""

    @pytest.fixture
    def wa_channel(self):
        from skillforge.channels.whatsapp import WhatsAppChannel, WhatsAppConfig

        config = WhatsAppConfig(service_url="http://localhost:3979")
        handler = AsyncMock(return_value="Image analyzed")
        channel = WhatsAppChannel(config=config, message_handler=handler)
        return channel

    @pytest.mark.asyncio
    async def test_text_message_backward_compat(self, wa_channel):
        """Regular text messages should work as before (no attachments key)."""
        data = {
            "messageId": "msg_001",
            "chatId": "123456@s.whatsapp.net",
            "senderId": "123456",
            "senderName": "Test User",
            "content": "Hello!",
            "messageType": "text",
        }

        # Mock send_message to avoid actual HTTP calls
        wa_channel.send_message = AsyncMock(return_value=True)

        result = await wa_channel.handle_incoming_webhook(data)

        assert result == "Image analyzed"
        wa_channel.message_handler.assert_called_once()
        call_kwargs = wa_channel.message_handler.call_args.kwargs
        assert call_kwargs["user_message"] == "Hello!"
        assert "attachments" not in call_kwargs

    @pytest.mark.asyncio
    async def test_image_message_triggers_download(self, wa_channel, tmp_path):
        """Image messages should attempt to download media and create Attachment."""
        data = {
            "messageId": "img_001",
            "chatId": "123456@s.whatsapp.net",
            "senderId": "123456",
            "senderName": "Test User",
            "content": "Check this out",
            "messageType": "image",
            "imageMimetype": "image/jpeg",
            "imageCaption": "Check this out",
            "raw": {
                "key": {"remoteJid": "123456@s.whatsapp.net", "id": "img_001"},
                "message": {"imageMessage": {"mimetype": "image/jpeg"}},
            },
        }

        # Create a fake JPEG for the download
        fake_jpeg = _make_jpeg(tmp_path / "fake.jpg")
        b64_data = base64.b64encode(fake_jpeg.read_bytes()).decode("ascii")

        # Build a proper async context manager mock for aiohttp session.post()
        mock_resp = MagicMock()
        mock_resp.status = 200

        async def mock_json():
            return {
                "success": True,
                "data": b64_data,
                "mimetype": "image/jpeg",
                "size": fake_jpeg.stat().st_size,
            }
        mock_resp.json = mock_json

        class _MockCtx:
            async def __aenter__(self):
                return mock_resp

            async def __aexit__(self, *args):
                pass

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_MockCtx())

        # Patch _get_session to return our mock session
        wa_channel._get_session = AsyncMock(return_value=mock_session)
        wa_channel.send_message = AsyncMock(return_value=True)

        with patch("skillforge.channels.whatsapp.PROJECT_ROOT", tmp_path):
            result = await wa_channel.handle_incoming_webhook(data)

        assert result == "Image analyzed"
        wa_channel.message_handler.assert_called_once()
        call_kwargs = wa_channel.message_handler.call_args.kwargs
        assert "attachments" in call_kwargs
        attachments = call_kwargs["attachments"]
        assert len(attachments) == 1
        assert attachments[0].mime_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_image_download_failure_still_sends_text(self, wa_channel, tmp_path):
        """If image download fails, message should still be forwarded (text only)."""
        data = {
            "messageId": "img_002",
            "chatId": "123456@s.whatsapp.net",
            "senderId": "123456",
            "senderName": "Test User",
            "content": "[Image]",
            "messageType": "image",
            "raw": {
                "key": {"remoteJid": "123456@s.whatsapp.net", "id": "img_002"},
                "message": {"imageMessage": {"mimetype": "image/jpeg"}},
            },
        }

        # Mock download to fail
        mock_resp = MagicMock()
        mock_resp.status = 500

        async def mock_text():
            return "Server error"
        mock_resp.text = mock_text

        class _MockCtx:
            async def __aenter__(self):
                return mock_resp

            async def __aexit__(self, *args):
                pass

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_MockCtx())

        wa_channel._get_session = AsyncMock(return_value=mock_session)
        wa_channel.send_message = AsyncMock(return_value=True)

        with patch("skillforge.channels.whatsapp.PROJECT_ROOT", tmp_path):
            result = await wa_channel.handle_incoming_webhook(data)

        # Should still process the text message even though image download failed
        assert result == "Image analyzed"
        wa_channel.message_handler.assert_called_once()
        call_kwargs = wa_channel.message_handler.call_args.kwargs
        # No attachments since download failed
        assert "attachments" not in call_kwargs

    @pytest.mark.asyncio
    async def test_image_no_raw_message(self, wa_channel, tmp_path):
        """If raw message is missing, image download should be skipped gracefully."""
        data = {
            "messageId": "img_003",
            "chatId": "123456@s.whatsapp.net",
            "senderId": "123456",
            "senderName": "Test User",
            "content": "[Image]",
            "messageType": "image",
            # No "raw" key
        }

        wa_channel.send_message = AsyncMock(return_value=True)

        with patch("skillforge.channels.whatsapp.PROJECT_ROOT", tmp_path):
            result = await wa_channel.handle_incoming_webhook(data)

        wa_channel.message_handler.assert_called_once()
        call_kwargs = wa_channel.message_handler.call_args.kwargs
        assert "attachments" not in call_kwargs


# =============================================================================
# Flet ChatMessage Tests
# =============================================================================

class TestChatMessageWithAttachments:
    """Test ChatMessage renders images when attachments are present."""

    def test_message_without_attachments(self):
        """ChatMessage should render normally without attachments (backward compat)."""
        msg = MagicMock()
        with patch("skillforge.flet.components.chat_message.PROJECT_ROOT", Path("/fake")):
            from skillforge.flet.components.chat_message import ChatMessage

            cm = ChatMessage(text="Hello world", is_user=True, timestamp="12:00")
            # Should have 2 controls: avatar + message_column
            assert len(cm.controls) == 2

    def test_message_with_attachments_renders_images(self, tmp_path):
        """ChatMessage with attachments should include ft.Image controls."""
        attachment = _sample_attachment(tmp_path, "photo.jpg")

        with patch("skillforge.flet.components.chat_message.PROJECT_ROOT", Path("/fake")):
            from skillforge.flet.components.chat_message import ChatMessage

            cm = ChatMessage(
                text="Check this photo",
                is_user=True,
                timestamp="12:00",
                attachments=[attachment],
            )
            # Should have 2 controls: avatar + message_column
            assert len(cm.controls) == 2

            # controls[1] is the bubble Container, its content is a Column
            message_column = cm.controls[1].content
            controls = message_column.controls
            # At least: label, image_container, body, timestamp = 4
            assert len(controls) >= 4

            # Second control should be a Container with an ft.Image
            import flet as ft
            image_container = controls[1]
            assert isinstance(image_container, ft.Container)
            image_widget = image_container.content
            assert isinstance(image_widget, ft.Image)

    def test_message_with_multiple_attachments(self, tmp_path):
        """Multiple attachments should all render as images."""
        att1 = _sample_attachment(tmp_path, "photo1.jpg")
        att2 = _sample_attachment(tmp_path, "photo2.jpg")

        with patch("skillforge.flet.components.chat_message.PROJECT_ROOT", Path("/fake")):
            from skillforge.flet.components.chat_message import ChatMessage

            cm = ChatMessage(
                text="Two photos",
                is_user=False,
                timestamp="12:00",
                attachments=[att1, att2],
            )

            message_column = cm.controls[1].content
            controls = message_column.controls
            # label + 2 image containers + body + timestamp = 5
            assert len(controls) >= 5

    def test_assistant_message_with_attachments(self, tmp_path):
        """Assistant messages with attachments should use Markdown for text."""
        attachment = _sample_attachment(tmp_path, "result.jpg")

        with patch("skillforge.flet.components.chat_message.PROJECT_ROOT", Path("/fake")):
            from skillforge.flet.components.chat_message import ChatMessage
            import flet as ft

            cm = ChatMessage(
                text="Here is the analysis",
                is_user=False,
                timestamp="12:00",
                attachments=[attachment],
            )

            message_column = cm.controls[1].content
            controls = message_column.controls
            # The text body (after images) should be Markdown for assistant
            body = controls[-2]  # second-to-last (before timestamp)
            assert isinstance(body, ft.Markdown)

    def test_user_message_with_attachments_uses_text(self, tmp_path):
        """User messages with attachments should use plain Text for body."""
        attachment = _sample_attachment(tmp_path, "photo.jpg")

        with patch("skillforge.flet.components.chat_message.PROJECT_ROOT", Path("/fake")):
            from skillforge.flet.components.chat_message import ChatMessage
            import flet as ft

            cm = ChatMessage(
                text="My vacation photo",
                is_user=True,
                timestamp="12:00",
                attachments=[attachment],
            )

            message_column = cm.controls[1].content
            controls = message_column.controls
            # The text body should be ft.Text for user
            body = controls[-2]  # second-to-last (before timestamp)
            assert isinstance(body, ft.Text)

    def test_backward_compat_no_attachments_param(self):
        """ChatMessage without attachments param should work (old call signature)."""
        with patch("skillforge.flet.components.chat_message.PROJECT_ROOT", Path("/fake")):
            from skillforge.flet.components.chat_message import ChatMessage

            # Old-style call without attachments param
            cm = ChatMessage(text="Old style message", is_user=False, timestamp="10:00")
            assert len(cm.controls) == 2

            message_column = cm.controls[1].content
            # label + body + timestamp = 3 controls (no images)
            assert len(message_column.controls) == 3


# =============================================================================
# Telegram Handler Registration Tests
# =============================================================================

class TestTelegramHandlerRegistration:
    """Test that photo and document handlers are registered."""

    @pytest.mark.asyncio
    async def test_initialize_registers_photo_handler(self):
        """initialize() should register a handler for PHOTO messages."""
        from skillforge.channels.telegram import TelegramChannel, TelegramConfig

        config = TelegramConfig(bot_token="fake-token-123")
        channel = TelegramChannel(config=config, message_handler=AsyncMock())

        with patch("skillforge.channels.telegram.Application") as MockApp:
            mock_app = MagicMock()
            mock_builder = MagicMock()
            mock_builder.token.return_value = mock_builder
            mock_builder.build.return_value = mock_app
            MockApp.builder.return_value = mock_builder

            await channel.initialize()

            # Count add_handler calls — should include at least one for PHOTO
            handler_calls = mock_app.add_handler.call_args_list
            assert len(handler_calls) >= 6  # start, help, reset, stats, text, photo, doc, skill


# =============================================================================
# Integration: Attachment dataclass compatibility
# =============================================================================

class TestAttachmentIntegration:
    """Test that Attachment objects work across channel boundaries."""

    def test_attachment_has_required_fields(self, tmp_path):
        """Attachment created by a channel should have all fields the router needs."""
        att = _sample_attachment(tmp_path)
        assert hasattr(att, "file_path")
        assert hasattr(att, "original_filename")
        assert hasattr(att, "mime_type")
        assert hasattr(att, "size_bytes")
        assert att.file_path
        assert att.original_filename
        assert att.mime_type in EXTENSION_TO_MIME.values()
        assert att.size_bytes > 0

    def test_attachment_serialization_round_trip(self, tmp_path):
        """Attachment should survive to_dict/from_dict round trip."""
        att = _sample_attachment(tmp_path)
        d = att.to_dict()
        att2 = Attachment.from_dict(d)
        assert att2.file_path == att.file_path
        assert att2.mime_type == att.mime_type
        assert att2.size_bytes == att.size_bytes

    def test_attachment_file_exists(self, tmp_path):
        """Attachment file_path should point to an existing file."""
        att = _sample_attachment(tmp_path)
        assert Path(att.file_path).exists()


# =============================================================================
# End of test_channel_images.py
# =============================================================================
