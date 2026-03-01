# =============================================================================
# test_pattern_detector.py — Tests for pattern detection system
# =============================================================================

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path


class TestPatternType:
    """Test pattern type constants."""

    def test_pattern_types_defined(self):
        """All pattern types should be defined."""
        from coco_b.core.pattern_detector import PatternType
        
        assert PatternType.REPEATED_COMMAND == "repeated_command"
        assert PatternType.REPEATED_WORKFLOW == "repeated_workflow"
        assert PatternType.TIME_BASED == "time_based"
        assert PatternType.CONTEXT_BASED == "context_based"

    def test_all_types_list(self):
        """ALL_TYPES should contain all pattern types."""
        from coco_b.core.pattern_detector import PatternType
        
        assert len(PatternType.ALL_TYPES) == 4
        assert PatternType.REPEATED_COMMAND in PatternType.ALL_TYPES


class TestDetectedPattern:
    """Test DetectedPattern dataclass."""

    def test_pattern_creation(self):
        """Should create pattern with required fields."""
        from coco_b.core.pattern_detector import DetectedPattern
        
        pattern = DetectedPattern(
            pattern_id="test123",
            pattern_type="repeated_command",
            description="Test pattern",
            confidence=0.8,
            occurrences=5,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat()
        )
        
        assert pattern.pattern_id == "test123"
        assert pattern.confidence == 0.8
        assert not pattern.dismissed
        assert not pattern.created_skill

    def test_is_actionable(self):
        """Should correctly determine if pattern is actionable."""
        from coco_b.core.pattern_detector import DetectedPattern
        
        # Actionable pattern
        pattern = DetectedPattern(
            pattern_id="test",
            pattern_type="repeated_command",
            description="Test",
            confidence=0.8,
            occurrences=5,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat()
        )
        assert pattern.is_actionable is True
        
        # Not actionable - dismissed
        pattern.dismissed = True
        assert pattern.is_actionable is False
        
        # Not actionable - low confidence
        pattern.dismissed = False
        pattern.confidence = 0.5
        assert pattern.is_actionable is False
        
        # Not actionable - too few occurrences
        pattern.confidence = 0.8
        pattern.occurrences = 2
        assert pattern.is_actionable is False

    def test_to_dict(self):
        """Should convert to dictionary."""
        from coco_b.core.pattern_detector import DetectedPattern
        
        pattern = DetectedPattern(
            pattern_id="test",
            pattern_type="repeated_command",
            description="Test",
            confidence=0.8,
            occurrences=5,
            first_seen="2026-01-01T00:00:00",
            last_seen="2026-01-02T00:00:00"
        )
        
        data = pattern.to_dict()
        assert data["pattern_id"] == "test"
        assert data["confidence"] == 0.8

    def test_from_dict(self):
        """Should create from dictionary."""
        from coco_b.core.pattern_detector import DetectedPattern
        
        data = {
            "pattern_id": "test",
            "pattern_type": "repeated_command",
            "description": "Test",
            "confidence": 0.8,
            "occurrences": 5,
            "first_seen": "2026-01-01T00:00:00",
            "last_seen": "2026-01-02T00:00:00",
            "dismissed": True
        }
        
        pattern = DetectedPattern.from_dict(data)
        assert pattern.pattern_id == "test"
        assert pattern.dismissed is True


class TestUserInteraction:
    """Test UserInteraction dataclass."""

    def test_interaction_creation(self):
        """Should create interaction."""
        from coco_b.core.pattern_detector import UserInteraction
        
        interaction = UserInteraction(
            timestamp=datetime.now().isoformat(),
            command="test command",
            context="test context"
        )
        
        assert interaction.command == "test command"
        assert interaction.context == "test context"


class TestPatternDetectorInitialization:
    """Test PatternDetector initialization."""

    def test_initialization(self):
        """Should initialize with empty state."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            assert len(detector._interactions) == 0
            assert len(detector._patterns) == 0

    def test_creates_data_directory(self):
        """Should create data directory."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "patterns"
            detector = PatternDetector(data_dir=data_dir)
            
            assert data_dir.exists()


class TestInteractionTracking:
    """Test interaction tracking."""

    def test_record_interaction(self):
        """Should record interaction."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            detector.record_interaction("user1", "check email")
            
            assert len(detector._interactions["user1"]) == 1
            assert detector._interactions["user1"][0].command == "check email"

    def test_record_multiple_interactions(self):
        """Should record multiple interactions."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            detector.record_interaction("user1", "check email")
            detector.record_interaction("user1", "check calendar")
            detector.record_interaction("user1", "check email")
            
            assert len(detector._interactions["user1"]) == 3

    def test_record_with_context(self):
        """Should record interaction with context."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            detector.record_interaction("user1", "check email", 
                                       context="morning routine")
            
            assert detector._interactions["user1"][0].context == "morning routine"


class TestPatternDetection:
    """Test pattern detection algorithms."""

    def test_detect_repeated_command(self):
        """Should detect repeated command pattern."""
        from coco_b.core.pattern_detector import PatternDetector, PatternType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Record same command 3 times
            for _ in range(3):
                detector.record_interaction("user1", "check email")
            
            patterns = detector._patterns["user1"]
            
            assert len(patterns) >= 1
            assert any(p.pattern_type == PatternType.REPEATED_COMMAND 
                      for p in patterns)

    def test_detect_repeated_command_with_variations(self):
        """Should detect pattern despite minor variations."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Record similar commands
            detector.record_interaction("user1", "Check Email")
            detector.record_interaction("user1", "check  email")
            detector.record_interaction("user1", "CHECK EMAIL")
            
            patterns = detector._patterns["user1"]
            
            # Should be detected as same pattern
            command_patterns = [p for p in patterns 
                              if "check email" in p.description.lower()]
            assert len(command_patterns) >= 1

    def test_detect_workflow(self):
        """Should detect workflow patterns."""
        from coco_b.core.pattern_detector import PatternDetector, PatternType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Record workflow multiple times
            for _ in range(3):
                detector.record_interaction("user1", "check email")
                detector.record_interaction("user1", "check calendar")
            
            patterns = detector._patterns["user1"]
            
            # Should detect workflow
            workflow_patterns = [p for p in patterns 
                               if p.pattern_type == PatternType.REPEATED_WORKFLOW]
            assert len(workflow_patterns) >= 1

    def test_normalize_command(self):
        """Should normalize commands correctly."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Test normalization
            assert detector._normalize_command("  Check   EMAIL  ") == "check email"
            assert detector._normalize_command("CHECK EMAIL") == "check email"
            assert "{N}" in detector._normalize_command("check 5 emails")


class TestPatternManagement:
    """Test pattern management methods."""

    def test_get_suggestions(self):
        """Should return actionable suggestions."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Create patterns
            for _ in range(5):
                detector.record_interaction("user1", "check email")
            
            suggestions = detector.get_suggestions("user1")
            
            # Should have at least one suggestion
            assert len(suggestions) >= 1
            assert all(s.confidence >= 0.7 for s in suggestions)

    def test_dismiss_pattern(self):
        """Should dismiss pattern."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Create pattern
            for _ in range(5):
                detector.record_interaction("user1", "check email")
            
            patterns = detector._patterns["user1"]
            pattern_id = patterns[0].pattern_id
            
            # Dismiss it
            result = detector.dismiss_pattern("user1", pattern_id)
            assert result is True
            
            # Should not appear in suggestions
            suggestions = detector.get_suggestions("user1")
            assert not any(s.pattern_id == pattern_id for s in suggestions)

    def test_mark_skill_created(self):
        """Should mark pattern as skill created."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Create pattern
            for _ in range(5):
                detector.record_interaction("user1", "check email")
            
            patterns = detector._patterns["user1"]
            pattern_id = patterns[0].pattern_id
            
            # Mark as created
            result = detector.mark_skill_created("user1", pattern_id)
            assert result is True
            
            # Should not appear in suggestions
            suggestions = detector.get_suggestions("user1")
            assert not any(s.pattern_id == pattern_id for s in suggestions)

    def test_get_all_patterns(self):
        """Should return all patterns including dismissed."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Create and dismiss pattern
            for _ in range(5):
                detector.record_interaction("user1", "check email")
            
            patterns = detector._patterns["user1"]
            pattern_id = patterns[0].pattern_id
            detector.dismiss_pattern("user1", pattern_id)
            
            # get_all_patterns should include dismissed
            all_patterns = detector.get_all_patterns("user1")
            assert len(all_patterns) >= 1


class TestPatternPersistence:
    """Test pattern data persistence."""

    def test_save_and_load(self):
        """Should persist patterns across instances."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # First instance - record interactions
            detector1 = PatternDetector(data_dir=tmpdir)
            for _ in range(5):
                detector1.record_interaction("user1", "check email")
            
            # Second instance - should load patterns
            detector2 = PatternDetector(data_dir=tmpdir)
            
            assert len(detector2._patterns["user1"]) >= 1
            assert len(detector2._interactions["user1"]) >= 5


class TestPatternStatistics:
    """Test pattern statistics."""

    def test_get_stats(self):
        """Should return correct statistics."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Create some data
            for _ in range(5):
                detector.record_interaction("user1", "check email")
            
            stats = detector.get_stats("user1")
            
            assert stats["total_interactions"] == 5
            assert stats["total_patterns_detected"] >= 1
            assert "patterns_by_type" in stats

    def test_clear_data(self):
        """Should clear all user data."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Create data
            for _ in range(5):
                detector.record_interaction("user1", "check email")
            
            # Clear it
            result = detector.clear_data("user1")
            assert result is True
            
            assert len(detector._interactions.get("user1", [])) == 0
            assert len(detector._patterns.get("user1", [])) == 0


class TestPatternConfidence:
    """Test pattern confidence calculations."""

    def test_confidence_increases_with_occurrences(self):
        """Confidence should increase with more occurrences."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            # Record many times
            for _ in range(15):
                detector.record_interaction("user1", "daily report")
            
            patterns = [p for p in detector._patterns["user1"]
                       if "daily report" in p.description.lower()]
            
            if patterns:
                # Confidence should be high with many occurrences
                assert patterns[0].confidence >= 0.9

    def test_suggest_skill_name(self):
        """Should suggest appropriate skill names."""
        from coco_b.core.pattern_detector import PatternDetector
        
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = PatternDetector(data_dir=tmpdir)
            
            name = detector._suggest_skill_name("check my email inbox")
            assert "check" in name or "my" in name
            assert len(name) <= 30
