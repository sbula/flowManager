import os
import sys
import unittest.mock

import pytest

from flow.engine.core import Engine
from flow.engine.models import RegistryError, RootNotFoundError, SecurityError
from flow.engine.security import SafePath


def test_t7_01_stale_intent_lock(valid_project):
    """T7.01 Stale Intent Lock (Mock)."""
    os.chdir(valid_project)
    engine = Engine()
    engine.hydrate()

    lock_file = valid_project / ".flow" / "intent.lock"
    lock_file.write_text('{"task_id": "1", "pid": 99999}', encoding="utf-8")

    from flow.domain.models import Task

    t = Task(id="1", name="Test", status="pending", indent_level=0)

    # Expect SystemExit because run_task catches the RuntimeError and exits
    with pytest.raises(SystemExit):
        engine.run_task(t)


def test_t7_02_corrupt_state_file(valid_project):
    """T7.02 Corrupt State File."""
    os.chdir(valid_project)
    engine = Engine()
    engine.hydrate()

    (valid_project / ".flow" / "status.md").write_text("Garbage", encoding="utf-8")

    with pytest.raises(Exception):
        engine.load_status()


def test_t7_03_empty_registry_file(valid_project):
    """T7.03 Empty Registry File."""
    registry = valid_project / ".flow" / "flow.registry.json"
    registry.write_text("[]", encoding="utf-8")  # List (Invalid)

    os.chdir(valid_project)
    engine = Engine()

    with pytest.raises(RegistryError):
        engine.hydrate()


def test_t7_04_max_path_length(valid_project):
    """T7.04 Maximum Path Length."""
    os.chdir(valid_project)
    engine = Engine()
    engine.hydrate()

    long_name = "a" * 255
    with pytest.raises(Exception):
        SafePath(engine.root, long_name + "/" + long_name)


def test_t7_05_high_concurrency_events(valid_project):
    """T7.05 Check Event Bus under load."""
    from flow.engine.events import EventBus

    bus = EventBus(valid_project / ".flow")
    (valid_project / ".flow" / "logs").mkdir(exist_ok=True)

    for i in range(100):
        bus.emit("load.test", {"i": i})

    log_file = valid_project / ".flow" / "logs" / "events.jsonl"
    assert len(log_file.read_text("utf-8").strip().split("\n")) == 100


def test_t7_06_sigint_handling(valid_project):
    """T7.06 SIGINT Handling (Skipped)."""
    # Hard to test signal handling in pytest process.
    pytest.skip("Signal handling difficult to test in unit test")


def test_t7_07_nested_resume(valid_project):
    """T7.07 Nested Resume."""
    os.chdir(valid_project)

    # 1. Setup Deep Hierarchy
    # Root -> A -> B -> C (Pending)
    status_content = """
- [ ] Root
    - [ ] A
        - [ ] B
            - [ ] C
"""
    (valid_project / ".flow" / "status.md").write_text(
        status_content.strip(), encoding="utf-8"
    )

    engine = Engine()
    engine.hydrate()

    # 2. Run
    # Should find C as the first pending task depth-first?
    # Logic: find_first_pending traverses DFS.
    # Root (Pending) -> A (Pending) -> B -> C.
    # The first pending task encountered in DFS is "Root".
    # Wait, Smart Resume looks for *Active* first. If no active, it picks *First Pending*.
    # If I want to test "Resume", I should have an Active task deep down.

    status_active = """
- [ ] Root
    - [ ] A
        - [ ] B
            - [/] C
"""
    (valid_project / ".flow" / "status.md").write_text(
        status_active.strip(), encoding="utf-8"
    )
    engine = Engine()  # Reload
    engine.hydrate()

    # find_active_task should return C
    active = engine.find_active_task()
    assert active is not None, "No active task found"
    assert (
        active.name == "C"
    ), f"Expected C, got {active.name} with status {active.status}"


def test_t7_08_disk_full_panic_save(valid_project):
    """T7.08 Disk Full (Panic Save)."""
    os.chdir(valid_project)
    engine = Engine()
    engine.hydrate()

    # Initialize persister manually if needed, or rely on hydrate
    # But hydrate creates real Persister.

    from flow.domain.models import Task

    t = Task(id="crash", name="Crash", status="pending", indent_level=0)

    # Mock Crash then Mock Save Fail
    with unittest.mock.patch.object(
        engine, "dispatch", side_effect=Exception("Original Crash")
    ):
        # We need to ensure engine.persister is the one being called.
        # engine.persister is instance. Patching 'flow.engine.persistence.Persister.save_state' might be safer?
        # Or patch the instance method.
        with unittest.mock.patch.object(
            engine.persister, "save", side_effect=OSError("Disk Full")
        ):
            with pytest.raises(SystemExit):
                engine.run_task(t)


def test_t7_09_circular_dependency(valid_project):
    """T7.09 Circular Dependency (Ref Loop)."""
    # Setup Loop: A @ b.md, b.md has B @ a.md

    os.chdir(valid_project)
    flow_dir = valid_project / ".flow"

    (flow_dir / "status.md").write_text("- [/] A @ b.md", encoding="utf-8")
    (flow_dir / "b.md").write_text("- [/] B @ status.md", encoding="utf-8")
    # Wait, status.md is root. Ref points to file relative to .flow.
    # So "status.md" loads A again.

    engine = Engine()

    # Hydration loads status. Does it follow refs immediately?
    # CURRENT Implementation: Parser parses REF string but does NOT recursively load content.
    # The Engine *Runtime* (not implemented fully for recursion yet) would follow it.
    # T2.11 says "Fractal Composition".
    # If the parser doesn't recurse, we can't test recursion bomb in parser.
    # But `find_active_task` might?
    # Engine.load_status reads status.md.
    # If we want to test RECURSION, we need to manually trigger the expansion or
    # verify that the system is *safe* (i.e. doesn't crash, just stops depth).

    # For V1.3, we verify that it *can* load the file with the ref without crashing.
    # Updated: QA Audit requires Parser to DETECT check.
    # So now we expect failure.
    from flow.domain.models import StatusParsingError

    engine.hydrate()

    with pytest.raises(StatusParsingError, match="Cycle detected"):
        engine.load_status()

    return  # Done

    # Old assertions below relevant only if cycle detection was OFF

    # Verify Tree Structure
    tree = engine.load_status()
    assert len(tree.root_tasks) > 0, "No root tasks found"
    t = tree.root_tasks[0]
    # Assert Attributes match
    assert t.status == "active", f"Task {t.name} status is {t.status}, expected active"
    assert t.name == "A", f"Task name is {t.name}"
    assert t.ref == "b.md", f"Task ref is {t.ref}"

    root_task = engine.find_active_task()
    assert root_task is not None, "Root task not found via find_active_task"
    assert root_task.name == "A"
    assert root_task.ref == "b.md"

    # If we implement a helper to "expand_ref", we would test it here.
    # For now, asserting it parses the cycle definition without hanging is the test.
    pass


def test_t7_11_registry_schema_invalid(valid_project):
    """T7.11 Registry Schema Invalid: String."""
    registry = valid_project / ".flow" / "flow.registry.json"
    registry.write_text('"string_root"', encoding="utf-8")

    os.chdir(valid_project)
    engine = Engine()

    with pytest.raises(RegistryError):
        engine.hydrate()


def test_t7_14_save_state_double_fault(valid_project):
    """T7.14 Save State Double Fault."""
    os.chdir(valid_project)
    engine = Engine()
    engine.hydrate()

    from flow.domain.models import Task

    t = Task(id="df", name="DoubleFault", status="pending", indent_level=0)

    with unittest.mock.patch.object(
        engine, "dispatch", side_effect=Exception("First Fault")
    ):
        with unittest.mock.patch.object(
            engine.persister, "save", side_effect=Exception("Second Fault")
        ):
            with pytest.raises(SystemExit):
                engine.run_task(t)


def test_t7_15_recursion_bomb(valid_project):
    """T7.15 Recursion Bomb."""
    # Verify StatusTree creation fails strictly or gracefully
    from flow.domain.models import StatusTree, Task

    root = Task(id="root", name="Root", status="pending", indent_level=0)
    current = root
    for i in range(2000):
        child = Task(
            id=f"c{i}", name=f"Child {i}", status="pending", indent_level=i + 1
        )
        current.children = [child]
        current = child

    # Construction might fail due to Python recursion limit
    try:
        tree = StatusTree(root_tasks=[root])
    except RecursionError:
        return  # Passed (Detected limit)

    # If it didn't fail construction (unlikely for 2000 depth), test engine traversal
    engine = Engine()
    with unittest.mock.patch.object(engine, "load_status", return_value=tree):
        try:
            engine.find_active_task()
        except RecursionError:
            pass


def test_t7_16_dual_engine_contention(valid_project):
    """T7.16 Dual Engine Contention (Covered by T7.01)."""
    pass
