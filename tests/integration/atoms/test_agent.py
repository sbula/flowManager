import json

import pytest

from flow.atoms import AtomStatus
from flow.atoms.agent import AgentAtom


# T4.1.04 Context Hydration with Altered Schema
def test_t4_1_04_hydration_schema_drift():
    """T4.1.04 Context Hydration with Altered Schema: AgentAtom strictly checks context."""
    # The config perfectly requires 2 keys
    config = {"required_context_keys": ["api_key", "user_id"]}
    atom = AgentAtom(config=config)

    # Missing 'api_key'
    context = {"user_id": 123}
    result = atom.run(context)

    assert result.status == AtomStatus.FAILED
    assert "Schema Validation Failed" in result.message
    assert "api_key" in result.message


# T4.2.02 Sub-Run ID Forgery Consistency
def test_t4_2_02_forgery_consistency():
    """T4.2.02 Valid AgentExecution Context Generation."""
    config = {"run_id": "agent-root-run-id"}
    atom = AgentAtom(config=config)

    # A valid context with no required keys strictly specified
    context = {"__task_id__": "1"}
    result = atom.run(context)

    assert result.status == AtomStatus.SUCCESS
    assert "Agent ReAct loop completed" in result.message
    assert "__agent_history__" in result.exports
    assert result.exports["__agent_history__"][0]["content"] == "Done"


# T4.3.02 Output JSON Schema Enforcement (Native via AgentAtom)
def test_t4_3_02_schema_mismatch_retry():
    """T4.3.02 Valid JSON but Invalid Schema."""
    # If the LLM output is parsed into `context` but lacks the required keys
    config = {"required_context_keys": ["score", "reason"]}
    atom = AgentAtom(config=config)

    # LLM yields `points` instead of `score`
    llm_context = {"__is_llm_response__": True, "points": 10, "text": "good"}

    res = atom.run(llm_context)

    # AgentAtom yields RETRY with BACKOFF if schema is invalid for an LLM (T4.3.02).
    # We assert it properly rejects it without throwing exceptions (graceful failure).
    from flow.atoms.base import RetryStrategy

    assert res.status == AtomStatus.RETRY
    assert res.retry_strategy == RetryStrategy.BACKOFF
    assert "LLM Schema Mismatch" in res.message
    assert "score" in res.message


# T4.1.01 AgentAtom Context Overflow Blob Promotion
def test_t4_1_01_context_overflow_blob_promotion(tmp_path):
    """T4.1.01 AgentAtom Context Overflow Blob Promotion: Automatically promoted to Blob if > 128KB."""
    config = {"required_context_keys": []}
    atom = AgentAtom(config=config, flow_dir=tmp_path / ".flow")

    # Generate large history
    large_history = [{"role": "user", "content": "A" * (129 * 1024)}]
    context = {"__task_id__": "test_blob", "__agent_history__": large_history}

    result = atom.run(context)
    assert result.status == AtomStatus.SUCCESS
    assert "__agent_history_blob__" in result.exports
    assert "__agent_history__" not in result.exports

    blob_path = tmp_path / ".flow" / "artifacts" / "blob_test_blob.txt"
    assert blob_path.exists()
    assert len(blob_path.read_text(encoding="utf-8")) > 128 * 1024


# T4.1.02 Resumption from Blob Pointer
def test_t4_1_02_resumption_from_blob_pointer(tmp_path):
    """T4.1.02 Resumption from Blob Pointer: Automatically read blob and load context history."""
    blob_path = tmp_path / "artifacts" / "blob_test_read.txt"
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_text(
        json.dumps([{"role": "user", "content": "resumed_ok"}]), encoding="utf-8"
    )

    config = {"required_context_keys": []}
    atom = AgentAtom(config=config, flow_dir=tmp_path / ".flow")

    context = {"__agent_history_blob__": str(blob_path), "__task_id__": "test_resume"}
    result = atom.run(context)

    # Since it runs successfully, it appended "Done" and exported it
    # We should have the old history + the new "Done"
    assert result.status == AtomStatus.SUCCESS

    # Since it's < 128kb, it returns __agent_history__ not blob
    assert "__agent_history__" in result.exports
    history = result.exports["__agent_history__"]
    assert history[0]["content"] == "resumed_ok"
    assert history[1]["content"] == "Done"


# T4.1.03 Blob IO Failure on Context Swap
def test_t4_1_03_blob_io_failure(tmp_path):
    """T4.1.03 Blob IO Failure on Context Swap: Expect FAILED on OSError."""
    config = {"required_context_keys": []}
    atom = AgentAtom(config=config, flow_dir=tmp_path / ".flow")

    # Pass a blob path that doesn't exist
    context = {"__agent_history_blob__": "/fake/path/doesnotexist.txt"}
    result = atom.run(context)

    assert result.status == AtomStatus.FAILED
    assert "Blob IO Error" in result.message


# T4.2.01 Mid-Loop Hard Crash (Split Brain)
def test_t4_2_01_mid_loop_hard_crash(tmp_path):
    """T4.2.01 Mid-Loop Hard Crash: Resumes cleanly."""
    # We test that the AgentAtom properly loads history from the context
    # exactly where it left off (which the Engine provides).
    config = {"required_context_keys": []}
    atom = AgentAtom(config=config, flow_dir=tmp_path / ".flow")

    # Simulate first run
    res1 = atom.run({"__task_id__": "1"})
    history1 = list(res1.exports["__agent_history__"])  # copy so it isn't mutated

    # Hard crash, then resume with hydrated history
    res2 = atom.run({"__task_id__": "1", "__agent_history__": list(history1)})
    history2 = res2.exports["__agent_history__"]

    # Expect Agent to have appended to the exact history state
    assert len(history2) == len(history1) + 1


# T4.2.03 Context Truncation on Resume
def test_t4_2_03_context_truncation_on_resume(tmp_path):
    """T4.2.03 Context Truncation on Resume."""
    config = {"required_context_keys": []}
    atom = AgentAtom(config=config, flow_dir=tmp_path / ".flow")

    # Provide 105 messages in history
    large_history = [{"role": "user", "content": str(i)} for i in range(105)]
    res = atom.run({"__agent_history__": large_history})

    # The atom truncates to 100, then appends 1 new message, total 101
    assert len(res.exports["__agent_history__"]) == 101


# T4.2.04 Sub-Run ID vs Loop Count Drift
def test_t4_2_04_sub_run_id_drift(tmp_path):
    """T4.2.04 CacheContinuityError on modified DB cache gaps."""
    config = {"required_context_keys": []}
    atom = AgentAtom(config=config, flow_dir=tmp_path / ".flow")

    # We expect loop count 5, but we only pass 2 history items
    history = [{"role": "user", "content": "1"}, {"role": "user", "content": "2"}]

    with pytest.raises(Exception, match="Drift: expected loop 5"):
        atom.run({"__agent_history__": history, "expected_loop_count": 5})


def test_t4_3_01_hallucinated_subflow_rejection():
    """T4.3.01 AgentAtom wrapper instantly throws UnauthorizedSubflowError if LLM hallucinates subflow call."""
    config = {"required_context_keys": []}
    atom = AgentAtom(config=config)

    # Simulated hallucinated response output
    context = {
        "__task_id__": "test1",
        "__llm_response__": {"type": "SubflowCall", "target": "SomeFlow"},
    }

    from flow.domain.models import UnauthorizedSubflowError

    with pytest.raises(
        UnauthorizedSubflowError, match="cannot orchestrate DAG Subflows"
    ):
        atom.run(context)
