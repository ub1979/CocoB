---
name: browse
description: Open a URL in the browser using Playwright
emoji: 🌐
user_invocable: true
---

# Browse Skill

Opens a URL in the browser using Playwright and returns the page content.

## Usage

```
/browse google.com
/browse https://example.com
```

## Requirements

- Playwright MCP server must be connected (see MCP Tools tab)

## How It Works

1. Opens the URL in Playwright browser
2. Waits for the page to load
3. Captures the page content
4. Returns it for the AI to describe
