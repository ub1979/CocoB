---
name: commit
description: Create git commits with good messages
user-invocable: true
emoji: "📝"
---

# Commit Skill

When the user asks to commit changes, follow these steps:

## 1. Check Current State
Run `git status` to see what files have changed:
- Modified files
- Untracked files
- Staged files

## 2. Review Changes
Run `git diff` to see the actual changes:
- What was added/removed
- Which functions/sections were modified
- The overall scope of changes

## 3. Stage Changes
Stage the appropriate files:
- Use `git add <file>` for specific files
- Use `git add .` to stage all changes (ask user first if there are many changes)

## 4. Write Commit Message
Follow the Conventional Commits format:

**Type prefixes:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Formatting, missing semicolons, etc.
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

**Format:**
```
type(scope): brief description

Longer explanation if needed.
- Bullet points for details
- What and why, not how
```

**Examples:**
- `feat(auth): add password reset functionality`
- `fix(ui): resolve button alignment on mobile`
- `docs: update API documentation`

## 5. Create the Commit
Run `git commit -m "message"` with the crafted message.

## Tips
- Keep the first line under 72 characters
- Use present tense ("add" not "added")
- Be specific about what changed
- If the user provides context about the change, incorporate it
