"""SkillResult and SkillStatus — standard return type for all Skill executions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class SkillStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY = "RETRY"
    PAUSED_FOR_EXPANSION = "PAUSED_FOR_EXPANSION"


@dataclass
class SkillResult:
    """Standard return type for all Skill executions.

    Mirrors AtomResult (01_05 §2.2) for consistency.
    """

    status: SkillStatus
    message: str = ""
    exports: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None

    # Metadata for observability
    skill_name: str = ""
    skill_version: str = ""
    duration_ms: int = 0
