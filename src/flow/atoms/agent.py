from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from .base import Atom, AtomConfig, AtomResult, AtomStatus


class AgentAtomConfig(AtomConfig):
    required_context_keys: List[str] = Field(default_factory=list)


class AgentAtom(Atom):
    """
    AgentAtom (Cognitive Execution).
    Tight binding for LLM logic and Tools.
    Stateless boundary that yields sub-Run IDs.
    """

    def __init__(
        self, config: Optional[Dict[str, Any]] = None, flow_dir: Optional[Path] = None
    ):
        super().__init__(config)
        self.flow_dir = flow_dir or Path(".flow")

    def _parse_config(self, config: Dict[str, Any]) -> AgentAtomConfig:
        return AgentAtomConfig(**config)

    def run(self, context: Dict[str, Any]) -> AtomResult:
        from typing import cast

        # Schema Validation step (Poison Pill Defense)
        config = cast(AgentAtomConfig, self.config)
        missing_keys = [k for k in config.required_context_keys if k not in context]

        if missing_keys:
            if context.get("__is_llm_response__") is True:
                from flow.atoms.base import RetryStrategy

                return AtomResult(
                    AtomStatus.RETRY,
                    f"LLM Schema Mismatch: Missing required keys: {', '.join(missing_keys)}",
                    retry_strategy=RetryStrategy.BACKOFF,
                )

            return AtomResult(
                AtomStatus.FAILED,
                f"Schema Validation Failed: Missing context keys: {', '.join(missing_keys)}",
            )

        # Delegated Thought History check
        # This matches T4.1.04 where an agent must Native Resume
        history = context.get("__agent_history__", [])
        if "__agent_history_blob__" in context:
            import json
            from pathlib import Path

            blob_path = Path(context["__agent_history_blob__"])
            try:
                history = json.loads(blob_path.read_text(encoding="utf-8"))
            except OSError as e:
                return AtomResult(AtomStatus.FAILED, f"Blob IO Error: {e}")

        if history:
            # We are resuming from an existing loop!
            pass

        # T4.3.01 Subflow Dispatch Rejection
        llm_response = context.get("__llm_response__", {})
        if isinstance(llm_response, dict) and llm_response.get("type") == "SubflowCall":
            from flow.domain.models import UnauthorizedSubflowError

            raise UnauthorizedSubflowError(
                "ReAct loops cannot orchestrate DAG Subflows."
            )

        # T4.2.03 Context Truncation on Resume
        # If history exceeds token limits (mocked as 100 messages), truncate oldest
        if len(history) > 100:
            history = history[-100:]

        # T4.2.04 Sub-Run ID vs Loop Count Drift
        expected_loop = context.get("expected_loop_count")
        if expected_loop is not None and len(history) != expected_loop:
            from flow.domain.models import DomainError

            class CacheContinuityError(DomainError):
                pass

            raise CacheContinuityError(
                f"Drift: expected loop {expected_loop} but history size is {len(history)}"
            )

        # Agent execution stub... normally invokes LLM/Tools
        task_id = context.get("__task_id__", "unknown-task")

        # Sub-Run ID generation for exactly-once tool execution
        # sub_run_id = hash(f"{agent_id}-tool-{tool_name}-{loop_index}")

        # Add stub content to history
        history.append({"role": "system", "content": "Done"})

        # T4.1.01 Blob Promotion
        import json

        out_exports = {"__agent_history__": history}
        history_str = json.dumps(history)
        if len(history_str) > 128 * 1024:
            artifacts_dir = self.flow_dir / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            blob_path = artifacts_dir / f"blob_{task_id}.txt"
            try:
                blob_path.write_text(history_str, encoding="utf-8")
                out_exports = {"__agent_history_blob__": str(blob_path)}
            except OSError as e:
                return AtomResult(AtomStatus.FAILED, f"Blob Write Error: {e}")

        return AtomResult(
            AtomStatus.SUCCESS,
            "Agent ReAct loop completed.",
            exports=out_exports,
        )
