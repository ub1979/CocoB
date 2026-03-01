---
name: github
description: Manage GitHub issues, PRs, notifications, and repos through chat
emoji: 🐙
user_invocable: true
---

# GitHub Skill

Interact with GitHub repositories through chat. Use the GitHub MCP tools when available to perform operations.

## Prerequisites

- GitHub MCP server connected with a valid personal access token
- If GitHub MCP is not available, reply: "GitHub integration isn't connected yet. Ask your admin to set up the GitHub MCP server."

## Operations

### List Issues

When asked to show issues for a repo:
1. Use the GitHub MCP tool to list issues
2. Format as a numbered list:
   - **#123** — Issue title _(open/closed)_ `label1` `label2`
3. Default to open issues, limit 10 unless specified

### Create Issue

When asked to create/file/open an issue:
1. Ask for repo, title, and body if not provided
2. Use GitHub MCP to create the issue
3. Confirm with: "Created **#123** — Title"

### Close Issue

When asked to close an issue:
1. Use GitHub MCP to close it
2. Confirm: "Closed **#123** — Title"

### View / Create Pull Requests

- **List PRs**: Format like issues with status (open/merged/closed) and reviewer info
- **Create PR**: Ask for base branch, head branch, title, and body. Confirm before creating.
- **View PR**: Show title, description, status, reviewers, and checks

### Check Notifications

When asked about notifications:
1. Use GitHub MCP to fetch notifications
2. Group by repository
3. Show type (issue, PR, review) and reason (mention, assigned, subscribed)

### Repo Info

When asked about a repository:
- Show description, stars, forks, language, recent activity
- Show open issue/PR counts

## Formatting

- Always include issue/PR numbers as **#NNN**
- Use repo format: `owner/repo`
- Show dates in relative format ("2 days ago") when possible
- Keep responses concise — summaries, not full bodies unless asked

## Examples

User: "show my open issues on myorg/myrepo"
→ List open issues using GitHub MCP

User: "create an issue on myorg/myrepo: Fix login button"
→ Create issue with title "Fix login button", ask for body if needed

User: "what PRs need my review?"
→ List PRs where user is requested reviewer

User: "check my github notifications"
→ Fetch and display grouped notifications
