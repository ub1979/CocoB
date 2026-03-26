# =============================================================================
# test_web_tools.py — Unit tests for native web search and fetch tools
# =============================================================================

import pytest
from unittest.mock import patch, MagicMock
import httpx

from skillforge.core.web_tools import (
    WebToolsHandler,
    HTMLTextExtractor,
    extract_text_from_html,
)


@pytest.fixture
def handler():
    return WebToolsHandler()


@pytest.fixture
def handler_with_key():
    return WebToolsHandler(brave_api_key="test-key-123")


# =============================================================================
# TestHTMLExtractor
# =============================================================================

class TestHTMLExtractor:
    """Test HTML text extraction."""

    def test_basic_html(self):
        html = "<html><body><p>Hello world</p></body></html>"
        text = extract_text_from_html(html)
        assert "Hello world" in text

    def test_strips_scripts(self):
        html = "<p>Before</p><script>alert('x')</script><p>After</p>"
        text = extract_text_from_html(html)
        assert "Before" in text
        assert "After" in text
        assert "alert" not in text

    def test_strips_style(self):
        html = "<p>Content</p><style>body{color:red}</style>"
        text = extract_text_from_html(html)
        assert "Content" in text
        assert "color" not in text

    def test_max_chars(self):
        html = "<p>" + "x" * 20000 + "</p>"
        text = extract_text_from_html(html, max_chars=100)
        assert len(text) <= 100

    def test_empty_html(self):
        text = extract_text_from_html("")
        assert text == ""

    def test_nested_tags(self):
        html = "<div><p><strong>Bold</strong> text</p></div>"
        text = extract_text_from_html(html)
        assert "Bold" in text
        assert "text" in text


# =============================================================================
# TestDetection
# =============================================================================

class TestDetection:
    """Test web command block detection."""

    def test_detects_search_block(self, handler):
        response = "```web_search\nQUERY: python tutorial\n```"
        assert handler.has_web_commands(response) is True

    def test_detects_fetch_block(self, handler):
        response = "```web_fetch\nURL: https://example.com\n```"
        assert handler.has_web_commands(response) is True

    def test_no_false_positive(self, handler):
        assert handler.has_web_commands("no blocks here") is False

    def test_case_insensitive(self, handler):
        response = "```Web_Search\nQUERY: test\n```"
        assert handler.has_web_commands(response) is True


# =============================================================================
# TestParsing
# =============================================================================

class TestParsing:
    """Test block parsing."""

    def test_parse_search_block(self, handler):
        block = "QUERY: python asyncio\nCOUNT: 3"
        result = handler._parse_block(block)
        assert result["QUERY"] == "python asyncio"
        assert result["COUNT"] == "3"

    def test_parse_fetch_block(self, handler):
        block = "URL: https://example.com\nMAX_CHARS: 5000"
        result = handler._parse_block(block)
        assert result["URL"] == "https://example.com"
        assert result["MAX_CHARS"] == "5000"

    def test_parse_empty_block(self, handler):
        result = handler._parse_block("")
        assert result == {}


# =============================================================================
# TestSearchNoKey
# =============================================================================

class TestSearchNoKey:
    """Test search behavior without API key."""

    def test_search_without_key_uses_ddg_fallback(self, handler):
        result = handler.web_search("python tutorial")
        # Should use DuckDuckGo fallback, not return "not configured"
        assert "python tutorial" in result.lower() or "Search results" in result or "Search failed" in result

    def test_execute_search_without_key_uses_fallback(self, handler):
        response = "Let me search for that.\n```web_search\nQUERY: python tutorial\n```"
        cleaned, results = handler.execute_commands(response)
        assert len(results) == 1
        assert "not configured" not in results[0]["result"]


# =============================================================================
# TestSearchWithKey
# =============================================================================

class TestSearchWithKey:
    """Test search with mocked Brave API."""

    def test_search_success(self, handler_with_key):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Python Tutorial", "url": "https://python.org", "description": "Learn Python"},
                    {"title": "Async IO", "url": "https://docs.python.org/asyncio", "description": "Async docs"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler_with_key._client, 'get', return_value=mock_response):
            result = handler_with_key.web_search("python tutorial", count=2)
            assert "Python Tutorial" in result
            assert "https://python.org" in result
            assert "Async IO" in result

    def test_search_no_results(self, handler_with_key):
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler_with_key._client, 'get', return_value=mock_response):
            result = handler_with_key.web_search("xyznonexistent")
            assert "No results" in result

    def test_search_api_error(self, handler_with_key):
        with patch.object(handler_with_key._client, 'get', side_effect=Exception("Connection refused")):
            result = handler_with_key.web_search("test")
            assert "failed" in result.lower()

    def test_search_count_clamped(self, handler_with_key):
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler_with_key._client, 'get', return_value=mock_response) as mock_get:
            handler_with_key.web_search("test", count=100)
            call_params = mock_get.call_args[1]["params"]
            assert call_params["count"] == 20  # Clamped to max


# =============================================================================
# TestFetch
# =============================================================================

class TestFetch:
    """Test web fetch."""

    def test_fetch_html(self, handler):
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Hello from example</p></body></html>"
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler._client, 'get', return_value=mock_response):
            result = handler.web_fetch("https://example.com")
            assert "Hello from example" in result
            assert "example.com" in result

    def test_fetch_plain_text(self, handler):
        mock_response = MagicMock()
        mock_response.text = "Plain text content here"
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler._client, 'get', return_value=mock_response):
            result = handler.web_fetch("https://example.com/file.txt")
            assert "Plain text content" in result

    def test_fetch_json(self, handler):
        mock_response = MagicMock()
        mock_response.text = '{"key": "value"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler._client, 'get', return_value=mock_response):
            result = handler.web_fetch("https://api.example.com/data")
            assert '"key"' in result

    def test_fetch_unsupported_type(self, handler):
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/octet-stream"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler._client, 'get', return_value=mock_response):
            result = handler.web_fetch("https://example.com/file.bin")
            assert "Cannot extract" in result

    def test_fetch_error(self, handler):
        with patch.object(handler._client, 'get', side_effect=Exception("Timeout")):
            result = handler.web_fetch("https://example.com")
            assert "failed" in result.lower()

    def test_fetch_max_chars(self, handler):
        mock_response = MagicMock()
        mock_response.text = "x" * 20000
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(handler._client, 'get', return_value=mock_response):
            result = handler.web_fetch("https://example.com", max_chars=500)
            # Result includes header line + content
            assert len(result) < 1000


# =============================================================================
# TestExecuteCommands
# =============================================================================

class TestExecuteCommands:
    """Test full execute_commands flow."""

    def test_execute_search_and_fetch(self, handler):
        response = ("Here's what I found:\n"
                     "```web_search\nQUERY: python\nCOUNT: 2\n```\n"
                     "And the page content:\n"
                     "```web_fetch\nURL: https://example.com\nMAX_CHARS: 500\n```")

        with patch.object(handler, 'web_search', return_value="Search results..."):
            with patch.object(handler, 'web_fetch', return_value="Page content..."):
                cleaned, results = handler.execute_commands(response)
                assert len(results) == 2
                assert results[0]["type"] == "search"
                assert results[1]["type"] == "fetch"

    def test_cleans_blocks_from_response(self, handler):
        response = "Prefix text ```web_search\nQUERY: test\n``` suffix text"
        cleaned, _ = handler.execute_commands(response)
        assert "web_search" not in cleaned
        assert "Prefix text" in cleaned
        assert "suffix text" in cleaned

    def test_no_commands_returns_unchanged(self, handler):
        response = "Just a normal response"
        cleaned, results = handler.execute_commands(response)
        assert cleaned == response
        assert results == []

    def test_empty_query_skipped(self, handler):
        response = "```web_search\nCOUNT: 5\n```"
        cleaned, results = handler.execute_commands(response)
        assert results == []
