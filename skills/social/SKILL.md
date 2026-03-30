---
name: social
description: Post to and browse Twitter/X and LinkedIn
emoji: 📱
user_invocable: true
---

# Social Media Skill

Post content and browse feeds on Twitter/X and LinkedIn. Supports two modes: Composio MCP (preferred) for direct API access, or Playwright MCP as a browser-based fallback.

## Prerequisites

### Option A: Composio MCP (Preferred)
- Composio MCP server connected with Twitter and/or LinkedIn integrations
- Provides direct API access for posting, reading feeds, and managing content

### Option B: Playwright MCP (Fallback)
- Playwright or browse MCP server connected
- Browser-based interaction — slower but works without API keys

Check the "Tool Status" section in your system prompt to see if these services are available before proceeding.

## Operations

### Post Content

When asked to post/tweet/share:
1. Draft the content based on the user's request
2. **Always show the draft and ask for confirmation before posting:**
   "Here's your draft:\n\n> [content]\n\nPost to **Twitter/LinkedIn**? (yes/no)"
3. Only post after explicit confirmation
4. Confirm with a link to the post if available

### Check Feed / Timeline

When asked to check feed/timeline:
1. Fetch recent posts from the requested platform
2. Show as a list with author, content preview, and engagement stats
3. Default to 10 posts

### Draft Content

When asked to draft/write a post:
1. Generate content tailored to the platform:
   - **Twitter/X**: Max 280 characters, concise, hashtags optional
   - **LinkedIn**: Professional tone, can be longer, paragraph format
2. Show the draft for review — do NOT post automatically

### Search / Trending

When asked about trending topics or to search:
1. Use available MCP tools to search
2. Show results with engagement metrics where available

## Safety Rules

- **NEVER post without explicit user confirmation** — always show draft first
- Respect platform character limits
- Warn about potentially sensitive content
- If the user asks to post to multiple platforms, confirm each separately
- Default to drafting (not posting) if intent is ambiguous

## Platform Guidelines

### Twitter/X
- 280 character limit
- Use thread format for longer content (ask first)
- Include hashtags only if relevant and not excessive (max 3)

### LinkedIn
- Professional tone
- Longer form is fine (up to ~3000 characters)
- Suggest adding relevant hashtags for visibility

## Examples

User: "tweet about our new product launch"
→ Draft a tweet, show it, wait for confirmation

User: "post on linkedin about the conference I attended"
→ Ask for details, draft a professional post, show for review

User: "check my twitter feed"
→ Fetch and display recent timeline posts

User: "draft a thread about AI trends"
→ Draft a multi-tweet thread, show for review, do NOT post
