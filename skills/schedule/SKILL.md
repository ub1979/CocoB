---
name: schedule
description: Create, list, pause, resume, and delete scheduled tasks using natural language
emoji: ⏰
user_invocable: true
---

# Schedule Skill

Create and manage recurring tasks through chat. When the user asks to schedule something, emit a ```schedule``` code block with the appropriate action.

## Actions

### Create a cron task (recurring on a schedule)

```schedule
ACTION: create
NAME: <short descriptive name>
SCHEDULE: <cron expression>
MESSAGE: <text to send when triggered>
CHANNEL: <channel — default to current>
TIMEZONE: <tz — default UTC>
```

Use `SKILL` + `PARAMS` instead of `MESSAGE` to run a skill:

```schedule
ACTION: create
NAME: Morning calendar briefing
SCHEDULE: 0 9 * * *
SKILL: calendar
PARAMS: today
CHANNEL: discord
TIMEZONE: America/New_York
```

### Create an interval task (repeating)

Runs every N minutes/hours/seconds. Use `KIND: every` with an `INTERVAL` field.

```schedule
ACTION: create
NAME: Health check
KIND: every
INTERVAL: 30m
MESSAGE: Running health check...
```

### Create a one-shot task (run once)

Runs once at a specific datetime, then auto-deletes. Use `KIND: at` with a `RUN_AT` field (ISO 8601).

```schedule
ACTION: create
NAME: Meeting reminder
KIND: at
RUN_AT: 2026-02-25T14:00:00
MESSAGE: Your meeting starts in 15 minutes!
```

Set `DELETE_AFTER: false` to keep the task after it runs (default is `true` for one-shot tasks).

### List tasks

```schedule
ACTION: list
```

### Pause / Resume / Delete

```schedule
ACTION: pause
TASK_ID: <id>
```

```schedule
ACTION: resume
TASK_ID: <id>
```

```schedule
ACTION: delete
TASK_ID: <id>
```

## Common Cron Presets

| Pattern | Meaning |
|---------|---------|
| `0 9 * * *` | Every day at 9:00 AM |
| `0 9 * * 1-5` | Weekdays at 9:00 AM |
| `0 */2 * * *` | Every 2 hours |
| `30 8 * * 1` | Every Monday at 8:30 AM |
| `0 0 1 * *` | First day of each month |
| `*/15 * * * *` | Every 15 minutes |

## Interval Presets

| Value | Meaning |
|-------|---------|
| `30m` | Every 30 minutes |
| `1h` | Every hour |
| `2h` | Every 2 hours |
| `6h` | Every 6 hours |
| `12h` | Every 12 hours |
| `24h` | Every 24 hours |
| `60s` | Every 60 seconds |

## Examples

User: "remind me every day at 9 to check my calendar"

```schedule
ACTION: create
NAME: Daily calendar reminder
SCHEDULE: 0 9 * * *
MESSAGE: Time to check your calendar!
TIMEZONE: UTC
```

User: "check the server every 30 minutes"

```schedule
ACTION: create
NAME: Server check
KIND: every
INTERVAL: 30m
MESSAGE: Running server health check...
```

User: "remind me at 3pm tomorrow about the meeting"

```schedule
ACTION: create
NAME: Meeting reminder
KIND: at
RUN_AT: 2026-02-25T15:00:00
MESSAGE: Don't forget your meeting!
```

User: "list my scheduled tasks"

```schedule
ACTION: list
```

User: "cancel task abc123"

```schedule
ACTION: delete
TASK_ID: abc123
```

## Trigger Types

| Kind | Field | Description |
|------|-------|-------------|
| `cron` (default) | `SCHEDULE` | Standard cron expression for recurring tasks |
| `every` | `INTERVAL` | Repeat every N seconds/minutes/hours |
| `at` | `RUN_AT` | Run once at a specific ISO 8601 datetime |

## Retry Behavior

Failed tasks automatically retry with exponential backoff: 30s → 1m → 5m → 15m → 60m (up to 5 retries). One-shot tasks do not retry.

## Tips

- Always confirm the timezone with the user if not obvious
- When listing tasks, show IDs so the user can pause/resume/delete them
- For "every morning" default to `0 9 * * *` unless the user specifies a time
- For "every N minutes/hours" use `KIND: every` with `INTERVAL`
- For "at <specific time>" use `KIND: at` with `RUN_AT` in ISO 8601 format
- Natural phrases like "cancel that alarm" or "stop the reminder" map to delete/pause actions — use the task ID from context
