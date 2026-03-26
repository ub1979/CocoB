# =============================================================================
# test_cli.py — Unit tests for CLI entry point and doctor command
# =============================================================================

import pytest
import subprocess
import sys


class TestCLIEntryPoint:
    """Test skillforge CLI command."""

    def test_no_args_shows_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "skillforge"],
            capture_output=True, text=True
        )
        assert "skillforge ui" in result.stdout or "skillforge ui" in result.stderr
        assert "gradio" in (result.stdout + result.stderr)

    def test_unknown_command(self):
        result = subprocess.run(
            [sys.executable, "-m", "skillforge", "nonexistent"],
            capture_output=True, text=True
        )
        assert result.returncode != 0
        assert "Unknown command" in (result.stdout + result.stderr)

    def test_doctor_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "skillforge", "doctor"],
            capture_output=True, text=True
        )
        output = result.stdout + result.stderr
        assert "SkillForge" in output
        assert "Doctor" in output
        assert "[OK]" in output

    def test_doctor_checks_core_imports(self):
        result = subprocess.run(
            [sys.executable, "-m", "skillforge", "doctor"],
            capture_output=True, text=True
        )
        output = result.stdout + result.stderr
        assert "MessageRouter" in output
        assert "SessionManager" in output
        assert "SchedulerManager" in output

    def test_doctor_checks_skills(self):
        result = subprocess.run(
            [sys.executable, "-m", "skillforge", "doctor"],
            capture_output=True, text=True
        )
        output = result.stdout + result.stderr
        assert "bundled skills" in output


class TestCLIModule:
    """Test __main__.py module directly."""

    def test_main_importable(self):
        from skillforge.__main__ import main
        assert callable(main)

    def test_doctor_function_importable(self):
        from skillforge.__main__ import _run_doctor
        assert callable(_run_doctor)


class TestConsoleScript:
    """Test that skillforge console script is registered."""

    def test_skillforge_command_exists(self):
        result = subprocess.run(
            ["skillforge", "doctor"],
            capture_output=True, text=True
        )
        output = result.stdout + result.stderr
        assert "Doctor" in output
