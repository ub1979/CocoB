---
name: explain
description: Explain how code works
user-invocable: true
emoji: "📖"
---

# Explain Skill

When explaining code to the user:

## 1. One-Line Summary
Start with a brief summary of what the code does:
- "This function calculates the total price including tax"
- "This class manages user authentication sessions"

## 2. Break Down Components
Identify and explain the main parts:
- Functions/methods and their purposes
- Important variables and data structures
- Key imports and dependencies

## 3. Explain the Flow
Walk through how the code executes:
- Entry point
- Decision points (if/else, switches)
- Loops and iterations
- Return values or side effects

## 4. Highlight Key Concepts
Point out important patterns or techniques:
- Design patterns used
- Algorithms implemented
- Language-specific features
- Best practices followed

## 5. Note Edge Cases
Mention any gotchas or special handling:
- Error handling
- Boundary conditions
- Performance considerations
- Known limitations

## Example Format
```
**Summary:**
This function validates user input and returns a cleaned result.

**Components:**
- `validate_email()` - Checks email format
- `sanitize_input()` - Removes dangerous characters
- `UserInput` class - Holds validated data

**Flow:**
1. Receives raw input from form
2. Validates format using regex
3. Sanitizes for SQL injection
4. Returns validated UserInput object

**Key Concepts:**
- Uses regex for pattern matching
- Implements the Validator pattern
- Returns None on failure instead of throwing

**Gotchas:**
- Does NOT validate email exists, only format
- Maximum input length is 255 characters
```

## Tips
- Adjust depth based on user's apparent skill level
- Use analogies for complex concepts
- Offer to dive deeper into specific parts
- Link to relevant documentation when helpful
