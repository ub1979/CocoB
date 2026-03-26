"""SkillForge — AI assistant with persistent memory."""

import sys
from pathlib import Path

__version__ = "1.0.0"

# Project root: src/skillforge/__init__.py → src/ → project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Add config/ to sys.path so `import config` works from anywhere
_config_dir = str(PROJECT_ROOT / "config")
if _config_dir not in sys.path:
    sys.path.insert(0, _config_dir)
