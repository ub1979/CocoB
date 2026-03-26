# =============================================================================
# test_channel_outbound.py -- Tests for E-005: Channel Outbound image handling
#
# Tests image path extraction, Telegram send_image, WhatsApp send_image,
# Flet response handling, backward compat, and mixed content.
# =============================================================================

import asyncio
import base64
import os
import struct
import zlib
from pathlib import Path
from typing import Optional, List
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock, call

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


# =============================================================================
# Part A: Router — Image path extraction utility
# =============================================================================

class TestExtractOutboundImages:
    """Test MessageRouter.extract_outbound_images()."""

    def _extract(self, text):
        from skillforge.core.router import MessageRouter
        return MessageRouter.extract_outbound_images(text)

    def test_no_images_returns_original(self):
        """Text without image markers is returned unchanged."""
        text = "Here is a plain response with no images."
        cleaned, paths = self._extract(text)
        assert cleaned == text
        assert paths == []

    def test_generated_image_marker(self, tmp_path):
        """[Generated Image: /path.png] is extracted and cleaned."""
        img = _make_png(tmp_path / "gen.png")
        text = f"Here is your image:\n[Generated Image: {img}]\nEnjoy!"
        cleaned, paths = self._extract(text)
        assert str(img) in paths
        assert "[Generated Image:" not in cleaned
        assert "Enjoy!" in cleaned

    def test_saved_to_marker(self, tmp_path):
        """- Saved to: `/path.png` is extracted and cleaned."""
        img = _make_png(tmp_path / "saved.png")
        text = f"**Image Generated**\n- Prompt: sunset\n- Saved to: `{img}`\nDone."
        cleaned, paths = self._extract(text)
        assert str(img) in paths
        assert "Saved to:" not in cleaned
        assert "Done." in cleaned

    def test_markdown_image(self, tmp_path):
        """![alt](/path.png) is extracted and cleaned."""
        img = _make_png(tmp_path / "md.png")
        text = f"Check this out:\n![result]({img})\nPretty cool."
        cleaned, paths = self._extract(text)
        assert str(img) in paths
        assert "![result]" not in cleaned
        assert "Pretty cool." in cleaned

    def test_multiple_images(self, tmp_path):
        """Multiple image markers in one response are all extracted."""
        img1 = _make_png(tmp_path / "a.png")
        img2 = _make_jpeg(tmp_path / "b.jpg")
        text = f"[Generated Image: {img1}]\nAnd also:\n[Generated Image: {img2}]"
        cleaned, paths = self._extract(text)
        assert len(paths) == 2
        assert str(img1) in paths
        assert str(img2) in paths

    def test_nonexistent_file_filtered(self, tmp_path):
        """Paths to non-existent files are silently dropped."""
        text = "[Generated Image: /nonexistent/path/to/image.png]"
        cleaned, paths = self._extract(text)
        assert paths == []
        # Marker is still cleaned from the text
        assert "[Generated Image:" not in cleaned

    def test_http_url_preserved(self):
        """HTTP(S) URLs are preserved without filesystem check."""
        url = "https://example.com/image.png"
        text = f"[Generated Image: {url}]"
        cleaned, paths = self._extract(text)
        assert url in paths

    def test_duplicate_paths_deduplicated(self, tmp_path):
        """Same image referenced twice should only appear once."""
        img = _make_png(tmp_path / "dup.png")
        text = f"[Generated Image: {img}]\nAgain: [Generated Image: {img}]"
        cleaned, paths = self._extract(text)
        assert len(paths) == 1

    def test_empty_response(self):
        """Empty string returns empty results."""
        cleaned, paths = self._extract("")
        assert cleaned == ""
        assert paths == []

    def test_mixed_text_and_images(self, tmp_path):
        """Response with both text and images is properly split."""
        img = _make_png(tmp_path / "mix.png")
        text = (
            "I generated an image for you.\n\n"
            f"[Generated Image: {img}]\n\n"
            "The image shows a beautiful sunset over the mountains."
        )
        cleaned, paths = self._extract(text)
        assert len(paths) == 1
        assert "generated an image" in cleaned
        assert "beautiful sunset" in cleaned
        assert "[Generated Image:" not in cleaned

    def test_blank_lines_collapsed(self, tmp_path):
        """Removing markers should not leave excessive blank lines."""
        img = _make_png(tmp_path / "bl.png")
        text = f"Line 1.\n\n\n[Generated Image: {img}]\n\n\nLine 2."
        cleaned, paths = self._extract(text)
        assert "\n\n\n" not in cleaned


# =============================================================================
# Part B: Telegram send_image
# =============================================================================

class TestTelegramSendImage:
    """Test TelegramChannel.send_image()."""

    @pytest.fixture
    def tg_channel(self):
        from skillforge.channels.telegram import TelegramChannel, TelegramConfig

        config = TelegramConfig(bot_token="fake-token")
        handler = AsyncMock(return_value="OK")
        channel = TelegramChannel(config=config, message_handler=handler)
        return channel

    @pytest.mark.asyncio
    async def test_send_local_image_via_reply(self, tg_channel, tmp_path):
        """send_image with an update should use reply_photo."""
        img = _make_png(tmp_path / "photo.png")

        update = MagicMock()
        update.message.reply_photo = AsyncMock()

        result = await tg_channel.send_image(
            chat_id="12345",
            image_path=str(img),
            caption="A photo",
            update=update,
        )

        assert result is True
        update.message.reply_photo.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_local_image_via_bot(self, tg_channel, tmp_path):
        """send_image without update should use application.bot.send_photo."""
        img = _make_png(tmp_path / "photo.png")

        tg_channel.application = MagicMock()
        tg_channel.application.bot.send_photo = AsyncMock()

        result = await tg_channel.send_image(
            chat_id="12345",
            image_path=str(img),
        )

        assert result is True
        tg_channel.application.bot.send_photo.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_url_image(self, tg_channel):
        """send_image with an HTTP URL passes the URL string."""
        tg_channel.application = MagicMock()
        tg_channel.application.bot.send_photo = AsyncMock()

        url = "https://example.com/image.png"
        result = await tg_channel.send_image(chat_id="12345", image_path=url)

        assert result is True
        call_kwargs = tg_channel.application.bot.send_photo.call_args
        assert call_kwargs.kwargs["photo"] == url

    @pytest.mark.asyncio
    async def test_send_image_file_not_found(self, tg_channel):
        """send_image for a missing file should return False."""
        result = await tg_channel.send_image(
            chat_id="12345",
            image_path="/nonexistent/photo.png",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_send_image_no_application(self, tg_channel):
        """send_image without application or update should return False."""
        tg_channel.application = None
        result = await tg_channel.send_image(
            chat_id="12345",
            image_path="https://example.com/img.png",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_send_image_error_fallback(self, tg_channel, tmp_path):
        """On send_photo error, fallback to text message."""
        img = _make_png(tmp_path / "err.png")

        tg_channel.application = MagicMock()
        tg_channel.application.bot.send_photo = AsyncMock(
            side_effect=Exception("API error")
        )
        tg_channel.application.bot.send_message = AsyncMock()

        result = await tg_channel.send_image(chat_id="12345", image_path=str(img))
        # send_image returns False but tries fallback
        assert result is False


class TestTelegramOutboundIntegration:
    """Test that _process_message detects and sends outbound images."""

    @pytest.fixture
    def tg_channel(self):
        from skillforge.channels.telegram import TelegramChannel, TelegramConfig

        config = TelegramConfig(bot_token="fake-token")
        channel = TelegramChannel(config=config)
        return channel

    @pytest.mark.asyncio
    async def test_response_with_image_sends_photo(self, tg_channel, tmp_path):
        """If router returns a response with [Generated Image:...], send_image is called."""
        img = _make_png(tmp_path / "gen.png")
        response_text = f"Here is your image\n[Generated Image: {img}]"

        tg_channel.message_handler = AsyncMock(return_value=response_text)
        tg_channel.send_message = AsyncMock(return_value=True)
        tg_channel.send_image = AsyncMock(return_value=True)

        update = MagicMock()
        update.effective_user.id = 1
        update.effective_user.first_name = "U"
        update.effective_chat.id = 2
        update.effective_chat.send_action = AsyncMock()
        update.message.reply_text = AsyncMock()

        await tg_channel._process_message(update=update, user_message="generate sunset")

        # send_image should have been called for the image
        tg_channel.send_image.assert_called_once()
        call_kwargs = tg_channel.send_image.call_args
        assert str(img) in str(call_kwargs)

        # send_message should be called for the cleaned text
        tg_channel.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_without_image_sends_text_only(self, tg_channel):
        """Plain text response should use send_message only."""
        tg_channel.message_handler = AsyncMock(return_value="Hello world")
        tg_channel.send_message = AsyncMock(return_value=True)
        tg_channel.send_image = AsyncMock()

        update = MagicMock()
        update.effective_user.id = 1
        update.effective_user.first_name = "U"
        update.effective_chat.id = 2
        update.effective_chat.send_action = AsyncMock()
        update.message.reply_text = AsyncMock()

        await tg_channel._process_message(update=update, user_message="hello")

        tg_channel.send_message.assert_called_once()
        tg_channel.send_image.assert_not_called()


# =============================================================================
# Part C: WhatsApp send_image
# =============================================================================

class TestWhatsAppSendImage:
    """Test WhatsAppChannel.send_image()."""

    @pytest.fixture
    def wa_channel(self):
        from skillforge.channels.whatsapp import WhatsAppChannel, WhatsAppConfig

        config = WhatsAppConfig(service_url="http://localhost:3979")
        channel = WhatsAppChannel(config=config)
        channel.is_connected = True
        return channel

    @pytest.mark.asyncio
    async def test_send_local_image(self, wa_channel, tmp_path):
        """Send a local image file via base64 to /send-media."""
        img = _make_png(tmp_path / "photo.png")

        mock_resp = MagicMock()
        mock_resp.status = 200

        class _MockCtx:
            async def __aenter__(self):
                return mock_resp
            async def __aexit__(self, *args):
                pass

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_MockCtx())
        wa_channel._get_session = AsyncMock(return_value=mock_session)

        result = await wa_channel.send_image("123@s.whatsapp.net", str(img), caption="Hi")

        assert result is True
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "/send-media" in call_args[0][0]
        payload = call_args[1]["json"]
        assert "image" in payload
        assert payload["caption"] == "Hi"

    @pytest.mark.asyncio
    async def test_send_url_image(self, wa_channel):
        """Send an image URL to /send-media."""
        mock_resp = MagicMock()
        mock_resp.status = 200

        class _MockCtx:
            async def __aenter__(self):
                return mock_resp
            async def __aexit__(self, *args):
                pass

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_MockCtx())
        wa_channel._get_session = AsyncMock(return_value=mock_session)

        url = "https://example.com/image.png"
        result = await wa_channel.send_image("123@s.whatsapp.net", url)

        assert result is True
        payload = mock_session.post.call_args[1]["json"]
        assert payload["imageUrl"] == url

    @pytest.mark.asyncio
    async def test_send_image_file_not_found(self, wa_channel):
        """Missing local file should return False."""
        result = await wa_channel.send_image(
            "123@s.whatsapp.net",
            "/nonexistent/photo.png",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_send_image_not_connected(self, wa_channel):
        """Should return False when not connected."""
        wa_channel.is_connected = False

        # Mock check_status to return not connected
        wa_channel.check_status = AsyncMock(return_value={"connected": False})

        result = await wa_channel.send_image(
            "123@s.whatsapp.net",
            "https://example.com/img.png",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_send_image_service_error(self, wa_channel, tmp_path):
        """Service returning non-200 should return False."""
        img = _make_png(tmp_path / "err.png")

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

        result = await wa_channel.send_image("123@s.whatsapp.net", str(img))
        assert result is False

    @pytest.mark.asyncio
    async def test_send_image_phone_number_format(self, wa_channel, tmp_path):
        """Phone number (no @) should use 'to' key in payload."""
        img = _make_png(tmp_path / "ph.png")

        mock_resp = MagicMock()
        mock_resp.status = 200

        class _MockCtx:
            async def __aenter__(self):
                return mock_resp
            async def __aexit__(self, *args):
                pass

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=_MockCtx())
        wa_channel._get_session = AsyncMock(return_value=mock_session)

        result = await wa_channel.send_image("1234567890", str(img))
        assert result is True
        payload = mock_session.post.call_args[1]["json"]
        assert "to" in payload
        assert "chatId" not in payload


class TestWhatsAppOutboundIntegration:
    """Test that handle_incoming_webhook detects and sends outbound images."""

    @pytest.fixture
    def wa_channel(self):
        from skillforge.channels.whatsapp import WhatsAppChannel, WhatsAppConfig

        config = WhatsAppConfig(service_url="http://localhost:3979")
        channel = WhatsAppChannel(config=config)
        channel.is_connected = True
        return channel

    @pytest.mark.asyncio
    async def test_response_with_image_sends_image(self, wa_channel, tmp_path):
        """Webhook response with image marker should call send_image."""
        img = _make_png(tmp_path / "resp.png")
        response = f"Generated!\n[Generated Image: {img}]"

        wa_channel.message_handler = AsyncMock(return_value=response)
        wa_channel.send_message = AsyncMock(return_value=True)
        wa_channel.send_image = AsyncMock(return_value=True)

        data = {
            "chatId": "123@s.whatsapp.net",
            "senderId": "123",
            "senderName": "Test",
            "content": "generate image",
            "messageType": "text",
        }

        result = await wa_channel.handle_incoming_webhook(data)

        assert result == response
        wa_channel.send_image.assert_called_once()
        wa_channel.send_message.assert_called_once()  # For the cleaned text

    @pytest.mark.asyncio
    async def test_response_without_image_sends_text(self, wa_channel):
        """Plain text response should only call send_message."""
        wa_channel.message_handler = AsyncMock(return_value="Hello!")
        wa_channel.send_message = AsyncMock(return_value=True)
        wa_channel.send_image = AsyncMock()

        data = {
            "chatId": "123@s.whatsapp.net",
            "senderId": "123",
            "senderName": "Test",
            "content": "hi",
            "messageType": "text",
        }

        await wa_channel.handle_incoming_webhook(data)
        wa_channel.send_message.assert_called_once()
        wa_channel.send_image.assert_not_called()


# =============================================================================
# Part D: Flet UI — _update_bot_message creates Attachments from images
# =============================================================================

class TestFletOutboundImages:
    """Test that _update_bot_message creates Attachments for outbound images."""

    def test_bot_response_with_image_creates_attachment(self, tmp_path):
        """_update_bot_message should detect images and pass Attachments to ChatMessage."""
        img = _make_png(tmp_path / "flet_out.png")
        text = f"Here is the result\n[Generated Image: {img}]"

        # We need to test that ChatMessage is constructed with attachments
        with patch("skillforge.flet.components.chat_message.PROJECT_ROOT", Path("/fake")):
            from skillforge.flet.views.chat import ChatView

            # Create a minimal ChatView with mocks
            page = MagicMock()
            page.update = MagicMock()

            view = ChatView.__new__(ChatView)
            view.page = page
            view.messages_list = MagicMock()
            view.messages_list.controls = []
            view._typing_row = None
            view._last_ui_update = 0.0

            # Call _update_bot_message
            view._update_bot_message(text, is_partial=False)

            # Verify a ChatMessage was appended
            assert len(view.messages_list.controls) == 1
            msg = view.messages_list.controls[0]
            # The message should have been constructed with attachments
            # Check the controls — avatar + message_column
            message_column = msg.controls[1].content
            # Should have: label + image container + body + timestamp = 4
            assert len(message_column.controls) >= 4

    def test_bot_response_without_image_no_attachments(self):
        """Plain text response should not create attachments."""
        text = "Just a simple response."

        with patch("skillforge.flet.components.chat_message.PROJECT_ROOT", Path("/fake")):
            from skillforge.flet.views.chat import ChatView

            page = MagicMock()
            page.update = MagicMock()

            view = ChatView.__new__(ChatView)
            view.page = page
            view.messages_list = MagicMock()
            view.messages_list.controls = []
            view._typing_row = None
            view._last_ui_update = 0.0

            view._update_bot_message(text, is_partial=False)

            assert len(view.messages_list.controls) == 1
            msg = view.messages_list.controls[0]
            message_column = msg.controls[1].content
            # label + body + timestamp = 3 controls (no image)
            assert len(message_column.controls) == 3

    def test_partial_response_no_image_extraction(self, tmp_path):
        """Partial (streaming) responses should NOT attempt image extraction."""
        img = _make_png(tmp_path / "partial.png")
        text = f"[Generated Image: {img}]"

        with patch("skillforge.flet.components.chat_message.PROJECT_ROOT", Path("/fake")):
            from skillforge.flet.views.chat import ChatView

            page = MagicMock()
            page.update = MagicMock()

            view = ChatView.__new__(ChatView)
            view.page = page
            view.messages_list = MagicMock()
            view.messages_list.controls = []
            view._typing_row = None
            view._last_ui_update = 0.0

            # Partial — should not extract
            view._update_bot_message(text, is_partial=True)

            msg = view.messages_list.controls[0]
            message_column = msg.controls[1].content
            # Partial: no image extraction → label + body + timestamp = 3
            # (the raw marker text is in the Markdown body)
            assert len(message_column.controls) == 3


# =============================================================================
# Backward compatibility
# =============================================================================

class TestBackwardCompatibility:
    """Verify that responses without images work identically to before."""

    def test_extract_plain_text(self):
        """Plain text passes through extract_outbound_images unchanged."""
        from skillforge.core.router import MessageRouter
        text = "This is a normal response without any images."
        cleaned, paths = MessageRouter.extract_outbound_images(text)
        assert cleaned == text
        assert paths == []

    def test_extract_code_blocks(self):
        """Code blocks with file paths should NOT be extracted."""
        from skillforge.core.router import MessageRouter
        text = "Here is some code:\n```python\npath = '/data/image.png'\n```"
        cleaned, paths = MessageRouter.extract_outbound_images(text)
        assert paths == []

    def test_extract_markdown_link_not_image(self):
        """Regular markdown links (not images) should be untouched."""
        from skillforge.core.router import MessageRouter
        text = "Check [this link](https://example.com/page.html) out."
        cleaned, paths = MessageRouter.extract_outbound_images(text)
        assert cleaned == text
        assert paths == []


# =============================================================================
# Edge cases and mixed content
# =============================================================================

class TestMixedContent:
    """Test responses with both text and various image formats."""

    def test_image_gen_handler_output_format(self, tmp_path):
        """Test the exact output format from image_gen_handler._format_results."""
        from skillforge.core.router import MessageRouter
        img = _make_png(tmp_path / "gen_output.png")

        # This is the exact format _format_results produces
        text = (
            "**Image Generated**\n"
            f"- Prompt: A sunset\n"
            f"- Style: realistic\n"
            f"- Size: 1024x1024\n"
            f"- Saved to: `{img}`"
        )
        cleaned, paths = MessageRouter.extract_outbound_images(text)
        assert str(img) in paths
        assert "Saved to:" not in cleaned
        assert "**Image Generated**" in cleaned
        assert "Prompt: A sunset" in cleaned

    def test_multiple_generated_images_with_text(self, tmp_path):
        """Multiple images with surrounding text."""
        from skillforge.core.router import MessageRouter
        img1 = _make_png(tmp_path / "one.png")
        img2 = _make_jpeg(tmp_path / "two.jpg")

        text = (
            f"I created two images for you:\n\n"
            f"First: [Generated Image: {img1}]\n\n"
            f"Second: [Generated Image: {img2}]\n\n"
            f"Hope you like them!"
        )
        cleaned, paths = MessageRouter.extract_outbound_images(text)
        assert len(paths) == 2
        assert str(img1) in paths
        assert str(img2) in paths
        assert "created two images" in cleaned
        assert "Hope you like them!" in cleaned
        assert "[Generated Image:" not in cleaned

    def test_url_and_local_file_mixed(self, tmp_path):
        """Mix of local file and URL in same response."""
        from skillforge.core.router import MessageRouter
        img = _make_png(tmp_path / "local.png")
        url = "https://cdn.example.com/remote.jpg"

        text = f"[Generated Image: {img}]\n[Generated Image: {url}]"
        cleaned, paths = MessageRouter.extract_outbound_images(text)
        assert len(paths) == 2
        assert str(img) in paths
        assert url in paths


# =============================================================================
# End of test_channel_outbound.py
# =============================================================================
