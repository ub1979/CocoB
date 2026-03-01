---
name: files
description: Browse, search, read, and manage local files and directories
emoji: 📂
user_invocable: true
---

# Files Skill

Browse and manage local files through chat. Uses the Filesystem MCP server for all operations.

## Prerequisites

- Filesystem MCP server connected with appropriate directories in allowed paths
- If Filesystem MCP is not available, reply: "File management requires the Filesystem MCP server. Ask your admin to set it up with your allowed directories."

## Operations

### Browse Directory

When asked to list/browse/show files in a directory:
1. Use Filesystem MCP to list directory contents
2. Format as:
   - 📁 **dirname/** — directory
   - 📄 **filename.ext** — file (size if available)
3. Default to the user's home or first allowed directory if no path given

### Search Files

When asked to find/search for files:
1. Search by name pattern or content across allowed directories
2. Show matching paths with context

### Read File

When asked to read/show/view a file:
1. Read the file content via Filesystem MCP
2. Show with appropriate formatting (code blocks for code, plain text otherwise)
3. For large files, show first ~50 lines and offer to show more

### Create Directory

When asked to create/make a directory:
1. Create via Filesystem MCP
2. Confirm: "Created **path/to/dir/**"

### Move / Copy Files

When asked to move, rename, or copy files:
1. **Always confirm before executing**: "Move **old-path** → **new-path**?"
2. Execute only after user confirms
3. Confirm completion

### Delete Files

When asked to delete/remove files:
1. **Always confirm before deleting**: "Delete **path/to/file**? This can't be undone."
2. Only delete after explicit confirmation

## Safety Rules

- Never operate outside the Filesystem MCP's allowed directories
- Always confirm before any destructive operation (delete, overwrite, move)
- Show full paths so the user knows exactly what's affected
- If a path is ambiguous, ask for clarification
- Refuse to modify system files or config files unless the user is explicit

## Formatting

- Use emoji prefixes for file types (📁 dirs, 📄 files)
- Show file sizes in human-readable format (KB, MB)
- Use code blocks when displaying file contents
- Keep directory listings concise — max 30 items, then summarize remaining
