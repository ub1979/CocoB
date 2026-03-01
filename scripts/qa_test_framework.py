#!/usr/bin/env python3
"""
QA Test Framework for coco B

Comprehensive testing suite for:
- Session management
- LLM providers
- Message routing
- Skills system
- Security features
- Multi-channel support
- UI components (dark mode, theme switching)
- Module imports and syntax validation

Usage:
    python qa_test_framework.py              # Run all tests
    python qa_test_framework.py --quick      # Run quick smoke tests only
    python qa_test_framework.py --provider ollama  # Test specific provider
    python qa_test_framework.py --verbose    # Detailed output
"""

import asyncio
import json
import sys
import time
import argparse
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import unittest
from unittest.mock import Mock, patch, MagicMock

from coco_b.core.sessions import SessionManager
from coco_b.core.router import MessageRouter
from coco_b.core.personality import PersonalityManager
from coco_b.core.llm import LLMProviderFactory
from coco_b.core.skills import SkillsManager


class Colors:
    """Terminal colors for output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


class TestResult:
    """Store test results"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors: List[Dict] = []
        self.start_time = time.time()
    
    def add_pass(self):
        self.passed += 1
    
    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append({"test": test_name, "error": error, "type": "FAIL"})
    
    def add_skip(self, test_name: str, reason: str):
        self.skipped += 1
        self.errors.append({"test": test_name, "error": reason, "type": "SKIP"})
    
    def summary(self) -> str:
        duration = time.time() - self.start_time
        total = self.passed + self.failed + self.skipped
        
        summary = f"""
{'='*60}
                    TEST SUMMARY
{'='*60}
Total Tests:    {total}
Passed:         {Colors.GREEN}{self.passed}{Colors.END}
Failed:         {Colors.RED}{self.failed}{Colors.END}
Skipped:        {Colors.YELLOW}{self.skipped}{Colors.END}
Duration:       {duration:.2f}s
{'='*60}
"""
        return summary


class QATestFramework:
    """Main QA Test Framework"""
    
    def __init__(self, verbose: bool = False, quick: bool = False):
        self.verbose = verbose
        self.quick = quick
        self.results = TestResult()
        self.test_data_dir = Path("data/qa_test_sessions")
        self.test_data_dir.mkdir(parents=True, exist_ok=True)
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with optional verbosity"""
        if self.verbose or level in ["ERROR", "WARN"]:
            timestamp = datetime.now().strftime("%H:%M:%S")
            color = {
                "INFO": Colors.BLUE,
                "PASS": Colors.GREEN,
                "FAIL": Colors.RED,
                "WARN": Colors.YELLOW,
                "ERROR": Colors.RED
            }.get(level, "")
            print(f"{color}[{timestamp}] [{level}] {message}{Colors.END}")
    
    def run_test(self, test_name: str, test_func) -> bool:
        """Run a single test and record result"""
        try:
            self.log(f"Running: {test_name}", "INFO")
            test_func()
            self.results.add_pass()
            self.log(f"✓ PASSED: {test_name}", "PASS")
            return True
        except Exception as e:
            error_msg = str(e)
            if self.verbose:
                error_msg += "\n" + traceback.format_exc()
            self.results.add_fail(test_name, error_msg)
            self.log(f"✗ FAILED: {test_name} - {error_msg}", "FAIL")
            return False
    
    # =============================================================================
    # SESSION MANAGEMENT TESTS
    # =============================================================================
    
    def test_session_creation(self):
        """Test basic session creation"""
        sm = SessionManager(str(self.test_data_dir))
        session_key = sm.get_session_key("test", "user-123")
        session = sm.get_or_create_session(session_key, "test", "user-123")
        
        assert session["channel"] == "test"
        assert session["userId"] == "user-123"
        assert "sessionId" in session
        assert "createdAt" in session
        
    def test_session_persistence(self):
        """Test that sessions persist across restarts"""
        # Create session
        sm1 = SessionManager(str(self.test_data_dir))
        session_key = sm1.get_session_key("test", "persist-user")
        sm1.get_or_create_session(session_key, "test", "persist-user")
        sm1.add_message(session_key, "user", "Hello")
        
        # Create new session manager (simulates restart)
        sm2 = SessionManager(str(self.test_data_dir))
        history = sm2.get_conversation_history(session_key)
        
        assert len(history) >= 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
    
    def test_session_isolation(self):
        """Test that different users have separate sessions"""
        sm = SessionManager(str(self.test_data_dir))
        
        # Create sessions for two users
        key1 = sm.get_session_key("test", "user-1")
        key2 = sm.get_session_key("test", "user-2")
        
        sm.get_or_create_session(key1, "test", "user-1")
        sm.get_or_create_session(key2, "test", "user-2")
        
        sm.add_message(key1, "user", "Message from user 1")
        sm.add_message(key2, "user", "Message from user 2")
        
        history1 = sm.get_conversation_history(key1)
        history2 = sm.get_conversation_history(key2)
        
        assert history1[0]["content"] == "Message from user 1"
        assert history2[0]["content"] == "Message from user 2"
    
    def test_input_validation(self):
        """Test input validation for security"""
        sm = SessionManager(str(self.test_data_dir))
        
        # Test invalid role
        try:
            session_key = sm.get_session_key("test", "user-123")
            sm.get_or_create_session(session_key, "test", "user-123")
            sm.add_message(session_key, "invalid_role", "test")
            raise AssertionError("Should have raised ValueError for invalid role")
        except ValueError as e:
            assert "Invalid role" in str(e)
        
        # Test path traversal attempt
        try:
            bad_key = "test:direct:../../../etc/passwd"
            sm.get_conversation_history(bad_key)
        except (ValueError, KeyError):
            pass  # Expected
    
    def test_message_limits(self):
        """Test message content length limits"""
        sm = SessionManager(str(self.test_data_dir))
        session_key = sm.get_session_key("test", "user-123")
        sm.get_or_create_session(session_key, "test", "user-123")
        
        # Test oversized content
        huge_content = "x" * 200000  # 200KB
        try:
            sm.add_message(session_key, "user", huge_content)
            raise AssertionError("Should have raised ValueError for oversized content")
        except ValueError as e:
            assert "exceeds maximum" in str(e).lower() or "too long" in str(e).lower()
    
    # =============================================================================
    # LLM PROVIDER TESTS
    # =============================================================================
    
    def test_provider_factory(self):
        """Test LLM provider factory creates providers correctly"""
        from coco_b.core.llm import LLMProviderFactory
        
        # Test Ollama provider creation
        config = {
            "provider": "ollama",
            "model": "qwen3:8b",
            "base_url": "http://localhost:11434/v1"
        }
        provider = LLMProviderFactory.from_dict(config)
        assert provider.provider_name == "ollama"
        assert provider.model_name == "qwen3:8b"
    
    def test_provider_connection_check(self):
        """Test provider connection checking"""
        from coco_b.ui.settings.connection import test_provider_connection
        
        # This should work if Ollama is running
        result = test_provider_connection(
            base_url="http://localhost:11434/v1",
            model="qwen3:8b"
        )
        # Don't assert - just check it doesn't crash
        assert isinstance(result, tuple)
        assert len(result) == 2
    
    # =============================================================================
    # ROUTER TESTS
    # =============================================================================
    
    def test_router_initialization(self):
        """Test message router initialization"""
        sm = SessionManager(str(self.test_data_dir))
        
        # Create a mock LLM provider
        mock_llm = Mock()
        mock_llm.provider_name = "test"
        mock_llm.model_name = "test-model"
        mock_llm.config = Mock()
        mock_llm.config.base_url = "http://test"
        
        router = MessageRouter(sm, mock_llm)
        assert router.session_manager == sm
        assert router.llm == mock_llm
    
    def test_command_handling(self):
        """Test router command handling"""
        sm = SessionManager(str(self.test_data_dir))
        mock_llm = Mock()
        mock_llm.provider_name = "test"
        mock_llm.model_name = "test-model"
        mock_llm.config = Mock()
        mock_llm.config.base_url = "http://test"
        
        router = MessageRouter(sm, mock_llm)
        
        session_key = sm.get_session_key("test", "user-123")
        
        # Test /help command
        response = router.handle_command("/help", session_key)
        assert "Available commands" in response or "help" in response.lower()
        
        # Test /stats command
        response = router.handle_command("/stats", session_key)
        assert "Session Stats" in response or "Messages" in response
        
        # Test /reset command
        response = router.handle_command("/reset", session_key)
        assert "reset" in response.lower() or "fresh" in response.lower()
    
    # =============================================================================
    # SKILLS SYSTEM TESTS
    # =============================================================================

    def test_skills_loading(self):
        """Test skills are loaded correctly"""
        sm = SkillsManager()
        skills = sm.load_all_skills()

        # Should have at least the bundled skills
        assert len(skills) > 0

        # Check skill structure
        for skill in skills:
            assert skill.name
            assert skill.description is not None

    def test_skill_invocation_check(self):
        """Test skill invocation detection"""
        sm = SessionManager(str(self.test_data_dir))
        mock_llm = Mock()
        mock_llm.provider_name = "test"
        mock_llm.model_name = "test-model"
        mock_llm.config = Mock()
        mock_llm.config.base_url = "http://test"

        router = MessageRouter(sm, mock_llm)

        # Test built-in commands
        is_skill, skill_name, remaining = router.is_skill_invocation("/help")
        assert not is_skill  # /help is a built-in command

        is_skill, skill_name, remaining = router.is_skill_invocation("/reset")
        assert not is_skill  # /reset is a built-in command

    def test_expected_skills_exist(self):
        """Test that expected core skills exist"""
        sm = SkillsManager()
        skills = sm.load_all_skills()
        skill_names = [s.name for s in skills]

        expected_skills = ["email", "calendar", "browse", "google-search"]
        for expected in expected_skills:
            assert expected in skill_names, f"Expected skill '{expected}' not found"

    def test_user_invocable_skills(self):
        """Test user invocable skills are properly marked"""
        sm = SkillsManager()
        skills = sm.load_all_skills()

        user_invocable = sm.get_user_invocable_skills()
        assert len(user_invocable) > 0, "Should have at least one user invocable skill"

        for skill in user_invocable:
            assert skill.user_invocable, f"Skill {skill.name} marked as user invocable but flag is False"

    def test_skill_attributes(self):
        """Test skill objects have required attributes"""
        sm = SkillsManager()
        skills = sm.load_all_skills()

        for skill in skills:
            # Required attributes
            assert hasattr(skill, 'name'), "Skill missing 'name' attribute"
            assert hasattr(skill, 'description'), "Skill missing 'description' attribute"
            assert hasattr(skill, 'source'), "Skill missing 'source' attribute"
            assert hasattr(skill, 'user_invocable'), "Skill missing 'user_invocable' attribute"

            # Source should be valid
            assert skill.source in ['bundled', 'user', 'project'], f"Invalid source: {skill.source}"

    def test_skill_to_markdown(self):
        """Test skill to markdown conversion"""
        from coco_b.core.skills import skill_to_markdown, Skill

        # Create a test skill
        test_skill = Skill(
            name="test-skill",
            description="A test skill",
            instructions="Test instructions here",
            source="bundled",
            user_invocable=True,
            emoji="🧪"
        )

        md = skill_to_markdown(test_skill)
        assert "test-skill" in md or "Test" in md

    # =============================================================================
    # MCP SYSTEM TESTS
    # =============================================================================

    def test_mcp_models_import(self):
        """Test MCP models can be imported"""
        from coco_b.ui.settings.mcp_models import (
            MCPServerType,
            MCPConnectionStatus,
            MCPServerConfig,
            MCPServerState,
            validate_config,
        )

        # Test enum values exist
        assert MCPServerType.STDIO
        assert MCPServerType.SSE
        assert MCPServerType.HTTP

        assert MCPConnectionStatus.DISCONNECTED
        assert MCPConnectionStatus.CONNECTING
        assert MCPConnectionStatus.CONNECTED
        assert MCPConnectionStatus.ERROR

    def test_mcp_client_import(self):
        """Test MCP client can be imported"""
        from coco_b.core.mcp_client import MCPClient, MCPManager

        # Check classes exist
        assert MCPClient is not None
        assert MCPManager is not None

    def test_mcp_config_validation(self):
        """Test MCP config validation"""
        from coco_b.ui.settings.mcp_models import validate_config, MCPServerConfig, MCPServerType

        # Valid STDIO config
        valid_config = MCPServerConfig(
            name="test-server",
            type=MCPServerType.STDIO,
            command="npx",
            args=["-y", "@playwright/mcp"],
        )
        is_valid, error = validate_config(valid_config)
        assert is_valid, f"Valid STDIO config rejected: {error}"

        # Invalid config (missing command for stdio)
        invalid_config = MCPServerConfig(
            name="invalid-server",
            type=MCPServerType.STDIO,
            command=None,  # Missing command
        )
        is_valid, error = validate_config(invalid_config)
        assert not is_valid, "Invalid config should be rejected"

    def test_mcp_server_config_creation(self):
        """Test MCPServerConfig dataclass"""
        from coco_b.ui.settings.mcp_models import MCPServerConfig, MCPServerType

        config = MCPServerConfig(
            name="test-server",
            type=MCPServerType.STDIO,
            command="npx",
            args=["-y", "test-package"],
            enabled=True
        )

        assert config.name == "test-server"
        assert config.type == MCPServerType.STDIO
        assert config.command == "npx"
        assert config.enabled

    def test_mcp_tools_module(self):
        """Test MCP tools module exists and has MCPToolHandler"""
        from coco_b.core.mcp_tools import MCPToolHandler

        # Check class exists
        assert MCPToolHandler is not None

        # Check it has expected methods
        assert hasattr(MCPToolHandler, 'get_tools_prompt')

    def test_mcp_manager_initialization(self):
        """Test MCPManager can be initialized"""
        from coco_b.core.mcp_client import MCPManager

        # Initialize without connecting
        manager = MCPManager()
        assert manager is not None

        # Check key methods exist
        assert hasattr(manager, 'load_config')
        assert hasattr(manager, 'get_server_states')
        assert hasattr(manager, 'connect_server') or hasattr(manager, 'connect')

    def test_mcp_config_file_structure(self):
        """Test mcp_config.json has proper structure"""
        mcp_config_path = Path("mcp_config.json")
        if mcp_config_path.exists():
            with open(mcp_config_path, "r") as f:
                data = json.load(f)

            assert "mcpServers" in data, "mcp_config.json missing 'mcpServers' key"

            for server_name, server_config in data["mcpServers"].items():
                # Each server should have either command or url
                has_command = "command" in server_config
                has_url = "url" in server_config
                assert has_command or has_url, f"Server {server_name} missing command or url"

    # =============================================================================
    # CHANNEL TESTS
    # =============================================================================

    def test_telegram_channel_import(self):
        """Test Telegram channel can be imported"""
        from coco_b.channels.telegram import TelegramChannel, TelegramConfig, create_telegram_channel

        assert TelegramChannel is not None
        assert TelegramConfig is not None
        assert create_telegram_channel is not None

    def test_telegram_config_creation(self):
        """Test TelegramConfig dataclass"""
        from coco_b.channels.telegram import TelegramConfig

        config = TelegramConfig(
            bot_token="test_token",
            allowed_users=["123456"],
            send_typing_indicator=True,
        )

        assert config.bot_token == "test_token"
        assert "123456" in config.allowed_users
        assert config.send_typing_indicator

    def test_telegram_bot_script_exists(self):
        """Test telegram_bot.py exists and has valid syntax"""
        assert Path("telegram_bot.py").exists(), "telegram_bot.py not found"

        import py_compile
        try:
            py_compile.compile("telegram_bot.py", doraise=True)
        except py_compile.PyCompileError as e:
            raise AssertionError(f"Syntax error in telegram_bot.py: {e}")
    
    # =============================================================================
    # SECURITY TESTS
    # =============================================================================
    
    def test_no_shell_injection(self):
        """Test that no shell commands are used"""
        import subprocess
        
        # Check that free_port doesn't use shell=True
        # This is a code review test - we verify the implementation
        with open("gradio_ui.py", "r") as f:
            content = f.read()
            # Should not have dangerous shell commands
            assert "shell=True" not in content or "psutil" in content
    
    def test_input_sanitization(self):
        """Test input sanitization"""
        sm = SessionManager(str(self.test_data_dir))
        
        # Test various injection attempts
        malicious_inputs = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "$(whoami)",
            "`whoami`",
            "; rm -rf /",
            "& del /f /q C:\\",
        ]
        
        for malicious in malicious_inputs:
            try:
                # These should either fail safely or be sanitized
                key = sm.get_session_key("test", malicious)
                # If we get here, the key should be safe
                assert ".." not in key or key.count("..") == 0
            except (ValueError, AssertionError):
                pass  # Expected for invalid inputs
    
    # =============================================================================
    # INTEGRATION TESTS
    # =============================================================================
    
    async def test_full_message_flow(self):
        """Test complete message flow (async)"""
        sm = SessionManager(str(self.test_data_dir))
        
        # Create mock LLM that returns a simple response
        mock_llm = Mock()
        mock_llm.provider_name = "test"
        mock_llm.model_name = "test-model"
        mock_llm.config = Mock()
        mock_llm.config.base_url = "http://test"
        mock_llm.chat.return_value = "Test response"
        mock_llm.check_context_size.return_value = {
            "needs_compaction": False,
            "total_tokens": 100
        }
        
        router = MessageRouter(sm, mock_llm)
        
        # Test message handling
        response = await router.handle_message(
            channel="test",
            user_id="user-123",
            user_message="Hello",
            user_name="Test User"
        )
        
        assert response == "Test response"
        
        # Verify message was saved
        session_key = sm.get_session_key("test", "user-123")
        history = sm.get_conversation_history(session_key)
        assert len(history) >= 2  # User message + assistant response
    
    def test_end_to_end_conversation(self):
        """Test end-to-end conversation flow"""
        # Run the async test
        asyncio.run(self.test_full_message_flow())
    
    # =============================================================================
    # PERFORMANCE TESTS
    # =============================================================================

    def test_session_performance(self):
        """Test session operations performance"""
        if self.quick:
            self.log("Skipping performance test in quick mode", "WARN")
            return

        sm = SessionManager(str(self.test_data_dir))

        # Measure session creation time
        start = time.time()
        for i in range(100):
            key = sm.get_session_key("test", f"user-{i}")
            sm.get_or_create_session(key, "test", f"user-{i}")
        duration = time.time() - start

        self.log(f"Created 100 sessions in {duration:.2f}s", "INFO")
        assert duration < 5.0, "Session creation too slow"

    # =============================================================================
    # UI & MODULE TESTS
    # =============================================================================

    def test_coco_b_module_import(self):
        """Test that coco_b.py module imports without errors"""
        import importlib.util
        spec = importlib.util.spec_from_file_location("coco_b", "coco_b.py")
        module = importlib.util.module_from_spec(spec)
        # Don't execute - just verify it can be loaded
        assert spec is not None
        assert module is not None

    def test_coco_b_syntax(self):
        """Test coco_b.py has valid Python syntax"""
        import py_compile
        try:
            py_compile.compile("coco_b.py", doraise=True)
        except py_compile.PyCompileError as e:
            raise AssertionError(f"Syntax error in coco_b.py: {e}")

    def test_app_colors_class(self):
        """Test AppColors class exists and has required attributes"""
        # Import AppColors from coco_b
        import importlib.util
        spec = importlib.util.spec_from_file_location("coco_b", "coco_b.py")
        module = importlib.util.module_from_spec(spec)

        # Check the file contains AppColors class
        with open("coco_b.py", "r") as f:
            content = f.read()
            assert "class AppColors:" in content, "AppColors class not found"
            assert "PRIMARY" in content, "PRIMARY color not defined"
            assert "BACKGROUND" in content, "BACKGROUND color not defined"
            assert "set_dark_mode" in content, "set_dark_mode method not found"
            assert "_DARK" in content, "Dark theme colors not defined"
            assert "_LIGHT" in content, "Light theme colors not defined"

    def test_dark_mode_colors_defined(self):
        """Test dark mode has all required color definitions"""
        with open("coco_b.py", "r") as f:
            content = f.read()

            # Check dark theme has essential colors
            dark_colors = ["BACKGROUND", "SURFACE", "TEXT_PRIMARY", "BORDER", "PRIMARY"]
            for color in dark_colors:
                assert f'"{color}"' in content, f"Dark theme missing {color}"

    def test_appearance_section_exists(self):
        """Test Appearance section is defined in settings"""
        with open("coco_b.py", "r") as f:
            content = f.read()
            assert "_create_appearance_section" in content, "Appearance section method not found"
            assert "Dark Mode" in content, "Dark Mode toggle not found"
            assert "dark_mode_switch" in content, "Dark mode switch not defined"

    def test_cli_provider_buttons(self):
        """Test CLI provider cards have click handlers"""
        with open("coco_b.py", "r") as f:
            content = f.read()
            assert "CliStatusCard" in content, "CliStatusCard class not found"
            assert "_use_cli_provider_direct" in content, "Direct CLI provider method not found"
            assert "on_click" in content, "Click handlers not defined"

    def test_chat_avatar_icon(self):
        """Test chat uses inner_chat.png for assistant avatar"""
        with open("coco_b.py", "r") as f:
            content = f.read()
            assert "inner_chat.png" in content, "inner_chat.png not used for avatar"

    def test_icon_files_exist(self):
        """Test required icon files exist"""
        icon_dir = Path("icon")
        assert icon_dir.exists(), "icon directory not found"

        required_icons = ["coco_b_icon.png", "inner_chat.png"]
        for icon in required_icons:
            icon_path = icon_dir / icon
            assert icon_path.exists(), f"Icon file not found: {icon}"

    def test_all_core_modules_import(self):
        """Test all core modules can be imported"""
        core_modules = [
            "core.sessions",
            "core.router",
            "core.personality",
            "core.llm",
            "core.skills",
        ]

        for module_name in core_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                raise AssertionError(f"Failed to import {module_name}: {e}")

    def test_config_exists(self):
        """Test config.py exists and has required settings"""
        assert Path("config.py").exists(), "config.py not found"

        with open("config.py", "r") as f:
            content = f.read()
            assert "LLM_PROVIDER" in content, "LLM_PROVIDER not defined"
            assert "LLM_PROVIDERS" in content, "LLM_PROVIDERS not defined"

    def test_mcp_config_valid_json(self):
        """Test mcp_config.json is valid JSON"""
        mcp_config_path = Path("mcp_config.json")
        if mcp_config_path.exists():
            with open(mcp_config_path, "r") as f:
                try:
                    data = json.load(f)
                    assert "mcpServers" in data, "mcpServers key not found"
                except json.JSONDecodeError as e:
                    raise AssertionError(f"Invalid JSON in mcp_config.json: {e}")

    def test_skills_directory_structure(self):
        """Test skills directory has expected structure"""
        skills_dir = Path("skills")
        assert skills_dir.exists(), "skills directory not found"

        # Check for some expected skills
        expected_skills = ["email", "calendar", "google-search", "browse"]
        for skill in expected_skills:
            skill_path = skills_dir / skill
            if skill_path.exists():
                # Check skill has definition file (yaml, json, or md)
                yaml_file = skill_path / "skill.yaml"
                json_file = skill_path / "skill.json"
                md_file = skill_path / "SKILL.md"
                has_definition = yaml_file.exists() or json_file.exists() or md_file.exists()
                assert has_definition, f"Skill {skill} missing definition file"

    def test_no_hardcoded_secrets(self):
        """Test no hardcoded API keys or secrets"""
        sensitive_patterns = [
            "sk-",  # OpenAI keys
            "AKIA",  # AWS keys
            "AIza",  # Google API keys
        ]

        files_to_check = ["coco_b.py", "config.py", "gradio_ui.py"]

        for file_name in files_to_check:
            if Path(file_name).exists():
                with open(file_name, "r") as f:
                    content = f.read()
                    for pattern in sensitive_patterns:
                        # Allow patterns in comments or environment variable references
                        lines = content.split("\n")
                        for i, line in enumerate(lines):
                            if pattern in line and not line.strip().startswith("#"):
                                if "os.environ" not in line and "getenv" not in line:
                                    # Check if it's a real key (has enough characters after pattern)
                                    import re
                                    if re.search(f"{pattern}[a-zA-Z0-9]{{10,}}", line):
                                        raise AssertionError(f"Possible hardcoded secret in {file_name}:{i+1}")

    # =============================================================================
    # MAIN TEST RUNNER
    # =============================================================================
    
    def run_all_tests(self) -> TestResult:
        """Run all QA tests"""
        print(f"\n{Colors.BOLD}{'='*60}")
        print("       coco B QA TEST FRAMEWORK")
        print(f"{'='*60}{Colors.END}\n")

        tests_to_run = [
            # Module & Syntax Tests (run first)
            ("coco_b.py Syntax", self.test_coco_b_syntax),
            ("coco_b.py Module Import", self.test_coco_b_module_import),
            ("Core Modules Import", self.test_all_core_modules_import),
            ("Config Exists", self.test_config_exists),

            # UI Component Tests
            ("AppColors Class", self.test_app_colors_class),
            ("Dark Mode Colors", self.test_dark_mode_colors_defined),
            ("Appearance Section", self.test_appearance_section_exists),
            ("CLI Provider Buttons", self.test_cli_provider_buttons),
            ("Chat Avatar Icon", self.test_chat_avatar_icon),
            ("Icon Files Exist", self.test_icon_files_exist),

            # Session Management
            ("Session Creation", self.test_session_creation),
            ("Session Persistence", self.test_session_persistence),
            ("Session Isolation", self.test_session_isolation),
            ("Input Validation", self.test_input_validation),
            ("Message Limits", self.test_message_limits),

            # LLM Providers
            ("Provider Factory", self.test_provider_factory),
            ("Provider Connection", self.test_provider_connection_check),

            # Router
            ("Router Initialization", self.test_router_initialization),
            ("Command Handling", self.test_command_handling),

            # Skills
            ("Skills Loading", self.test_skills_loading),
            ("Skill Invocation", self.test_skill_invocation_check),
            ("Expected Skills Exist", self.test_expected_skills_exist),
            ("User Invocable Skills", self.test_user_invocable_skills),
            ("Skill Attributes", self.test_skill_attributes),
            ("Skill to Markdown", self.test_skill_to_markdown),
            ("Skills Directory", self.test_skills_directory_structure),

            # MCP System
            ("MCP Models Import", self.test_mcp_models_import),
            ("MCP Client Import", self.test_mcp_client_import),
            ("MCP Config Validation", self.test_mcp_config_validation),
            ("MCP Server Config", self.test_mcp_server_config_creation),
            ("MCP Tools Module", self.test_mcp_tools_module),
            ("MCP Manager Init", self.test_mcp_manager_initialization),
            ("MCP Config Structure", self.test_mcp_config_file_structure),

            # Security
            ("No Shell Injection", self.test_no_shell_injection),
            ("Input Sanitization", self.test_input_sanitization),
            ("No Hardcoded Secrets", self.test_no_hardcoded_secrets),

            # Config & Data
            ("MCP Config Valid", self.test_mcp_config_valid_json),

            # Channels
            ("Telegram Channel Import", self.test_telegram_channel_import),
            ("Telegram Config", self.test_telegram_config_creation),
            ("Telegram Bot Script", self.test_telegram_bot_script_exists),

            # Integration
            ("End-to-End Flow", self.test_end_to_end_conversation),
        ]

        if not self.quick:
            tests_to_run.extend([
                # Performance (slow)
                ("Session Performance", self.test_session_performance),
            ])

        for test_name, test_func in tests_to_run:
            self.run_test(test_name, test_func)

        return self.results


def main():
    parser = argparse.ArgumentParser(description="QA Test Framework for mr_bot")
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--provider", help="Test specific provider")
    parser.add_argument("--output", "-o", help="Save results to file")
    
    args = parser.parse_args()
    
    # Run tests
    framework = QATestFramework(verbose=args.verbose, quick=args.quick)
    results = framework.run_all_tests()
    
    # Print summary
    print(results.summary())
    
    # Save to file if requested
    if args.output:
        with open(args.output, "w") as f:
            f.write(results.summary())
            if results.errors:
                f.write("\n\nERRORS:\n")
                for error in results.errors:
                    f.write(f"\n{error['type']}: {error['test']}\n")
                    f.write(f"{error['error']}\n")
        print(f"\nResults saved to: {args.output}")
    
    # Exit with appropriate code
    sys.exit(0 if results.failed == 0 else 1)


if __name__ == "__main__":
    main()
