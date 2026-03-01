---
name: todo
description: Add, list, complete, edit, and delete to-do items with priorities and due dates
emoji: ✅
user_invocable: true
---

# Todo Skill

Manage your personal to-do list through chat. When the user asks to manage tasks, emit a ```todo``` code block with the appropriate action.

## Actions

### Add a task

```todo
ACTION: add
TITLE: <task description>
PRIORITY: <low|medium|high — default medium>
DUE: <due date — e.g. 2026-02-25, tomorrow, next friday>
TAGS: <comma-separated tags — optional>
```

### List tasks

```todo
ACTION: list
```

List only specific tasks:

```todo
ACTION: list
TAGS: work
PRIORITY: high
```

### Mark task as done

```todo
ACTION: done
TODO_ID: <id>
```

### Delete a task

```todo
ACTION: delete
TODO_ID: <id>
```

### Edit a task

```todo
ACTION: edit
TODO_ID: <id>
TITLE: <new title — optional>
PRIORITY: <new priority — optional>
DUE: <new due date — optional>
TAGS: <new tags — optional>
```

### Set a reminder

```todo
ACTION: remind
TODO_ID: <id>
REMIND_AT: <cron expression or datetime — e.g. 0 9 * * *, 2026-02-25 09:00>
```

## Examples

User: "add a task to buy groceries"

```todo
ACTION: add
TITLE: Buy groceries
PRIORITY: medium
```

User: "remind me about task abc123 tomorrow at 9am"

```todo
ACTION: remind
TODO_ID: abc123
REMIND_AT: 0 9 21 2 *
```

User: "show my todos"

```todo
ACTION: list
```

User: "mark abc123 as done"

```todo
ACTION: done
TODO_ID: abc123
```

User: "delete task abc123"

```todo
ACTION: delete
TODO_ID: abc123
```

User: "change the priority of abc123 to high"

```todo
ACTION: edit
TODO_ID: abc123
PRIORITY: high
```

## Tips

- When adding, infer priority from urgency cues ("urgent" → high, "whenever" → low)
- When listing, show IDs so the user can act on specific tasks
- For "remind me" requests, create a todo with a reminder
- Natural phrases like "I need to", "don't forget to", "remember to" mean add a task
- "What do I need to do?" or "what's on my list?" means list tasks
