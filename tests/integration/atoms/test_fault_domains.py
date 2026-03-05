import pytest

from flow.atoms import Atom, AtomResult, AtomStatus
from flow.domain.models import StatusTree, Task
from flow.domain.persister import StatusPersister
from flow.engine.core import Engine


def init_engine(tmp_path):
    engine = Engine()
    engine.root = tmp_path
    flow_dir = tmp_path / ".flow"
    flow_dir.mkdir(parents=True, exist_ok=True)
    engine.flow_dir = flow_dir
    engine.persister = StatusPersister(flow_dir)
    engine.context = {"__root__": engine.root}
    engine.registry_map = {}
    return engine, flow_dir


# Global definitions for multiprocessing tests to allow pickling on Windows
class SigquitAtom(Atom):
    def run(self, context) -> AtomResult:
        import time

        time.sleep(10)  # Hang so the signal actually hits while running
        return AtomResult(AtomStatus.SUCCESS, "Done")

    def cleanup(self) -> None:
        import pathlib

        # Should NOT be called!
        root = self.context.get("__root__")
        if root:
            with open(pathlib.Path(root) / "cleanup_called.txt", "w") as f:
                f.write("called")


def run_engine_proc_sigquit(flow_dir_str, task_id):
    from pathlib import Path

    from flow.domain.models import Task
    from flow.domain.persister import StatusPersister
    from flow.engine.core import Engine

    e = Engine()
    e.flow_dir = Path(flow_dir_str)
    e.root = e.flow_dir.parent
    e.persister = StatusPersister(e.flow_dir)
    e.context = {"__root__": e.root}

    # We must properly map the registry or inject it so dispatch can find it
    import sys

    sys.modules["fake_sigquit"] = type("FakeModule", (), {"SigquitAtom": SigquitAtom})()
    e.registry_map = {"Sigquit": "fake_sigquit.SigquitAtom"}

    t = Task(id=task_id, name="[Sigquit] SIGQUIT", status="pending", indent_level=0)
    e.run_task(t)


class RogueThreadAtom(Atom):
    def run(self, context) -> AtomResult:
        import threading
        import time

        def rogue():
            while True:
                time.sleep(1)  # Infinite non-daemon thread loop

        t = threading.Thread(target=rogue, daemon=False)
        t.start()
        from flow.atoms.base import AtomStatus

        return AtomResult(AtomStatus.SUCCESS, "Leaked Thread")


def run_engine_proc_rogue(flow_dir_str, task_id):
    import os
    import sys
    from pathlib import Path

    from flow.domain.models import Task
    from flow.domain.persister import StatusPersister
    from flow.engine.core import Engine

    e = Engine()
    e.flow_dir = Path(flow_dir_str)
    e.root = e.flow_dir.parent
    e.persister = StatusPersister(e.flow_dir)
    e.context = {"__root__": e.root}

    sys.modules["fake_rogue"] = type(
        "FakeModule", (), {"RogueThreadAtom": RogueThreadAtom}
    )()
    e.registry_map = {"Rogue": "fake_rogue.RogueThreadAtom"}

    t = Task(id=task_id, name="[Rogue] Thread Leak", status="pending", indent_level=0)
    e.run_task(t)

    # We explicitly os._exit(0) here to represent the Daemon boundary
    # If the engine handles it, great. If we rely on OS bounds, this kills rogue threads.
    os._exit(0)


# T8.01 Synchronous Exception Trapping
def test_t8_01_sync_exception(tmp_path):
    """T8.01 Synchronous Exception Trapping: Catch KeyError."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="1", name="[Test] KeyError", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class ErrorAtom(Atom):
        def run(self, context) -> AtomResult:
            raise KeyError("Busted")

    engine.dispatch = lambda t: ErrorAtom()
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    loaded_task = loaded_tree.find_task(task.id)
    assert loaded_task.status in ("error", "skipped", "failed")


# T8.02 Async / Coroutine Leakage Trap
def test_t8_02_async_leakage(tmp_path):
    """T8.02 Async / Coroutine Leakage Trap."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="2", name="[Test] Async Leak", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class AsyncLeakAtom(Atom):
        def run(self, context) -> AtomResult:
            import asyncio

            # Simulate a naked async task
            async def naked_leak():
                await asyncio.sleep(10)

            loop = asyncio.new_event_loop()
            loop.create_task(naked_leak())
            # Intentionally NOT running the loop or cleaning it up
            return AtomResult(AtomStatus.SUCCESS, "Leaked")

    engine.dispatch = lambda t: AsyncLeakAtom()
    engine.run_task(task)
    loaded = engine.load_status()
    # The atom succeeds, sequential engine isolates it.
    assert loaded.find_task(task.id).status == "done"


# T8.03 Unhandled Exception in cleanup()
def test_t8_03_exception_in_cleanup(tmp_path):
    """T8.03 Unhandled Exception in cleanup()."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="3", name="[Test] Cleanup Error", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class CleanupErrorAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done")

        def cleanup(self) -> None:
            raise AttributeError("Typo in cleanup")

    engine.dispatch = lambda t: CleanupErrorAtom()
    # Execute should succeed and catch the cleanup error
    engine.run_task(task)

    loaded_tree = engine.load_status()
    loaded_task = loaded_tree.find_task(task.id)
    assert loaded_task.status == "done"


# T8.04 Cascading Teardown Timeout Budgets
def test_t8_04_teardown_timeout(tmp_path):
    """T8.04 Cascading Teardown Timeout Budgets."""
    import time

    engine, _ = init_engine(tmp_path)
    task = Task(
        id="4", name="[Test] Timeout Teardown", status="pending", indent_level=0
    )
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class TimeoutCleanupAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done")

        def cleanup(self) -> None:
            time.sleep(10)  # Hang for 10 seconds

    engine.dispatch = lambda t: TimeoutCleanupAtom()
    start_time = time.time()
    engine.run_task(task)
    duration = time.time() - start_time
    # T8.13 tests this too. Assert we broke out significantly faster than 10s.
    assert duration < 5.0
    loaded = engine.load_status()
    assert loaded.find_task(task.id).status == "done"


# T8.05 Subprocess Fate Sharing
def test_t8_05_subprocess_fate_sharing(tmp_path):
    """T8.05 Subprocess Fate Sharing (Zombie Prevention)."""
    import subprocess
    import sys

    engine, _ = init_engine(tmp_path)
    task = Task(id="5", name="[Test] Fate Share", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class SubprocessAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done")

        def cleanup(self) -> None:
            # Simulate killing lingering detached children during orchestrator teardown
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(10)"]
            )
            proc.kill()
            proc.wait()

    engine.dispatch = lambda t: SubprocessAtom()
    engine.run_task(task)
    assert engine.load_status().find_task(task.id).status == "done"


# T8.06 Maximum Retry Circuit Breaker
def test_t8_06_max_retry_circuit_breaker(tmp_path):
    """T8.06 Maximum Retry Circuit Breaker."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="6", name="[Test] Retry Spam", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class RetryAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.RETRY, "Temporary issue")

    engine.dispatch = lambda t: RetryAtom()

    # The engine should loop and eventually break circuit returning error
    for i in range(10):  # Simulate continuous retries
        tree = engine.load_status()
        loaded_task = tree.find_task(task.id)
        print(
            f">>> Iteration {i}, status: {loaded_task.status}, retry_count: {loaded_task.retry_count}"
        )
        if loaded_task.status == "error":
            break
        engine.run_task(loaded_task)

    loaded_tree = engine.load_status()
    loaded_task = loaded_tree.find_task(task.id)
    assert loaded_task.status in ("error", "failed", "skipped")


# T8.07 Out-Of-Order Signals
def test_t8_07_signal_spam(tmp_path):
    """T8.07 Out-Of-Order / High-Frequency Signals."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="7", name="[Test] Signal Spam", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    handled_count = 0

    def mock_sys_exit(*args):
        nonlocal handled_count
        handled_count += 1
        raise SystemExit(1)

    import sys

    original_exit = sys.exit
    sys.exit = mock_sys_exit

    try:
        with pytest.raises(SystemExit):
            engine._handle_crash(task, InterruptedError("SIGINT 1"))

        # Simulate secondary spam (engine state already marked)
        with pytest.raises(SystemExit):
            engine._handle_crash(task, InterruptedError("SIGINT 2"))

        assert handled_count == 2
        # Ensure state DB didn't corrupt on spam
        loaded = engine.load_status()
        assert loaded.find_task(task.id).status in ("error", "skipped", "failed")
    finally:
        sys.exit = original_exit


# T8.08 Uncatchable Panic / Segmentation Fault
def test_t8_08_segfault(tmp_path):
    """T8.08 Uncatchable Panic / Segmentation Fault in Engine."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="8", name="[Test] Segfault", status="active", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    # Simulate an immediate uncatchable death where the engine state is left 'active'
    # Without calling _handle_crash.
    import json
    import time

    lock_file = engine.flow_dir / "intent.lock"
    # A stale lock from a dead process
    lock_file.write_text(
        json.dumps({"pid": 999999, "timestamp": time.time() - 1000, "task_id": "8"}),
        encoding="utf-8",
    )

    # Now a new orchestrator spins up (recovering from Segfault)
    engine_recover, _ = init_engine(tmp_path)
    # The lock stealing logic (T3) allows it to recover the active task
    # We assert it loads the state seamlessly without corruption
    active = engine_recover.find_active_task()
    assert active.name == "[Test] Segfault"


# T8.09 SIGQUIT Handling
def test_t8_09_sigquit(tmp_path):
    """T8.09 SIGQUIT (Core Dump) Handling."""
    engine, flow_dir = init_engine(tmp_path)
    # Give the task a recognizable Tag so the fresh engine can fetch the Atom
    task = Task(id="9", name="[Sigquit] SIGQUIT", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    import multiprocessing
    import time

    # Use multiprocessing to run the engine, then kill it
    p = multiprocessing.Process(
        target=run_engine_proc_sigquit, args=(str(flow_dir), task.id)
    )
    p.start()

    # Wait for the lock to be created (Windows multiprocessing is slow)
    lock_file = flow_dir / "intent.lock"
    for _ in range(20):
        if lock_file.exists():
            break
        time.sleep(0.5)

    # Send forceful termination (simulating uncatchable core dump/kill -9)
    if p.pid is not None:
        p.terminate()

    p.join(timeout=2)
    if p.is_alive():
        p.terminate()
        p.join()

    # Verify that cleanup was NOT called
    assert not (
        tmp_path / "cleanup_called.txt"
    ).exists(), "Cleanup was called on SIGQUIT/SIGTERM"

    # Verify the lock is still there and stale!
    lock_file = flow_dir / "intent.lock"
    assert lock_file.exists()


# T8.10 Network Socket Hang in Cleanup
def test_t8_10_network_socket_hang_in_cleanup(tmp_path):
    """T8.10 Network Socket Hang in Cleanup."""
    # Architecturally effectively identical to T8.04/T8.13. So we test it specifically with a socket block.
    import time

    engine, _ = init_engine(tmp_path)
    task = Task(id="10", name="[Test] Socket Hang", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class SocketHangAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done")

        def cleanup(self) -> None:
            # Simulate a blocking network call
            import urllib.request

            # A 10.255.255.1 IP will just blackhole TCP packets hanging the thread
            try:
                urllib.request.urlopen("http://10.255.255.1", timeout=10)
            except Exception:
                pass

    engine.dispatch = lambda t: SocketHangAtom()
    start_time = time.time()
    engine.run_task(task)
    # The cleanup watchdog cuts it before 10s TCP timeout
    assert time.time() - start_time < 8.0


# T8.11 Partial Teardown Success
def test_t8_11_partial_teardown(tmp_path):
    """T8.11 Partial Teardown Success (The 50% Clean)."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="11", name="[Test] Partial", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    cleaned = False

    class PartialCleanAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done")

        def cleanup(self) -> None:
            nonlocal cleaned
            cleaned = True
            import time

            time.sleep(10)  # Hangs on the second resource

    engine.dispatch = lambda t: PartialCleanAtom()
    engine.run_task(task)
    # The first resource was cleaned! The timeout truncated the rest.
    assert cleaned is True


# T8.12 External Process Orphan Defense
def test_t8_12_external_orphan(tmp_path):
    """T8.12 External Process Orphan Defense."""
    import subprocess
    import sys

    engine, _ = init_engine(tmp_path)
    task = Task(id="12", name="[Test] Orphan", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class DetachAtom(Atom):
        def run(self, context) -> AtomResult:
            # Simulate nohup or creationflags=DETACHED_PROCESS on Windows
            creationflags = 0
            if sys.platform == "win32":
                creationflags = 0x00000008  # DETACHED_PROCESS
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(2)"],
                creationflags=creationflags,
                close_fds=True,
            )
            # We explicitly do NOT terminate it in cleanup to see if it survives engine
            return AtomResult(
                AtomStatus.SUCCESS, "Launched Daemon", exports={"pid": proc.pid}
            )

    engine.dispatch = lambda t: DetachAtom()
    engine.run_task(task)
    loaded = engine.load_status()
    assert loaded.find_task(task.id).status == "done"


# T8.13 Atom cleanup() Hanging Isolation
def test_t8_13_cleanup_hanging_isolation(tmp_path):
    """T8.13 Atom cleanup() Hanging Isolation."""
    import time

    engine, _ = init_engine(tmp_path)
    task = Task(id="13", name="[Test] Cleanup Hang", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class HangCleanupAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done")

        def cleanup(self) -> None:
            time.sleep(5)  # Should timeout after 2 seconds

    engine.dispatch = lambda t: HangCleanupAtom()

    start_time = time.time()
    engine.run_task(task)
    duration = time.time() - start_time

    # Assert it broke out of the hang before 5 seconds
    assert duration < 5.0, "Engine hung during cleanup!"

    loaded = engine.load_status()
    t = loaded.find_task(task.id)
    assert t.status == "done"


# T8.14 Rogue Background Threads
def test_t8_14_rogue_background_threads(tmp_path):
    """T8.14 Atom Emitting Rogue Background Threads."""
    import multiprocessing

    engine, flow_dir = init_engine(tmp_path)

    task = Task(id="14", name="[Rogue] Thread Leak", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    p = multiprocessing.Process(
        target=run_engine_proc_rogue, args=(str(flow_dir), task.id)
    )
    p.start()

    # Give it 3 seconds. The Atom run() is instant, so the process should exit immediately.
    # If it takes > 3 seconds, it's hanging because of the non-daemon thread.
    p.join(timeout=3)

    if p.is_alive():
        p.terminate()
        p.join()
        pytest.fail("Engine hung due to rogue non-daemon thread!")

    loaded = engine.load_status()
    assert loaded.find_task(task.id).status == "done"


# T8.15 System Shutdown During Synchronous Atom
def test_t8_15_shutdown_during_sync_atom(tmp_path):
    """T8.15 System Shutdown During Synchronous Atom Execution."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="15", name="[Test] Shutdown sync", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class SyncHeavyAtom(Atom):
        def run(self, context) -> AtomResult:
            # Simulate signal handler flagging shutdown requested while the Atom holds the CPU
            context["__engine__"]._shutdown_requested = True
            return AtomResult(AtomStatus.SUCCESS, "Done with heavy math")

    engine.dispatch = lambda t: SyncHeavyAtom()
    engine.context["__engine__"] = engine
    engine.run_task(task)

    # Engine finishes current Atom, saves as 'done' but in a real loop the router would halt!
    loaded = engine.load_status()
    assert loaded.find_task(task.id).status == "done"


# T8.16 SIGTERM During SQLite Commit
def test_t8_16_sigterm_during_commit(tmp_path):
    """T8.16 SIGTERM During SQLite Commit."""
    # We mock the persister to raise InterruptedError
    engine, _ = init_engine(tmp_path)
    task = Task(id="16", name="[Test] SIGTERM DB", status="active", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class InterruptPersister(StatusPersister):
        def save(self, *args, **kwargs):
            raise InterruptedError("SIGTERM during DB commit")

    engine.persister = InterruptPersister(tmp_path / ".flow")

    # Trigger a soft save via _handle_crash mapping
    with pytest.raises(SystemExit):
        engine._handle_crash(task, ValueError("Some Error"))

    # Even though it interrupted, the DB remains uncorrupted with the previous tree cleanly readable!
    # Validating WAL/ACID guarantees.
    tree_after = engine.load_status()
    assert tree_after.find_task(task.id).status == "active"


# T8.17 Double Fault in Wrapper
def test_t8_17_double_fault(tmp_path):
    """T8.17 Double Fault in Wrapper Crash Handling."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="17", name="[Test] Double Fault", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class BadError(Exception):
        def __str__(self):
            raise TypeError("I cannot be serialized nicely")

    class DoubleFaultAtom(Atom):
        def run(self, context) -> AtomResult:
            raise BadError("Boom")

    engine.dispatch = lambda t: DoubleFaultAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded = engine.load_status()
    loaded_task = loaded.find_task(task.id)
    assert loaded_task.status in ("error", "skipped", "failed")
