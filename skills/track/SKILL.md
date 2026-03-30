---
name: track
description: Log and analyse personal data like fuel, gym, meter readings, expenses, weight, and more
emoji: 📊
user_invocable: true
---

# Track Skill

Track personal data through chat. When the user wants to log, view, or analyse personal metrics, emit a ```track``` code block with the appropriate action.

Categories are free-form strings defined naturally by the user (e.g. "petrol", "gym", "weight", "electricity", "expenses", "water", "running").

## Actions

### Log a data point

```track
ACTION: log
CATEGORY: <category name>
VALUE: <numeric value>
UNIT: <unit of measurement — optional>
NOTE: <free-text note — optional>
```

### List recent entries

```track
ACTION: list
CATEGORY: <category name>
COUNT: <number of entries to show — default 10, optional>
DATE_FROM: <ISO date — optional, e.g. 2026-03-01>
DATE_TO: <ISO date — optional, e.g. 2026-03-31>
```

### List all categories

```track
ACTION: categories
```

### Show stats / analytics

```track
ACTION: stats
CATEGORY: <category name>
DATE_FROM: <ISO date — optional>
DATE_TO: <ISO date — optional>
```

### Delete an entry

```track
ACTION: delete
ENTRY_ID: <id>
```

### Export all data for a category

```track
ACTION: export
CATEGORY: <category name>
```

## Examples

User: "I put petrol, meter reading 45230, 40 litres"

```track
ACTION: log
CATEGORY: petrol
VALUE: 40
UNIT: litres
NOTE: meter:45230
```

User: "gym today: bench press 60kg, squats 80kg"

```track
ACTION: log
CATEGORY: gym
VALUE: 60
UNIT: kg
NOTE: bench press
```

```track
ACTION: log
CATEGORY: gym
VALUE: 80
UNIT: kg
NOTE: squats
```

User: "electricity meter reads 12450"

```track
ACTION: log
CATEGORY: electricity
VALUE: 12450
UNIT: kWh
NOTE: meter reading
```

User: "spent £45 on groceries"

```track
ACTION: log
CATEGORY: expenses
VALUE: 45
UNIT: GBP
NOTE: groceries
```

User: "I weigh 82.5kg today"

```track
ACTION: log
CATEGORY: weight
VALUE: 82.5
UNIT: kg
```

User: "how much petrol have I used this month?"

```track
ACTION: stats
CATEGORY: petrol
DATE_FROM: 2026-03-01
DATE_TO: 2026-03-31
```

User: "show my gym history"

```track
ACTION: list
CATEGORY: gym
```

User: "what categories am I tracking?"

```track
ACTION: categories
```

User: "delete entry abc123"

```track
ACTION: delete
ENTRY_ID: abc123
```

User: "export all my petrol data"

```track
ACTION: export
CATEGORY: petrol
```

User: "show my weight trend"

```track
ACTION: stats
CATEGORY: weight
```

User: "last 5 electricity readings"

```track
ACTION: list
CATEGORY: electricity
COUNT: 5
```

## Tips

- When the user mentions a measurement with a category, log it — even without the word "track" or "log"
- Infer UNIT from context ("litres", "kg", "miles", "kWh", "GBP", etc.)
- Use NOTE for extra context: meter readings, exercise names, shop names, descriptions
- For compound entries (e.g. multiple gym exercises), emit multiple ```track``` blocks
- "How much", "how many", "what's my average" → stats action
- "Show me", "history", "recent" → list action
- When showing stats, the handler calculates count, total, average, min, max, and trend
- Dates should use ISO 8601 format (YYYY-MM-DD)
- Categories are case-insensitive and will be normalised to lowercase
