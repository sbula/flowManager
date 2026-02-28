import logging
import re
from typing import Any, Dict, List

from flow.tools.base import ToolError

logger = logging.getLogger(__name__)


class PatchApplicator:
    """
    Applies surgical edits to text content.
    Enforces strict match counting and supports idempotency.
    """

    def apply(self, content: str, edits: List[Dict[str, Any]]) -> str:
        current_content = content

        for edit in edits:
            current_content = self._apply_single_edit(current_content, edit)

        return current_content

    def _apply_single_edit(self, content: str, edit: Dict[str, Any]) -> str:
        op = edit.get("operation", "replace")
        spec = edit.get("spec")
        replacement = edit.get("content", "")
        count = edit.get("count", 1)
        match_mode = edit.get("match_mode", "exact")

        if not spec:
            raise ToolError("Missing 'spec' in edit", code="ValidationError")

        if match_mode not in ["exact", "regex"]:
            raise ToolError(
                f"Unsupported match_mode: {match_mode}", code="ValidationError"
            )

        pattern, matches = self._count_matches(content, spec, match_mode)

        # Idempotency / Validation
        if matches != count:
            if (
                matches == 0
                and op == "replace"
                and match_mode == "exact"
                and replacement in content
            ):
                return content
            if matches == 0:
                raise ToolError(f"Target text not found: '{spec}'", code="PatchError")
            raise ToolError(
                f"Match count mismatch: Expected {count}, Found {matches}",
                code="PatchError",
            )

        return self._apply_operation(
            content, op, spec, replacement, match_mode, pattern
        )

    def _count_matches(
        self, content: str, spec: str, match_mode: str
    ) -> tuple[Any, int]:
        if match_mode == "regex":
            try:
                pattern = re.compile(spec, re.MULTILINE)
            except re.error as e:
                raise ToolError(f"Invalid regex: {e}", code="ValidationError")
            return pattern, len(pattern.findall(content))
        return None, content.count(spec)

    def _apply_operation(
        self,
        content: str,
        op: str,
        spec: str,
        replacement: str,
        match_mode: str,
        pattern: Any,
    ) -> str:
        if op == "replace":
            return (
                pattern.sub(replacement, content)
                if match_mode == "regex"
                else content.replace(spec, replacement)
            )
        elif op == "delete":
            return (
                pattern.sub("", content)
                if match_mode == "regex"
                else content.replace(spec, "")
            )
        elif op == "append_after":
            return (
                pattern.sub(r"\g<0>\n" + replacement, content)
                if match_mode == "regex"
                else content.replace(spec, spec + "\n" + replacement)
            )
        elif op == "prepend_before":
            return (
                pattern.sub(replacement + r"\n\g<0>", content)
                if match_mode == "regex"
                else content.replace(spec, replacement + "\n" + spec)
            )

        raise ToolError(f"Unknown edit operation: {op}", code="ValidationError")
