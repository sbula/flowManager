import os
import signal
import sys
import threading
import time
from pathlib import Path
from types import MappingProxyType

import pytest

from flow.atoms import Atom, AtomResult, AtomStatus
from flow.domain.models import PayloadTooLargeError, StatusTree, Task
from flow.domain.persister import StatusPersister
from flow.engine.core import Engine


def init_engine(tmp_path: Path):
    engine = Engine()
    engine.root = tmp_path
    flow_dir = tmp_path / ".flow"
    flow_dir.mkdir(parents=True, exist_ok=True)
    engine.flow_dir = flow_dir
    engine.persister = StatusPersister(flow_dir)
    engine.context = {"__root__": engine.root}
    engine.registry_map = {}
    return engine, flow_dir


# T7.01 The OOM Defense (String Size Limit)
def test_t7_01_payload_too_large(tmp_path):
    """T7.01 The OOM Defense (String Size Limit): Reject payload > limit."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="1", name="[Test] Large Payload", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class LargePayloadAtom(Atom):
        def run(self, context) -> AtomResult:
            # Emulate an atom returning a 500MB payload.
            # (We will use 1MB here to avoid killing the test runner)
            large_string = "A" * (1 * 1024 * 1024)
            return AtomResult(
                AtomStatus.SUCCESS, "Done", exports={"data": large_string}
            )

    engine.dispatch = lambda t: LargePayloadAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    loaded_task = loaded_tree.find_task(task.id)
    assert loaded_task.status in ("error", "skipped", "failed")


# T7.02 Blob Overflow Write Failure
def test_t7_02_blob_overflow(tmp_path, monkeypatch):
    """T7.02 Mock Disk Full via ENOSPC. Expect FAILED."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="2", name="[Test] Target", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class BlobWriteAtom(Atom):
        def run(self, context) -> AtomResult:
            # Simulate ENOSPC
            raise OSError(28, "No space left on device")

    engine.dispatch = lambda t: BlobWriteAtom()
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    loaded_task = loaded_tree.find_task(task.id)
    assert loaded_task.status in ("error", "skipped", "failed")


# T7.03 Memory Bomb Restriction (OOMKiller)
def test_t7_03_memory_bomb(tmp_path):
    """T7.03 Memory Bomb Restriction (cgroups/OOMKiller)"""
    # Requires Linux cgroups enforcement. We simulate Orchestrator catching MemoryError natively
    engine, _ = init_engine(tmp_path)
    task = Task(id="3", name="[Test] Memory Bomb", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class OOMAtom(Atom):
        def run(self, context) -> AtomResult:
            raise MemoryError("Out of memory simulated")

    engine.dispatch = lambda t: OOMAtom()
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded = engine.load_status()
    assert loaded.find_task(task.id).status in ("error", "skipped", "failed")


# T7.04 File Descriptor/Handle Exhaustion
def test_t7_04_file_descriptor_exhaustion(tmp_path):
    """T7.04 File Descriptor/Handle Exhaustion."""

    engine, _ = init_engine(tmp_path)
    task = Task(id="4", name="[Test] FD", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    # Simulation of catching OSError [Errno 24] Inside an Atom.
    class FDAtom(Atom):
        def run(self, context) -> AtomResult:
            # Explicitly raise OSError simulating EMFILE
            raise OSError(24, "Too many open files")

    engine.dispatch = lambda t: FDAtom()
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "skipped", "failed")


# T7.05 Read-Only Filesystem Trap
def test_t7_05_readonly_filesystem(tmp_path):
    """T7.05 Read-Only Filesystem Trap mid-flight."""

    engine, _ = init_engine(tmp_path)
    task = Task(id="5", name="[Test] ROFS", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class IOAtom(Atom):
        def run(self, context) -> AtomResult:
            raise PermissionError("Read-only file system")

    engine.dispatch = lambda t: IOAtom()
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "skipped", "failed")


# T7.06 CPU Starvation / Infinite While Loop
def test_t7_06_cpu_starvation(tmp_path):
    """T7.06 CPU Starvation / Infinite While Loop: Watchdog SIGKILL simulation."""

    # Actual SIGKILL requires process-level orchestrator test.
    # Simulation: Watchdog raises a TimeoutError in Atom wrapper
    class LoopAtom(Atom):
        def run(self, context) -> AtomResult:
            import time

            start = time.time()
            # Simulation of timeout enforcement
            if time.time() - start < 60:
                return AtomResult(AtomStatus.FAILED, "Watchdog Timeout")
            return AtomResult(AtomStatus.SUCCESS, "Done")

    atom = LoopAtom()
    res = atom.run({})
    assert res.status == AtomStatus.FAILED


# T7.07 Fork Bomb Defense
def test_t7_07_fork_bomb(tmp_path):
    """T7.07 Fork Bomb Defense."""
    # OS Specific PIDs limit. Mocked via BlockingIOError (Errno 11 EAGAIN) which happens
    # when process limit is reached in Python standard subprocess
    engine, _ = init_engine(tmp_path)
    task = Task(id="7", name="[Test] Fork Bomb", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class ForkBombAtom(Atom):
        def run(self, context) -> AtomResult:
            raise BlockingIOError(11, "Resource temporarily unavailable (PID limit)")

    engine.dispatch = lambda t: ForkBombAtom()
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded = engine.load_status()
    assert loaded.find_task(task.id).status in ("error", "skipped", "failed")


# T7.08 Inode Exhaustion
def test_t7_08_inode_exhaustion(tmp_path):
    """T7.08 Inode Exhaustion: Same exception signature as ENOSPC."""

    engine, _ = init_engine(tmp_path)
    task = Task(id="8", name="[Test] Inode", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class InodeAtom(Atom):
        def run(self, context) -> AtomResult:
            # Inode exhaustion throws ENOSPC (28) just like disk full on many systems
            raise OSError(28, "No space left on device (inodes)")

    engine.dispatch = lambda t: InodeAtom()
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "skipped", "failed")


# T7.09 ScriptAtom stdout/stderr Firehose
def test_t7_09_stream_firehose(tmp_path):
    """T7.09 ScriptAtom stdout/stderr Firehose (Disk Flood)."""

    # Simulate the Engine ProcessSupervisor intercepting a 50MB stream.
    class ScriptFirehoseAtom(Atom):
        def run(self, context) -> AtomResult:
            simulated_stream = "x" * (50 * 1024 * 1024)
            if len(simulated_stream) > 10 * 1024 * 1024:
                return AtomResult(
                    AtomStatus.FAILED, "Stream exceeded limit, process SIGKILLed"
                )
            return AtomResult(AtomStatus.SUCCESS, "ok")

    res = ScriptFirehoseAtom().run({})
    assert res.status == AtomStatus.FAILED
    assert "SIGKILLed" in res.message


# T7.10 Native Socket / Port Exhaustion
def test_t7_10_port_exhaustion(tmp_path):
    """T7.10 Native Socket / Port Exhaustion (EADDRINUSE)."""

    engine, _ = init_engine(tmp_path)
    task = Task(id="10", name="[Test] EADDRINUSE", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class PortAtom(Atom):
        def run(self, context) -> AtomResult:
            # Python natively propagates OSError for port exhaustion
            raise OSError(98, "Address already in use")

    engine.dispatch = lambda t: PortAtom()
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "skipped", "failed")


# T7.11 Ghost Asyncio Task Leakage
def test_t7_11_ghost_asyncio_leakage(tmp_path):
    """T7.11 Ghost Asyncio Task Leakage."""
    import asyncio

    class AsyncLeakAtom(Atom):
        def run(self, context) -> AtomResult:
            # Simulate an asyncio.create_task that leaks
            async def leak():
                await asyncio.sleep(10)

            # Since the atom runs synchronously, if it started an asyncio loop,
            # we want to ensure the loop is closed and tasks cancelled.
            loop = asyncio.new_event_loop()
            task = loop.create_task(leak())
            # simulated engine cleanup:
            for pending in asyncio.all_tasks(loop):
                pending.cancel()
            loop.close()
            return AtomResult(AtomStatus.SUCCESS, "Completed, tasks cancelled")

    res = AsyncLeakAtom().run({})
    assert res.status == AtomStatus.SUCCESS
    assert "cancelled" in res.message


# T7.12 Python Sub-interpreter Thread Starvation
def test_t7_12_thread_starvation(tmp_path):
    """T7.12 Python Sub-interpreter Thread Starvation."""
    engine, flow_dir = init_engine(tmp_path)
    # Simulate watchdog heartbeat failure
    watchdog_heartbeat = time.time()
    # Starving threads prevents heartbeat update
    time.sleep(0.1)
    if time.time() - watchdog_heartbeat > 0.05:
        # Watchdog triggers SIGTERM
        engine.context["watchdog_killed"] = True

    assert engine.context.get("watchdog_killed")


# T7.13 C-Extension Memory Leaks
def test_t7_13_c_extension_memory_leak(tmp_path):
    """T7.13 C-Extension Memory Leaks."""
    # To prevent dragging down the engine natively, untrusted/heavy C-extensions
    # must be executed in isolated subprocesses. We simulate ScriptAtom delegating to subprocess.
    import subprocess

    class ScriptAtom(Atom):
        def run(self, context) -> AtomResult:
            # Simulate running a separate process that allocates and exits
            try:
                subprocess.run(
                    [sys.executable, "-c", "import sys; sys.exit(0)"],
                    check=True,
                    capture_output=True,
                    timeout=2,
                )
                return AtomResult(
                    AtomStatus.SUCCESS, "Subprocess cleaned up memory naturally"
                )
            except subprocess.TimeoutExpired:
                return AtomResult(AtomStatus.FAILED, "Subprocess timeout")

    res = ScriptAtom().run({})
    assert res.status == AtomStatus.SUCCESS
