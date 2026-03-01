---
name: notes
description: Create, search, edit, and manage markdown notes
emoji: 📝
user_invocable: true
---

# Notes Skill

Manage personal notes as markdown files in `~/notes/`. Uses the Filesystem MCP server for all file operations.

## Prerequisites

- Filesystem MCP server connected with `~/notes` (or equivalent) in allowed paths
- If Filesystem MCP is not available, reply: "Notes require the Filesystem MCP server with access to your notes directory. Ask your admin to set it up."

## Note Format

Each note is a markdown file stored as `~/notes/<slug>.md`:

```
# Note Title
_Created: 2026-02-20_

Note content here...
```

- Filename: lowercase slug from title (e.g., "Meeting Notes" → `meeting-notes.md`)
- Always include a date header when creating

## Operations

### Create a Note

When asked to create/write/save a note:
1. Derive filename from title (slugified)
2. Write the file with title heading and date
3. Confirm: "Saved **meeting-notes.md**"

### List Notes

When asked to list/show notes:
1. List files in `~/notes/`
2. Show as: `- **filename.md** — first line of content`
3. Sort by most recent

### Search Notes

When asked to search/find in notes:
1. Read files and search for the keyword in content
2. Show matching notes with the relevant snippet

### Edit a Note

When asked to edit/update a note:
1. Read the current content
2. Apply the requested changes
3. Write the updated file
4. Confirm what was changed

### Delete a Note

When asked to delete/remove a note:
1. Confirm with the user before deleting: "Delete **filename.md**? This can't be undone."
2. Only delete after confirmation

## Tips

- If the user says "note" without a title, ask for one
- For quick notes (e.g., "note: buy milk"), use the content as both title and body
- When listing, show at most 20 notes unless asked for more
- Support tags via `#tag` in note content for searching
