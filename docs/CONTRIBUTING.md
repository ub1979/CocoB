# Contributing to SkillForge

Thank you for your interest in contributing to **SkillForge**! This document provides guidelines and instructions for contributing to this open-source project.

> 🤝 **Our Mission**: Making AI Useful for Everyone through open collaboration.

---

## 🌟 Ways to Contribute

### Code Contributions
- 🐛 **Bug fixes** - Fix issues reported by users
- ✨ **New features** - Add functionality to the bot
- 🚀 **Performance improvements** - Optimize existing code
- 🛡️ **Security enhancements** - Improve security measures

### Non-Code Contributions
- 📖 **Documentation** - Improve docs, add examples
- 🐛 **Bug reports** - Report issues with detailed information
- 💡 **Feature requests** - Suggest new features
- 🧪 **Testing** - Test new releases, report findings
- 🌍 **Translation** - Translate documentation to other languages

---

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/SkillForge.git
cd SkillForge

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL-OWNER/SkillForge.git
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest black flake8 mypy

# Copy config
cp config.example.py config.py
```

### 3. Create a Branch

```bash
# Pull latest changes
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

---

## 📝 Coding Standards

### Code Style

We follow **PEP 8** with some modifications:

```bash
# Format code with black
black .

# Check with flake8
flake8 . --max-line-length=100 --extend-ignore=E203,W503

# Type checking with mypy
mypy core/ --ignore-missing-imports
```

### Comment Style

We use a specific comment format for consistency:

```python
# =============================================================================
'''
    File Name : module.py
    
    Description : Brief description of the module
    
    Modifying it on YYYY-MM-DD
    
    Done by : Your Name
    
    Project : SkillForge - Persistent Memory AI Chatbot
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function function_name -> input_type to output_type
# =========================================================================
# =============================================================================
def function_name(param: str) -> str:
    # ==================================
    # Description of what this block does
    # ==================================
    if condition:
        pass
```

### Security Requirements

All contributions must:
- ✅ **Never use `shell=True`** in subprocess calls
- ✅ **Validate all user inputs** before processing
- ✅ **Use environment variables** for secrets, never hardcode
- ✅ **Add rate limiting** for new endpoints
- ✅ **Include security headers** for new routes

See [SECURITY.md](SECURITY.md) for detailed security guidelines.

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov-report=html

# Run specific test file
pytest tests/test_sessions.py

# Run with verbose output
pytest -v
```

### Writing Tests

```python
# tests/test_example.py
import pytest
from core.sessions import SessionManager

def test_session_creation():
    """Test that sessions are created correctly"""
    sm = SessionManager("/tmp/test_sessions")
    session_key = sm.get_session_key("test", "user-123")
    session = sm.get_or_create_session(session_key, "test", "user-123")
    
    assert session["channel"] == "test"
    assert session["userId"] == "user-123"
    assert "sessionId" in session
```

### Test Coverage

Aim for at least **80% code coverage** for new features.

---

## 📋 Pull Request Process

### 1. Before Submitting

- [ ] Code follows style guidelines (run `black` and `flake8`)
- [ ] All tests pass (`pytest`)
- [ ] New tests added for new features
- [ ] Documentation updated (if needed)
- [ ] Security review completed (see checklist below)
- [ ] Commit messages are clear and descriptive

### 2. Security Checklist

Before submitting PR, verify:
- [ ] No hardcoded API keys or credentials
- [ ] No `shell=True` in subprocess calls
- [ ] All user inputs are validated
- [ ] No SQL injection vulnerabilities (if applicable)
- [ ] No path traversal vulnerabilities
- [ ] Rate limiting considered for new endpoints

### 3. Submit Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create PR on GitHub with:
# - Clear title
# - Detailed description
# - Reference to related issues
```

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Security enhancement

## Testing
- [ ] Tests pass locally
- [ ] New tests added
- [ ] Manual testing completed

## Security Checklist
- [ ] No hardcoded secrets
- [ ] Input validation added
- [ ] No shell injection risks

## Related Issues
Fixes #123
```

### 4. Review Process

1. **Automated checks** must pass (CI/CD)
2. **Code review** by at least one maintainer
3. **Security review** for sensitive changes
4. **Merge** by maintainer once approved

---

## 🏷️ Commit Message Guidelines

Use conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Test changes
- `security`: Security fixes
- `chore`: Maintenance tasks

### Examples

```bash
feat(sessions): add input validation for session keys

fix(router): handle empty messages gracefully

docs(readme): update installation instructions

security(bot): replace shell commands with psutil
```

---

## 🐛 Reporting Bugs

### Before Reporting

- [ ] Search existing issues
- [ ] Check if it's already fixed in latest version
- [ ] Try to reproduce with minimal steps

### Bug Report Template

```markdown
**Description**
Clear description of the bug

**Steps to Reproduce**
1. Step one
2. Step two
3. Step three

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.11.0]
- Version: [e.g., 1.2.3]

**Logs**
```
Paste relevant logs here
```

**Additional Context**
Any other relevant information
```

---

## 💡 Feature Requests

### Feature Request Template

```markdown
**Feature Description**
Clear description of the proposed feature

**Use Case**
Why is this feature needed? Who would use it?

**Proposed Solution**
How should this feature work?

**Alternatives Considered**
Other approaches you've considered

**Additional Context**
Mockups, examples, or references
```

---

## 🏆 Recognition

Contributors will be:
- Listed in [CONTRIBUTORS.md](CONTRIBUTORS.md) (if created)
- Mentioned in release notes
- Credited in documentation (with permission)

---

## 📞 Getting Help

- **General questions**: GitHub Discussions
- **Bug reports**: GitHub Issues
- **Security issues**: security@idrak.ai (do not open public issues)
- **Direct contact**: Idrak AI Ltd Team

---

## 📜 Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the community

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Personal or political attacks
- Publishing others' private information

### Enforcement

Violations may result in:
1. Warning
2. Temporary ban
3. Permanent ban

---

## 🙏 Thank You!

Your contributions make SkillForge better for everyone. We appreciate your time and effort!

**Project**: SkillForge - Persistent Memory AI Chatbot  
**Organization**: Idrak AI Ltd  
**License**: Open Source - Safe Open Community Project  
**Mission**: Making AI Useful for Everyone

---

*Last updated: 2026-02-07*
