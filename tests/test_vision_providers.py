# =============================================================================
'''
    File Name : test_vision_providers.py

    Description : Tests for LLM provider vision support (E-002).
                  Validates supports_vision property, format_vision_messages
                  output for OpenAI, Anthropic, and Gemini, backward compat,
                  and non-vision provider passthrough.

    Created on 2026-03-19

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - AI Assistant with Persistent Memory

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

import base64
import os
import struct
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from skillforge.core.image_handler import Attachment, ImageHandler
from skillforge.core.llm.base import LLMConfig, LLMProvider


# =============================================================================
# Helpers
# =============================================================================

def _make_tiny_png(path: str) -> None:
    """Create a minimal 1x1 red PNG file at *path*."""
    # Minimal valid PNG: 1x1 pixel, 8-bit RGBA, red
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1, 8-bit RGB
    ihdr = _chunk(b"IHDR", ihdr_data)
    # Raw row: filter byte (0) + R G B
    raw_row = b"\x00\xff\x00\x00"
    compressed = zlib.compress(raw_row)
    idat = _chunk(b"IDAT", compressed)
    iend = _chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(signature + ihdr + idat + iend)


def _make_tiny_jpeg(path: str) -> None:
    """Create a minimal valid JPEG file at *path*."""
    # Minimal JPEG: SOI + APP0 (JFIF) + a tiny scan + EOI
    # We'll use a known minimal JPEG byte sequence
    # This is the smallest valid JPEG (a 1x1 white pixel)
    data = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
        0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08,
        0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C,
        0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D,
        0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20,
        0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27,
        0x39, 0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34,
        0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4,
        0x00, 0x1F, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
        0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04,
        0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xFF,
        0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04,
        0x00, 0x00, 0x01, 0x7D, 0x01, 0x02, 0x03, 0x00,
        0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32,
        0x81, 0x91, 0xA1, 0x08, 0x23, 0x42, 0xB1, 0xC1,
        0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A,
        0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x34, 0x35,
        0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55,
        0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65,
        0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85,
        0x86, 0x87, 0x88, 0x89, 0x8A, 0x92, 0x93, 0x94,
        0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2,
        0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA,
        0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8,
        0xD9, 0xDA, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6,
        0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA,
        0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
        0x7B, 0x94, 0x11, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0xFF, 0xD9,
    ])
    with open(path, "wb") as f:
        f.write(data)


@pytest.fixture
def tmp_image_dir(tmp_path):
    """Temporary directory for test images and image handler storage."""
    return tmp_path


@pytest.fixture
def tiny_png(tmp_image_dir):
    """Create a tiny valid PNG file and return its path."""
    p = str(tmp_image_dir / "test.png")
    _make_tiny_png(p)
    return p


@pytest.fixture
def tiny_jpeg(tmp_image_dir):
    """Create a tiny valid JPEG file and return its path."""
    p = str(tmp_image_dir / "test.jpg")
    _make_tiny_jpeg(p)
    return p


@pytest.fixture
def png_attachment(tiny_png):
    """Return an Attachment for the tiny PNG."""
    return Attachment(
        file_path=tiny_png,
        original_filename="test.png",
        mime_type="image/png",
        size_bytes=os.path.getsize(tiny_png),
    )


@pytest.fixture
def jpeg_attachment(tiny_jpeg):
    """Return an Attachment for the tiny JPEG."""
    return Attachment(
        file_path=tiny_jpeg,
        original_filename="photo.jpg",
        mime_type="image/jpeg",
        size_bytes=os.path.getsize(tiny_jpeg),
    )


@pytest.fixture
def sample_messages():
    """Standard conversation messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "What is in this image?"},
    ]


# =============================================================================
# 1. Base class tests
# =============================================================================

class _ConcreteProvider(LLMProvider):
    """Minimal concrete provider for testing the ABC."""

    def _validate_config(self):
        pass

    def chat(self, messages, **kwargs):
        return "ok"

    def chat_stream(self, messages, **kwargs):
        yield "ok"

    def estimate_tokens(self, text):
        return len(text) // 4


class TestBaseProvider:

    def test_supports_vision_default_false(self):
        cfg = LLMConfig(provider="test", model="test-model")
        p = _ConcreteProvider(cfg)
        assert p.supports_vision is False

    def test_format_vision_messages_noop(self, sample_messages, png_attachment):
        cfg = LLMConfig(provider="test", model="test-model")
        p = _ConcreteProvider(cfg)
        result = p.format_vision_messages(sample_messages, [png_attachment])
        assert result is sample_messages  # exact same object — no copy


# =============================================================================
# 2. OpenAI-compatible provider tests
# =============================================================================

class TestOpenAICompatVision:

    def _make_provider(self, model="gpt-4o"):
        from skillforge.core.llm.openai_compat import OpenAICompatibleProvider
        cfg = LLMConfig(
            provider="ollama",
            model=model,
            base_url="http://localhost:11434/v1",
        )
        return OpenAICompatibleProvider(cfg)

    def test_supports_vision_true(self):
        p = self._make_provider()
        assert p.supports_vision is True

    def test_format_vision_single_image(self, sample_messages, png_attachment, tmp_image_dir):
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [png_attachment])

        # Original unchanged
        assert result is not sample_messages
        assert len(result) == len(sample_messages)

        # Only the last user message should be modified
        assert result[0] == sample_messages[0]  # system
        assert result[1] == sample_messages[1]  # first user (text)
        assert result[2] == sample_messages[2]  # assistant

        # Last user message should be multi-part
        last = result[3]
        assert last["role"] == "user"
        assert isinstance(last["content"], list)
        assert len(last["content"]) == 2  # text + 1 image

        text_part = last["content"][0]
        assert text_part["type"] == "text"
        assert text_part["text"] == "What is in this image?"

        img_part = last["content"][1]
        assert img_part["type"] == "image_url"
        assert img_part["image_url"]["url"].startswith("data:image/png;base64,")

        # Verify the base64 data decodes to valid bytes
        b64_data = img_part["image_url"]["url"].split(",", 1)[1]
        decoded = base64.b64decode(b64_data)
        assert decoded[:4] == b"\x89PNG"

    def test_format_vision_multiple_images(self, sample_messages, png_attachment, jpeg_attachment):
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [png_attachment, jpeg_attachment])

        last = result[3]
        assert isinstance(last["content"], list)
        assert len(last["content"]) == 3  # text + 2 images
        assert last["content"][0]["type"] == "text"
        assert last["content"][1]["type"] == "image_url"
        assert last["content"][2]["type"] == "image_url"

        # Check MIME types are correct
        assert "image/png" in last["content"][1]["image_url"]["url"]
        assert "image/jpeg" in last["content"][2]["image_url"]["url"]

    def test_format_vision_no_attachments_noop(self, sample_messages):
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [])
        assert result is sample_messages

    def test_format_vision_no_user_message(self, png_attachment):
        p = self._make_provider()
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "assistant", "content": "How can I help?"},
        ]
        result = p.format_vision_messages(messages, [png_attachment])
        # No user message found, messages returned unchanged
        assert len(result) == 2
        # Should still be new list (shallow copy), but content unchanged
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "assistant"

    def test_format_vision_preserves_earlier_messages(self, sample_messages, png_attachment):
        """Earlier user messages stay as plain text strings."""
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [png_attachment])

        # First user message at index 1 should still be a plain string
        assert isinstance(result[1]["content"], str)
        assert result[1]["content"] == "Hello"

    def test_backward_compat_chat_without_vision(self):
        """Calling chat() without any vision processing works identically."""
        p = self._make_provider()
        messages = [{"role": "user", "content": "hello"}]
        # We just verify chat() still accepts regular string-content messages
        # (would raise if our changes broke the payload builder)
        # We mock the HTTP call so no network needed
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Hi!"}}]
            }
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            result = p.chat(messages)
            assert result == "Hi!"


# =============================================================================
# 3. Anthropic provider tests
# =============================================================================

class TestAnthropicVision:

    def _make_provider(self):
        from skillforge.core.llm.anthropic_provider import AnthropicProvider
        cfg = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
        )
        return AnthropicProvider(cfg)

    def test_supports_vision_true(self):
        p = self._make_provider()
        assert p.supports_vision is True

    def test_format_vision_single_image(self, sample_messages, png_attachment):
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [png_attachment])

        last = result[3]
        assert last["role"] == "user"
        assert isinstance(last["content"], list)
        assert len(last["content"]) == 2  # 1 image + text

        # Anthropic format: image first, text last
        img_part = last["content"][0]
        assert img_part["type"] == "image"
        assert img_part["source"]["type"] == "base64"
        assert img_part["source"]["media_type"] == "image/png"
        assert isinstance(img_part["source"]["data"], str)

        text_part = last["content"][1]
        assert text_part["type"] == "text"
        assert text_part["text"] == "What is in this image?"

    def test_format_vision_message_structure(self, sample_messages, png_attachment, jpeg_attachment):
        """Multiple images: all image blocks before text block."""
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [png_attachment, jpeg_attachment])

        last = result[3]
        assert len(last["content"]) == 3  # 2 images + text
        assert last["content"][0]["type"] == "image"
        assert last["content"][0]["source"]["media_type"] == "image/png"
        assert last["content"][1]["type"] == "image"
        assert last["content"][1]["source"]["media_type"] == "image/jpeg"
        assert last["content"][2]["type"] == "text"

    def test_format_vision_no_attachments_noop(self, sample_messages):
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [])
        assert result is sample_messages

    def test_format_vision_no_user_message(self, png_attachment):
        p = self._make_provider()
        messages = [
            {"role": "system", "content": "system"},
            {"role": "assistant", "content": "hi"},
        ]
        result = p.format_vision_messages(messages, [png_attachment])
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "assistant"

    def test_prepare_request_handles_list_content(self, sample_messages, png_attachment):
        """_prepare_request should pass list content through correctly."""
        p = self._make_provider()
        formatted = p.format_vision_messages(sample_messages, [png_attachment])
        payload = p._prepare_request(formatted, stream=False)

        # The user messages in payload should include one with list content
        user_msgs = [m for m in payload["messages"] if m["role"] == "user"]
        assert len(user_msgs) == 2
        # Last user message has list content
        assert isinstance(user_msgs[-1]["content"], list)
        # First user message has string content
        assert isinstance(user_msgs[0]["content"], str)


# =============================================================================
# 4. Gemini provider tests
# =============================================================================

class TestGeminiVision:

    def _make_provider(self):
        from skillforge.core.llm.gemini_provider import GeminiProvider
        cfg = LLMConfig(
            provider="gemini",
            model="gemini-2.0-flash",
            api_key="test-key",
        )
        return GeminiProvider(cfg)

    def test_supports_vision_true(self):
        p = self._make_provider()
        assert p.supports_vision is True

    def test_format_vision_single_image(self, sample_messages, png_attachment):
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [png_attachment])

        last = result[3]
        assert last["role"] == "user"
        assert isinstance(last["content"], list)
        assert len(last["content"]) == 2  # 1 inline_data + text string

        inline = last["content"][0]
        assert "inline_data" in inline
        assert inline["inline_data"]["mime_type"] == "image/png"
        assert isinstance(inline["inline_data"]["data"], str)

        # Text part is a plain string (not a dict)
        assert last["content"][1] == "What is in this image?"

    def test_format_vision_multiple_images(self, sample_messages, png_attachment, jpeg_attachment):
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [png_attachment, jpeg_attachment])

        last = result[3]
        assert len(last["content"]) == 3  # 2 images + text
        assert "inline_data" in last["content"][0]
        assert "inline_data" in last["content"][1]
        assert isinstance(last["content"][2], str)

    def test_format_vision_no_attachments_noop(self, sample_messages):
        p = self._make_provider()
        result = p.format_vision_messages(sample_messages, [])
        assert result is sample_messages

    def test_convert_messages_with_list_content(self, sample_messages, png_attachment):
        """_convert_messages should handle list content from format_vision_messages."""
        p = self._make_provider()
        formatted = p.format_vision_messages(sample_messages, [png_attachment])
        history, current_message, system_instruction = p._convert_messages(formatted)

        # System instruction extracted
        assert system_instruction == "You are a helpful assistant."

        # History contains: model("Hi there!") then user("Hello")
        # (assistant is appended directly; user("Hello") is pushed
        #  from current_message when the second user message arrives)
        assert len(history) == 2
        assert history[0]["role"] == "model"
        assert history[0]["parts"] == ["Hi there!"]
        assert history[1]["role"] == "user"
        assert history[1]["parts"] == ["Hello"]  # plain text

        # Current message should have multi-part content
        assert current_message is not None
        assert current_message["role"] == "user"
        assert isinstance(current_message["parts"], list)
        assert len(current_message["parts"]) == 2  # inline_data dict + text string
        assert "inline_data" in current_message["parts"][0]
        assert current_message["parts"][1] == "What is in this image?"

    def test_convert_messages_plain_text_unchanged(self):
        """_convert_messages with plain text content still works."""
        p = self._make_provider()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "How are you?"},
        ]
        history, current_message, system_instruction = p._convert_messages(messages)

        assert system_instruction is None
        # History: model("Hi") first (appended directly), then user("Hello")
        # (pushed from current_message when second user message arrives)
        assert len(history) == 2
        assert history[0]["parts"] == ["Hi"]
        assert history[1]["parts"] == ["Hello"]
        assert current_message["parts"] == ["How are you?"]


# =============================================================================
# 5. CLI provider tests
# =============================================================================

class TestClaudeCLIVision:

    def test_supports_vision_false(self):
        from skillforge.core.llm.claude_cli_provider import ClaudeCLIProvider
        cfg = LLMConfig(provider="claude_cli", model="claude-sonnet-4-20250514")
        with patch("shutil.which", return_value="/usr/bin/claude"):
            p = ClaudeCLIProvider(cfg)
        assert p.supports_vision is False

    def test_format_vision_messages_passthrough(self, sample_messages, png_attachment):
        from skillforge.core.llm.claude_cli_provider import ClaudeCLIProvider
        cfg = LLMConfig(provider="claude_cli", model="claude-sonnet-4-20250514")
        with patch("shutil.which", return_value="/usr/bin/claude"):
            p = ClaudeCLIProvider(cfg)
        result = p.format_vision_messages(sample_messages, [png_attachment])
        # Base class no-op: returns the same object
        assert result is sample_messages


class TestGeminiCLIVision:

    def test_supports_vision_false(self):
        from skillforge.core.llm.gemini_cli_provider import GeminiCLIProvider
        cfg = LLMConfig(provider="gemini_cli", model="gemini-2.0-flash")
        with patch("shutil.which", return_value="/usr/bin/gemini"):
            p = GeminiCLIProvider(cfg)
        assert p.supports_vision is False

    def test_format_vision_messages_passthrough(self, sample_messages, png_attachment):
        from skillforge.core.llm.gemini_cli_provider import GeminiCLIProvider
        cfg = LLMConfig(provider="gemini_cli", model="gemini-2.0-flash")
        with patch("shutil.which", return_value="/usr/bin/gemini"):
            p = GeminiCLIProvider(cfg)
        result = p.format_vision_messages(sample_messages, [png_attachment])
        assert result is sample_messages


# =============================================================================
# 6. LlamaCpp provider tests
# =============================================================================

class TestLlamaCppVision:

    def test_supports_vision_default_false(self):
        from skillforge.core.llm.llamacpp_provider import LlamaCppProvider
        cfg = LLMConfig(
            provider="llamacpp",
            model="llama-7b",
            extra={"model_path": "/tmp/fake.gguf"},
        )
        p = LlamaCppProvider(cfg)
        assert p.supports_vision is False

    def test_supports_vision_configurable_true(self):
        from skillforge.core.llm.llamacpp_provider import LlamaCppProvider
        cfg = LLMConfig(
            provider="llamacpp",
            model="llava-v1.5",
            extra={"model_path": "/tmp/fake.gguf", "supports_vision": True},
        )
        p = LlamaCppProvider(cfg)
        assert p.supports_vision is True

    def test_supports_vision_configurable_false(self):
        from skillforge.core.llm.llamacpp_provider import LlamaCppProvider
        cfg = LLMConfig(
            provider="llamacpp",
            model="llava-v1.5",
            extra={"model_path": "/tmp/fake.gguf", "supports_vision": False},
        )
        p = LlamaCppProvider(cfg)
        assert p.supports_vision is False

    def test_format_vision_messages_passthrough(self, sample_messages, png_attachment):
        """LlamaCpp uses base class no-op for format_vision_messages."""
        from skillforge.core.llm.llamacpp_provider import LlamaCppProvider
        cfg = LLMConfig(
            provider="llamacpp",
            model="llava-v1.5",
            extra={"model_path": "/tmp/fake.gguf", "supports_vision": True},
        )
        p = LlamaCppProvider(cfg)
        result = p.format_vision_messages(sample_messages, [png_attachment])
        assert result is sample_messages


# =============================================================================
# 7. Edge case and robustness tests
# =============================================================================

class TestVisionEdgeCases:

    def test_empty_messages_list(self, png_attachment):
        """format_vision_messages with empty message list."""
        from skillforge.core.llm.openai_compat import OpenAICompatibleProvider
        cfg = LLMConfig(provider="ollama", model="gpt-4o",
                        base_url="http://localhost:11434/v1")
        p = OpenAICompatibleProvider(cfg)

        result = p.format_vision_messages([], [png_attachment])
        assert result == []  # No user message to modify

    def test_single_user_message(self, png_attachment):
        """Only one user message — it should be modified."""
        from skillforge.core.llm.openai_compat import OpenAICompatibleProvider
        cfg = LLMConfig(provider="ollama", model="gpt-4o",
                        base_url="http://localhost:11434/v1")
        p = OpenAICompatibleProvider(cfg)

        messages = [{"role": "user", "content": "Describe this."}]
        result = p.format_vision_messages(messages, [png_attachment])
        assert isinstance(result[0]["content"], list)
        assert result[0]["content"][0]["text"] == "Describe this."

    def test_user_message_empty_content(self, png_attachment):
        """User message with empty string content."""
        from skillforge.core.llm.anthropic_provider import AnthropicProvider
        cfg = LLMConfig(provider="anthropic", model="claude-sonnet-4-20250514",
                        api_key="test-key")
        p = AnthropicProvider(cfg)

        messages = [{"role": "user", "content": ""}]
        result = p.format_vision_messages(messages, [png_attachment])
        last = result[0]
        assert isinstance(last["content"], list)
        # Should still have text block (empty) and image block
        text_parts = [c for c in last["content"] if c.get("type") == "text"]
        img_parts = [c for c in last["content"] if c.get("type") == "image"]
        assert len(text_parts) == 1
        assert len(img_parts) == 1
        assert text_parts[0]["text"] == ""

    def test_base64_encoding_roundtrip(self, tiny_png, tmp_image_dir):
        """Base64 data in vision message can be decoded back to valid PNG."""
        from skillforge.core.llm.openai_compat import OpenAICompatibleProvider
        cfg = LLMConfig(provider="ollama", model="gpt-4o",
                        base_url="http://localhost:11434/v1")
        p = OpenAICompatibleProvider(cfg)

        att = Attachment(
            file_path=tiny_png,
            original_filename="test.png",
            mime_type="image/png",
            size_bytes=os.path.getsize(tiny_png),
        )
        messages = [{"role": "user", "content": "What is this?"}]
        result = p.format_vision_messages(messages, [att])

        url = result[0]["content"][1]["image_url"]["url"]
        b64_str = url.split(",", 1)[1]
        decoded = base64.b64decode(b64_str)

        # Should be valid PNG
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"

        # Should match original file
        with open(tiny_png, "rb") as f:
            original = f.read()
        assert decoded == original

    def test_gemini_content_to_send_single_text(self):
        """_convert_messages with single text part sends string, not list."""
        from skillforge.core.llm.gemini_provider import GeminiProvider
        cfg = LLMConfig(provider="gemini", model="gemini-2.0-flash",
                        api_key="test-key")
        p = GeminiProvider(cfg)

        messages = [{"role": "user", "content": "Hello"}]
        _, current, _ = p._convert_messages(messages)

        parts = current["parts"]
        # Single text: content_to_send logic should select parts[0]
        assert len(parts) == 1
        assert isinstance(parts[0], str)
        content_to_send = parts[0] if len(parts) == 1 and isinstance(parts[0], str) else parts
        assert content_to_send == "Hello"

    def test_gemini_content_to_send_multi_part(self, sample_messages, png_attachment):
        """_convert_messages with vision parts sends full list."""
        from skillforge.core.llm.gemini_provider import GeminiProvider
        cfg = LLMConfig(provider="gemini", model="gemini-2.0-flash",
                        api_key="test-key")
        p = GeminiProvider(cfg)

        formatted = p.format_vision_messages(sample_messages, [png_attachment])
        _, current, _ = p._convert_messages(formatted)

        parts = current["parts"]
        assert len(parts) == 2
        # Multi-part: content_to_send logic should select full list
        content_to_send = parts[0] if len(parts) == 1 and isinstance(parts[0], str) else parts
        assert isinstance(content_to_send, list)
        assert len(content_to_send) == 2


# =============================================================================
# 8. ImageHandler integration (used by providers internally)
# =============================================================================

class TestImageHandlerInVisionFlow:

    def test_handler_encode_base64_used(self, tiny_png, tmp_image_dir):
        """Verify ImageHandler.encode_base64 is called and returns valid data."""
        handler = ImageHandler(data_dir=str(tmp_image_dir / "store"))
        b64 = handler.encode_base64(tiny_png)
        assert isinstance(b64, str)
        decoded = base64.b64decode(b64)
        assert decoded[:4] == b"\x89PNG"


# =============================================================================
'''
    End of File : test_vision_providers.py

    Project : SkillForge - AI Assistant with Persistent Memory

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
