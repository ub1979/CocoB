---
name: google-search
description: Search Google using Playwright browser
emoji: 🔍
user_invocable: false
---

# Google Search Skill

This skill automatically uses Playwright to search Google and returns live results.

## How It Works

When you invoke `/google-search <query>`:
1. Playwright opens a browser and navigates to Google
2. Searches for your query
3. Returns the page content
4. The AI summarizes the results for you

## Requirements

- Playwright MCP server must be connected (see MCP Tools tab)

## Example

```
/google-search best restaurants in london
```

The bot will search Google and summarize the results.
