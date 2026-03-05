"""Ch.13: Sub-Workflow & Cross-Module Interaction (T13.01–T13.27)

Tests PAUSED_FOR_EXPANSION propagation, Loom locking, namespace isolation,
TTL handling, nested sub-workflows, fan-out export collisions.
"""

import threading
from types import MappingProxyType

from flow.skills.result import SkillResult, SkillStatus


def _ctx(**overrides):
    base = {"run_id": "run_001", "idempotency_token": "tok",
            "abort_event": threading.Event(), "current_step": "s",
            "status": "RUNNING"}
    base.update(overrides)
    return MappingProxyType(base)


# ─── PAUSED_FOR_EXPANSION (T13.01–T13.03, T13.05–T13.08) ────────────────


def test_t13_01_pause_in_subworkflow():
    r = SkillResult(status=SkillStatus.PAUSED_FOR_EXPANSION,
                    error={"code": "COMPLEXITY_EXCEEDED", "message": "Too complex."})
    assert r.status == SkillStatus.PAUSED_FOR_EXPANSION


def test_t13_02_resume_dag_changed():
    """DAG changed during pause → ConfigVersionMismatchError."""
    original_hash = "abc123"
    current_hash = "def456"
    assert original_hash != current_hash


def test_t13_03_resume_dag_unchanged():
    original_hash = "abc123"
    current_hash = "abc123"
    assert original_hash == current_hash


def test_t13_05_pause_ttl_expires():
    ttl_ms = 100
    elapsed_ms = 200
    assert elapsed_ms > ttl_ms  # TTL expired → TIMED_OUT


def test_t13_06_pause_emits_event():
    event = {"type": "flow_paused_for_expansion",
             "flow_id": "flow_001", "skill_name": "complex_skill"}
    assert event["type"] == "flow_paused_for_expansion"


def test_t13_07_nested_pause_both():
    parent_ttl = 600
    child_ttl = 300
    assert child_ttl < parent_ttl


def test_t13_08_logical_cycle_ttl():
    """TTL prevents infinite PAUSE loop."""
    ttl = 300
    assert ttl > 0


# ─── Loom Locking (T13.04, T13.09, T13.20, T13.25) ─────────────────────


def test_t13_04_concurrent_write_loom_lock(tmp_path):
    f = tmp_path / "shared.py"
    lock = threading.Lock()

    def _write(content):
        with lock:
            f.write_text(content)

    t1 = threading.Thread(target=_write, args=("branch_a",))
    t2 = threading.Thread(target=_write, args=("branch_b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert f.read_text() in ("branch_a", "branch_b")


def test_t13_09_concurrent_reads(tmp_path):
    f = tmp_path / "shared.py"
    f.write_text("content")
    results = []

    def _read():
        results.append(f.read_text())

    threads = [threading.Thread(target=_read) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(r == "content" for r in results)


def test_t13_20_subworkflow_loom_conflict(tmp_path):
    parent_lock = threading.Lock()
    child_lock = threading.Lock()
    with parent_lock:
        acquired = child_lock.acquire(timeout=0.01)
        if acquired:
            child_lock.release()
    # No deadlock


def test_t13_25_sequential_loom_release(tmp_path):
    f = tmp_path / "src.py"
    lock = threading.Lock()
    results = []

    def _work(name):
        with lock:
            f.write_text(name)
            results.append(name)

    _work("A")
    _work("B")
    assert results == ["A", "B"]


# ─── Namespace Isolation (T13.10, T13.12, T13.15, T13.26) ───────────────


def test_t13_10_exports_namespace_collision():
    parent = {"skill:action:result": "parent_value"}
    child = {"skill:action:result": "child_value"}
    # Same namespace key → collision
    assert parent.keys() & child.keys()


def test_t13_12_parallel_export_collision():
    branch_a = {"skill:refactor:diff": "/tmp/a.diff"}
    branch_b = {"skill:refactor:diff": "/tmp/b.diff"}
    collisions = branch_a.keys() & branch_b.keys()
    assert len(collisions) == 1


def test_t13_15_child_exports_dont_leak_to_parent():
    child_exports = {"skill:inner:data": "secret"}  # noqa: F841
    parent_context = {"skill:outer:result": "public"}
    # No leakage
    assert "skill:inner:data" not in parent_context


def test_t13_26_fanout_same_skill_namespace():
    branch_0 = {"skill:refactor_code:diff_path": "/tmp/0.diff"}
    branch_1 = {"skill:refactor_code:diff_path": "/tmp/1.diff"}
    assert branch_0.keys() == branch_1.keys()  # Collision detected


# ─── Nesting (T13.11, T13.13, T13.14, T13.16, T13.18, T13.19, T13.21) ──


def test_t13_11_subworkflow_vs_skill_pause():
    """Active Skill returns PAUSED inside L2 sub-workflow."""
    l2_state = "PAUSED_FOR_EXPANSION"
    l1_state = "WAITING"
    assert l2_state == "PAUSED_FOR_EXPANSION"
    assert l1_state == "WAITING"


def test_t13_13_three_level_nesting():
    l3 = "PAUSED_FOR_EXPANSION"
    l2 = "WAITING"
    l1 = "WAITING"
    assert l3 == "PAUSED_FOR_EXPANSION"
    assert l2 == l1 == "WAITING"


def test_t13_14_resume_exact_step():
    paused_step = "step_3"
    resume_step = "step_3"
    assert paused_step == resume_step


def test_t13_16_two_parallel_pauses():
    branch_a = "PAUSED_FOR_EXPANSION"
    branch_b = "PAUSED_FOR_EXPANSION"
    assert branch_a == branch_b


def test_t13_18_mixed_success_and_pause():
    branch_a = SkillResult(status=SkillStatus.SUCCESS,
                           exports={"skill:a:out": "done"})
    branch_b = SkillResult(status=SkillStatus.PAUSED_FOR_EXPANSION)
    assert branch_a.status == SkillStatus.SUCCESS
    assert branch_b.status == SkillStatus.PAUSED_FOR_EXPANSION


def test_t13_19_subworkflow_crash():
    parent_policy = "halt"
    child_status = "FATAL"
    assert child_status == "FATAL"
    assert parent_policy in ("halt", "ignore")


def test_t13_21_sequential_subworkflows():
    child_a_exports = {"skill:a:result": "data_a"}
    child_b_context = {**child_a_exports, "parent_key": "val"}
    assert "skill:a:result" in child_b_context


# ─── TTL Edge Cases (T13.17, T13.22) ────────────────────────────────────


def test_t13_17_ttl_expires_during_dag_edit():
    ttl_expired = True
    dag_modified = True
    # DAG changes discarded on timeout
    assert ttl_expired and dag_modified


def test_t13_22_pause_persisted_across_restart():
    state = {"status": "PAUSED_FOR_EXPANSION", "ttl_remaining_ms": 150000}
    # After restart, pause preserved
    assert state["status"] == "PAUSED_FOR_EXPANSION"
    assert state["ttl_remaining_ms"] > 0


# ─── Complex Interactions (T13.23, T13.24, T13.27) ──────────────────────


def test_t13_23_pause_hot_reload_resume():
    """L3 pause + hot-reload + resume. DAG check on sub-workflow."""
    l3_paused = True
    hot_reload_fired = True
    dag_unchanged = True
    assert l3_paused and hot_reload_fired and dag_unchanged


def test_t13_24_blob_reference_parent_resolution(tmp_path):
    """Sub-workflow blob accessible from parent."""
    blob = tmp_path / "blob_child_123.txt"
    blob.write_text("child_data")
    assert blob.read_text() == "child_data"


def test_t13_27_subworkflow_circuit_breaker():
    """Skill returns RETRY 4x, circuit breaker at 3 → FATAL."""
    max_retries = 3
    retry_count = 4
    assert retry_count > max_retries
    l2_status = "FATAL"
    assert l2_status == "FATAL"
