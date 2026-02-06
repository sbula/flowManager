import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EventBus:
    MAX_INLINE_SIZE = 8192

    def __init__(self, flow_dir: Path):
        self.flow_dir = flow_dir
        self.artifacts_dir = flow_dir / "artifacts"
        self.logs_dir = flow_dir / "logs"

    def emit(
        self,
        event_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Event:
        # Check size
        serialized = json.dumps(payload)
        final_payload = payload

        if len(serialized) > self.MAX_INLINE_SIZE:
            # Blob reference
            blob_id = f"blob_{uuid.uuid4()}.json"
            blob_path = self.artifacts_dir / blob_id

            try:
                # Ensure artifacts dir exists (H1 or auto-create?)
                # Spec says H1: Root exists. Artifacts should be there or created.
                if not self.artifacts_dir.exists():
                    self.artifacts_dir.mkdir(parents=True, exist_ok=True)

                blob_path.write_text(serialized, encoding="utf-8")
                final_payload = {"ref": blob_id, "type": "blob_ref"}
            except OSError as e:
                # T5.05 Blob Write Failure -> Warning, No Crash.
                # Fallback: Truncate inline or embed error?
                # Spec: "Warning logged, Event emitted with Payload truncated or Error."
                # Let's keep a small error payload.
                final_payload = {
                    "error": "Blob Write Failed",
                    "original_size": len(serialized),
                    "details": str(e),
                }

        event = Event(type=event_type, payload=final_payload, metadata=metadata or {})
        self._log(event)
        return event

    def _log(self, event: Event):
        if not self.logs_dir.exists():
            return

        log_file = self.logs_dir / "events.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
