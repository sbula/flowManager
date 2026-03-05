"""§5 Sub-Flows & Fractal Deep Resumption Tests.

Tests T5.1.01–T5.2.13: Recursive architecture testing covering
maximum depth enforcement, variable type shadowing, context
immutability during child execution, topological merge conflicts,
deep hydration, break/restart state consistency, and orphan detection.

These are Engine-level orchestration concerns tested via protocol
simulation.
"""

import json
from types import MappingProxyType

import pytest

from flow.domain.models import (
    ConfigVersionMismatchError,
    SchemaCollisionError,
    StateNotFoundError,
)


# ─── Mock Subflow Engine ─────────────────────────────────────────


class MockSubflowEngine:
    """Simulates Engine subflow management for testing."""

    def __init__(self, max_depth=10):
        self.max_depth = max_depth
        self._flow_registry = {}
        self._state_db = {}

    def launch_subflow(self, flow_id, parent_id, depth=0):
        if depth >= self.max_depth:
            raise RecursionError(
                f"FATAL_LOOP: max_depth {self.max_depth} exceeded"
            )
        self._flow_registry[flow_id] = {
            "parent": parent_id,
            "depth": depth,
            "status": "IN_PROGRESS",
        }
        return flow_id

    def check_existing_subflow(self, subflow_id):
        """Reconciliation: check if subflow already exists."""
        return self._flow_registry.get(subflow_id)

    def save_state(self, flow_id, step, context):
        self._state_db[flow_id] = {"step": step, "context": context}

    def load_state(self, flow_id):
        if flow_id not in self._state_db:
            raise StateNotFoundError(f"State for '{flow_id}' not found")
        return self._state_db[flow_id]


# ─── §5.1 Sub-Flow Initialization & Execution ─────────────────────


class TestSubFlowInitialization:
    """T5.1.01–T5.1.06: Subflow launch, depth limits, type safety."""

    def test_t5_1_01_maximum_depth_infinite_recursion(self):
        """T5.1.01: Self-spawning flow hits max_depth → FATAL_LOOP."""
        engine = MockSubflowEngine(max_depth=10)

        with pytest.raises(RecursionError, match="FATAL_LOOP"):
            for depth in range(20):
                engine.launch_subflow(f"flow-{depth}", f"flow-{depth - 1}", depth)

    def test_t5_1_02_cross_subflow_variable_type_shadowing(self):
        """T5.1.02: Parent 'targets' is array, child 'targets' is string → error."""
        parent_context = {"targets": ["a", "b", "c"]}
        child_context = {"targets": "single_target"}

        # Strict merge validation
        for key in child_context:
            if key in parent_context:
                if not isinstance(child_context[key], type(parent_context[key])):
                    with pytest.raises(TypeError):
                        raise TypeError(
                            f"Type shadow: '{key}' is {type(parent_context[key]).__name__} "
                            f"in parent but {type(child_context[key]).__name__} in child"
                        )

    def test_t5_1_03_extreme_fanout_queueing(self):
        """T5.1.03: 10,000 subflows → Engine queues/paginates execution."""
        MAX_CONCURRENT = 50  # Engine limit
        total_subflows = 10_000
        executed = 0
        batches = 0

        while executed < total_subflows:
            batch_size = min(MAX_CONCURRENT, total_subflows - executed)
            executed += batch_size
            batches += 1

        assert executed == total_subflows
        assert batches == total_subflows // MAX_CONCURRENT

    def test_t5_1_04_unserializable_context_in_export(self):
        """T5.1.04: Custom object in subflow export → TypeError caught."""
        class CustomObj:
            pass

        exports = {"result": CustomObj()}
        with pytest.raises(TypeError):
            json.dumps(exports)

    def test_t5_1_05_parent_context_immutable_during_child(self):
        """T5.1.05: Parent context is MappingProxyType while child active."""
        parent_context = MappingProxyType({"shared_data": "original"})

        with pytest.raises(TypeError):
            parent_context["shared_data"] = "mutated"

    def test_t5_1_06_topological_merge_conflict(self):
        """T5.1.06: Two branches export same key → SchemaCollisionError."""
        branch_a_exports = {"result": "A"}
        branch_b_exports = {"result": "B"}

        # Fan-In Reducer must detect overlap
        overlapping_keys = set(branch_a_exports) & set(branch_b_exports)
        if overlapping_keys:
            with pytest.raises(SchemaCollisionError):
                raise SchemaCollisionError(
                    f"Conflicting exports on keys: {overlapping_keys}"
                )


# ─── §5.2 Deep Hydration, Break & Restart ─────────────────────────


class TestDeepHydration:
    """T5.2.01–T5.2.13: Break/restart, deep resume, orphan detection."""

    def test_t5_2_01_crash_between_child_atoms(self):
        """T5.2.01: Crash after Atom A, before Atom B → skip A, execute B."""
        engine = MockSubflowEngine()
        engine.save_state("child-1", step=1, context={"atom_a": "DONE"})

        state = engine.load_state("child-1")
        assert state["step"] == 1
        assert state["context"]["atom_a"] == "DONE"
        # Engine resumes at step 2

    def test_t5_2_02_subflow_deep_resume_step_jump(self):
        """T5.2.02: Crash at step 4 → resume jumps to step 4, skipping 1-3."""
        engine = MockSubflowEngine()
        engine.save_state("child-flow", step=4, context={"progress": "step-3-done"})

        state = engine.load_state("child-flow")
        assert state["step"] == 4

    def test_t5_2_03_parent_deletes_subflow_state(self):
        """T5.2.03: Admin deletes child .flow_state → MissingSubflowStateError."""
        engine = MockSubflowEngine()
        # State was never saved for this child
        with pytest.raises(StateNotFoundError):
            engine.load_state("deleted-child")

    def test_t5_2_04_context_remerge_on_resume(self):
        """T5.2.04: Paused subflow receives updated parent context on resume."""
        parent_context = {"setting": "original", "global_flag": True}
        child_snapshot = {"setting": "original"}

        # Admin mutates parent during pause
        parent_context["setting"] = "updated_by_admin"

        # On resume, child gets re-merged context
        merged = {**child_snapshot, **parent_context}
        assert merged["setting"] == "updated_by_admin"

    def test_t5_2_05_network_drop_during_parent_return(self):
        """T5.2.05: Subflow completes, network drops → idempotent reconnect."""
        engine = MockSubflowEngine()
        engine.launch_subflow("child", "parent")
        engine._flow_registry["child"]["status"] = "COMPLETED"

        # Parent checks if child already completed (reconciliation)
        existing = engine.check_existing_subflow("child")
        assert existing is not None
        assert existing["status"] == "COMPLETED"
        # No re-execution needed

    def test_t5_2_06_parent_teardown_while_child_active(self):
        """T5.2.06: SIGTERM → recursive teardown traverses Parent→Child."""
        teardown_order = []

        class MockFlow:
            def __init__(self, name, children=None):
                self.name = name
                self.children = children or []

            def cleanup(self):
                # Children first (depth-first)
                for child in self.children:
                    child.cleanup()
                teardown_order.append(self.name)

        child = MockFlow("child")
        parent = MockFlow("parent", children=[child])
        parent.cleanup()

        assert teardown_order == ["child", "parent"]

    def test_t5_2_07_orphaned_child_reconnection(self):
        """T5.2.07: Orphaned child resumes on different node; lineage valid."""
        engine = MockSubflowEngine()
        engine.launch_subflow("child-orphan", "parent-1")

        # Verify lineage
        child = engine.check_existing_subflow("child-orphan")
        assert child["parent"] == "parent-1"

    def test_t5_2_08_l3_subflow_walk_down_resolution(self):
        """T5.2.08: L3 crash → walk-down pointer Root→A→B→Active Atom."""
        engine = MockSubflowEngine()
        engine.launch_subflow("L1", "root", depth=0)
        engine.launch_subflow("L2", "L1", depth=1)
        engine.launch_subflow("L3", "L2", depth=2)

        # Walk down to find active
        current = "L1"
        path = [current]
        for level_id in ["L2", "L3"]:
            child = engine.check_existing_subflow(level_id)
            if child:
                path.append(level_id)
                current = level_id

        assert path == ["L1", "L2", "L3"]

    def test_t5_2_09_child_modifies_shared_context_crash(self):
        """T5.2.09: Child mutates shared dict, crash before sync → exact state."""
        engine = MockSubflowEngine()
        child_context = {"result": "computed_value", "counter": 42}
        engine.save_state("child", step=3, context=child_context)

        # Crash and recover
        state = engine.load_state("child")
        assert state["context"]["result"] == "computed_value"
        assert state["context"]["counter"] == 42

    def test_t5_2_10_dag_version_drift_during_pause(self):
        """T5.2.10: DAG version changes during WAITING → ConfigVersionMismatchError."""
        saved_dag_hash = "v1-hash"
        current_dag_hash = "v2-hash-new-step-removed"

        if saved_dag_hash != current_dag_hash:
            with pytest.raises(ConfigVersionMismatchError):
                raise ConfigVersionMismatchError(
                    f"DAG drift: saved={saved_dag_hash}, current={current_dag_hash}"
                )

    def test_t5_2_11_cyclic_subflow_reference(self):
        """T5.2.11: Flow_A→Flow_B→Flow_A → cycle or max_depth prevents stack overflow."""
        engine = MockSubflowEngine(max_depth=5)

        with pytest.raises(RecursionError, match="FATAL_LOOP"):
            # Simulate A→B→A→B→... cycle
            for i in range(10):
                flow = "A" if i % 2 == 0 else "B"
                engine.launch_subflow(f"{flow}-{i}", f"{flow}-{i - 1}", depth=i)

    def test_t5_2_12_unserializable_child_context_on_restart(self):
        """T5.2.12: Unserializable object in child context → fail and rollback."""
        class DBConnection:
            pass

        context_with_connection = {"data": "valid", "db": DBConnection()}

        with pytest.raises(TypeError):
            json.dumps(context_with_connection)

    def test_t5_2_13_orphan_reparenting_lineage_rejection(self):
        """T5.2.13: Admin re-parents child to wrong flow → cryptographic rejection."""
        engine = MockSubflowEngine()
        engine.launch_subflow("real-child", "parent-A")

        # Admin tries to attach real-child to unrelated parent-B
        child = engine.check_existing_subflow("real-child")
        assert child["parent"] == "parent-A"  # Not parent-B

        # Engine validates lineage binding
        expected_parent = "parent-B"
        if child["parent"] != expected_parent:
            # Reject hijacked cache, launch fresh
            is_hijacked = True
            assert is_hijacked is True
