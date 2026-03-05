"""Skill ABC — the standard Skill protocol from spec §4.3."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from flow.skills.result import SkillResult


class Skill(ABC):
    """Abstract Base Class for all Skills.

    Design Rules:
      - Single Responsibility: One Skill = one capability.
      - Stateless: No mutable instance state between invocations.
      - Verb-Noun naming: e.g., refactor_code.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier. MUST match the key in skills.registry.json."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Version string: '1', '2', etc."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description shown to the LLM."""
        pass

    @property
    def required_tools(self) -> List[str]:
        """Tool names this Skill depends on. Default: empty."""
        return []

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """JSON Schema defining the Skill's input parameters.
        MUST have type: object and additionalProperties: false."""
        pass

    @property
    def expected_duration_ms(self) -> Optional[int]:
        """Optional hint for the Engine's timeout scheduler."""
        return None

    @property
    def strict_schema(self) -> bool:
        """If True, LLMGateway requests strict schema conformance."""
        return True

    @abstractmethod
    def execute(
        self,
        context: Dict[str, Any],
        tool_context: Any,
        **kwargs,
    ) -> SkillResult:
        """Execute the Skill's logic."""
        pass

    def cleanup(self) -> None:
        """Optional graceful teardown hook. Default: no-op."""
        pass

    def as_tool(self) -> Dict[str, Any]:
        """Project this Skill as an LLM-callable tool definition."""
        return {
            "type": "skill_reference",
            "skill_name": self.name,
            "skill_version": self.version,
            "description": self.description,
            "parameters": self.parameters_schema,
            "strict": self.strict_schema,
        }
