# SkillForge QA & Testing Playbook

> The go-to reference when running tests, adding tests, or figuring out what to
> test after a code change.

---

## Quick Reference

```bash
# Run the full suite
pytest

# Run a single file
pytest tests/test_router.py

# Run a single class
pytest tests/test_router.py::TestCommands

# Run a single test
pytest tests/test_router.py::TestCommands::test_help_command

# Run with verbose output
pytest -v

# Run with short traceback
pytest --tb=short

# Run only tests matching a keyword
pytest -k "permission"

# Run only async tests
pytest -k "async"

# Show print output (disable capture)
pytest -s

# Stop on first failure
pytest -x

# Run last-failed only
pytest --lf

# Run with coverage (if pytest-cov installed)
pytest --cov=skillforge --cov-report=term-missing
```

### pytest Configuration

Defined in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- **asyncio_mode = "auto"**: async test functions are detected automatically;
  you do not need to add `@pytest.mark.asyncio` (though existing tests still
  carry the decorator for clarity).

### Required Test Dependencies

- `pytest`
- `pytest-asyncio`
- `httpx` (used in web_tools tests)

---

## Test Inventory

**37 test files | ~1 164 test methods | ~14 636 lines of test code**

### 1. Router & Message Handling

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_router.py` | `TestRouterInit`, `TestSetSchedulerManager`, `TestSkillInvocation`, `TestCommands`, `TestSetPassword`, `TestUnlock`, `TestHandleMessageTodoIntegration` | 32 | Core MessageRouter: init, commands (/help, /think, /persona, /memory), skill detection, password flow, todo integration |
| `test_integration_chat.py` | `TestNormalConversation`, `TestSkillInvocation`, `TestCommandHandling`, `TestStreamingResponse`, `TestContextCompaction`, `TestMultiTurnSession`, `TestMemoryExtraction`, `TestAuthCommands`, `TestHeartbeatCommands`, `TestPatternCommands`, `TestTaskCommands`, `TestMCPCommands`, `TestSkillCreationViaChat`, `TestMCPServerManagement`, `TestDirectSkillExecution`, `TestSchedulerIntegration`, `TestHeartbeatIntegration` | 88 | End-to-end chat flow parametrized across 3 LLM providers (ollama, claude-cli, gemini-cli) |
| `test_think_levels.py` | `TestThinkLevelConstants`, `TestThinkCommand`, `TestThinkInSkillList`, `TestThinkTemperatureInjection`, `TestThinkingModelCodeBlockExtraction` | 26 | /think command, temperature levels, code-block extraction from reasoning field |

### 2. LLM Providers & Vision

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_claude_cli.py` | `TestFormatMessages`, `TestSessionPersistence`, `TestBuildCommand` | 11 | Claude CLI provider message formatting, session file management, command building |
| `test_vision_providers.py` | `TestBaseProvider`, `TestOpenAICompatVision`, `TestAnthropicVision`, `TestGeminiVision`, `TestClaudeCLIVision`, `TestGeminiCLIVision`, `TestLlamaCppVision`, `TestVisionEdgeCases`, `TestImageHandlerInVisionFlow` | 36 | Vision/image support across all LLM providers, minimal valid PNG/JPEG creation |

### 3. Image Handling & Generation

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_image_handler.py` | `TestAttachment`, `TestConstants`, `TestMagicByteValidation`, `TestFileValidation`, `TestFilenameSanitization`, `TestStoreImage`, `TestGetImagesForSession`, `TestBase64Encoding`, `TestCleanupEviction`, `TestConvenienceFunction`, `TestHandlerInit`, `TestEdgeCases` | 97 | Attachment model, magic-byte validation, file storage, base64 encoding, eviction, sanitization |
| `test_image_gen_handler.py` | `TestHasImageGenCommands`, `TestParseBlock`, `TestExtractCommands`, `TestExecuteCommandsNoMCP`, `TestExecuteCommandsWithMCP`, `TestTryMCPGeneration`, `TestFormatResponse`, `TestFormatResults`, `TestSetMCPManager`, `TestConvenienceFunction`, `TestPatternConstants`, `TestEdgeCases` | 67 | Image generation code-block detection, MCP delegation, pattern constants |
| `test_router_image_integration.py` | `TestRouterImageInit`, `TestBackwardCompatibility`, `TestAttachmentStorage`, `TestVisionFormatting`, `TestNonVisionFallback`, `TestPermissionGating`, `TestJSONLAttachmentRecording`, `TestSessionHistoryAttachments`, `TestStreamingWithAttachments` | 20 | Router-level vision integration, attachment recording in JSONL history |

### 4. Channel Integrations

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_channel_images.py` | `TestTelegramPhotoHandler`, `TestTelegramDocumentImageHandler`, `TestTelegramProcessMessageAttachments`, `TestWhatsAppImageWebhook`, `TestChatMessageWithAttachments`, `TestTelegramHandlerRegistration`, `TestAttachmentIntegration` | 22 | Inbound image handling for Telegram (photos + documents) and WhatsApp |
| `test_channel_outbound.py` | `TestExtractOutboundImages`, `TestTelegramSendImage`, `TestTelegramOutboundIntegration`, `TestWhatsAppSendImage`, `TestWhatsAppOutboundIntegration`, `TestFletOutboundImages`, `TestBackwardCompatibility`, `TestMixedContent` | 36 | Outbound image delivery across Telegram, WhatsApp, and Flet UI |

### 5. Permissions, Auth & Security

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_user_permissions.py` | `TestBackwardCompat`, `TestEnums`, `TestDefaultRoles`, `TestGetRole`, `TestSetRole`, `TestGrantRevoke`, `TestRemoveUser`, `TestGetAllUsers`, `TestPermittedCapabilities`, `TestPersistenceRoundTrip`, `TestEdgeCases`, `TestRouterIntegration`, `TestRouterCommands` | 64 | PermissionManager RBAC, role hierarchy, capability checks, JSON persistence, router /role commands |
| `test_auth_manager.py` | `TestSecurityLevel`, `TestAuthSession`, `TestAuthManagerSetup`, `TestAuthManagerVerification`, `TestAuthManagerSessions`, `TestAuthManagerAccessControl`, `TestAuthManagerPersistence`, `TestAuthManagerUtilities` | 42 | Auth sessions, password hashing, security levels, access control, persistence |
| `test_permission_requests.py` | `TestPermissionRequests` | 9 | Permission request queue: submit, approve, deny, list |
| `test_admin_login.py` | `TestAdminCredentials` | 6 | SecureStorage admin credential management |
| `test_webhook_security.py` | `TestWebhookSecurityError`, `TestVerifyWhatsAppSignature`, `TestVerifyTelegramSecret`, `TestVerifySlackSignature`, `TestVerifyMSTeamsToken`, `TestEnvironmentFunctions` | 35 | Webhook signature verification for WhatsApp, Telegram, Slack, MS Teams; env var helpers |
| `test_file_access.py` | `TestPasswordManagement`, `TestSandbox`, `TestFileOps`, `TestPendingActions` | 29 | FileAccessManager sandboxing, password management, file operations |
| `test_file_access_timing.py` | `TestFileAccessTimingAttack` | 7 | Timing-attack resistance in password verification (constant-time compare) |
| `test_mcp_security.py` | `TestMCPConstants`, `TestValidateMCPCommand` | 32 | MCP command validation, blocked commands, subprocess isolation |
| `test_identity_resolver.py` | `TestIdentityResolver` | 8 | Cross-platform identity link/unlink/resolve |

### 6. Memory & Persistence

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_sqlite_wal_mode.py` | `TestSQLiteWALMode` | 5 | WAL mode enabled, synchronous setting, table creation, .wal/.shm files, concurrent access |
| `test_sqlite_timeout.py` | `TestSQLiteTimeout` | 4 | busy_timeout=30000, concurrent access, row_factory |
| `test_session_key_namespace.py` | `TestSessionKeyNamespace` | 7 | Session key generation and namespacing |

### 7. Skills & ClawHub

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_skills_loading.py` | `TestSkillFiles`, `TestSkillsManager` | 7 | SKILL.md file parsing, emoji field, find_skill_files, parametrized x15 expected skills |
| `test_auto_skill_creation.py` | `TestGetAutoSkillPrompt`, `TestMarkAutoSkillPattern`, `TestIntegrationAutoSkillFlow` | 22 | PatternDetector.get_auto_skill_prompt() thresholds, marking patterns, integration flow |
| `test_clawhub.py` | `TestOpenClawFormatAdapter`, `TestSkillNewFields`, `TestClawHubCaching`, `TestClawHubSearch`, `TestClawHubSkillInfo`, `TestClawHubInstall`, `TestClawHubListInstalled`, `TestClawHubUpdates`, `TestClawHubRequirements`, `TestClawHubTracking`, `TestClawHubRouterIntegration`, `TestClawHubZipExtraction` | 70 | ClawHub registry: search, install, update, caching, zip extraction, router integration |

### 8. Scheduling & Background Tasks

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_schedule_handler.py` | `TestDetection`, `TestParsing`, `TestExecuteWithoutManager`, `TestFormatResults`, `TestNewFieldParsing`, `TestParseInterval`, `TestHandlerCreateNewKinds`, `TestDeleteByName`, `TestDeleteAll` | 34 | Schedule code-block detection, interval parsing, CRUD operations |
| `test_scheduler.py` | `TestScheduledTask`, `TestHumanReadable`, `TestMultiTrigger`, `TestRetryBackoff`, `TestConcurrency`, `TestOneShot`, `TestPersistence`, `TestExecutionLog`, `TestSchedulerStatus`, `TestFletChannelHandler` | 51 | SchedulerManager: task models, retry/backoff, concurrency, one-shot, persistence, execution log |
| `test_todo_handler.py` | `TestDetection`, `TestParsing`, `TestAdd`, `TestList`, `TestDone`, `TestDelete`, `TestEdit`, `TestFormatResults`, `TestCleanedResponse` | 33 | Todo code-block CRUD |
| `test_background_tasks.py` | `TestTaskStatus`, `TestTaskType`, `TestBackgroundTask`, `TestTaskResult`, `TestBackgroundTaskRunnerInitialization`, `TestTaskManagement`, `TestTaskExecution`, `TestTaskScheduler`, `TestTaskResults`, `TestTaskPersistence`, `TestTaskStatus`, `TestTaskAuthorization` | 31 | Background task runner: status/type enums, task lifecycle, scheduling, persistence, authorization |

### 9. Behavioral & Pattern Detection

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_pattern_detector.py` | `TestPatternType`, `TestDetectedPattern`, `TestUserInteraction`, `TestPatternDetectorInitialization`, `TestInteractionTracking`, `TestPatternDetection`, `TestPatternManagement`, `TestPatternPersistence`, `TestPatternStatistics`, `TestPatternConfidence` | 25 | Pattern types, interaction tracking, pattern detection logic, confidence scoring, persistence |
| `test_personas.py` | `TestPersonaLoading`, `TestUserProfiles`, `TestPersonaResolution`, `TestSystemPromptLayering`, `TestPersonaCRUD`, `TestRouterPersonaIntegration` | 55 | Persona loading, user profiles, resolution order, system prompt layering, CRUD, router integration |
| `test_heartbeat_manager.py` | `TestHeartbeatType`, `TestHeartbeatConfig`, `TestHeartbeatManagerInitialization`, `TestHeartbeatConfiguration`, `TestHeartbeatGeneration`, `TestHeartbeatSending`, `TestHeartbeatScheduler`, `TestHeartbeatUtilities` | 27 | Heartbeat types, config, generation, sending, scheduling |

### 10. Web, MCP, CLI & UI

| File | Classes | Tests | What It Covers |
|---|---|---|---|
| `test_web_tools.py` | `TestHTMLExtractor`, `TestDetection`, `TestParsing`, `TestSearchNoKey`, `TestSearchWithKey`, `TestFetch`, `TestExecuteCommands` | 29 | HTML extraction, Brave API search (mocked), DuckDuckGo fallback, web fetch, command execution |
| `test_mcp_manager.py` | `TestMCPManagerInitialization`, `TestListServers`, `TestEnableDisable`, `TestInstallVerified`, `TestConfirmInstall`, `TestCancelInstall`, `TestUninstall`, `TestVerifiedList` | 21 | MCP server management: list, enable/disable, install/uninstall, verified list |
| `test_cli.py` | `TestCLIEntryPoint`, `TestCLIModule`, `TestConsoleScript` | 8 | CLI entry points via subprocess (`python -m skillforge`) |
| `test_imports.py` | `TestCoreImports`, `TestFletImports` | 35 | Import smoke tests for all core (21) and flet (14) modules |
| `test_flet_app.py` | `TestViewBuilds`, `TestComponentBuilds`, `TestThemeAndStorage`, `TestSkillForgeAppSmoke` | 33 | Flet UI views build without crashing, component rendering, theme/storage |

---

## Impact Matrix

When you change a source module, run the corresponding test files.

| Source Module | Test File(s) |
|---|---|
| `core/router.py` | `test_router.py`, `test_integration_chat.py`, `test_think_levels.py`, `test_router_image_integration.py` |
| `core/ai.py` | `test_integration_chat.py` |
| `core/sessions.py` | `test_session_key_namespace.py`, `test_integration_chat.py` |
| `core/memory/sqlite_memory.py` | `test_sqlite_wal_mode.py`, `test_sqlite_timeout.py`, `test_integration_chat.py` |
| `core/memory/chroma_store.py` | *(no dedicated tests -- coverage gap)* |
| `core/llm/base.py` | `test_vision_providers.py` |
| `core/llm/openai_compat.py` | `test_think_levels.py`, `test_vision_providers.py` |
| `core/llm/anthropic_provider.py` | `test_vision_providers.py` |
| `core/llm/gemini_provider.py` | `test_vision_providers.py` |
| `core/llm/claude_cli_provider.py` | `test_claude_cli.py`, `test_vision_providers.py` |
| `core/llm/gemini_cli_provider.py` | `test_vision_providers.py` |
| `core/llm/llamacpp_provider.py` | `test_vision_providers.py` |
| `core/llm/factory.py` | `test_integration_chat.py` |
| `core/llm/auth/*` | *(no dedicated tests -- coverage gap)* |
| `core/user_permissions.py` | `test_user_permissions.py`, `test_router.py` |
| `core/auth_manager.py` | `test_auth_manager.py`, `test_integration_chat.py` |
| `core/permission_requests.py` | `test_permission_requests.py` |
| `core/identity_resolver.py` | `test_identity_resolver.py` |
| `core/file_access.py` | `test_file_access.py`, `test_file_access_timing.py` |
| `core/image_handler.py` | `test_image_handler.py`, `test_router_image_integration.py`, `test_vision_providers.py` |
| `core/image_gen_handler.py` | `test_image_gen_handler.py` |
| `core/web_tools.py` | `test_web_tools.py` |
| `core/webhook_security.py` | `test_webhook_security.py` |
| `core/mcp_client.py` | *(no dedicated tests -- coverage gap)* |
| `core/mcp_manager.py` | `test_mcp_manager.py`, `test_integration_chat.py` |
| `core/mcp_tools.py` | `test_mcp_security.py` |
| `core/todo_handler.py` | `test_todo_handler.py`, `test_router.py` |
| `core/schedule_handler.py` | `test_schedule_handler.py` |
| `core/scheduler.py` | `test_scheduler.py`, `test_integration_chat.py` |
| `core/background_tasks.py` | `test_background_tasks.py`, `test_integration_chat.py` |
| `core/heartbeat_manager.py` | `test_heartbeat_manager.py`, `test_integration_chat.py` |
| `core/pattern_detector.py` | `test_pattern_detector.py`, `test_auto_skill_creation.py` |
| `core/personality.py` | `test_personas.py`, `test_integration_chat.py` |
| `core/skill_creator_handler.py` | `test_auto_skill_creation.py`, `test_integration_chat.py` |
| `core/skill_executor.py` | `test_integration_chat.py` |
| `core/skills/loader.py` | `test_skills_loading.py` |
| `core/skills/manager.py` | `test_skills_loading.py`, `test_integration_chat.py` |
| `core/clawhub.py` | `test_clawhub.py` |
| `channels/telegram.py` | `test_channel_images.py`, `test_channel_outbound.py` |
| `channels/whatsapp.py` | `test_channel_images.py`, `test_channel_outbound.py` |
| `channels/slack_channel.py` | *(no dedicated tests -- coverage gap)* |
| `channels/discord_channel.py` | *(no dedicated tests -- coverage gap)* |
| `flet/app.py` | `test_flet_app.py` |
| `flet/views/*.py` | `test_flet_app.py` |
| `flet/components/*.py` | `test_flet_app.py` |
| `flet/theme.py` | `test_flet_app.py` |
| `flet/storage.py` | `test_flet_app.py` |
| `ui/chat/handlers.py` | *(no dedicated tests -- coverage gap)* |
| `ui/settings/*.py` | *(no dedicated tests -- coverage gap)* |
| `gradio_ui.py` | *(no dedicated tests -- coverage gap)* |
| `app.py` (FastAPI) | *(no dedicated tests -- coverage gap)* |
| `bot.py` | *(no dedicated tests -- coverage gap)* |
| `telegram_bot.py` | *(no dedicated tests -- coverage gap)* |

---

## Testing Patterns & Conventions

### Fixture Patterns

#### Router Fixture (most common)

Used in `test_router.py`, `test_think_levels.py`, and more:

```python
@pytest.fixture
def router():
    mock_session_mgr = MagicMock()
    mock_session_mgr.get_or_create_session.return_value = {"sessionId": "test"}
    mock_session_mgr.get_session_key.return_value = "test:direct:user1"
    mock_session_mgr.get_conversation_history.return_value = []

    mock_llm = MagicMock()
    mock_llm.provider_name = "test"
    mock_llm.model_name = "test-model"
    mock_llm.chat.return_value = "Hello!"
    mock_llm.check_context_size.return_value = {"needs_compaction": False}

    router = MessageRouter(
        session_manager=mock_session_mgr,
        llm_provider=mock_llm,
    )
    return router
```

#### Integration Router Factory (test_integration_chat.py)

Uses a `make_router` factory parametrized across 3 LLM providers:

```python
@pytest.fixture(params=["ollama", "claude-cli", "gemini-cli"])
def make_router(request, tmp_path):
    # Creates real SessionManager + SQLiteMemory with tmp_path
    # Mocks LLM with smart_response / smart_stream side effects
    ...
```

#### Permission Manager Override

When tests need to bypass or control permissions:

```python
router._permission_manager = PermissionManager(data_dir=str(tmp_path))
```

#### FileAccessManager Sandboxing

```python
router._file_access = FileAccessManager(project_root=str(tmp_path))
```

#### ImageHandler with Temp Directory

```python
handler = ImageHandler(data_dir=str(tmp_path))
```

### Mocking Patterns

| Pattern | When to Use |
|---|---|
| `MagicMock()` | Synchronous methods and attributes |
| `AsyncMock()` | Async methods (coroutines) |
| `patch.object(instance, 'method')` | Replace a method on a specific object |
| `patch('module.path.function')` | Replace a function by import path |
| `patch.dict(os.environ, {...})` | Temporarily set environment variables |
| `side_effect=Exception(...)` | Simulate errors |
| `side_effect=lambda *a, **kw: ...` | Dynamic return values (smart_response) |

### Temp Directory Approaches

```python
# pytest built-in (preferred for most tests)
def test_something(tmp_path):
    db_path = tmp_path / "test.db"

# Manual (used in some older tests)
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = os.path.join(tmpdir, "test.db")
```

### Async Test Convention

```python
@pytest.mark.asyncio
async def test_async_operation(self, router):
    result = await router.handle_message(
        channel="test", user_id="user1", user_message="hello"
    )
```

With `asyncio_mode = "auto"` in pyproject.toml, the `@pytest.mark.asyncio`
decorator is technically optional but kept for clarity.

### Parametrized Tests

```python
# Skills loading: parametrized over 15 expected skill names
@pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
def test_skill_exists(self, skill_name):
    ...

# Integration chat: parametrized over 3 LLM providers
@pytest.fixture(params=["ollama", "claude-cli", "gemini-cli"])
def make_router(request, tmp_path):
    ...
```

### Subprocess Isolation (MCP Security)

Tests that need a clean process environment:

```python
result = subprocess.run(
    [sys.executable, "-c", test_code],
    capture_output=True, text=True, timeout=10
)
assert result.returncode == 0
```

### Timing Attack Testing

```python
def test_timing_attack_resistance(self):
    times_correct_prefix = []
    times_wrong_prefix = []
    for _ in range(100):
        start = time.perf_counter_ns()
        manager.verify_password("correct_start_wrong_end")
        elapsed = time.perf_counter_ns() - start
        times_correct_prefix.append(elapsed)
    # Assert standard deviation is within acceptable bounds
```

---

## Writing New Tests

### Skeleton: Unit Test

```python
# tests/test_my_module.py
import pytest
from unittest.mock import MagicMock, patch
from skillforge.core.my_module import MyClass


@pytest.fixture
def instance(tmp_path):
    return MyClass(data_dir=str(tmp_path))


class TestMyFeature:
    """Test the my_feature behavior."""

    def test_basic_case(self, instance):
        result = instance.do_thing("input")
        assert result == "expected"

    def test_error_case(self, instance):
        with pytest.raises(ValueError, match="bad input"):
            instance.do_thing("")

    def test_with_mock(self, instance):
        with patch.object(instance, '_internal_method', return_value="mocked"):
            result = instance.do_thing("input")
            assert "mocked" in result
```

### Skeleton: Async Test

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


class TestAsyncFeature:
    @pytest.mark.asyncio
    async def test_async_operation(self):
        mock_service = AsyncMock()
        mock_service.fetch.return_value = {"data": "value"}

        result = await my_async_function(mock_service)
        assert result["data"] == "value"
        mock_service.fetch.assert_called_once()
```

### Skeleton: Handler Code-Block Test

Many SkillForge features use the code-block pattern (todo, schedule,
web_search, image_gen). Follow this structure:

```python
class TestDetection:
    def test_detects_block(self, handler):
        response = "```my_block\nKEY: value\n```"
        assert handler.has_commands(response) is True

    def test_no_false_positive(self, handler):
        assert handler.has_commands("no blocks here") is False


class TestParsing:
    def test_parse_block(self, handler):
        block = "KEY: value\nCOUNT: 3"
        result = handler._parse_block(block)
        assert result["KEY"] == "value"
        assert result["COUNT"] == "3"


class TestExecuteCommands:
    def test_execute_and_clean(self, handler):
        response = "Text ```my_block\nKEY: value\n``` more text"
        cleaned, results = handler.execute_commands(response)
        assert "my_block" not in cleaned
        assert len(results) == 1
```

### Naming Conventions

- File: `tests/test_<module_name>.py`
- Class: `Test<FeatureOrBehavior>` (PascalCase)
- Method: `test_<what_is_being_tested>` (snake_case)
- Fixture: lowercase, descriptive (`router`, `handler`, `handler_with_key`,
  `make_router`)

### General Rules

1. **One assert per concept** -- a test can have multiple asserts if they
   validate the same logical outcome, but avoid unrelated assertions.
2. **Isolate via tmp_path** -- never write to the real filesystem.
3. **Mock external I/O** -- network calls, subprocess, file system outside
   tmp_path.
4. **Test the public API** -- prefer testing public methods over private ones.
   Private method tests (e.g., `_parse_block`) are acceptable when the method
   encapsulates significant logic.
5. **Keep tests fast** -- no real network calls, no real LLM invocations.

---

## Coverage Gaps

Modules with **no dedicated tests** (only incidental coverage via integration
tests, if any):

| Module | Risk | Suggested Tests |
|---|---|---|
| `core/memory/chroma_store.py` | High | Vector store CRUD, similarity search, embedding errors |
| `core/mcp_client.py` | High | MCP client connection, tool invocation, error handling |
| `core/llm/auth/*` (6 files) | Medium | Credential storage, provider-specific auth flows, CLI auth |
| `channels/slack_channel.py` | Medium | Slack event parsing, message formatting, thread handling |
| `channels/discord_channel.py` | Medium | Discord event parsing, message formatting |
| `ui/chat/handlers.py` | Medium | Chat handler message processing, UI event dispatch |
| `ui/settings/*.py` (7 files) | Low | Settings state management, tab rendering, MCP/provider config |
| `gradio_ui.py` | Low | Gradio interface building, event binding |
| `app.py` (FastAPI) | Medium | Route handling, webhook endpoints, middleware |
| `bot.py` | Low | Bot initialization, channel orchestration |
| `telegram_bot.py` | Low | Telegram-specific bot startup, webhook setup |
| `run_discord.py` | Low | Discord bot runner |
| `run_slack.py` | Low | Slack bot runner |
| `core/llm/factory.py` | Low | Provider factory selection logic (partially covered by integration) |

### Priority Recommendations

1. **chroma_store.py** -- the vector memory backend has no tests at all;
   failures here silently degrade memory recall.
2. **mcp_client.py** -- MCP tool execution is a core feature; only security
   validation (mcp_security) is tested, not the actual client.
3. **app.py** (FastAPI routes) -- webhook endpoints handle all inbound
   channel traffic; consider adding request/response tests with
   `httpx.AsyncClient` or `TestClient`.
4. **llm/auth/** -- credential management is security-sensitive; at minimum
   test credential storage and retrieval round-trips.

---

## Running Tests After Code Changes

### Quick Decision Guide

| What Changed | What to Run |
|---|---|
| A single module | Check the Impact Matrix above; run those test files |
| Router logic | `pytest tests/test_router.py tests/test_integration_chat.py tests/test_think_levels.py` |
| Any LLM provider | `pytest tests/test_vision_providers.py tests/test_claude_cli.py tests/test_think_levels.py` |
| Permissions / auth | `pytest tests/test_user_permissions.py tests/test_auth_manager.py tests/test_file_access.py tests/test_permission_requests.py` |
| Image pipeline | `pytest tests/test_image_handler.py tests/test_image_gen_handler.py tests/test_router_image_integration.py tests/test_channel_images.py tests/test_channel_outbound.py` |
| Memory / SQLite | `pytest tests/test_sqlite_wal_mode.py tests/test_sqlite_timeout.py tests/test_session_key_namespace.py` |
| Skills / ClawHub | `pytest tests/test_skills_loading.py tests/test_clawhub.py tests/test_auto_skill_creation.py` |
| Scheduling | `pytest tests/test_schedule_handler.py tests/test_scheduler.py tests/test_background_tasks.py` |
| Channels | `pytest tests/test_channel_images.py tests/test_channel_outbound.py tests/test_webhook_security.py` |
| Flet UI | `pytest tests/test_flet_app.py` |
| Imports / packaging | `pytest tests/test_imports.py tests/test_cli.py` |
| Unsure / broad refactor | `pytest` (full suite) |
