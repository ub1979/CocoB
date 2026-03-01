---
name: search
description: Search the web for information
user-invocable: true
emoji: "🔍"
---

# Search Skill

When the user asks to search for information:

## 1. Understand the Query
- Clarify what specific information is needed
- Identify key terms and concepts
- Consider what type of sources would be most useful

## 2. Perform the Search
Use available tools to search:
- Use the Playwright MCP tool if available for web browsing
- Use any search API tools available
- For code searches, use grep/find on local files

## 3. Analyze Results
- Read through the top results
- Extract relevant information
- Cross-reference multiple sources when possible

## 4. Present Findings
Summarize the information clearly:
- Start with a direct answer if possible
- Provide supporting details
- Include relevant quotes or data points

## 5. Cite Sources
Always provide sources with links:
- Include the title and URL
- Note the date if relevant
- Indicate reliability of sources

## Example Response Format
```
**Summary:**
[Direct answer to the question]

**Details:**
- Key point 1
- Key point 2
- Key point 3

**Sources:**
- [Title](https://example.com) - Brief description
- [Title](https://example.com) - Brief description
```

## Tips
- If a search fails, try rephrasing the query
- For technical topics, prefer official documentation
- For current events, prefer recent articles
- Always verify important claims with multiple sources
