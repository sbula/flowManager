import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

# Imports for Loom integration
try:
    from flow.engine.loom import Loom, LoomError
    from flow.engine.models import SecurityError
    from flow.engine.security import SafePath
except ImportError:
    # Handle circular imports or missing modules if run in isolation
    pass


class AtomResult:
    def __init__(
        self, success: bool, message: str, exports: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.message = message
        self.exports = exports or {}


class Atom(ABC):
    """Base interface for all Atoms."""

    @abstractmethod
    def run(self, context: Dict[str, Any], **kwargs) -> AtomResult:
        pass


class ManualInterventionAtom(Atom):
    """Fallback atom when no specific atom is found."""

    def run(
        self, context: Dict[str, Any], task_name: str = "Unknown", **kwargs
    ) -> AtomResult:
        return AtomResult(False, f"Manual Intervention Required for task: {task_name}")


class FlowEngineAtom(Atom):
    """Pseudo-atom for Flow sub-workflows."""

    def run(self, context: Dict[str, Any], **kwargs) -> AtomResult:
        return AtomResult(True, "Flow dispatched")


class LoomAtom(Atom):
    """
    Surgical file editing Atom.
    Expects task.ref to point to a JSON operation definition.

    JSON Schema (.flow/artifact.json):
    {
        "op": "insert",
        "path": "src/target.py",  # Relative to Project Root
        "anchor": "def foo():",
        "content": "    print('bar')",
        "position": "after"
    }
    """

    def run(self, context: Dict[str, Any], **kwargs) -> AtomResult:
        root = context.get("__root__")
        ref = context.get("__task_ref__")

        if not root:
            return AtomResult(False, "Root context missing. Cannot initialize Loom.")
        if not ref:
            return AtomResult(
                False, "LoomAtom requires a 'ref' pointing to an operation JSON file."
            )

        try:
            data = self._load_op_data(root, ref)
            if not data:
                return AtomResult(False, f"Operation file not found or invalid: {ref}")

            return self._execute_op(root, data)

        except (SecurityError, LoomError) as e:
            return AtomResult(False, f"Loom Error: {str(e)}")
        except Exception as e:
            return AtomResult(False, f"Unexpected Error: {str(e)}")

    def _load_op_data(self, root: Path, ref: str) -> Optional[Dict[str, Any]]:
        flow_dir = root / ".flow"
        op_path = SafePath(flow_dir, ref)
        if not op_path.exists():
            return None
        try:
            return json.loads(op_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise LoomError(f"Invalid JSON in {ref}")

    def _execute_op(self, root: Path, data: Dict[str, Any]) -> AtomResult:
        op = data.get("op")
        target_file = data.get("path")

        if not op or not target_file:
            return AtomResult(False, "Invalid Op JSON: Missing 'op' or 'path'.")

        loom = Loom(project_root=root)

        if op == "insert":
            return self._op_insert(loom, target_file, data)
        else:
            return AtomResult(False, f"Unknown Loom Operation: {op}")

    def _op_insert(
        self, loom: Loom, target_file: str, data: Dict[str, Any]
    ) -> AtomResult:
        anchor = data.get("anchor")
        content = data.get("content")
        position = data.get("position", "after")

        if not anchor or content is None:
            return AtomResult(False, "Insert op requires 'anchor' and 'content'.")

        loom.insert(target_file, anchor, content, position)
        return AtomResult(True, f"Inserted content into {target_file}")
