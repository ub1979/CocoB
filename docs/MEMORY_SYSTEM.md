# Memory System Documentation

SkillForge uses a dual-storage memory architecture: JSONL for ordered session history, and **SQLite FTS5** for fast full-text search and fact extraction.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MEMORY ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────────┐              ┌──────────────────┐               │
│  │     JSONL         │              │  SQLite FTS5     │               │
│  │  (Session History)│              │  (Search + Facts)│               │
│  ├──────────────────┤              ├──────────────────┤               │
│  │ • Full history    │              │ • Full-text search│              │
│  │ • Ordered         │              │ • User facts      │              │
│  │ • Every message   │              │ • Conversation    │              │
│  │ • Compaction      │              │   summaries       │              │
│  │   summaries       │              │ • Zero deps       │              │
│  └──────────────────┘              └──────────────────┘               │
│           │                                 │                          │
│           └────────────┬────────────────────┘                          │
│                        │                                               │
│                        ▼                                               │
│              ┌──────────────────┐                                      │
│              │   LLM Context    │                                      │
│              │                  │                                      │
│              │ • System prompt  │                                      │
│              │ • User facts (SQLite)                                   │
│              │ • Relevant past conversations (FTS5)                    │
│              │ • Summary (if compacted)                                │
│              │ • Last 5 messages (JSONL)                               │
│              └──────────────────┘                                      │
│                                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. JSONL Storage (SessionManager)

**Location:** `data/sessions/`

**Purpose:** Complete, ordered transcript of all conversations.

- `sessions.json` — Index of all sessions
- `sess-{date}-{uuid}.jsonl` — Full conversation transcript
- Supports compaction (summarizing old messages when context fills up)

### 2. SQLite FTS5 Memory (SQLiteMemory)

**Location:** `data/memory.db`

**Purpose:** Fast full-text search + structured fact storage. Zero external dependencies.

**Tables:**
- `facts` — Extracted user facts (name, preferences, traits, etc.)
- `conversations` — Conversation summaries for search
- `facts_fts` / `conversations_fts` — FTS5 virtual tables for full-text search

**Fact Extraction:**
1. **Regex first-pass** — Instant pattern matching for explicit statements ("my name is X", "I like Y", "I work at Z")
2. **LLM second-pass** — If regex finds nothing, the LLM extracts subtler facts from the conversation turn

**Features:**
- Instant startup (no embedding model to load)
- Automatic deduplication of facts
- FTS5 triggers keep search index in sync with data tables
- Context injection capped at ~500 tokens to avoid prompt bloat

## User Commands

| Command | Description |
|---------|-------------|
| `/memory` | Show all stored facts about you |
| `/forget` | Clear all stored facts |
| `/forget [topic]` | Delete facts matching a keyword |

## Message Flow

```
1. USER SENDS MESSAGE
   │
   ▼
2. RETRIEVE RELEVANT MEMORIES (SQLite FTS5)
   │  • User facts (top 10)
   │  • Relevant past conversations (top 3)
   │  • Capped at ~500 tokens
   │
   ▼
3. LOAD RECENT HISTORY (JSONL)
   │  • Last 5 messages for speed
   │  • Compaction if context > 80% full
   │
   ▼
4. BUILD LLM CONTEXT
   │  System prompt + memories + history
   │
   ▼
5. LLM GENERATES RESPONSE
   │
   ▼
6. POST-RESPONSE PROCESSING
   │  • Extract facts (regex → LLM fallback)
   │  • Store conversation summary
   │  • Parse mood/personality updates
   │
   ▼
7. RETURN RESPONSE TO USER
```

## Storage Comparison

| Feature | JSONL | SQLite FTS5 |
|---------|-------|-------------|
| **Purpose** | Full history | Fast search + facts |
| **Search** | Sequential | Full-text indexed |
| **Order** | Preserved | Not important |
| **Dependencies** | None | None (stdlib) |
| **Backup** | Human-readable | Single .db file |

## Configuration

Memory paths are auto-configured relative to the project root:
- Sessions: `data/sessions/`
- Memory DB: `data/memory.db`

Context settings are in `config.py`:
- `MAX_CONTEXT_TOKENS` — Maximum context window size
- `COMPACTION_THRESHOLD` — Compact at 80% full

## Troubleshooting

### Memory DB not created
Delete the empty file and restart:
```bash
rm data/memory.db
python skillforge.py
```
The system auto-detects and removes 0-byte DB files on startup.

### Memory not being retrieved
Check stats:
```python
from core.memory import SQLiteMemory
mem = SQLiteMemory()
print(mem.get_stats())
```

### Reset all memories for a user
Use `/forget` in chat, or programmatically:
```python
mem.delete_user_facts("user-id")
```

---

*SkillForge — Persistent Memory AI Chatbot*
*Making AI Useful for Everyone*
