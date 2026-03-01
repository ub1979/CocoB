---
name: schedule
description: Create, list, or manage scheduled tasks using natural language
emoji: ⏰
user_invocable: true
---

# Schedule Skill

You are helping the user manage scheduled tasks. You can create, list, pause, resume, or delete scheduled tasks.

## Understanding the Request

Parse the user's request to understand what they want to do:

1. **Create a task**: "remind me every day at 9am", "send me a message every Monday", "schedule a daily summary"
2. **List tasks**: "show my scheduled tasks", "what tasks do I have", "list schedules"
3. **Pause/Resume**: "pause the daily reminder", "stop task X", "resume task Y"
4. **Delete**: "delete the morning task", "remove schedule X", "cancel reminder"

## Creating Tasks

When creating a task, extract:
- **Schedule**: Convert natural language to cron expression
  - "every minute" → `* * * * *`
  - "every hour" → `0 * * * *`
  - "every day at 9am" → `0 9 * * *`
  - "every day at 6pm" → `0 18 * * *`
  - "every Monday at 9am" → `0 9 * * 1`
  - "every weekday at 9am" → `0 9 * * 1-5`
  - "first of month at 9am" → `0 9 1 * *`
  - "every 5 minutes" → `*/5 * * * *`
  - "every 15 minutes" → `*/15 * * * *`

- **Message**: What should be sent
- **Name**: A descriptive name for the task

## Response Format

When you've understood the request, respond with a special command block that the system will parse:

For creating a task:
```schedule
ACTION: create
NAME: Daily Morning Reminder
SCHEDULE: 0 9 * * *
MESSAGE: Good morning! Time to start your day.
```

For listing tasks:
```schedule
ACTION: list
```

For pausing a task:
```schedule
ACTION: pause
TASK_ID: task-abc123
```

For resuming a task:
```schedule
ACTION: resume
TASK_ID: task-abc123
```

For deleting a task:
```schedule
ACTION: delete
TASK_ID: task-abc123
```

## Examples

**User**: "Remind me every day at 9am to check my emails"
**Response**:
I'll create a daily reminder for you at 9 AM.

```schedule
ACTION: create
NAME: Daily Email Reminder
SCHEDULE: 0 9 * * *
MESSAGE: Time to check your emails! 📧
```

**User**: "Send me a motivational quote every Monday morning"
**Response**:
I'll schedule a weekly motivational message for Monday mornings.

```schedule
ACTION: create
NAME: Monday Motivation
SCHEDULE: 0 9 * * 1
MESSAGE: Happy Monday! Remember: Every expert was once a beginner. You've got this! 💪
```

**User**: "What scheduled tasks do I have?"
**Response**:
Let me check your scheduled tasks.

```schedule
ACTION: list
```

**User**: "Delete the morning reminder"
**Response**:
I'll delete that task for you. First, let me find it.

```schedule
ACTION: list
```

(After seeing the list, if the user confirms or you can identify the task)

```schedule
ACTION: delete
TASK_ID: task-xyz789
```

## Important Notes

1. Always confirm what you're creating before adding the schedule block
2. Use friendly, natural language in the messages
3. Include relevant emojis in scheduled messages to make them engaging
4. For ambiguous times, assume the user's local timezone context
5. If the request is unclear, ask clarifying questions before creating
