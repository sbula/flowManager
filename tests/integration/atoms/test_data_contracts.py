
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


# T6.01 Context Immutability
def test_t6_01_context_immutability(tmp_path):
    """T6.01 Context Immutability (Read-Only Guard)."""
    engine, _ = init_engine(tmp_path)

    task = Task(id="1", name="[Test] Immutate", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    error_caught = False

    class MutatingAtom(Atom):
        def run(self, context) -> AtomResult:
            nonlocal error_caught
            try:
                context["new"] = "x"
                return AtomResult(AtomStatus.SUCCESS, "Mutated")
            except TypeError:
                error_caught = True
                return AtomResult(AtomStatus.FAILED, "TypeError Caught")

    engine.dispatch = lambda t: MutatingAtom()
    # We use actual lifecycle to simulate engine behavior
    try:
        engine._execute_task_lifecycle(task)
    except Exception:
        pass  # Just in case engine throws instead of catching

    assert error_caught is True


# T6.02 Invalid Return Type Safety
def test_t6_02_invalid_return_type(tmp_path):
    """T6.02 Custom Atom returns True instead of AtomResult."""
    engine, _ = init_engine(tmp_path)

    task = Task(id="2", name="[Test] Bad Return", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class BadReturnAtom(Atom):
        def run(self, context):
            return True  # Invalid return type

    engine.dispatch = lambda t: BadReturnAtom()

    # The engine should trap this gracefully and not crash the DAG routing thread
    # Depending on V1.2 it maps failed states to 'skipped' or 'error' and exits.
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    loaded_task = loaded_tree.find_task(task.id)

    assert loaded_task.status in ("error", "skipped", "failed")


# T6.03 JSON Serialization Barrier
def test_t6_03_json_serialization_barrier(tmp_path):
    """T6.03 JSON Serialization Barrier: set() or FileHandle in exports."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="3", name="[Test] Bad Export", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class BadExportAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done", exports={"data": set([1, 2])})

    engine.dispatch = lambda t: BadExportAtom()

    # The engine catches json serialization issue, raises RuntimeError, and exits
    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    loaded_task = loaded_tree.find_task(task.id)

    assert loaded_task.status in ("error", "failed", "skipped")


# T6.04 Administrative Context Mutation
def test_t6_04_admin_mutation(tmp_path):
    """T6.04 Administrative Context Mutation (Poison Pill Bypass)."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="4", name="[Test] Dependent", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class DependentAtom(Atom):
        def run(self, context) -> AtomResult:
            if context.get("valid") is True:
                return AtomResult(AtomStatus.SUCCESS, "Worked")
            return AtomResult(AtomStatus.FAILED, "Needs valid=True")

    engine.dispatch = lambda t: DependentAtom()
    engine.context = {"valid": False}
    (engine.flow_dir / "intent.lock").touch()

    # Exec 1: fails
    engine._execute_task_lifecycle(task)
    tree = engine.load_status()
    # Depending on V1.2 it maps failed states to 'error', 'skipped' or 'done'
    # Actually AtomStatus.FAILED isn't raising an exception in Atom, Engine handles it.
    # We will verify what Engine does
    # Now simulate "Admin executes flow mutate-context"
    engine.context = {"valid": True}
    # Resetting task to pending so it can resume
    tree = engine.load_status()
    tree.update_task(task.id, status="pending")
    engine.persister.save(tree)

    # Exec 2: succeeds
    (engine.flow_dir / "intent.lock").touch()
    engine._execute_task_lifecycle(task)

    tree = engine.load_status()
    assert tree.find_task(task.id).status == "done"


# T6.05 Self-Referential Context Injection
def test_t6_05_self_referential_injection(tmp_path):
    """T6.05 Self-Referential (Cyclic) Context Injection."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="5", name="[Test] Cyclic Export", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class CyclicExportAtom(Atom):
        def run(self, context) -> AtomResult:
            a = {}
            a["self"] = a
            return AtomResult(AtomStatus.SUCCESS, "Did it", exports=a)

    engine.dispatch = lambda t: CyclicExportAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    loaded_task = loaded_tree.find_task(task.id)
    assert loaded_task.status in ("error", "failed", "skipped")


# T6.06 NaN / Infinity Injection
def test_t6_06_nan_infinity_injection(tmp_path):
    """T6.06 Custom Python tool returns float('inf') or float('nan')."""
    import math

    engine, _ = init_engine(tmp_path)
    task = Task(id="6", name="[Test] NaN", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class NaNAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done", exports={"val": math.inf})

    engine.dispatch = lambda t: NaNAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    loaded_task = loaded_tree.find_task(task.id)
    assert loaded_task.status in ("error", "failed", "skipped")


# T6.07 Massively Nested JSON
def test_t6_07_massively_nested_json(tmp_path):
    """T6.07 Massively Nested JSON (Stack Overflow Vector)."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="7", name="[Test] Nested", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class NestedAtom(Atom):
        def run(self, context) -> AtomResult:
            d = {}
            curr = d
            for _ in range(600):
                curr["n"] = {}
                curr = curr["n"]
            return AtomResult(AtomStatus.SUCCESS, "Done", exports=d)

    engine.dispatch = lambda t: NestedAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "failed", "skipped")


# T6.08 Escape Sequence Poisoning
def test_t6_08_escape_sequence_poisoning(tmp_path):
    """T6.08 Escape Sequence Poisoning."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="8", name="[Test] ANSI", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class ANSIAtom(Atom):
        def run(self, context) -> AtomResult:
            dirty = "payload\\x1b[2J!"
            return AtomResult(AtomStatus.SUCCESS, "Done", exports={"v": dirty})

    engine.dispatch = lambda t: ANSIAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "failed", "skipped")


# T6.09 Invalid Atom Schema Declaration
def test_t6_09_invalid_atom_schema(tmp_path):
    """T6.09 Missing field in properties.

    Not strictly Engine level until Agent schema validation,
    but we assume an Atom raising error on init.
    """
    engine, _ = init_engine(tmp_path)
    task = Task(id="9", name="[Test] Bad Schema", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class BadSchemaAtom(Atom):
        def run(self, context) -> AtomResult:
            # Emulating a validation failure during Schema build
            try:
                schema = {"required": ["missing_prop"], "properties": {"other": "type"}}
                for req in schema["required"]:
                    if req not in schema["properties"]:
                        raise ValueError("Invalid Atom Schema")
            except ValueError as e:
                return AtomResult(
                    AtomStatus.FAILED, f"Schema validation failed: {str(e)}"
                )
            return AtomResult(AtomStatus.SUCCESS, "Worked")

    engine.dispatch = lambda t: BadSchemaAtom()

    # The engine catches failed run and updates status
    engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "failed", "skipped")


# T6.10 Un-Hashable Custom Object Injection
def test_t6_10_unhashable_custom_object(tmp_path):
    """T6.10 Custom Python class instance injection."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="10", name="[Test] Unhashable", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class CustomObj:
        pass

    class UnhashAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done", exports={"obj": CustomObj()})

    engine.dispatch = lambda t: UnhashAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "failed", "skipped")


# T6.11 Dictionary Key Type Coercion Anomaly
def test_t6_11_key_type_coercion(tmp_path):
    """T6.11 Dictionary Key Type Coercion Anomaly."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="11", name="[Test] Int Key", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class IntKeyAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done", exports={1: "val"})

    engine.dispatch = lambda t: IntKeyAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "failed", "skipped")


# T6.12 Serialization Deep Hash Poisoning
def test_t6_12_dunder_key_poisoning(tmp_path):
    """T6.12 Serialization Deep Hash Poisoning (__class__)."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="12", name="[Test] Dunder Key", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class DunderAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(
                AtomStatus.SUCCESS, "Done", exports={"__class__": "Malicious"}
            )

    engine.dispatch = lambda t: DunderAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "failed", "skipped")


# T6.13 Export Key Masking Core Engine Properties
def test_t6_13_export_key_masking(tmp_path):
    """T6.13 Export Key Masking Core Engine Properties."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="13", name="[Test] Masking", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class MaskAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(
                AtomStatus.SUCCESS, "Done", exports={"__task_id__": "forged"}
            )

    engine.dispatch = lambda t: MaskAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "failed", "skipped")


# T6.14 The Tuple-List Rehydration Failure
def test_t6_14_tuple_rehydration(tmp_path):
    """T6.14 The Tuple-List Rehydration Failure."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="14", name="[Test] Tuple", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class TupleAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(AtomStatus.SUCCESS, "Done", exports={"items": (1, 2)})

    engine.dispatch = lambda t: TupleAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "failed", "skipped")


# T6.15 MRO Injection
def test_t6_15_mro_injection(tmp_path):
    """T6.15 MRO Injection bypassing base model."""
    engine, _ = init_engine(tmp_path)
    task = Task(id="15", name="[Test] MRO Dict", status="pending", indent_level=0)
    tree = StatusTree()
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class CustomDict(dict):
        def items(self):
            return []  # Hide from Python loop

    class MROAtom(Atom):
        def run(self, context) -> AtomResult:
            cd = CustomDict({"__task_id__": "hidden!"})
            return AtomResult(AtomStatus.SUCCESS, "Done", exports={"data": cd})

    engine.dispatch = lambda t: MROAtom()

    with pytest.raises(SystemExit):
        engine.run_task(task)

    loaded_tree = engine.load_status()
    assert loaded_tree.find_task(task.id).status in ("error", "failed", "skipped")
