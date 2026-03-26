# Contributing to SkillForge

First off, thanks for taking the time to contribute! All types of contributions are encouraged and valued. See the [Table of Contents](#table-of-contents) for different ways to help and details about how this project handles them.

> If you like the project but don't have time to contribute, that's fine too. There are other ways to show your support:
> - Star the project on GitHub
> - Share it with others
> - Mention it in your blog or at meetups

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Your First Code Contribution](#your-first-code-contribution)
  - [Adding a Skill](#adding-a-skill)
  - [Adding a Handler](#adding-a-handler)
- [Style Guide](#style-guide)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [License](#license)

## Code of Conduct

This project and everyone participating in it is governed by a commitment to making participation a harassment-free experience for everyone. By participating, you are expected to uphold this standard. Please be respectful, inclusive, and constructive in all interactions.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/SkillForge.git
   cd SkillForge
   ```
3. **Add the upstream remote** so you can keep your fork in sync:
   ```bash
   git remote add upstream https://github.com/ub1979/SkillForge.git
   ```

## Development Setup

### Prerequisites

- Python 3.10 or higher
- pip (or conda)
- Git

### Installation

```bash
# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Verify installation
python -m pytest tests/ -v
```

### Configuration

Copy the example config and adjust for your setup:
```bash
cp config/config.example.py config.py
```

At minimum, configure an LLM provider (Ollama is the easiest for local development).

## Project Structure

```
SkillForge/
├── src/skillforge/               # Main Python package
│   ├── core/                  # Core modules (router, sessions, handlers, etc.)
│   │   ├── router.py          # Central message orchestrator
│   │   ├── llm/               # LLM provider framework
│   │   └── ...                # Handlers, managers, utilities
│   ├── channels/              # Channel integrations (Telegram, WhatsApp, etc.)
│   └── flet/                  # Desktop UI (Flet framework)
├── skills/                    # Skill definitions (SKILL.md files)
├── data/                      # Runtime data (sessions, memory, config)
├── tests/                     # Test suite (pytest)
├── docs/                      # Documentation
└── config.py                  # Local configuration (not committed)
```

For detailed architecture, see [docs/read_me_claude.md](docs/read_me_claude.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check [existing issues](https://github.com/ub1979/SkillForge/issues) to avoid duplicates.

When filing a bug report, please include:

- **A clear title** describing the issue
- **Steps to reproduce** the behavior
- **Expected behavior** vs. what actually happened
- **Environment details** (OS, Python version, LLM provider)
- **Error messages** or logs (if applicable)
- **Screenshots** (for UI issues)

### Suggesting Features

Feature requests are welcome! Please open an issue with:

- **A clear description** of the feature
- **The problem it solves** or the use case
- **Any alternatives** you've considered
- Whether you'd be willing to implement it

### Your First Code Contribution

Not sure where to start? Look for issues labeled:

- `good first issue` - Simple, well-defined tasks
- `help wanted` - More involved but well-documented
- `documentation` - Improvements to docs

### Adding a Skill

Skills are the easiest way to extend SkillForge. They're just markdown files with YAML frontmatter:

1. Create `skills/my-skill/SKILL.md`:
   ```yaml
   ---
   name: my-skill
   description: Brief description of what it does
   emoji: "🎯"
   user_invocable: true
   ---

   # Instructions for the LLM

   When the user invokes /my-skill, do the following:
   ...
   ```

2. The skill is automatically loaded on startup. Test it with `/my-skill` in chat.

3. Add a test in `tests/test_skills_loading.py` to verify it parses correctly.

### Adding a Handler

Handlers process code blocks from LLM responses (e.g., `` ```schedule``` ``, `` ```todo``` ``). Follow the pattern in `src/skillforge/core/schedule_handler.py`:

1. Create `src/skillforge/core/my_handler.py` with:
   - A regex pattern to detect your blocks
   - `has_commands()`, `extract_commands()`, `execute_commands()` methods
2. Wire it into `src/skillforge/core/router.py`:
   - Import and initialize in `__init__`
   - Add processing in section 7.x of both `handle_message` and `handle_message_stream`
3. Write tests in `tests/test_my_handler.py`

## Style Guide

### Python

- Follow existing code patterns and conventions in the codebase
- Use type hints for function signatures
- Keep functions focused — one function, one responsibility
- Use `logging` instead of `print()` for new code (existing code uses `print()`)
- Use `datetime.now(tz=timezone.utc)` instead of `datetime.utcnow()` (deprecated)
- For project root paths: `from skillforge import PROJECT_ROOT`

### Commits

- Use clear, descriptive commit messages
- Start with a verb: "Add", "Fix", "Update", "Remove"
- Reference issue numbers where applicable: "Fix #42: handle empty response"
- Keep commits focused on a single change

### Documentation

- Update `CHANGELOG.md` for any user-facing changes
- Update `docs/read_me_claude.md` if project structure changes
- Add docstrings to public classes and methods

## Testing

We use **pytest** with **pytest-asyncio** for async tests.

### Running Tests

```bash
# Run full suite
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_user_permissions.py -v

# Run a specific test class
python -m pytest tests/test_router.py::TestRouterInit -v

# Run with coverage (if installed)
python -m pytest tests/ --cov=skillforge --cov-report=term-missing
```

### Writing Tests

- Every new feature or bug fix should include tests
- Place tests in `tests/` following the naming convention `test_<module>.py`
- Use `tmp_path` fixture for file-based tests (no shared state)
- Use `MagicMock` / `AsyncMock` for external dependencies (LLM, MCP, etc.)
- When testing with a router, override the permission manager to use a temp directory:
  ```python
  from skillforge.core.user_permissions import PermissionManager
  r._permission_manager = PermissionManager(data_dir=tmp_path / "perm_data")
  ```

### Test Coverage

The project currently has **989+ tests** covering:
- Core modules (router, sessions, handlers)
- All skill definitions
- Security modules (auth, webhooks, file access)
- UI components (Flet views and widgets)
- End-to-end integration (full message flow across 3 LLM providers)

## Pull Request Process

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes** following the style guide

3. **Write or update tests** — PRs without tests for new functionality will be asked to add them

4. **Run the full test suite** and ensure all tests pass:
   ```bash
   python -m pytest tests/ -v
   ```

5. **Update documentation**:
   - `CHANGELOG.md` — what changed and when
   - `docs/read_me_claude.md` — if project structure changed

6. **Push your branch** and open a Pull Request:
   ```bash
   git push origin feature/my-feature
   ```

7. **In the PR description**, include:
   - What the change does and why
   - How to test it
   - Any breaking changes
   - Related issue numbers

8. **Address review feedback** — maintainers may request changes before merging

### What to Expect

- PRs are typically reviewed within a few days
- Small, focused PRs are reviewed faster than large ones
- All PRs must pass the test suite before merging
- Maintainers may suggest improvements or alternative approaches

## License

By contributing to SkillForge, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

Thank you for helping make SkillForge better! Every contribution, no matter how small, makes a difference.
