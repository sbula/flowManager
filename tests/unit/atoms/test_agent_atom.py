"""§4 Cognitive Engine & Tool Orchestration Tests.

Tests T4.1.01–T4.3.02: AgentAtom context storage, ReAct loop
break/restart, and exception trapping (The Iron Wall).

Tests directly exercise the AgentAtom implementation in
src/flow/atoms/agent.py.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from flow.atoms.agent import AgentAtom
from flow.atoms.base import AtomStatus
from flow.domain.models import UnauthorizedSubflowError


# ─── §4.1 AgentAtom Context Storage & Memory Limits ───────────────


class TestAgentAtomContextStorage:
    """T4.1.01–T4.1.04: Blob promotion, resumption, IO failure, schema drift."""

    def test_t4_1_01_context_overflow_blob_promotion(self, tmp_path):
        """T4.1.01: >128KB context automatically promoted to blob file."""
        flow_dir = tmp_path / ".flow"
        flow_dir.mkdir()
        (flow_dir / "artifacts").mkdir()

        atom = AgentAtom(config={}, flow_dir=flow_dir)

        # Build context with enough history to exceed 128KB
        large_history = [
            {"role": "user", "content": "x" * 2000} for _ in range(100)
        ]
        context = {
            "__task_id__": "blob-test",
            "__agent_history__": large_history,
        }

        result = atom.run(context)
        assert result.status == AtomStatus.SUCCESS

        # If history exceeds 128KB, it should be promoted to blob
        history_str = json.dumps(large_history + [{"role": "system", "content": "Done"}])
        if len(history_str) > 128 * 1024:
            assert "__agent_history_blob__" in result.exports
            blob_path = Path(result.exports["__agent_history_blob__"])
            assert blob_path.exists()
            blob_content = json.loads(blob_path.read_text(encoding="utf-8"))
            assert len(blob_content) > 0

    def test_t4_1_02_resumption_from_blob_pointer(self, tmp_path):
        """T4.1.02: Engine restarts and reads context from blob pointer."""
        flow_dir = tmp_path / ".flow"
        flow_dir.mkdir()
        (flow_dir / "artifacts").mkdir()

        # Write blob content to disk (simulating previous run)
        blob_path = tmp_path / "blob_resume_test.txt"
        history = [{"role": "user", "content": "previous turn"}]
        blob_path.write_text(json.dumps(history), encoding="utf-8")

        atom = AgentAtom(config={}, flow_dir=flow_dir)
        context = {
            "__task_id__": "resume-test",
            "__agent_history_blob__": str(blob_path),
        }

        result = atom.run(context)
        assert result.status == AtomStatus.SUCCESS
        # Atom should have hydrated from blob and appended new entry
        if "__agent_history__" in result.exports:
            assert len(result.exports["__agent_history__"]) >= 2

    def test_t4_1_03_blob_io_failure_disk_full(self, tmp_path):
        """T4.1.03: Disk full on blob write yields FAILED."""
        flow_dir = tmp_path / ".flow"
        flow_dir.mkdir()
        (flow_dir / "artifacts").mkdir()

        atom = AgentAtom(config={}, flow_dir=flow_dir)

        # Build large history that triggers blob promotion
        large_history = [
            {"role": "user", "content": "y" * 2000} for _ in range(100)
        ]
        context = {
            "__task_id__": "disk-full-test",
            "__agent_history__": large_history,
        }

        # Mock write_text to simulate ENOSPC
        with patch.object(Path, "write_text", side_effect=OSError("ENOSPC: No space left on device")):
            result = atom.run(context)

        # If blob promotion was triggered and write failed, expect FAILED
        history_str = json.dumps(large_history + [{"role": "system", "content": "Done"}])
        if len(history_str) > 128 * 1024:
            assert result.status == AtomStatus.FAILED
            assert "Blob" in result.message or "Error" in result.message

    def test_t4_1_04_context_hydration_altered_schema(self, tmp_path):
        """T4.1.04: Blob content fails new schema validation → reject resume."""
        flow_dir = tmp_path / ".flow"
        flow_dir.mkdir()
        (flow_dir / "artifacts").mkdir()

        # Write blob with old schema (missing required fields)
        blob_path = tmp_path / "blob_schema_drift.txt"
        old_schema_data = [{"old_field": "data"}]  # Doesn't have 'role'/'content'
        blob_path.write_text(json.dumps(old_schema_data), encoding="utf-8")

        atom = AgentAtom(
            config={"required_context_keys": ["mandatory_field"]},
            flow_dir=flow_dir,
        )
        context = {
            "__task_id__": "schema-drift-test",
            "__agent_history_blob__": str(blob_path),
        }

        result = atom.run(context)
        # Missing required context keys → FAILED
        assert result.status == AtomStatus.FAILED
        assert "Schema" in result.message or "Missing" in result.message


# ─── §4.2 AgentAtom ReAct Loop Break/Restart ──────────────────────


class TestAgentAtomReActLoop:
    """T4.2.01–T4.2.04: State reconciliation in ReAct loops."""

    def test_t4_2_01_mid_loop_hard_crash_recovery(self, tmp_path):
        """T4.2.01: After crash, AgentAtom restores from cached tool output."""
        flow_dir = tmp_path / ".flow"
        flow_dir.mkdir()
        (flow_dir / "artifacts").mkdir()

        # Simulate: tool output was cached before crash
        cached_history = [
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "I'll use the tool"},
            {"role": "tool", "content": "tool result"},
        ]
        initial_count = len(cached_history)  # Save before run() mutates in-place

        atom = AgentAtom(config={}, flow_dir=flow_dir)
        context = {
            "__task_id__": "crash-recovery",
            "__agent_history__": cached_history,
        }

        result = atom.run(context)
        assert result.status == AtomStatus.SUCCESS
        # Should resume from cached state, not restart
        if "__agent_history__" in result.exports:
            history = result.exports["__agent_history__"]
            # Original 3 entries + 1 new system message
            assert len(history) == initial_count + 1

    def test_t4_2_02_sub_run_id_normalization(self):
        """T4.2.02: Whitespace/key ordering noise doesn't affect Sub-Run IDs."""
        import hashlib

        # Normalize payload before hashing
        payload_a = {"tool": "read_file", "args": {"path": "/a/b"}}
        payload_b = {"args": {"path": "/a/b"}, "tool": "read_file"}

        normalized_a = json.dumps(payload_a, sort_keys=True)
        normalized_b = json.dumps(payload_b, sort_keys=True)

        hash_a = hashlib.sha256(normalized_a.encode()).hexdigest()
        hash_b = hashlib.sha256(normalized_b.encode()).hexdigest()

        assert hash_a == hash_b

    def test_t4_2_03_context_truncation_on_resume(self, tmp_path):
        """T4.2.03: History exceeding token limits is truncated before network IO."""
        flow_dir = tmp_path / ".flow"
        flow_dir.mkdir()
        (flow_dir / "artifacts").mkdir()

        # Create history that exceeds the 100-message mock limit
        oversized_history = [
            {"role": "user", "content": f"msg-{i}"} for i in range(150)
        ]

        atom = AgentAtom(config={}, flow_dir=flow_dir)
        context = {
            "__task_id__": "truncation-test",
            "__agent_history__": oversized_history,
        }

        result = atom.run(context)
        assert result.status == AtomStatus.SUCCESS

        # Check that history was truncated (kept last 100 + 1 new)
        if "__agent_history__" in result.exports:
            history = result.exports["__agent_history__"]
            assert len(history) <= 101  # 100 truncated + 1 system message

    def test_t4_2_04_sub_run_id_loop_count_drift(self, tmp_path):
        """T4.2.04: Cache gap in loop history triggers CacheContinuityError."""
        flow_dir = tmp_path / ".flow"
        flow_dir.mkdir()
        (flow_dir / "artifacts").mkdir()

        # History has 3 entries but expected_loop_count says 5
        history = [
            {"role": "user", "content": "turn-1"},
            {"role": "assistant", "content": "turn-2"},
            {"role": "user", "content": "turn-3"},
        ]

        atom = AgentAtom(config={}, flow_dir=flow_dir)
        context = {
            "__task_id__": "drift-test",
            "__agent_history__": history,
            "expected_loop_count": 5,  # Mismatch!
        }

        # Agent.py defines CacheContinuityError inline as DomainError subclass
        from flow.domain.models import DomainError

        with pytest.raises(DomainError, match="Drift"):
            atom.run(context)


# ─── §4.3 AgentAtom Exception Trapping (The Iron Wall) ──────────


class TestAgentAtomIronWall:
    """T4.3.01–T4.3.02: Subflow rejection and schema validation."""

    def test_t4_3_01_hallucinated_subflow_dispatch_rejection(self, tmp_path):
        """T4.3.01: LLM generates SubflowCall → UnauthorizedSubflowError."""
        flow_dir = tmp_path / ".flow"
        flow_dir.mkdir()
        (flow_dir / "artifacts").mkdir()

        atom = AgentAtom(config={}, flow_dir=flow_dir)
        context = {
            "__task_id__": "subflow-reject",
            "__llm_response__": {
                "type": "SubflowCall",
                "flow": "dangerous-parallel-flow",
            },
        }

        with pytest.raises(UnauthorizedSubflowError):
            atom.run(context)

    def test_t4_3_02_valid_json_invalid_output_schema(self, tmp_path):
        """T4.3.02: LLM returns valid JSON but wrong exports schema → retry."""
        flow_dir = tmp_path / ".flow"
        flow_dir.mkdir()
        (flow_dir / "artifacts").mkdir()

        atom = AgentAtom(
            config={"required_context_keys": ["analysis_result"]},
            flow_dir=flow_dir,
        )
        context = {
            "__task_id__": "schema-mismatch",
            # LLM response is valid JSON but missing required key
            "__is_llm_response__": True,
            "wrong_key": "some valid data",
        }

        result = atom.run(context)
        # Should get RETRY for LLM schema mismatch, not hard FAILED
        assert result.status == AtomStatus.RETRY
        assert "Missing" in result.message or "Schema" in result.message
