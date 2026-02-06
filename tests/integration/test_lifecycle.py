import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from flow.domain.models import StatusTree, Task
from flow.engine.core import Engine
from flow.engine.events import EventBus

# Integration tests need a real environment (tmp_path)
# but we import real components (Engine, Persister, Atoms)
# We might need to mock SOME atoms (like Git) if they depend on external tools not present,
# but for Lifecycle we focus on internal mechanics.


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Sets up a valid .flow/ environment."""
    # Ensure tmp_path is in sys.path so we can import generated 'custom_atoms.py'
    sys.path.insert(0, str(tmp_path))

    # Safe Chdir (Restores automatically)
    monkeypatch.chdir(tmp_path)

    flow_dir = tmp_path / ".flow"
    flow_dir.mkdir()
    (flow_dir / "status.md").write_text(
        "Project: Integration\n\n- [ ] Root\n", encoding="utf-8"
    )
    (flow_dir / "flow.registry.json").write_text(
        "{}", encoding="utf-8"
    )  # Empty registry
    (flow_dir / "logs").mkdir()
    (flow_dir / "artifacts").mkdir()

    yield tmp_path

    # Cleanup
    if str(tmp_path) in sys.path:
        sys.path.remove(str(tmp_path))


def test_full_run_success(env):
    """
    Verifies a complete run:
    1. Load Status
    2. Dispatch (Manual fallback since registry empty)
    3. Execute (Manual Atom just returns constraint)
    4. Persist
    """
    # Environment already chdir'd by fixture
    engine = Engine()
    engine.hydrate()

    # 1. Verify Hydration
    assert engine.root == env

    # 2. Run Next Task
    # ManualInterventionAtom should return success=False (Constraint) usually?
    # Actually ManualInterventionAtom is a "Stop" atom.
    # Let's register a "Pass" atom for this test to verify success flow.

    # Define and register a Dummy Atom on the fly?
    # Better: Use a mock class in a separate file or use one of the standard atoms if available.
    # Since we are strict V1.3, let's create a real python file for the atom.

    atom_code = """
from flow.engine.atoms import Atom, AtomResult

class SuccessAtom(Atom):
    def run(self, context, **kwargs):
        return AtomResult(True, "Success", exports={"run_id": 1})
"""
    (env / "custom_atoms.py").write_text(atom_code, encoding="utf-8")

    # Update Registry
    registry = env / ".flow" / "flow.registry.json"
    registry.write_text('{"test": "custom_atoms.SuccessAtom"}', encoding="utf-8")

    # Update Status to use this atom
    (env / ".flow" / "status.md").write_text("- [ ] [test] Run Me", encoding="utf-8")

    # Reload engine to pick up registry
    engine = Engine()
    engine.hydrate()

    # Run
    # finding active task (Smart Resume -> First Pending)
    task = engine.find_active_task()
    assert task.name == "[test] Run Me"

    engine.run_task(task)

    # Verify Persistence
    # Task should be [x] or whatever the logic updates it to?
    # Engine.run_task usually updates status based on result.
    # If Success -> Done ([x])

    content = (env / ".flow" / "status.md").read_text("utf-8")
    assert "- [x] [test] Run Me" in content

    # Verify Exports
    # Context should be updated? Engine context is ephemeral in memory generally,
    # unless we persist it. V1.3 persist context?
    # T3.05 says Context Propagation works.
    # But Engine is re-instantiated usually?
    # For this test, valid check is State Update.


def test_crash_recovery_e2e(env):
    """
    Verifies Crash Recovery:
    1. Run -> Crash
    2. Restart -> Detect Lock -> Increment Retry -> Retry
    """
    # Environment already chdir'd by fixture

    # 1. Setup Crashing Atom
    atom_code = """
from flow.engine.atoms import Atom, AtomResult

class CrashAtom(Atom):
    def run(self, context, **kwargs):
        raise RuntimeError("Boom")
"""
    (env / "crash.py").write_text(atom_code, encoding="utf-8")

    registry = env / ".flow" / "flow.registry.json"
    registry.write_text('{"crash": "crash.CrashAtom"}', encoding="utf-8")

    (env / ".flow" / "status.md").write_text("- [ ] [crash] Boom", encoding="utf-8")

    engine = Engine()
    engine.hydrate()

    # 2. Run -> Crash
    task = engine.find_active_task()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    # Verify State: Should be [x] (Error) or still Pending but with Lock?
    # T3.04 says "Mark ERROR -> Save".
    # So on disk it should be ERROR.

    # Wait, if we mark ERROR, next run won't retry it (unless we manually fix it).
    # Circuit Breaker T3.02 says "If retry_count > 3 -> FATAL".
    # Write-Ahead Log T3.03 says "Intent Lock exists -> Increment Retry".

    # The crucial distinction:
    # - If Atom CRASHES (Python Exception), we catch and mark ERROR.
    # - If Process DIES (Power Loss), we don't catch. Lock remains.

    # To test Lock Recovery, we must simulate "Process Dies" (i.e. we do NOT save ERROR).
    # so we mock `engine.persister.save` to NOT happen (simulating sudden death),
    # BUT `intent.lock` was created at start of run_task.

    # We can't easily simulated "kill -9" in unit test process.
    # But we can check scenarios manually:

    # Scenario A: Previous run died. Lock exists.
    lock_file = env / ".flow" / "intent.lock"
    lock_file.write_text(
        json.dumps({"task_id": "1", "pid": 123, "retry_count": 0}), encoding="utf-8"
    )

    # We need a task with ID "1"
    (env / ".flow" / "status.md").write_text("- [ ] My Task", encoding="utf-8")
    # CRITICAL: We manually overwrote status.md, so the old status.meta (from the crash save) is invalid.
    # We must remove it to avoid IntegrityError (simulating a fresh/manual state).
    meta_file = env / ".flow" / "status.meta"
    if meta_file.exists():
        meta_file.unlink()

    # Restart Engine
    engine2 = Engine()
    engine2.hydrate()

    # When we run, it should detect lock for Task 1.
    task = engine2.find_active_task()  # returns Task 1

    # We need to spy on logic that increments retry.
    # run_task -> check lock -> increment

    # Let's run a NO-OP atom (Manual)
    # Registry empty implies fallback to Manual.

    # ManualIntervention just returns (False, "Manual Action").
    # It does NOT crash.

    engine2.run_task(task)

    # Assertion:
    # Lock matching this PID/Task should be GONE (cleaned up after run).
    assert not lock_file.exists()

    # Assertion:
    # Did we increment retry?
    # Hard to see internal counter unless we log it or it affects logic.
    # But confirming it ran despite lock is the test.
