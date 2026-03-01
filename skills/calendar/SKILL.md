---
name: calendar
description: Manage your Google Calendar - view, create, update events
emoji: 📅
user_invocable: true
---

# Calendar Skill

Manage your Google Calendar using natural language commands.

## Usage

```
/calendar today
/calendar this week
/calendar create "Team Meeting" tomorrow at 3pm
/calendar free slots next Monday
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
| `today` | Show today's events |
| `tomorrow` | Show tomorrow's events |
| `this week` | Show this week's events |
| `next week` | Show next week's events |
| `create "<title>" <when>` | Create event |
| `free slots <when>` | Find available times |
| `delete <event>` | Delete event |
| `move <event> to <time>` | Reschedule event |

## Time Expressions

Natural language times are supported:
- `today at 3pm`
- `tomorrow at 10:30am`
- `next Monday at 2pm`
- `Friday at 14:00`
- `in 2 hours`
- `next week Tuesday`

## Examples

```
/calendar today
/calendar create "Doctor Appointment" March 15 at 10am
/calendar create "Team Standup" tomorrow at 9am for 30 minutes
/calendar free slots next Monday
/calendar delete "Old Meeting"
/calendar this week
```

## Multiple Calendars

```
/calendar show work calendar
/calendar create "Gym" in personal calendar tomorrow at 6am
/calendar list calendars
```

## Tips

1. **Morning routine**: Start with `/calendar today`
2. **Plan ahead**: Check `/calendar tomorrow` before end of day
3. **Scheduling**: Use `/calendar free slots` before proposing meetings
4. **Quick events**: `/calendar lunch with Sarah tomorrow noon`
