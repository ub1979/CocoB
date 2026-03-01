---
name: create-skill
description: Create, list, update, or delete custom skills through chat
emoji: 🛠️
user_invocable: true
---

# Create Skill

Create and manage custom skills through chat. When the user asks to create, update, list, or delete a skill, emit a ```create-skill``` code block with the appropriate action.

## Actions

### Create a skill

```create-skill
ACTION: create
NAME: <skill-name (lowercase, hyphens, no spaces)>
DESCRIPTION: <short one-line description>
EMOJI: <single emoji>
INSTRUCTIONS:
<multi-line markdown instructions for the skill>
<these tell the AI how to behave when the skill is invoked>
```

### List skills

```create-skill
ACTION: list
```

### Delete a skill

```create-skill
ACTION: delete
NAME: <skill-name>
```

### Update a skill

```create-skill
ACTION: update
NAME: <existing-skill-name>
DESCRIPTION: <new description>
EMOJI: <new emoji>
INSTRUCTIONS:
<new instructions — replaces the old ones entirely>
```

## Examples

User: "create a skill that tells dad jokes"

```create-skill
ACTION: create
NAME: dad-jokes
DESCRIPTION: Tell random dad jokes on demand
EMOJI: 😄
INSTRUCTIONS:
When invoked, tell a creative and original dad joke. Keep it family-friendly and groan-worthy.
Vary the jokes each time — never repeat the same joke in a session.
If the user asks for a specific topic, tailor the joke to that topic.
```

User: "make a skill for generating commit messages"

```create-skill
ACTION: create
NAME: commit-msg
DESCRIPTION: Generate concise git commit messages
EMOJI: 📝
INSTRUCTIONS:
Ask the user what changes they made (or read from context if available).
Generate a clear, concise commit message following conventional commits format.
Keep the subject line under 72 characters. Add a body only if the change is complex.
```

User: "list my skills"

```create-skill
ACTION: list
```

User: "delete the dad-jokes skill"

```create-skill
ACTION: delete
NAME: dad-jokes
```

User: "update dad-jokes to also tell puns"

```create-skill
ACTION: update
NAME: dad-jokes
DESCRIPTION: Tell dad jokes and puns on demand
EMOJI: 😄
INSTRUCTIONS:
When invoked, tell a creative dad joke or pun. Keep it family-friendly.
Alternate between dad jokes and puns for variety.
If the user asks for a specific type, honor that preference.
```

## Guidelines for Writing Good Skill Instructions

- Be specific about what the skill should do
- Include tone and style guidance (formal, casual, funny, etc.)
- Mention what to do with user input after the /command
- Add constraints (length limits, format requirements, etc.)
- Include examples of good output if helpful
- Keep instructions concise — a few lines is usually enough
