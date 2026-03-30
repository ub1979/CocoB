---
name: news
description: Get headlines and read articles from RSS feeds and news sources
emoji: 📰
user_invocable: true
---

# News Skill

Fetch headlines, read articles, and search news by topic using RSS feeds. Uses Playwright/browse MCP to fetch and parse feeds.

## Prerequisites

- Playwright or browse MCP server connected for fetching web content
- Check the "Tool Status" section in your system prompt to see if this service is available before proceeding.

## Default RSS Feeds

| Source | Feed URL |
|--------|----------|
| Hacker News | `https://hnrss.org/frontpage` |
| BBC World | `https://feeds.bbci.co.uk/news/world/rss.xml` |
| TechCrunch | `https://techcrunch.com/feed/` |
| Reuters World | `https://www.rss-bridge.org/bridge01/?action=display&bridge=Reuters&feed=world&format=Atom` |

## Operations

### Get Headlines

When asked for news/headlines (no specific topic):
1. Fetch the top stories from default feeds
2. Show as a numbered list:
   - **1.** Headline — _Source_ (time ago)
3. Default to 5–10 headlines per source
4. Group by source with headers

### Read Article

When asked to read/summarize an article:
1. Fetch the article URL via Playwright/browse MCP
2. Extract the main text content
3. Provide a concise summary (3–5 paragraphs)
4. Include the source URL at the end

### Search by Topic

When asked for news about a specific topic:
1. Use Google News RSS: `https://news.google.com/rss/search?q=<topic>&hl=en`
2. Fetch and parse the feed
3. Show results as headlines with sources
4. Default to 10 results

### Source-Specific Request

When asked for news from a specific source (e.g., "BBC news", "hacker news"):
1. Fetch only that source's feed
2. Show headlines from that source only

## Formatting

- Number all headlines for easy reference ("read article 3")
- Show relative timestamps ("2 hours ago", "yesterday")
- Bold the headline text
- Italicize the source name
- Keep summaries concise unless the user asks for detail

## Examples

User: "what's the news?"
→ Fetch headlines from all default feeds, show top 5 each

User: "tech news"
→ Fetch from Hacker News and TechCrunch

User: "news about AI"
→ Search Google News RSS for "AI", show top 10

User: "read article 3"
→ Fetch and summarize the 3rd article from the last headlines shown
