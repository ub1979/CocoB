---
name: notion
description: Manage Notion - search pages, create notes, add to databases
emoji: 📝
user_invocable: true
---

# Notion Skill

Manage your Notion workspace using natural language commands.

## Usage

```
/notion search meeting notes
/notion create Project Ideas
/notion add "Buy groceries" to Tasks
/notion databases
```

## Setup

1. Go to https://www.notion.so/my-integrations
2. Click **Create new integration**
3. Name it `SkillForge`, select your workspace
4. Copy the **Internal Integration Secret**
5. In `config/mcp_config.json`, set `notion.enabled` to `true` and paste your key
6. In Notion, **share** the pages/databases you want accessible with your integration

## Available Commands

| Command | Description |
|---------|-------------|
| _(empty)_ | Show recent pages |
| `search <query>` | Search pages and databases |
| `create <title>` | Create a new page |
| `add <item> to <database>` | Add item to a database |
| `databases` | List all databases |

## Examples

```
/notion
/notion search weekly standup
/notion create "Meeting Notes - March 29"
/notion add "Fix login bug" to Sprint Backlog
/notion databases
```

## Tips

1. Share pages/databases with your integration in Notion for them to be accessible
2. Use `/notion search` to find pages before referencing them
3. Natural language also works: "add a task to my notion" or "search notion for meeting notes"
