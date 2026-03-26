# =============================================================================
# test_router_image_integration.py — Tests for E-003: Router image/vision integration
# =============================================================================

import json
import struct
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skillforge.core.image_handler import Attachment, ImageHandler
from skillforge.core.router import MessageRouter
from skillforge.core.sessions import SessionManager


# =============================================================================
# Helpers — create minimal valid image files for testing
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


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    llm = MagicMock()
    llm.model_name = "test-model"
    llm.provider_name = "test-provider"
    llm.config = MagicMock()
    llm.config.base_url = "http://localhost"
    llm.config.model = "test-model"
    llm.check_context_size.return_value = {"needs_compaction": False, "total_tokens": 100}
    llm.chat.return_value = "I can see your image!"
    llm.estimate_tokens.return_value = 50
    # Default: no vision support
    llm.supports_vision = False
    return llm


@pytest.fixture
def mock_llm_vision():
    """Create a mock LLM provider WITH vision support."""
    llm = MagicMock()
    llm.model_name = "gpt-4-vision"
    llm.provider_name = "openai"
    llm.config = MagicMock()
    llm.config.base_url = "http://localhost"
    llm.config.model = "gpt-4-vision"
    llm.check_context_size.return_value = {"needs_compaction": False, "total_tokens": 100}
    llm.chat.return_value = "I can see a cat in this image!"
    llm.estimate_tokens.return_value = 50
    llm.supports_vision = True
    llm.format_vision_messages.side_effect = lambda msgs, atts: msgs  # pass through
    return llm


@pytest.fixture
def router(tmp_path, mock_llm):
    """Create a MessageRouter with temp session storage."""
    sm = SessionManager(str(tmp_path / "sessions"))
    r = MessageRouter(sm, mock_llm)
    # Point todo handler to temp file
    r._todo_handler._data_file = tmp_path / "todos.json"
    r._todo_handler._save_data({})
    # Point file access manager to temp directory
    from skillforge.core.file_access import FileAccessManager
    r._file_access = FileAccessManager(project_root=tmp_path)
    # Disable permission system for unit tests (all users get full access)
    from skillforge.core.user_permissions import PermissionManager
    r._permission_manager = PermissionManager(data_dir=tmp_path / "perm_data")
    # Point image handler to temp directory
    r._image_handler = ImageHandler(data_dir=str(tmp_path / "images"))
    return r


@pytest.fixture
def router_vision(tmp_path, mock_llm_vision):
    """Create a MessageRouter with vision-capable LLM."""
    sm = SessionManager(str(tmp_path / "sessions"))
    r = MessageRouter(sm, mock_llm_vision)
    r._todo_handler._data_file = tmp_path / "todos.json"
    r._todo_handler._save_data({})
    from skillforge.core.file_access import FileAccessManager
    r._file_access = FileAccessManager(project_root=tmp_path)
    from skillforge.core.user_permissions import PermissionManager
    r._permission_manager = PermissionManager(data_dir=tmp_path / "perm_data")
    r._image_handler = ImageHandler(data_dir=str(tmp_path / "images"))
    return r


@pytest.fixture
def sample_png(tmp_path):
    """Create a sample PNG file."""
    return _make_png(tmp_path / "test_photo.png")


@pytest.fixture
def sample_attachment(sample_png):
    """Create a sample Attachment from the test PNG."""
    return Attachment(
        file_path=str(sample_png),
        original_filename="test_photo.png",
        mime_type="image/png",
        size_bytes=sample_png.stat().st_size,
    )


# =============================================================================
# Test: Router has image handler
# =============================================================================

class TestRouterImageInit:
    """Test that the router initializes the image handler."""

    def test_has_image_handler(self, router):
        assert router._image_handler is not None
        assert isinstance(router._image_handler, ImageHandler)


# =============================================================================
# Test: handle_message backward compatibility (no attachments)
# =============================================================================

class TestBackwardCompatibility:
    """Ensure handle_message works identically without attachments."""

    @pytest.mark.asyncio
    async def test_no_attachments_works(self, router, mock_llm):
        """Calling handle_message without attachments should work as before."""
        response = await router.handle_message(
            channel="test", user_id="u1", user_message="hello",
        )
        assert response  # Should get a response
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_attachments_none_works(self, router, mock_llm):
        """Explicitly passing attachments=None should work."""
        response = await router.handle_message(
            channel="test", user_id="u1", user_message="hello",
            attachments=None,
        )
        assert response
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_attachments_works(self, router, mock_llm):
        """Passing an empty list of attachments should work."""
        response = await router.handle_message(
            channel="test", user_id="u1", user_message="hello",
            attachments=[],
        )
        assert response
        mock_llm.chat.assert_called_once()


# =============================================================================
# Test: handle_message with attachments stores images
# =============================================================================

class TestAttachmentStorage:
    """Test that attachments are stored via ImageHandler."""

    @pytest.mark.asyncio
    async def test_attachment_stored(self, router, sample_attachment, mock_llm):
        """Images should be stored when attachments are provided."""
        response = await router.handle_message(
            channel="test", user_id="u1",
            user_message="describe this image",
            attachments=[sample_attachment],
        )
        assert response
        # Check that images were stored
        images = router._image_handler.get_images_for_session("test:direct:u1")
        assert len(images) == 1

    @pytest.mark.asyncio
    async def test_multiple_attachments_stored(self, router, tmp_path, mock_llm):
        """Multiple images should all be stored."""
        png1 = _make_png(tmp_path / "img1.png")
        png2 = _make_png(tmp_path / "img2.png")
        atts = [
            Attachment(file_path=str(png1), original_filename="img1.png",
                       mime_type="image/png", size_bytes=png1.stat().st_size),
            Attachment(file_path=str(png2), original_filename="img2.png",
                       mime_type="image/png", size_bytes=png2.stat().st_size),
        ]
        response = await router.handle_message(
            channel="test", user_id="u1",
            user_message="compare these images",
            attachments=atts,
        )
        assert response
        images = router._image_handler.get_images_for_session("test:direct:u1")
        assert len(images) == 2

    @pytest.mark.asyncio
    async def test_invalid_attachment_gracefully_skipped(self, router, tmp_path, mock_llm):
        """An invalid image path should be skipped, not crash."""
        bad_att = Attachment(
            file_path=str(tmp_path / "nonexistent.png"),
            original_filename="ghost.png",
            mime_type="image/png",
            size_bytes=0,
        )
        response = await router.handle_message(
            channel="test", user_id="u1",
            user_message="what about this?",
            attachments=[bad_att],
        )
        assert response  # Should still get a text response


# =============================================================================
# Test: Vision formatting is called when provider supports it
# =============================================================================

class TestVisionFormatting:
    """Test that format_vision_messages is called for vision providers."""

    @pytest.mark.asyncio
    async def test_vision_provider_format_called(self, router_vision, sample_attachment, mock_llm_vision):
        """When LLM supports vision, format_vision_messages should be called."""
        response = await router_vision.handle_message(
            channel="test", user_id="u1",
            user_message="describe this",
            attachments=[sample_attachment],
        )
        assert response
        mock_llm_vision.format_vision_messages.assert_called_once()
        # Verify correct arguments: messages list and stored attachments
        call_args = mock_llm_vision.format_vision_messages.call_args
        messages_arg = call_args[0][0]
        atts_arg = call_args[0][1]
        assert isinstance(messages_arg, list)
        assert len(atts_arg) == 1
        assert atts_arg[0].mime_type == "image/png"

    @pytest.mark.asyncio
    async def test_vision_provider_no_format_without_attachments(self, router_vision, mock_llm_vision):
        """Without attachments, format_vision_messages should NOT be called."""
        response = await router_vision.handle_message(
            channel="test", user_id="u1",
            user_message="hello",
        )
        assert response
        mock_llm_vision.format_vision_messages.assert_not_called()


# =============================================================================
# Test: Non-vision provider gets fallback note
# =============================================================================

class TestNonVisionFallback:
    """Test that non-vision providers get a fallback note in messages."""

    @pytest.mark.asyncio
    async def test_non_vision_appends_note(self, router, sample_attachment, mock_llm):
        """When LLM does NOT support vision, a note should be appended."""
        response = await router.handle_message(
            channel="test", user_id="u1",
            user_message="what is this?",
            attachments=[sample_attachment],
        )
        assert response
        # Check the messages passed to llm.chat
        call_args = mock_llm.chat.call_args
        messages = call_args[0][0]
        # Find the last user message
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert user_msgs
        last_user_msg = user_msgs[-1]["content"]
        assert "does not support image analysis" in last_user_msg
        assert "test-model" in last_user_msg

    @pytest.mark.asyncio
    async def test_non_vision_no_note_without_attachments(self, router, mock_llm):
        """Without attachments, no fallback note should appear."""
        response = await router.handle_message(
            channel="test", user_id="u1",
            user_message="just text",
        )
        call_args = mock_llm.chat.call_args
        messages = call_args[0][0]
        user_msgs = [m for m in messages if m["role"] == "user"]
        for msg in user_msgs:
            assert "does not support image analysis" not in msg["content"]


# =============================================================================
# Test: Permission gating — user without 'files' permission
# =============================================================================

class TestPermissionGating:
    """Test that images are dropped when user lacks 'files' permission."""

    @pytest.mark.asyncio
    async def test_no_files_permission_drops_attachments(self, tmp_path, mock_llm):
        """When user lacks 'files' permission, attachments should be silently dropped."""
        sm = SessionManager(str(tmp_path / "sessions"))
        r = MessageRouter(sm, mock_llm)
        r._todo_handler._data_file = tmp_path / "todos.json"
        r._todo_handler._save_data({})
        from skillforge.core.file_access import FileAccessManager
        r._file_access = FileAccessManager(project_root=tmp_path)
        r._image_handler = ImageHandler(data_dir=str(tmp_path / "images"))

        # Set up permission manager with a restricted user
        from skillforge.core.user_permissions import PermissionManager
        perm_dir = tmp_path / "perm_data"
        perm_dir.mkdir(parents=True, exist_ok=True)
        r._permission_manager = PermissionManager(data_dir=perm_dir)
        # Enable the permission system and restrict the user
        r._permission_manager._enabled = True
        r._permission_manager._config = {
            "roles": {
                "restricted": {"permissions": ["chat"]},
            },
            "users": {
                "restricted_user": {"role": "restricted"},
            },
            "default_role": "restricted",
        }
        r._permission_manager._save()

        # Create a valid image attachment
        png = _make_png(tmp_path / "test.png")
        att = Attachment(
            file_path=str(png), original_filename="test.png",
            mime_type="image/png", size_bytes=png.stat().st_size,
        )

        response = await r.handle_message(
            channel="test", user_id="restricted_user",
            user_message="describe this",
            attachments=[att],
        )
        assert response
        # No images should have been stored
        images = r._image_handler.get_images_for_session("test:direct:restricted_user")
        assert len(images) == 0

        # And no vision note should appear (no attachments = no note)
        call_args = mock_llm.chat.call_args
        messages = call_args[0][0]
        user_msgs = [m for m in messages if m["role"] == "user"]
        for msg in user_msgs:
            assert "does not support image analysis" not in msg["content"]


# =============================================================================
# Test: JSONL records attachment references
# =============================================================================

class TestJSONLAttachmentRecording:
    """Test that session JSONL entries contain attachment metadata."""

    @pytest.mark.asyncio
    async def test_jsonl_has_attachment_metadata(self, router, sample_attachment, mock_llm):
        """The JSONL user message entry should contain attachment references."""
        await router.handle_message(
            channel="test", user_id="u1",
            user_message="describe this",
            attachments=[sample_attachment],
        )

        # Read the JSONL file directly
        session_key = router.session_manager.get_session_key("test", "u1")
        session = router.session_manager.sessions[session_key]
        session_file = Path(session["sessionFile"])

        entries = []
        with open(session_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

        # Find the user message entry
        user_entries = [e for e in entries if e.get("type") == "message" and e.get("role") == "user"]
        assert len(user_entries) >= 1
        user_entry = user_entries[-1]

        # Check metadata contains attachments
        metadata = user_entry.get("metadata", {})
        assert "attachments" in metadata
        atts = metadata["attachments"]
        assert len(atts) == 1
        assert atts[0]["original_filename"] == "test_photo.png"
        assert atts[0]["mime_type"] == "image/png"
        assert atts[0]["size_bytes"] > 0
        assert atts[0]["file_path"]  # Non-empty

    @pytest.mark.asyncio
    async def test_jsonl_no_metadata_without_attachments(self, router, mock_llm):
        """Without attachments, the JSONL entry should not have attachment metadata."""
        await router.handle_message(
            channel="test", user_id="u1",
            user_message="just text",
        )

        session_key = router.session_manager.get_session_key("test", "u1")
        session = router.session_manager.sessions[session_key]
        session_file = Path(session["sessionFile"])

        entries = []
        with open(session_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

        user_entries = [e for e in entries if e.get("type") == "message" and e.get("role") == "user"]
        assert len(user_entries) >= 1
        user_entry = user_entries[-1]
        metadata = user_entry.get("metadata")
        assert metadata is None or "attachments" not in metadata


# =============================================================================
# Test: Session history includes attachment refs
# =============================================================================

class TestSessionHistoryAttachments:
    """Test that get_conversation_history includes _attachments in messages."""

    @pytest.mark.asyncio
    async def test_history_includes_attachments(self, router, sample_attachment, mock_llm):
        """Conversation history should include _attachments for image messages."""
        await router.handle_message(
            channel="test", user_id="u1",
            user_message="look at this",
            attachments=[sample_attachment],
        )

        session_key = router.session_manager.get_session_key("test", "u1")
        history = router.session_manager.get_conversation_history(session_key)

        # Find user message with attachments
        user_msgs = [m for m in history if m["role"] == "user"]
        assert len(user_msgs) >= 1
        # The message with attachment should have _attachments key
        has_atts = any("_attachments" in m for m in user_msgs)
        assert has_atts, "Expected _attachments key in user message history"

        att_msg = [m for m in user_msgs if "_attachments" in m][0]
        assert len(att_msg["_attachments"]) == 1
        assert att_msg["_attachments"][0]["mime_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_history_no_attachments_key_for_text(self, router, mock_llm):
        """Text-only messages should NOT have _attachments key."""
        await router.handle_message(
            channel="test", user_id="u1",
            user_message="plain text",
        )

        session_key = router.session_manager.get_session_key("test", "u1")
        history = router.session_manager.get_conversation_history(session_key)

        user_msgs = [m for m in history if m["role"] == "user"]
        for msg in user_msgs:
            assert "_attachments" not in msg


# =============================================================================
# Test: Streaming path (handle_message_stream)
# =============================================================================

class TestStreamingWithAttachments:
    """Test that handle_message_stream also supports attachments."""

    @pytest.mark.asyncio
    async def test_stream_with_attachments_stores(self, router, sample_attachment, mock_llm):
        """Streaming with attachments should store images."""
        mock_llm.chat_stream.return_value = iter(["Hello", " there"])

        chunks = []
        async for chunk in router.handle_message_stream(
            channel="test", user_id="u1",
            user_message="what is this?",
            attachments=[sample_attachment],
        ):
            chunks.append(chunk)

        assert chunks  # Got some response
        images = router._image_handler.get_images_for_session("test:direct:u1")
        assert len(images) == 1

    @pytest.mark.asyncio
    async def test_stream_without_attachments(self, router, mock_llm):
        """Streaming without attachments should work normally."""
        mock_llm.chat_stream.return_value = iter(["Hi"])

        chunks = []
        async for chunk in router.handle_message_stream(
            channel="test", user_id="u1",
            user_message="hello",
        ):
            chunks.append(chunk)

        assert chunks

    @pytest.mark.asyncio
    async def test_stream_vision_format_called(self, router_vision, sample_attachment, mock_llm_vision):
        """Streaming with vision provider should call format_vision_messages."""
        mock_llm_vision.chat_stream.return_value = iter(["A cat!"])

        chunks = []
        async for chunk in router_vision.handle_message_stream(
            channel="test", user_id="u1",
            user_message="what animal?",
            attachments=[sample_attachment],
        ):
            chunks.append(chunk)

        assert chunks
        mock_llm_vision.format_vision_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_non_vision_fallback_note(self, router, sample_attachment, mock_llm):
        """Streaming with non-vision provider should add fallback note."""
        mock_llm.chat_stream.return_value = iter(["I can't see images."])

        chunks = []
        async for chunk in router.handle_message_stream(
            channel="test", user_id="u1",
            user_message="what is this?",
            attachments=[sample_attachment],
        ):
            chunks.append(chunk)

        # Verify the fallback note was added to messages before calling chat_stream
        call_args = mock_llm.chat_stream.call_args
        messages = call_args[0][0]
        user_msgs = [m for m in messages if m["role"] == "user"]
        last_user_msg = user_msgs[-1]["content"]
        assert "does not support image analysis" in last_user_msg


# =============================================================================
# End of test_router_image_integration.py
# =============================================================================
