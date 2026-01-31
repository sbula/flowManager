import json
from pathlib import Path
from typing import Optional, Dict
from pydantic import ValidationError
from workflow_core.engine.schemas.models import WorkflowState

class PersistenceManager:
    """Handles storage of flow state."""
    
    def __init__(self, root_dir: Path):
        self.state_dir = root_dir / ".flow_state"
        self._ensure_dir()

    def _ensure_dir(self):
        if not self.state_dir.exists():
            self.state_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, task_id: str) -> Path:
        # Sanitize ID for filename
        safe_id = task_id.replace(".", "_").replace("/", "_")
        return self.state_dir / f"{safe_id}.state.json"

    def load_state(self, task_id: str) -> Optional[WorkflowState]:
        path = self._get_path(task_id)
        if not path.exists():
            return None
            
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return WorkflowState(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            # TODO: Log error or backup corrupt state?
            # For now, treat as non-existent (reset) or raise?
            # Raising is safer to prevent data loss.
            raise ValueError(f"Corrupt State File {path}: {e}")

    def save_state(self, state: WorkflowState):
        path = self._get_path(state.task_id)
        path.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8"
        )
