# MCP (Model Context Protocol) Integration Guide

> Give SkillForge superpowers with MCP servers!

## What is MCP?

MCP lets AI models (like SkillForge) use **external tools and data sources**:
- **Playwright**: Browse websites, take screenshots, automate web tasks
- **Filesystem**: Read/write files, search code
- **GitHub**: Manage repos, PRs, issues
- **PostgreSQL**: Query databases
- **Brave Search**: Web search
- **Gmail**: Read/send emails
- **Google Calendar**: Manage events
- And 100+ more!

## Quick Setup: Using the MCP Tools Tab

### Step 1: Install Node.js (if not already installed)

MCP servers need Node.js:
```bash
# Check if installed
node --version
npm --version

# If not installed, download from: https://nodejs.org/
```

### Step 2: Start SkillForge Gradio UI

```bash
python gradio_ui.py
```

### Step 3: Connect MCP Servers via UI

1. Go to the **MCP Tools** tab
2. Click **Connect** on the Playwright server
3. Wait for connection (should show "Connected with X tools")
4. Go to **Chat** tab and ask the bot to use web tools!

### Step 4: Test It

In the chat, try:
```
Open a browser and go to google.com
```

The bot will use Playwright tools automatically!

---

## Supported Server Types

| Type | Transport | Use Case |
|------|-----------|----------|
| **STDIO** | Subprocess stdin/stdout | Local tools (npx, python scripts) |
| **Docker** | Docker container + STDIO | Containerized MCP servers |
| **SSE** | Server-Sent Events HTTP | Remote/legacy servers |
| **HTTP** | Streamable HTTP | Modern remote servers |

---

## Configuration File: `mcp_config.json`

### Basic Format

```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "enabled": true,
      "description": "Browser automation tools",
      "command": "npx",
      "args": ["-y", "@playwright/mcp"],
      "env": {}
    }
  }
}
```

### Server Type Fields

**STDIO/Docker servers:**
```json
{
  "my-server": {
    "type": "stdio",
    "enabled": true,
    "description": "Description here",
    "command": "npx",
    "args": ["-y", "@package/name"],
    "env": {"API_KEY": "value"}
  }
}
```

**SSE/HTTP servers:**
```json
{
  "remote-server": {
    "type": "http",
    "enabled": true,
    "description": "Remote MCP server",
    "url": "https://api.example.com/mcp",
    "headers": {"Authorization": "Bearer xxx"}
  }
}
```

---

## Popular MCP Server Packages

### Playwright (Web Automation)
```json
{
  "playwright": {
    "type": "stdio",
    "enabled": true,
    "command": "npx",
    "args": ["-y", "@playwright/mcp"]
  }
}
```

**Note:** The correct package is `@playwright/mcp` (NOT `@playwright/mcp-server`)

### GitHub
```json
{
  "github": {
    "type": "stdio",
    "enabled": true,
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token"
    }
  }
}
```

### Filesystem
```json
{
  "filesystem": {
    "type": "stdio",
    "enabled": true,
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allow"]
  }
}
```

### Brave Search
```json
{
  "brave-search": {
    "type": "stdio",
    "enabled": true,
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "env": {
      "BRAVE_API_KEY": "your_api_key"
    }
  }
}
```

---

## Available Playwright Tools (22 tools)

Once connected, Playwright provides:

### Browser Control
- `browser_close`: Close the page
- `browser_resize`: Resize the browser window
- `browser_console_messages`: Get console messages
- `browser_handle_dialog`: Handle dialogs/alerts

### Navigation
- `browser_navigate`: Go to URL
- `browser_navigate_back`: Go back
- `browser_navigate_forward`: Go forward

### Interaction
- `browser_click`: Click element
- `browser_type`: Type text
- `browser_fill`: Fill input field
- `browser_select_option`: Select dropdown option
- `browser_hover`: Hover over element
- `browser_drag`: Drag and drop

### Content
- `browser_snapshot`: Get accessibility snapshot
- `browser_take_screenshot`: Take screenshot
- `browser_pdf_save`: Save as PDF

### JavaScript
- `browser_evaluate`: Run JavaScript on page

---

## How Tools Work: Skills-Based Architecture

SkillForge uses a **skills-based architecture** where users interact via simple commands, and skills execute MCP tools directly. This approach provides:

- **Smaller prompts**: Tools aren't listed in every message
- **Faster responses**: No LLM deciding which tool to call
- **Lower costs**: Fewer tokens used
- **Reliability**: Skills call tools directly with correct parameters

### User Flow

```
User: /email check inbox
  ↓
Skill Handler → Detects /email skill
  ↓
Direct MCP Call → call_tool_sync("google-workspace", "list-emails", {...})
  ↓
Result → "📧 Recent Emails: ..."
```

### Available Skills

| Skill | MCP Server | Description |
|-------|------------|-------------|
| `/email` | google-workspace | Gmail management |
| `/calendar` | google-workspace | Google Calendar |
| `/google-search` | playwright | Web search via browser |
| `/browse` | playwright | Open URLs |

### Creating Custom Skills

Skills are defined in `skills/` directory. See [ARCHITECTURE.md](ARCHITECTURE.md) for details on creating new skills that call MCP tools directly.

---

## Import from Claude Desktop

If you have Claude Desktop configured with MCP servers, you can import them:

1. Go to **MCP Tools** tab
2. Click **Import Claude Desktop** button
3. Servers will be imported automatically

Claude Desktop config locations:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

---

## Programmatic Usage

### Connect to MCP Servers

```python
from core.mcp_client import MCPManager

# Connect to all enabled servers
mcp = MCPManager()
await mcp.connect_all()

# Or connect to specific server
await mcp.connect_server("playwright")
```

### Call a Tool

```python
result = await mcp.call_tool(
    server_name='playwright',
    tool_name='browser_navigate',
    arguments={'url': 'https://example.com'}
)
print(f"Result: {result}")
```

### List Available Tools

```python
tools = mcp.get_all_tools()
for server, server_tools in tools.items():
    print(f"\n{server}:")
    for tool in server_tools:
        print(f"  - {tool['name']}: {tool.get('description', '')}")
```

---

## Troubleshooting

### "npx command not found"
- Install Node.js from https://nodejs.org/

### "Package not found" / "404 Not Found"
- Check the package name is correct
- Example: Use `@playwright/mcp` NOT `@playwright/mcp-server`

### "Connection lost" immediately
- The MCP server process exited
- Check stderr for errors (visible in terminal)
- Try running the npx command manually to see errors

### "0 tools available"
- Server connected but initialization failed
- Check the terminal for error messages
- Ensure the MCP server package is installed correctly

### "Timeout waiting for response"
- MCP server is slow to respond
- First run may take 10-20s to download packages
- Wait and retry

### Docker MCP servers
- Must use `-i` flag (interactive mode)
- Must NOT use `-d` flag (detached mode)

---

## Security Notes

**Be careful with:**
- **Filesystem MCP**: Only allow specific directories
- **Database MCP**: Use read-only users when possible
- **Cloud MCP**: Limit permissions with scoped tokens
- **Web MCP**: Be respectful, don't scrape aggressively

---

## Finding More MCP Servers

### Official Registry
https://github.com/modelcontextprotocol/servers

### NPM Search
```bash
npm search @modelcontextprotocol/server-
npm search mcp
```

---

## Architecture

### Skills-Based Flow (Recommended)

```
+------------------+     +------------------+     +------------------+
|   Flet/Gradio    | --> |  Skill Handler   | --> |   MCP Manager    |
|                  |     |                  |     |                  |
| User: /email ... |     | _execute_email() |     | call_tool_sync() |
+------------------+     +------------------+     +------------------+
                                                          |
                                                          v
                                                  +------------------+
                                                  |  MCP Server      |
                                                  |  (google-ws)     |
                                                  |                  |
                                                  | Executes action  |
                                                  +------------------+
                                                          |
                                                          v
                                                  +------------------+
                                                  |   Direct Result  |
                                                  | "✅ Email sent"  |
                                                  +------------------+
```

### Legacy LLM Tool-Calling Flow

For advanced users who want LLM to decide which tools to use:

```
+------------------+     +------------------+     +------------------+
|   Chat UI        | --> |  MessageRouter   | --> |   MCPToolHandler |
|                  |     |                  |     |                  |
| User: "do X"     |     | Detects tool_call|     | Parses & executes|
+------------------+     +------------------+     +------------------+
                                                          |
                                                          v
                         +------------------+     +------------------+
                         |   MCP Manager    | <-- |   MCP Client     |
                         |                  |     |                  |
                         | Routes to server |     | JSON-RPC over    |
                         +------------------+     | STDIO/HTTP/SSE   |
                                                  +------------------+
```

---

Ready to give SkillForge superpowers? Use `/email` and `/calendar` skills or connect MCP servers for more tools!
