#!/usr/bin/env python3
"""
SkillForge — AI assistant with persistent memory.

Usage:
    skillforge ui          Flet desktop UI
    skillforge gradio      Gradio web UI
    skillforge bot         MS Teams Flask server
    skillforge telegram    Telegram bot
    skillforge slack       Slack bot
    skillforge discord     Discord bot
    skillforge doctor      Check config, dependencies, and connections
"""
import sys


def _run_doctor():
    """Check config, dependencies, and connections."""
    from pathlib import Path
    from skillforge import PROJECT_ROOT

    print("SkillForge — Doctor")
    print("=" * 50)
    issues = []
    ok_count = 0

    # 1. Check config.py (can be at root or in config/)
    config_file = PROJECT_ROOT / "config.py"
    config_dir_file = PROJECT_ROOT / "config" / "config.py"
    if config_file.exists() or config_dir_file.exists():
        loc = "config.py" if config_file.exists() else "config/config.py"
        print(f"[OK] {loc} found")
        ok_count += 1
    else:
        print("[!!] config.py NOT found — copy config.example.py and fill in your keys")
        issues.append("Missing config.py")

    # 2. Check data directories
    for d in ["data", "data/sessions", "skills"]:
        p = PROJECT_ROOT / d
        if p.exists():
            print(f"[OK] {d}/ exists")
            ok_count += 1
        else:
            print(f"[!!] {d}/ missing")
            issues.append(f"Missing {d}/")

    # 3. Check core imports
    core_modules = [
        ("skillforge.core.router", "MessageRouter"),
        ("skillforge.core.sessions", "SessionManager"),
        ("skillforge.core.personality", "PersonalityManager"),
        ("skillforge.core.scheduler", "SchedulerManager"),
        ("skillforge.core.memory.sqlite_memory", "SQLiteMemory"),
    ]
    for module_path, class_name in core_modules:
        try:
            mod = __import__(module_path, fromlist=[class_name])
            getattr(mod, class_name)
            print(f"[OK] {module_path}.{class_name}")
            ok_count += 1
        except Exception as e:
            print(f"[!!] {module_path}.{class_name} — {e}")
            issues.append(f"Import failed: {module_path}")

    # 4. Check optional dependencies
    optional = {
        "flet": "UI (skillforge ui)",
        "gradio": "Gradio web UI",
        "telegram": "Telegram bot (python-telegram-bot)",
        "discord": "Discord bot",
        "slack_bolt": "Slack bot",
        "anthropic": "Anthropic provider",
        "google.generativeai": "Gemini provider",
    }
    for pkg, label in optional.items():
        try:
            __import__(pkg)
            print(f"[OK] {label}")
            ok_count += 1
        except ImportError:
            print(f"[--] {label} — not installed (optional)")

    # 5. Check LLM config
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        import config as cfg
        provider = getattr(cfg, "LLM_PROVIDER", None)
        if provider:
            print(f"[OK] LLM provider: {provider}")
            ok_count += 1
        else:
            print("[!!] LLM_PROVIDER not set in config.py")
            issues.append("LLM_PROVIDER not configured")
    except Exception:
        pass  # Already reported config.py missing

    # 6. Check skills
    skills_dir = PROJECT_ROOT / "skills"
    if skills_dir.exists():
        skill_count = sum(1 for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists())
        print(f"[OK] {skill_count} bundled skills found")
        ok_count += 1

    # Summary
    print()
    print("=" * 50)
    if issues:
        print(f"Found {len(issues)} issue(s):")
        for i in issues:
            print(f"  - {i}")
    else:
        print(f"All good! {ok_count} checks passed.")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(0)

    cmd = sys.argv[1]
    # Remove the subcommand so the target module sees clean argv
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if cmd == "ui":
        import flet as ft
        from skillforge.flet.app import main as app_main
        ft.app(target=app_main)

    elif cmd == "gradio":
        import runpy
        runpy.run_module("skillforge.gradio_ui", run_name="__main__")

    elif cmd == "bot":
        from skillforge.bot import main as bot_main
        bot_main()

    elif cmd == "telegram":
        import runpy
        runpy.run_module("skillforge.telegram_bot", run_name="__main__")

    elif cmd == "slack":
        import runpy
        runpy.run_module("skillforge.run_slack", run_name="__main__")

    elif cmd == "discord":
        import runpy
        runpy.run_module("skillforge.run_discord", run_name="__main__")

    elif cmd == "doctor":
        _run_doctor()

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
