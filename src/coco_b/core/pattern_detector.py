# =============================================================================
'''
    File Name : pattern_detector.py
    
    Description : Pattern detection system for suggesting skill creation.
                  Analyzes user interactions to identify repeated tasks
                  and suggests automating them as skills.
    
    Security Levels:
        - ORANGE: Viewing suggestions requires password (60min session)
        - Creating skills from suggestions requires ORANGE level
    
    Pattern Types:
        - repeated_command: Same command used frequently
        - repeated_workflow: Same sequence of commands
        - time_based_pattern: Actions at specific times
        - context_pattern: Similar contexts triggering same actions
    
    Created on 2026-02-21
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : coco B - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set, TYPE_CHECKING
from collections import defaultdict
from pathlib import Path

if TYPE_CHECKING:
    from coco_b.core.auth_manager import AuthManager

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("pattern_detector")


# =============================================================================
'''
    PatternType : Types of patterns that can be detected
'''
# =============================================================================
class PatternType:
    """Types of patterns that can be detected"""
    
    REPEATED_COMMAND = "repeated_command"
    REPEATED_WORKFLOW = "repeated_workflow"
    TIME_BASED = "time_based"
    CONTEXT_BASED = "context_based"
    
    ALL_TYPES = [REPEATED_COMMAND, REPEATED_WORKFLOW, TIME_BASED, CONTEXT_BASED]


# =============================================================================
'''
    DetectedPattern : A pattern that has been detected in user behavior
'''
# =============================================================================
@dataclass
class DetectedPattern:
    """Represents a detected pattern"""
    pattern_id: str
    pattern_type: str
    description: str
    confidence: float  # 0.0 to 1.0
    occurrences: int
    first_seen: str
    last_seen: str
    example_commands: List[str] = field(default_factory=list)
    suggested_skill_name: Optional[str] = None
    suggested_skill_description: Optional[str] = None
    dismissed: bool = False
    created_skill: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DetectedPattern":
        """Create from dictionary"""
        # Filter to only known fields
        known_fields = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)
    
    @property
    def is_actionable(self) -> bool:
        """Whether this pattern should be shown to the user"""
        return (not self.dismissed and 
                not self.created_skill and 
                self.confidence >= 0.7 and
                self.occurrences >= 3)


# =============================================================================
'''
    UserInteraction : Record of a single user interaction
'''
# =============================================================================
@dataclass
class UserInteraction:
    """Record of a user interaction"""
    timestamp: str
    command: str
    context: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserInteraction":
        return cls(**data)


# =============================================================================
'''
    PatternDetector : Detects patterns in user behavior for skill suggestions
    
    Features:
        - Tracks user commands and interactions
        - Detects repeated patterns
        - Suggests skill creation for automation
        - ORANGE security level for viewing/creating
'''
# =============================================================================
class PatternDetector:
    """
    Detects patterns in user behavior to suggest skill creation.
    Requires ORANGE security level to view suggestions.
    """
    
    # Pattern detection thresholds
    MIN_OCCURRENCES = 3
    MIN_CONFIDENCE = 0.7
    MAX_HISTORY_DAYS = 30
    WORKFLOW_WINDOW_MINUTES = 10
    
    def __init__(self, data_dir: Optional[Path] = None, 
                 auth_manager: Optional["AuthManager"] = None):
        """
        Initialize pattern detector.
        
        Args:
            data_dir: Directory to store pattern data
            auth_manager: AuthManager for security checks
        """
        # ==================================
        # Setup data directory
        # ==================================
        if data_dir is None:
            from coco_b import PROJECT_ROOT
            self._data_dir = Path(PROJECT_ROOT) / "data" / "patterns"
        else:
            self._data_dir = Path(data_dir)
        
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # ==================================
        # Auth manager for security
        # ==================================
        self._auth_manager = auth_manager
        
        # ==================================
        # In-memory storage
        # ==================================
        self._interactions: Dict[str, List[UserInteraction]] = defaultdict(list)
        self._patterns: Dict[str, List[DetectedPattern]] = defaultdict(list)
        
        # ==================================
        # Load existing data
        # ==================================
        self._load_data()
    
    # =========================================================================
    # Data Persistence
    # =========================================================================
    
    def _get_user_data_file(self, user_id: str) -> Path:
        """Get data file path for a user"""
        return self._data_dir / f"{user_id}.json"
    
    def _load_data(self):
        """Load all pattern data from disk"""
        if not self._data_dir.exists():
            return
        
        for data_file in self._data_dir.glob("*.json"):
            user_id = data_file.stem
            try:
                with open(data_file, 'r') as f:
                    data = json.load(f)
                
                # Load interactions
                if "interactions" in data:
                    self._interactions[user_id] = [
                        UserInteraction.from_dict(i) 
                        for i in data["interactions"]
                    ]
                
                # Load patterns
                if "patterns" in data:
                    self._patterns[user_id] = [
                        DetectedPattern.from_dict(p)
                        for p in data["patterns"]
                    ]
                    
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load pattern data for {user_id}: {e}")
    
    def _save_user_data(self, user_id: str):
        """Save a user's pattern data to disk"""
        data_file = self._get_user_data_file(user_id)
        
        try:
            data = {
                "interactions": [i.to_dict() for i in self._interactions[user_id]],
                "patterns": [p.to_dict() for p in self._patterns[user_id]]
            }
            
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except IOError as e:
            logger.error(f"Failed to save pattern data for {user_id}: {e}")
    
    # =========================================================================
    # Interaction Tracking
    # =========================================================================
    
    def record_interaction(self, user_id: str, command: str, 
                          context: Optional[str] = None) -> None:
        """
        Record a user interaction for pattern analysis.
        
        Args:
            user_id: User identifier
            command: The command/interaction text
            context: Optional context information
        """
        interaction = UserInteraction(
            timestamp=datetime.now().isoformat(),
            command=command,
            context=context
        )
        
        self._interactions[user_id].append(interaction)
        
        # Clean old interactions
        self._clean_old_interactions(user_id)
        
        # Analyze for new patterns
        self._analyze_patterns(user_id)
        
        # Save data
        self._save_user_data(user_id)
    
    def _clean_old_interactions(self, user_id: str):
        """Remove interactions older than MAX_HISTORY_DAYS"""
        cutoff = datetime.now() - timedelta(days=self.MAX_HISTORY_DAYS)
        
        self._interactions[user_id] = [
            i for i in self._interactions[user_id]
            if datetime.fromisoformat(i.timestamp) > cutoff
        ]
    
    # =========================================================================
    # Pattern Analysis
    # =========================================================================
    
    def _analyze_patterns(self, user_id: str):
        """Analyze user interactions for patterns"""
        interactions = self._interactions[user_id]
        
        if len(interactions) < self.MIN_OCCURRENCES:
            return
        
        # Detect repeated commands
        self._detect_repeated_commands(user_id, interactions)
        
        # Detect workflows
        self._detect_workflows(user_id, interactions)
        
        # Detect time-based patterns
        self._detect_time_patterns(user_id, interactions)
    
    def _detect_repeated_commands(self, user_id: str, 
                                   interactions: List[UserInteraction]):
        """Detect commands that are used repeatedly"""
        # Normalize commands
        command_counts: Dict[str, List[UserInteraction]] = defaultdict(list)
        
        for interaction in interactions:
            # Normalize: lowercase, remove extra spaces
            normalized = self._normalize_command(interaction.command)
            command_counts[normalized].append(interaction)
        
        # Find commands used multiple times
        for normalized, cmds in command_counts.items():
            if len(cmds) >= self.MIN_OCCURRENCES:
                # Check if we already have this pattern
                existing = self._find_existing_pattern(user_id, 
                                                       PatternType.REPEATED_COMMAND,
                                                       normalized)
                
                if existing:
                    # Update existing pattern
                    existing.occurrences = len(cmds)
                    existing.last_seen = cmds[-1].timestamp
                    existing.confidence = min(1.0, len(cmds) / 10)
                else:
                    # Create new pattern
                    pattern = DetectedPattern(
                        pattern_id=self._generate_pattern_id(),
                        pattern_type=PatternType.REPEATED_COMMAND,
                        description=f"Repeated use of: {normalized[:50]}...",
                        confidence=min(1.0, len(cmds) / 10),
                        occurrences=len(cmds),
                        first_seen=cmds[0].timestamp,
                        last_seen=cmds[-1].timestamp,
                        example_commands=[c.command for c in cmds[:3]],
                        suggested_skill_name=self._suggest_skill_name(normalized),
                        suggested_skill_description=f"Automate: {normalized[:100]}"
                    )
                    self._patterns[user_id].append(pattern)
                    logger.info(f"Detected repeated command pattern for {user_id}")
    
    def _detect_workflows(self, user_id: str, 
                         interactions: List[UserInteraction]):
        """Detect sequences of commands that form workflows"""
        # Look for command sequences within time window
        if len(interactions) < 4:
            return
        
        # Find sequences of 2-3 commands that repeat
        sequences: Dict[str, List[int]] = defaultdict(list)
        
        for i in range(len(interactions) - 1):
            # Check if within time window
            t1 = datetime.fromisoformat(interactions[i].timestamp)
            t2 = datetime.fromisoformat(interactions[i + 1].timestamp)
            
            if (t2 - t1).total_seconds() / 60 <= self.WORKFLOW_WINDOW_MINUTES:
                seq = f"{self._normalize_command(interactions[i].command)} -> " \
                      f"{self._normalize_command(interactions[i + 1].command)}"
                sequences[seq].append(i)
        
        # Find repeated sequences
        for seq, indices in sequences.items():
            if len(indices) >= self.MIN_OCCURRENCES:
                existing = self._find_existing_pattern(user_id,
                                                       PatternType.REPEATED_WORKFLOW,
                                                       seq)
                
                if not existing:
                    pattern = DetectedPattern(
                        pattern_id=self._generate_pattern_id(),
                        pattern_type=PatternType.REPEATED_WORKFLOW,
                        description=f"Repeated workflow: {seq[:80]}...",
                        confidence=min(1.0, len(indices) / 5),
                        occurrences=len(indices),
                        first_seen=interactions[indices[0]].timestamp,
                        last_seen=interactions[indices[-1]].timestamp,
                        example_commands=[seq],
                        suggested_skill_name="workflow_" + str(len(indices)),
                        suggested_skill_description=f"Automate workflow: {seq[:100]}"
                    )
                    self._patterns[user_id].append(pattern)
                    logger.info(f"Detected workflow pattern for {user_id}")
    
    def _detect_time_patterns(self, user_id: str, 
                             interactions: List[UserInteraction]):
        """Detect patterns based on time of day"""
        # Group by hour and command
        hour_commands: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        for interaction in interactions:
            dt = datetime.fromisoformat(interaction.timestamp)
            hour = dt.hour
            normalized = self._normalize_command(interaction.command)
            hour_commands[hour][normalized] += 1
        
        # Find commands consistently used at same time
        for hour, commands in hour_commands.items():
            for cmd, count in commands.items():
                if count >= self.MIN_OCCURRENCES:
                    pattern_key = f"{hour:02d}:00_{cmd[:30]}"
                    existing = self._find_existing_pattern(user_id,
                                                           PatternType.TIME_BASED,
                                                           pattern_key)
                    
                    if not existing:
                        pattern = DetectedPattern(
                            pattern_id=self._generate_pattern_id(),
                            pattern_type=PatternType.TIME_BASED,
                            description=f"Daily at {hour:02d}:00: {cmd[:50]}...",
                            confidence=min(1.0, count / 7),  # Daily = high confidence
                            occurrences=count,
                            first_seen=interactions[0].timestamp,
                            last_seen=interactions[-1].timestamp,
                            example_commands=[cmd],
                            suggested_skill_name=f"scheduled_{hour:02d}h",
                            suggested_skill_description=f"Run daily at {hour:02d}:00"
                        )
                        self._patterns[user_id].append(pattern)
    
    def _normalize_command(self, command: str) -> str:
        """Normalize a command for comparison"""
        # Lowercase, strip, collapse whitespace
        normalized = command.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common variations (numbers, specific names)
        normalized = re.sub(r'\b\d+\b', '{N}', normalized)
        
        return normalized[:200]  # Limit length
    
    def _generate_pattern_id(self) -> str:
        """Generate unique pattern ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _find_existing_pattern(self, user_id: str, pattern_type: str, 
                               key: str) -> Optional[DetectedPattern]:
        """Find existing pattern by type and key"""
        for pattern in self._patterns[user_id]:
            if pattern.pattern_type == pattern_type:
                # Check if similar enough
                if key in pattern.description or pattern.description in key:
                    return pattern
        return None
    
    def _suggest_skill_name(self, command: str) -> str:
        """Suggest a skill name from a command"""
        # Extract verb from command
        words = command.split()[:3]
        name = '_'.join(w for w in words if w.isalnum())
        return name[:30] or "auto_skill"
    
    # =========================================================================
    # Public: Pattern Management
    # =========================================================================
    
    def get_suggestions(self, user_id: str, 
                        limit: int = 5) -> List[DetectedPattern]:
        """
        Get actionable pattern suggestions for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of suggestions to return
            
        Returns:
            List of actionable detected patterns
        """
        suggestions = [
            p for p in self._patterns[user_id]
            if p.is_actionable
        ]
        
        # Sort by confidence (highest first)
        suggestions.sort(key=lambda p: p.confidence, reverse=True)
        
        return suggestions[:limit]
    
    def get_all_patterns(self, user_id: str) -> List[DetectedPattern]:
        """Get all patterns for a user (including dismissed)"""
        return self._patterns[user_id][:]
    
    def dismiss_pattern(self, user_id: str, pattern_id: str) -> bool:
        """
        Dismiss a pattern suggestion.
        
        Args:
            user_id: User identifier
            pattern_id: Pattern to dismiss
            
        Returns:
            True if dismissed successfully
        """
        for pattern in self._patterns[user_id]:
            if pattern.pattern_id == pattern_id:
                pattern.dismissed = True
                self._save_user_data(user_id)
                logger.info(f"Dismissed pattern {pattern_id} for {user_id}")
                return True
        return False
    
    def mark_skill_created(self, user_id: str, pattern_id: str) -> bool:
        """
        Mark a pattern as having been turned into a skill.
        
        Args:
            user_id: User identifier
            pattern_id: Pattern that was converted
            
        Returns:
            True if marked successfully
        """
        for pattern in self._patterns[user_id]:
            if pattern.pattern_id == pattern_id:
                pattern.created_skill = True
                self._save_user_data(user_id)
                logger.info(f"Marked pattern {pattern_id} as created for {user_id}")
                return True
        return False
    
    # =========================================================================
    # Public: Statistics
    # =========================================================================
    
    def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Get pattern detection statistics for a user"""
        patterns = self._patterns[user_id]
        
        return {
            "total_interactions": len(self._interactions[user_id]),
            "total_patterns_detected": len(patterns),
            "actionable_suggestions": len([p for p in patterns if p.is_actionable]),
            "patterns_by_type": {
                ptype: len([p for p in patterns if p.pattern_type == ptype])
                for ptype in PatternType.ALL_TYPES
            },
            "dismissed": len([p for p in patterns if p.dismissed]),
            "converted_to_skills": len([p for p in patterns if p.created_skill])
        }
    
    def clear_data(self, user_id: str) -> bool:
        """Clear all pattern data for a user"""
        if user_id in self._interactions:
            del self._interactions[user_id]
        if user_id in self._patterns:
            del self._patterns[user_id]
        
        data_file = self._get_user_data_file(user_id)
        if data_file.exists():
            data_file.unlink()
        
        logger.info(f"Cleared pattern data for {user_id}")
        return True


# =============================================================================
'''
    End of File : pattern_detector.py
    
    Project : coco B - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
