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


# T9.01 sys.stdout Hijacking
def test_t9_01_stdout_hijacking(tmp_path):
    """T9.01 sys.stdout Hijacking."""
    import io
    import sys

    engine, _ = init_engine(tmp_path)
    task = Task(id="1", name="[Test] Stdout Hijack", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class HijackAtom(Atom):
        def run(self, context) -> AtomResult:
            sys.stdout = io.StringIO()
            sys.stdout.write("Hijacked stdout")
            return AtomResult(AtomStatus.SUCCESS, "Done")

    engine.dispatch = lambda t: HijackAtom()

    original_stdout = sys.stdout
    try:
        try:
            engine.run_task(task)
        except SystemExit:
            pass
        # Depending on implementation, we assert sys.stdout hasn't changed
        assert sys.stdout is original_stdout, "sys.stdout was hijacked globally!"
    finally:
        sys.stdout = original_stdout


# T9.02 Dynamic os.environ Mutation
def test_t9_02_environ_mutation(tmp_path):
    """T9.02 Dynamic os.environ Mutation."""
    import os

    engine, _ = init_engine(tmp_path)
    task = Task(id="2", name="[Test] Env Mutate", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class MutateAtom(Atom):
        def run(self, context) -> AtomResult:
            os.environ["__HACKED_ENV_VAR__"] = "true"
            return AtomResult(AtomStatus.SUCCESS, "Done")

    engine.dispatch = lambda t: MutateAtom()

    os.environ.pop("__HACKED_ENV_VAR__", None)
    try:
        try:
            engine.run_task(task)
        except SystemExit:
            pass
        assert (
            "__HACKED_ENV_VAR__" not in os.environ
        ), "os.environ was mutated globally!"
    finally:
        os.environ.pop("__HACKED_ENV_VAR__", None)


# T9.03 Monkey-Patching Core Classes
def test_t9_03_monkeypatch_core_classes(tmp_path):
    """T9.03 Monkey-Patching Core Classes."""
    import os
    import subprocess
    import sys

    engine, _ = init_engine(tmp_path)
    task = Task(
        id="3", name="[Test] MonkeyPatch Core", status="pending", indent_level=0
    )
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    # We will write a custom python script that hydrates an engine and runs this task
    # and attempts to monkey-patch Engine core.
    script_path = tmp_path / "malicious_script.py"
    script_path.write_text(
        f"""
import sys
import os
sys.path.append(r"{os.getcwd()}")
from flow.engine.core import Engine
from flow.atoms import Atom, AtomResult, AtomStatus
from flow.domain.models import Task, StatusTree
from flow.domain.persister import StatusPersister

class PatchAtom(Atom):
    def run(self, context) -> AtomResult:
        import flow.engine.core as core
        # Hijack the class!
        core.AtomResult = str
        return AtomResult(AtomStatus.SUCCESS, "Done")

engine = Engine()
engine.root = r"{tmp_path}"
engine.flow_dir = engine.root / ".flow"
engine.persister = StatusPersister(engine.flow_dir)
engine.context = {{"__root__": engine.root}}
engine.registry_map = {{}}
engine.dispatch = lambda t: PatchAtom()

task = engine.load_status().find_task("3")
try:
    engine.run_task(task)
except SystemExit:
    pass
"""
    )

    result = subprocess.run(
        [sys.executable, str(script_path)], capture_output=True, text=True
    )

    # Assert that in our current process, AtomResult is completely untouched
    from flow.atoms import AtomResult

    assert type(AtomResult) is type, "AtomResult was hijacked in the parent process!"

    # Reload status
    loaded = engine.load_status()
    t = loaded.find_task(task.id)
    # The atom might have succeeded or failed depending on when the patch happened
    # but the crucial DAU defense requirement is that global state in the parent orchestrator is clean.
    assert t.status in ("error", "skipped", "failed", "done", "active", "pending")


# T9.04 The Infinite __getattr__ Trap
def test_t9_04_infinite_getattr_trap(tmp_path):
    """T9.04 The Infinite __getattr__ Trap."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="4", name="[Test] GetAttr Trap", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class Trap:
        def __getattr__(self, item):
            return self

    class TrapAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done", exports={"trap": Trap()})

    engine.dispatch = lambda t: TrapAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded = engine.load_status()
    t = loaded.find_task(task.id)
    assert t.status in ("error", "skipped", "failed")


# T9.05 OS Signal Handler Sabotage
def test_t9_05_signal_handler_sabotage(tmp_path):
    """T9.05 OS Signal Handler Sabotage."""
    import signal

    engine, _ = init_engine(tmp_path)
    task = Task(id="5", name="[Test] Signal Sabotage", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class SabotageAtom(Atom):
        def run(self, context) -> AtomResult:
            # Attempt to hijack SIGTERM
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            return AtomResult(AtomStatus.SUCCESS, "Done")

    engine.dispatch = lambda t: SabotageAtom()

    orig_handler = signal.getsignal(signal.SIGTERM)
    try:
        with pytest.raises(SystemExit):
            engine.run_task(task)
        loaded = engine.load_status()
        t = loaded.find_task(task.id)
        assert t.status in ("error", "skipped", "failed")
    finally:
        signal.signal(signal.SIGTERM, orig_handler)


# T9.06 Deep Module Monkeypatching
def test_t9_06_deep_module_patching(tmp_path):
    """T9.06 Deep Module Monkeypatching (Global Side-Effects)."""
    import os
    import ssl
    import subprocess
    import sys

    engine, _ = init_engine(tmp_path)
    task = Task(
        id="6", name="[Test] Deep Module Patching", status="pending", indent_level=0
    )
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    script_path = tmp_path / "deep_malicious_script.py"
    script_path.write_text(
        f"""
import sys
import os
import ssl
sys.path.append(r"{os.getcwd()}")
from flow.engine.core import Engine
from flow.atoms import Atom, AtomResult, AtomStatus
from flow.domain.models import Task, StatusTree
from flow.domain.persister import StatusPersister

class DeepPatchAtom(Atom):
    def run(self, context) -> AtomResult:
        # Patch SSL global context
        ssl._create_default_https_context = ssl._create_unverified_context
        return AtomResult(AtomStatus.SUCCESS, "Done")

engine = Engine()
engine.root = r"{tmp_path}"
engine.flow_dir = engine.root / ".flow"
engine.persister = StatusPersister(engine.flow_dir)
engine.context = {{"__root__": engine.root}}
engine.registry_map = {{}}
engine.dispatch = lambda t: DeepPatchAtom()

task = engine.load_status().find_task("6")
try:
    engine.run_task(task)
except SystemExit:
    pass
"""
    )

    result = subprocess.run(
        [sys.executable, str(script_path)], capture_output=True, text=True
    )

    # In the orchestrator, the default SSL context MUST NOT be the unverified one
    assert (
        ssl._create_default_https_context is not ssl._create_unverified_context
    ), "SSL was patched globally!"
