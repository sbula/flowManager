import json
import time
from unittest.mock import MagicMock, patch

import pytest

from flow.domain.models import StateError, StatusTree, Task
from flow.engine.atoms import Atom, AtomResult, ManualInterventionAtom
from flow.engine.core import Engine
from flow.engine.models import CircuitBreakerError


class CrashingAtom(Atom):
    def run(self, context, **kwargs):
        raise RuntimeError("Boom")


class ExportAtom(Atom):
    def run(self, context, **kwargs):
        return AtomResult(True, "Success", exports={"a": 2, "b": 3})


def test_t3_01_smart_resume_pending(tmp_path):
    """T3.01 Smart Resume: Selects first pending task."""
    engine = Engine()

    # Setup Tree: [x] Task 1, [ ] Task 2, [ ] Task 3
    t1 = Task(id="1", name="Task 1", status="done", indent_level=0)
    t2 = Task(id="2", name="Task 2", status="pending", indent_level=0)
    t3 = Task(id="3", name="Task 3", status="pending", indent_level=0)

    tree = StatusTree(root_tasks=[t1, t2, t3])

    # Mock loading the tree
    with patch.object(engine, "load_status", return_value=tree):
        active = engine.find_active_task()
        assert active.id == "2"


def test_t3_04_crash_handling(tmp_path):
    """T3.04 Crash Handling: Catch Exception -> Mark ERROR -> Save."""
    engine = Engine()
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir()

    # Mock Persistence
    engine.persister = MagicMock()

    task = Task(id="1", name="[Crash] Test", status="active", indent_level=0)

    # Mock Dispatch to return CrashingAtom
    with patch.object(engine, "dispatch", return_value=CrashingAtom()):
        # Pre-Hydrate or Mock load_status to avoid RootNotFoundError
        # And ensure it returns a tree we can verify
        tree = StatusTree(root_tasks=[task])
        tree._reindex()
        engine.root = tmp_path  # Set root

        with patch.object(engine, "load_status", return_value=tree):
            # Run Task
            with pytest.raises(SystemExit):  # Should exit(1)
                engine.run_task(task)

            # Check impacts on TREE
            assert tree.find_task("1").status == "error"
            engine.persister.save.assert_called()


def test_t3_05_context_propagation(tmp_path):
    """T3.05 Context Propagation: Merge exports."""
    engine = Engine()
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir()
    engine.context = {"a": 1}

    task = Task(id="1", name="[Export] Test", status="active", indent_level=0)
    engine.root = tmp_path
    engine.persister = MagicMock()

    # Need status tree to update
    tree = StatusTree(root_tasks=[task])
    tree._reindex()

    with patch.object(engine, "dispatch", return_value=ExportAtom()):
        with patch.object(engine, "load_status", return_value=tree):
            engine.run_task(task)

    assert engine.context["a"] == 2
    assert engine.context["b"] == 3


def test_t3_02_circuit_breaker(tmp_path):
    """T3.02 Circuit Breaker: Task with retry_count > 3 -> FATAL."""
    engine = Engine()
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir()
    engine.root = tmp_path
    engine.persister = MagicMock()

    # Pre-existing lock with High Retry Count
    lock_file = engine.flow_dir / "intent.lock"
    lock_data = {"task_id": "1", "pid": 99999, "retry_count": 4}
    lock_file.write_text(json.dumps(lock_data), encoding="utf-8")

    task = Task(id="1", name="Fail Task", status="active", indent_level=0)
    tree = StatusTree(root_tasks=[task])
    tree._reindex()

    with patch.object(engine, "load_status", return_value=tree):
        # Should Exit due to Circuit Breaker
        with pytest.raises(SystemExit):
            engine.run_task(task)

        # Verify Status set to Error
        assert task.status == "error"
        engine.persister.save.assert_called()

        # Verify Lock Removed (Cleanup)
        assert not lock_file.exists()


def test_t3_09_multiple_active_tasks(tmp_path):
    """T3.09 Multiple Active Tasks: Validator or Engine Handling."""
    engine = Engine()

    # Status Tree with TWO active tasks
    t1 = Task(id="1", name="Active 1", status="active", indent_level=0)
    t2 = Task(id="2", name="Active 2", status="active", indent_level=0)

    tree = StatusTree(root_tasks=[t1, t2])
    tree._reindex()

    with patch.object(engine, "load_status", return_value=tree):
        # find_active_task should return FIRST or Error.
        # SpecT3.09 says: "Validator fails load OR Engine picks first."
        active = engine.find_active_task()

        # Current implementation likely picks first.
        assert active.id == "1"


def test_t3_11_lock_stale_pid_steal(tmp_path):
    """T3.11 Lock Stale PID (Zombie): Steal lock."""
    engine = Engine()
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir()
    engine.root = tmp_path
    engine.persister = MagicMock()

    # Stale Lock (> 30s old)
    lock_file = engine.flow_dir / "intent.lock"
    # Create stale timestamp
    old_time = time.time() - 40
    lock_data = {"task_id": "other", "pid": 99999, "timestamp": old_time}
    lock_file.write_text(json.dumps(lock_data), encoding="utf-8")

    task = Task(id="1", name="Stealer Task", status="active", indent_level=0)
    tree = StatusTree(root_tasks=[task])
    tree._reindex()

    with patch.object(engine, "dispatch", return_value=ExportAtom()):
        with patch.object(engine, "load_status", return_value=tree):
            # Should Succeed (Steal Lock)
            engine.run_task(task)

    # Verification
    assert not lock_file.exists()


def test_t3_03_write_ahead_recovery(tmp_path):
    """T3.03 Write-Ahead Log (Recovery): Intent lock exists -> Increment Retry."""
    engine = Engine()
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir()
    engine.root = tmp_path
    engine.persister = MagicMock()

    # Pre-existing lock with Low Retry Count
    lock_file = engine.flow_dir / "intent.lock"
    # Assume previous run failed, retries=2
    lock_data = {"task_id": "1", "pid": 99999, "retry_count": 2}
    lock_file.write_text(json.dumps(lock_data), encoding="utf-8")

    task = Task(id="1", name="Recover Task", status="active", indent_level=0)
    tree = StatusTree(root_tasks=[task])
    tree._reindex()

    # Mock Dispatch to Success
    with patch.object(engine, "dispatch", return_value=ExportAtom()):
        with patch.object(engine, "load_status", return_value=tree):
            # Mock getpid to be different from lock
            with patch("os.getpid", return_value=12345):
                engine.run_task(task)

    # Verify Success (Atom ran)
    # Verify Lock Removed
    assert not lock_file.exists()


def test_t3_12_system_context_immutable(tmp_path):
    """T3.12 System Context Immutable: Atom receives read-only context."""
    engine = Engine()
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir()
    engine.root = tmp_path
    engine.context = {"secure": "data"}

    class MaliciousAtom(Atom):
        def run(self, context, **kwargs):
            context["secure"] = "hacked"  # Should fail
            return AtomResult(True, "Hacked")

    task = Task(id="1", name="Hacker", status="active", indent_level=0)
    tree = StatusTree(root_tasks=[task])
    tree._reindex()
    engine.persister = MagicMock()

    with patch.object(engine, "dispatch", return_value=MaliciousAtom()):
        with patch.object(engine, "load_status", return_value=tree):
            # Should Crash (or handle error) because TypeError raised
            with pytest.raises(SystemExit):
                engine.run_task(task)

    # Verify context unchanged
    assert engine.context["secure"] == "data"


def test_t3_10_non_serializable_export(tmp_path):
    """T3.10 Non-Serializable Export: Engine rejects bad exports."""
    engine = Engine()
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir()
    engine.root = tmp_path
    engine.persister = MagicMock()

    class BadAtom(Atom):
        def run(self, context, **kwargs):
            # Return a file handle (non-serializable)
            return AtomResult(True, "Bad", exports={"file": open(__file__, "r")})

    task = Task(id="1", name="BadExport", status="active", indent_level=0)
    tree = StatusTree(root_tasks=[task])
    tree._reindex()

    with patch.object(engine, "dispatch", return_value=BadAtom()):
        with patch.object(engine, "load_status", return_value=tree):
            with pytest.raises(SystemExit):
                engine.run_task(task)

    # Verify Context NOT corrupted
    assert "file" not in engine.context
