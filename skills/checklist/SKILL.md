---
name: checklist
description: Create, manage, and quiz yourself on named checklists for trips, routines, projects, and more
emoji: "\u2611\uFE0F"
user_invocable: true
---

# Checklist Skill

Manage named checklists and quiz the user on them through chat. When the user asks to manage checklists or be quizzed, emit a ```checklist``` code block with the appropriate action.

## Actions

### Create a checklist

```checklist
ACTION: create
NAME: <checklist name>
ITEMS:
<item 1>
<item 2>
<item 3>
```

### List all checklists

```checklist
ACTION: list
```

### Show a specific checklist

```checklist
ACTION: show
NAME: <checklist name>
```

### Quiz the user on a checklist

```checklist
ACTION: quiz
NAME: <checklist name>
```

After receiving the checklist items back, go through each item one by one and ask the user if they remembered or completed it. For example: "Did you remember your passport?" "Did you pack your charger?" Keep going until all items are covered, then summarize what was missed.

### Delete a checklist

```checklist
ACTION: delete
NAME: <checklist name>
```

### Edit a checklist (add or remove items)

```checklist
ACTION: edit
NAME: <checklist name>
ADD_ITEMS:
<new item 1>
<new item 2>
REMOVE_ITEMS:
<item to remove>
```

You can use ADD_ITEMS, REMOVE_ITEMS, or both in a single edit command.

## Examples

User: "make a travel checklist: passport, tickets, charger, clothes, toothbrush"

```checklist
ACTION: create
NAME: Travel Checklist
ITEMS:
passport
tickets
charger
clothes
toothbrush
```

User: "quiz me on my travel checklist"

```checklist
ACTION: quiz
NAME: Travel Checklist
```

Then after receiving the items, ask interactively:
- "Did you remember your **passport**?"
- "Did you pack your **tickets**?"
- (continue for each item...)

User: "did I forget anything for the trip?"

```checklist
ACTION: quiz
NAME: Travel Checklist
```

User: "add sunscreen to travel checklist"

```checklist
ACTION: edit
NAME: Travel Checklist
ADD_ITEMS:
sunscreen
```

User: "remove charger from travel checklist"

```checklist
ACTION: edit
NAME: Travel Checklist
REMOVE_ITEMS:
charger
```

User: "show all my checklists"

```checklist
ACTION: list
```

User: "show my travel checklist"

```checklist
ACTION: show
NAME: Travel Checklist
```

User: "delete my travel checklist"

```checklist
ACTION: delete
NAME: Travel Checklist
```

## Tips

- When creating, infer the checklist name from context ("travel checklist", "grocery list", "morning routine")
- Items can be provided as comma-separated ("passport, tickets, charger") or newline-separated in the ITEMS field
- For "quiz me" or "did I forget anything" or "check if I got everything", use the quiz action
- When quizzing, show items one at a time and wait for user confirmation before moving to the next
- After a quiz, summarize: "You remembered 4/5 items. You missed: sunscreen"
- Natural phrases like "make a checklist", "create a packing list", "I need a list of" mean create
- "What checklists do I have?" or "show my lists" means list
