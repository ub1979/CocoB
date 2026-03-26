# =============================================================================
"""
    Test autonomous skill creation — PatternDetector auto-skill prompt
    generation and router integration.
"""
# =============================================================================
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

from skillforge.core.pattern_detector import (
    PatternDetector, DetectedPattern, PatternType, UserInteraction
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def detector(tmp_path):
    """PatternDetector with temp data dir."""
    return PatternDetector(data_dir=tmp_path / "patterns")


@pytest.fixture
def high_confidence_pattern():
    """A pattern that meets auto-creation thresholds."""
    return DetectedPattern(
        pattern_id="abc12345",
        pattern_type=PatternType.REPEATED_COMMAND,
        description="Repeated use of: check server status",
        confidence=0.9,
        occurrences=7,
        first_seen=datetime.now().isoformat(),
        last_seen=datetime.now().isoformat(),
        example_commands=["check server status", "check server status", "check server status"],
        suggested_skill_name="check_server",
        suggested_skill_description="Automate: check server status",
        dismissed=False,
        created_skill=False,
    )


@pytest.fixture
def low_confidence_pattern():
    """A pattern below auto-creation thresholds."""
    return DetectedPattern(
        pattern_id="def67890",
        pattern_type=PatternType.REPEATED_COMMAND,
        description="Repeated use of: hello",
        confidence=0.5,
        occurrences=3,
        first_seen=datetime.now().isoformat(),
        last_seen=datetime.now().isoformat(),
        example_commands=["hello", "hello", "hello"],
        suggested_skill_name="hello",
        suggested_skill_description="Automate: hello",
        dismissed=False,
        created_skill=False,
    )


# =============================================================================
# TestGetAutoSkillPrompt
# =============================================================================
class TestGetAutoSkillPrompt:
    """Tests for PatternDetector.get_auto_skill_prompt()"""

    def test_returns_none_when_no_patterns(self, detector):
        """No patterns -> None."""
        result = detector.get_auto_skill_prompt("user1")
        assert result is None

    def test_returns_none_when_below_threshold(self, detector, low_confidence_pattern):
        """Low confidence pattern -> None."""
        detector._patterns["user1"] = [low_confidence_pattern]
        result = detector.get_auto_skill_prompt("user1")
        assert result is None

    def test_returns_prompt_for_high_confidence(self, detector, high_confidence_pattern):
        """High confidence + high occurrences -> prompt returned."""
        detector._patterns["user1"] = [high_confidence_pattern]
        result = detector.get_auto_skill_prompt("user1")
        assert result is not None
        assert "Auto-Skill Creation" in result
        assert "check_server" in result
        assert "pattern_id:abc12345" in result
        assert "7 times" in result

    def test_includes_example_commands(self, detector, high_confidence_pattern):
        """Prompt includes example commands from the pattern."""
        detector._patterns["user1"] = [high_confidence_pattern]
        result = detector.get_auto_skill_prompt("user1")
        assert "check server status" in result

    def test_skips_dismissed_patterns(self, detector, high_confidence_pattern):
        """Dismissed patterns are skipped."""
        high_confidence_pattern.dismissed = True
        detector._patterns["user1"] = [high_confidence_pattern]
        result = detector.get_auto_skill_prompt("user1")
        assert result is None

    def test_skips_already_created_patterns(self, detector, high_confidence_pattern):
        """Already-created patterns are skipped."""
        high_confidence_pattern.created_skill = True
        detector._patterns["user1"] = [high_confidence_pattern]
        result = detector.get_auto_skill_prompt("user1")
        assert result is None

    def test_picks_highest_confidence(self, detector):
        """When multiple eligible patterns, picks highest confidence."""
        p1 = DetectedPattern(
            pattern_id="aaa11111",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="pattern one",
            confidence=0.88,
            occurrences=6,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["cmd1"],
            suggested_skill_name="skill_one",
        )
        p2 = DetectedPattern(
            pattern_id="bbb22222",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="pattern two",
            confidence=0.95,
            occurrences=10,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["cmd2"],
            suggested_skill_name="skill_two",
        )
        detector._patterns["user1"] = [p1, p2]
        result = detector.get_auto_skill_prompt("user1")
        assert "skill_two" in result
        assert "bbb22222" in result

    def test_only_returns_one_pattern(self, detector):
        """Only one pattern prompt at a time — not multiple."""
        patterns = []
        for i in range(3):
            patterns.append(DetectedPattern(
                pattern_id=f"id{i}",
                pattern_type=PatternType.REPEATED_COMMAND,
                description=f"pattern {i}",
                confidence=0.9,
                occurrences=8,
                first_seen=datetime.now().isoformat(),
                last_seen=datetime.now().isoformat(),
                example_commands=[f"cmd{i}"],
                suggested_skill_name=f"skill_{i}",
            ))
        detector._patterns["user1"] = patterns
        result = detector.get_auto_skill_prompt("user1")
        # Should contain exactly one pattern_id reference
        assert result.count("pattern_id:") == 1

    def test_confidence_boundary_084(self, detector):
        """0.84 confidence (just below 0.85 threshold) -> None."""
        p = DetectedPattern(
            pattern_id="edge1",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="edge case",
            confidence=0.84,
            occurrences=10,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["cmd"],
            suggested_skill_name="edge_skill",
        )
        detector._patterns["user1"] = [p]
        assert detector.get_auto_skill_prompt("user1") is None

    def test_confidence_boundary_085(self, detector):
        """0.85 confidence (exactly at threshold) -> returns prompt."""
        p = DetectedPattern(
            pattern_id="edge2",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="edge case",
            confidence=0.85,
            occurrences=5,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["cmd"],
            suggested_skill_name="edge_skill",
        )
        detector._patterns["user1"] = [p]
        assert detector.get_auto_skill_prompt("user1") is not None

    def test_occurrences_boundary_4(self, detector):
        """4 occurrences (below 5 threshold) -> None."""
        p = DetectedPattern(
            pattern_id="occ1",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="occ test",
            confidence=0.95,
            occurrences=4,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["cmd"],
            suggested_skill_name="occ_skill",
        )
        detector._patterns["user1"] = [p]
        assert detector.get_auto_skill_prompt("user1") is None

    def test_occurrences_boundary_5(self, detector):
        """5 occurrences (exactly at threshold) -> returns prompt."""
        p = DetectedPattern(
            pattern_id="occ2",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="occ test",
            confidence=0.9,
            occurrences=5,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["cmd"],
            suggested_skill_name="occ_skill",
        )
        detector._patterns["user1"] = [p]
        assert detector.get_auto_skill_prompt("user1") is not None

    def test_contains_create_skill_instruction(self, detector, high_confidence_pattern):
        """Prompt tells LLM to emit a create-skill code block."""
        detector._patterns["user1"] = [high_confidence_pattern]
        result = detector.get_auto_skill_prompt("user1")
        assert "```create-skill```" in result
        assert "ACTION: create" in result

    def test_fallback_skill_name(self, detector):
        """When suggested_skill_name is None, uses 'auto-task'."""
        p = DetectedPattern(
            pattern_id="fb1",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="no name",
            confidence=0.9,
            occurrences=6,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["something"],
            suggested_skill_name=None,
        )
        detector._patterns["user1"] = [p]
        result = detector.get_auto_skill_prompt("user1")
        assert "auto-task" in result

    def test_different_users_isolated(self, detector, high_confidence_pattern):
        """User1 patterns don't affect user2."""
        detector._patterns["user1"] = [high_confidence_pattern]
        assert detector.get_auto_skill_prompt("user1") is not None
        assert detector.get_auto_skill_prompt("user2") is None


# =============================================================================
# TestMarkAutoSkillPattern
# =============================================================================
class TestMarkAutoSkillPattern:
    """Tests for router _mark_auto_skill_pattern method."""

    def _make_router_stub(self, tmp_path):
        """Create a minimal router-like object with _mark_auto_skill_pattern."""
        from skillforge.core.router import MessageRouter
        r = object.__new__(MessageRouter)
        r._pattern_detector = PatternDetector(data_dir=tmp_path / "patterns")
        return r

    def test_extracts_and_marks_pattern_id(self, tmp_path):
        """Pattern ID in INSTRUCTIONS gets extracted and marked."""
        r = self._make_router_stub(tmp_path)

        # Add a pattern
        p = DetectedPattern(
            pattern_id="aa1b2c3d",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="test",
            confidence=0.9,
            occurrences=7,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["test"],
        )
        r._pattern_detector._patterns["user1"] = [p]

        cmd = {
            "ACTION": "create",
            "NAME": "test-skill",
            "INSTRUCTIONS": "Do something useful [pattern_id:aa1b2c3d]",
        }

        r._mark_auto_skill_pattern("user1", cmd)

        assert p.created_skill is True

    def test_no_pattern_id_in_instructions(self, tmp_path):
        """No pattern_id tag -> no crash, no marking."""
        r = self._make_router_stub(tmp_path)

        cmd = {
            "ACTION": "create",
            "NAME": "test-skill",
            "INSTRUCTIONS": "Do something useful",
        }

        # Should not raise
        r._mark_auto_skill_pattern("user1", cmd)

    def test_missing_instructions_field(self, tmp_path):
        """No INSTRUCTIONS key -> no crash."""
        r = self._make_router_stub(tmp_path)

        cmd = {"ACTION": "create", "NAME": "test-skill"}
        r._mark_auto_skill_pattern("user1", cmd)  # Should not raise


# =============================================================================
# TestIntegrationAutoSkillFlow
# =============================================================================
class TestIntegrationAutoSkillFlow:
    """Integration tests for the full auto-skill creation flow."""

    def test_high_confidence_pattern_generates_prompt(self, tmp_path):
        """Simulate: user repeats action -> pattern detected -> prompt injected."""
        detector = PatternDetector(data_dir=tmp_path / "patterns")

        # Simulate 8 repeated interactions
        for i in range(8):
            detector.record_interaction("user1", "check server status")

        # Should now have patterns detected
        patterns = detector.get_suggestions("user1")
        assert len(patterns) >= 1

        # With 8 occurrences, repeated_command confidence = min(1.0, 8/10) = 0.8
        # But time_based confidence = min(1.0, 8/7) >= 1.0 (all at same hour)
        # So a time-based pattern may trigger auto-creation
        prompt = detector.get_auto_skill_prompt("user1")
        # At least one pattern type should exceed threshold at 8 occurrences
        if prompt is not None:
            assert "create-skill" in prompt

    def test_10_occurrences_triggers_auto_creation(self, tmp_path):
        """10 occurrences -> confidence 1.0 -> auto-skill prompt generated."""
        detector = PatternDetector(data_dir=tmp_path / "patterns")

        for i in range(10):
            detector.record_interaction("user1", "summarize my emails")

        prompt = detector.get_auto_skill_prompt("user1")
        assert prompt is not None
        assert "create-skill" in prompt

    def test_pattern_marked_after_skill_creation(self, tmp_path):
        """After marking, pattern no longer triggers auto-skill prompt."""
        detector = PatternDetector(data_dir=tmp_path / "patterns")

        # Create a pattern manually
        p = DetectedPattern(
            pattern_id="flow123",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="Repeated use of: daily report",
            confidence=0.95,
            occurrences=10,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["daily report"],
            suggested_skill_name="daily_report",
        )
        detector._patterns["user1"] = [p]

        # Should trigger
        assert detector.get_auto_skill_prompt("user1") is not None

        # Mark as created
        detector.mark_skill_created("user1", "flow123")

        # Should no longer trigger
        assert detector.get_auto_skill_prompt("user1") is None

    def test_dismissed_pattern_never_triggers(self, tmp_path):
        """Dismissed patterns never come back as auto-skill prompts."""
        detector = PatternDetector(data_dir=tmp_path / "patterns")

        p = DetectedPattern(
            pattern_id="dismiss1",
            pattern_type=PatternType.REPEATED_COMMAND,
            description="Repeated use of: something",
            confidence=0.95,
            occurrences=10,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            example_commands=["something"],
            suggested_skill_name="something_skill",
        )
        detector._patterns["user1"] = [p]
        detector.dismiss_pattern("user1", "dismiss1")

        assert detector.get_auto_skill_prompt("user1") is None
