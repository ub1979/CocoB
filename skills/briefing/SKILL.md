---
name: briefing
description: Daily briefing with calendar, email, news, todos, and tracked data
emoji: 📋
user_invocable: true
---

# Briefing Skill

Generate a daily briefing that combines calendar, email, news, todos, tracked data, and scheduled reminders into one clean summary. This is a prompt-only skill -- it orchestrates existing skills and MCP tools; there is no dedicated handler.

## Trigger Phrases

- `/briefing` -- full daily briefing
- `/briefing morning` -- full daily briefing (alias)
- `/briefing quick` -- abbreviated briefing (calendar + todos only)
- "what's my day look like?"
- "morning briefing"
- "daily summary"
- "brief me"

## How to Build the Briefing

When triggered, work through each section below **in order**. For each section, attempt to fetch the data. If the data source is unavailable (MCP not connected, no entries, permission denied), **skip that section gracefully** -- do not show an error, just omit it or add a one-line note like "Calendar not connected."

Use today's date for all date-relative queries.

---

### 1. Calendar

Check today's calendar events using the Google Workspace or Outlook MCP tools (e.g. `google-calendar-list-events`, `GOOGLECALENDAR_FIND_EVENT`, or equivalent).

- If an MCP calendar tool is available, fetch today's events and list them with times.
- If the "Tool Status" section lists calendar as unavailable, skip this section.

### 2. Email

Check recent unread emails using the Gmail or Outlook MCP tools (e.g. `gmail-search`, `GMAIL_FETCH_EMAILS`, or equivalent).

- If an MCP email tool is available, show the unread count and list important/recent senders.
- If no email MCP is connected, skip this section entirely.

### 3. News

Fetch top headlines using a web search:

```web_search
QUERY: top news headlines today
COUNT: 5
```

Show 3-5 headlines as a bulleted list. Keep it brief -- one line per headline.

### 4. Todos

List pending tasks:

```todo
ACTION: list
```

Show all pending todos with their priority. If there are no todos, print: *"No pending todos -- nice!"*

### 5. Tracked Today

Show today's tracked data entries across all categories:

```track
ACTION: list
DATE_FROM: <today's date in YYYY-MM-DD>
DATE_TO: <today's date in YYYY-MM-DD>
```

If no entries exist for today, skip this section.

### 6. Reminders

List upcoming scheduled tasks:

```schedule
ACTION: list
```

Filter the results to show only tasks that fire today or are one-shot tasks with a `RUN_AT` in the near future. If no scheduled tasks exist, skip this section.

---

## Output Format

Present the briefing in this format:

```
## Good morning! Here's your briefing for [date]

### Calendar
- 10:00 Team standup
- 14:00 Client call

### Email
- 3 unread emails (1 from boss@company.com)

### News
- [headline 1]
- [headline 2]
- [headline 3]

### Todos
- Buy groceries (medium)
- Fix bug #123 (high)

### Tracked Today
- Gym: bench 60kg, squats 80kg
- Weight: 82.5kg

### Reminders
- 15:00 Take medicine
```

Adjust the greeting based on time of day if known ("Good morning", "Good afternoon", "Good evening"). Default to "Good morning" if time is unknown.

## Quick Mode

When the user says `/briefing quick`, only include:

1. **Calendar** -- today's events
2. **Todos** -- pending tasks

Skip news, email, tracked data, and reminders. Use a shorter header: `## Quick briefing for [date]`

## Graceful Degradation

- **MCP not connected:** Skip that section, optionally note it is not connected.
- **No data:** Skip the section silently (no "0 items" noise).
- **Permission denied:** Skip the section; do not show permission errors in the briefing.
- **Partial failure:** Show whatever sections succeeded. Even if only one section returns data, show the briefing with that section alone.

## Examples

User: "/briefing"

Produce a full briefing with all six sections (skipping any that are unavailable).

User: "/briefing quick"

Produce a short briefing with only Calendar and Todos.

User: "what's my day look like?"

Produce a full briefing (same as `/briefing`).

## Tips

- Keep the entire briefing scannable -- use short bullet points, not paragraphs.
- Show times in the user's local format if known, otherwise 24-hour format.
- For todos, show at most 10 items; if more exist, add "... and N more."
- For news, prefer variety -- one headline per source if possible.
- This skill is a great candidate for scheduling as a daily automation:
  ```schedule
  ACTION: create
  NAME: Daily morning briefing
  SCHEDULE: 0 9 * * *
  SKILL: briefing
  PARAMS: morning
  ```
