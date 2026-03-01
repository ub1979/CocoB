# =============================================================================
'''
    File Name : web_tools.py

    Description : Native web search and URL fetch tools. Provides agent-callable
                  web capabilities without requiring MCP server configuration.
                  Uses Brave Search API for search, httpx for URL fetching.

    Created on 2026-02-24

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : coco B - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import re
import logging
from typing import Optional, Dict, Any, List
from html.parser import HTMLParser

import httpx

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("web_tools")


# =============================================================================
'''
    HTMLTextExtractor : Strip HTML tags and extract plain text
'''
# =============================================================================
class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML, skipping script/style tags."""

    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False
        self._skip_tags = {"script", "style", "noscript"}

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._skip_tags:
            self._skip = True

    def handle_endtag(self, tag):
        if tag.lower() in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self._text.append(text)

    def get_text(self) -> str:
        return "\n".join(self._text)


def extract_text_from_html(html: str, max_chars: int = 10000) -> str:
    """Extract plain text from HTML content."""
    extractor = HTMLTextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        # Fallback: strip tags with regex
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]
    return extractor.get_text()[:max_chars]


# =============================================================================
'''
    WebToolsHandler : Handles ```web_search``` and ```web_fetch``` code blocks
                      from LLM responses.
'''
# =============================================================================
class WebToolsHandler:
    """
    Handles web search and fetch commands embedded in LLM responses.

    Parses code blocks like:
    ```web_search
    QUERY: python asyncio tutorial
    COUNT: 5
    ```

    ```web_fetch
    URL: https://example.com
    MAX_CHARS: 5000
    ```
    """

    SEARCH_BLOCK_PATTERN = re.compile(
        r'```web_search\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )

    FETCH_BLOCK_PATTERN = re.compile(
        r'```web_fetch\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )

    # =========================================================================
    # Function __init__
    # =========================================================================
    def __init__(self, brave_api_key: Optional[str] = None):
        """
        Initialize web tools handler.

        Args:
            brave_api_key: Optional Brave Search API key. If not provided,
                          search will return a message directing to /google-search skill.
        """
        self.brave_api_key = brave_api_key
        self._client = httpx.Client(timeout=15, follow_redirects=True)

    # =========================================================================
    # Detection
    # =========================================================================
    def has_web_commands(self, response: str) -> bool:
        """Check if response contains web_search or web_fetch blocks."""
        return bool(self.SEARCH_BLOCK_PATTERN.search(response) or
                     self.FETCH_BLOCK_PATTERN.search(response))

    # =========================================================================
    # Parsing
    # =========================================================================
    def _parse_block(self, block_content: str) -> Dict[str, str]:
        """Parse a web block into key-value pairs."""
        result = {}
        for line in block_content.strip().split('\n'):
            line = line.strip()
            if ':' in line:
                key, _, value = line.partition(':')
                key = key.strip().upper()
                value = value.strip()
                if key and value:
                    result[key] = value
        return result

    # =========================================================================
    # Web Search
    # =========================================================================
    def web_search(self, query: str, count: int = 5) -> str:
        """
        Search the web using Brave Search API (or DuckDuckGo fallback).

        Args:
            query: Search query
            count: Number of results (max 20)

        Returns:
            Formatted search results
        """
        if self.brave_api_key:
            return self._brave_search(query, count)
        return self._ddg_search(query, count)

    def _brave_search(self, query: str, count: int = 5) -> str:
        """Search using Brave Search API."""
        count = min(max(count, 1), 20)
        try:
            response = self._client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self.brave_api_key,
                },
                params={"q": query, "count": count},
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("web", {}).get("results", [])
            if not results:
                return f"No results found for: {query}"

            return self._format_results(query, results, count)

        except httpx.HTTPStatusError as e:
            logger.error(f"Brave Search API error: {e}")
            return f"Search failed: HTTP {e.response.status_code}"
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return self._ddg_search(query, count)

    def _ddg_search(self, query: str, count: int = 5) -> str:
        """Search using DuckDuckGo HTML (no API key needed)."""
        count = min(max(count, 1), 10)
        try:
            response = self._client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; coco-b/1.0)",
                },
            )
            response.raise_for_status()

            # Parse results from DDG HTML
            results = []
            html = response.text

            # Extract result blocks: <a class="result__a" href="...">title</a>
            # and <a class="result__snippet" ...>description</a>
            result_pattern = re.compile(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
                r'.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                re.DOTALL
            )

            for match in result_pattern.finditer(html):
                url = match.group(1)
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                desc = re.sub(r'<[^>]+>', '', match.group(3)).strip()
                if title and url:
                    # DDG wraps URLs in a redirect — extract the actual URL
                    if "uddg=" in url:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                        url = parsed.get("uddg", [url])[0]
                    results.append({"title": title, "url": url, "description": desc})

            if not results:
                return f"No results found for: {query}"

            return self._format_results(query, results, count)

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return f"Search failed: {e}"

    def _format_results(self, query: str, results: list, count: int) -> str:
        """Format search results into readable text."""
        lines = [f"**Search results for:** {query}\n"]
        for i, r in enumerate(results[:count], 1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            desc = r.get("description", "")
            lines.append(f"{i}. **{title}**")
            lines.append(f"   {url}")
            if desc:
                lines.append(f"   {desc}")
            lines.append("")
        return "\n".join(lines)

    # =========================================================================
    # Web Fetch
    # =========================================================================
    def web_fetch(self, url: str, max_chars: int = 10000) -> str:
        """
        Fetch and extract text content from a URL.

        Args:
            url: URL to fetch
            max_chars: Maximum characters to return

        Returns:
            Extracted text content
        """
        max_chars = min(max(max_chars, 100), 50000)

        try:
            response = self._client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; coco-b/1.0; +https://github.com)",
                },
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "text/html" in content_type:
                text = extract_text_from_html(response.text, max_chars)
            elif "text/plain" in content_type or "application/json" in content_type:
                text = response.text[:max_chars]
            else:
                return f"Cannot extract text from content type: {content_type}"

            if not text.strip():
                return f"No text content found at {url}"

            return f"**Content from:** {url}\n\n{text}"

        except httpx.HTTPStatusError as e:
            return f"Fetch failed: HTTP {e.response.status_code} for {url}"
        except Exception as e:
            logger.error(f"Web fetch error: {e}")
            return f"Fetch failed: {e}"

    # =========================================================================
    # Execute commands from LLM response
    # =========================================================================
    def execute_commands(self, response: str) -> tuple[str, list]:
        """
        Extract and execute all web commands from response.

        Args:
            response: LLM response text

        Returns:
            Tuple of (cleaned response, list of results)
        """
        results = []

        # Process web_search blocks
        for match in self.SEARCH_BLOCK_PATTERN.finditer(response):
            parsed = self._parse_block(match.group(1))
            query = parsed.get("QUERY", "")
            count = int(parsed.get("COUNT", "5"))
            if query:
                result = self.web_search(query, count)
                results.append({"type": "search", "query": query, "result": result})

        # Process web_fetch blocks
        for match in self.FETCH_BLOCK_PATTERN.finditer(response):
            parsed = self._parse_block(match.group(1))
            url = parsed.get("URL", "")
            max_chars = int(parsed.get("MAX_CHARS", "10000"))
            if url:
                result = self.web_fetch(url, max_chars)
                results.append({"type": "fetch", "url": url, "result": result})

        # Clean blocks from response
        cleaned = self.SEARCH_BLOCK_PATTERN.sub('', response)
        cleaned = self.FETCH_BLOCK_PATTERN.sub('', cleaned).strip()

        # Append results
        if results:
            result_text = "\n\n".join(r["result"] for r in results)
            if result_text:
                cleaned = cleaned + "\n\n" + result_text if cleaned else result_text

        return cleaned, results


# =============================================================================
'''
    End of File : web_tools.py
'''
# =============================================================================
