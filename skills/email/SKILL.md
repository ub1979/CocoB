---
name: email
description: Manage your Gmail - read, send, search emails
emoji: 📧
user_invocable: true
---

# Email Skill

Manage your Gmail inbox using natural language commands.

## Usage

```
/email check inbox
/email unread
/email search from:boss@company.com
/email send to john@example.com subject "Meeting" body "Hi John, let's meet at 3pm"
/email draft to sarah@example.com about project update
```

## Setup Options

### Option A: Self-Hosted (FREE - Recommended)

Uses [mcp-google-workspace](https://github.com/j3k0/mcp-google-workspace):
- Unlimited usage, completely free
- Data stays on your machine
- Requires Google Cloud OAuth setup (15 min one-time)

### Option B: Composio (Easy Setup)

Uses Composio managed service:
- 100 free actions/month, then $49/month
- 5-minute setup
- Data processed through Composio

**See [EMAIL_CALENDAR_SETUP.md](../../EMAIL_CALENDAR_SETUP.md) for detailed instructions.**

## Available Commands

| Command | Description |
|---------|-------------|
| `check inbox` | Show recent emails |
| `unread` | Show unread emails |
| `search <query>` | Search with Gmail syntax |
| `send to <email> subject "<subj>" body "<body>"` | Send email |
| `draft to <email> about <topic>` | Create draft |
| `reply to <thread>` | Reply to email |
| `archive <email>` | Archive email |
| `labels` | List Gmail labels |

## Gmail Search Syntax

```
from:someone@example.com    - From specific sender
to:someone@example.com      - To specific recipient
subject:meeting             - Subject contains "meeting"
is:unread                   - Unread only
is:starred                  - Starred only
has:attachment              - Has attachments
after:2024/01/01            - After date
label:important             - Specific label
```

## Examples

```
/email search from:amazon.com has:attachment
/email send to team@company.com subject "Update" body "Here's the weekly summary..."
/email unread from:boss
/email archive older_than:30d
```
