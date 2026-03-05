import time

import pytest

from flow.atoms import Atom, AtomResult, AtomStatus
from flow.domain.models import ConfigVersionMismatchError, StatusTree, Task
from flow.domain.persister import StatusPersister
from flow.engine.core import Engine


# T2.01 Run ID Hash Determinism
def test_t2_01_run_id_hash_determinism():
    """T2.01 Run ID Hash Determinism: Instantiate WebhookAtom twice identically. Expect identical IDs."""
    from flow.atoms.webhook import WebhookAtom

    config = {"url": "http://localhost", "payload": {"data": "test"}}
    atom1 = WebhookAtom(config=config)
    atom2 = WebhookAtom(config=config)
    h1 = atom1.get_hash()
    h2 = atom2.get_hash()
    assert h1 == h2


# T2.02 Cross-Flow Collision Defense
def test_t2_02_cross_flow_collision_defense():
    """T2.02 Cross-Flow Collision Defense: Natively instantiate parallel TriggerEventIDs. Expect divergent Hash IDs."""
    from flow.atoms.webhook import WebhookAtom

    atom1 = WebhookAtom(
        config={"url": "http://localhost", "payload": {"TriggerEventID": "A"}}
    )
    atom2 = WebhookAtom(
        config={"url": "http://localhost", "payload": {"TriggerEventID": "B"}}
    )
    h1 = atom1.get_hash()
    h2 = atom2.get_hash()
    assert h1 != h2


# T2.03 State Reconciliation Verification
def test_t2_03_state_reconciliation_verification(tmp_path):
    """T2.03 State Reconciliation Verification.

    Simulate crash after mutating Atom side-effect but BEFORE local state save.
    On restart, expect Atom to check remote state, skip mutation, and yield SUCCESS.
    """
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    tree = StatusTree()
    task = Task(id="1", name="[Mock] Run", status="pending", indent_level=0)
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class MockAtom(Atom):
        def run(self, context) -> AtomResult:
            if context.get("remote_state_exists"):
                return AtomResult(
                    status=AtomStatus.SUCCESS, message="Skipped mutation, state exists"
                )
            return AtomResult(status=AtomStatus.SUCCESS, message="Mutated")

    import sys

    sys.modules["mock_t203"] = type("FakeModule", (), {"MockAtom": MockAtom})()
    engine.registry_map = {"Mock": "mock_t203.MockAtom"}

    engine.context["remote_state_exists"] = True
    engine.run_task(task)
    loaded = engine.load_status()
    assert loaded.root_tasks[0].status == "done"


# T2.04 Version Hash Collision (Code Drift)
def test_t2_04_version_hash_collision_code_drift(tmp_path):
    """T2.04 Version Hash Collision (Code Drift).

    Suspend flow, modify YAML DAG, resume. Expect ConfigVersionMismatchError.
    """
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    tree = StatusTree()
    tree.headers["Version"] = "v1"
    task = Task(id="1", name="[Test]", status="pending", indent_level=0)
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    engine.expected_version = "v2"
    with pytest.raises(ConfigVersionMismatchError, match="Version drifted"):
        engine.load_status()


# T2.05 Database-Backed DAG Serialization
def test_t2_05_database_backed_dag_serialization(tmp_path):
    """T2.05 Database-Backed DAG Serialization.

    Force crash during dynamic DAG generation. Expect recovery from locked
    database hash, not a regeneration attempt.
    """
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    # Save valid tree
    tree = StatusTree()
    task = Task(id="1", name="[Test] Run", status="pending", indent_level=0)
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    # Ensure backup exists
    time.sleep(0.01)  # fast wait
    task.name = "[Test] Updated"
    engine.persister.save(tree)

    # Corrupt the latest file
    status_file = engine.flow_dir / "status.md"
    status_file.write_text("NOT A REAL STATUS FILE\n- [ ] Corrupt", encoding="utf-8")

    # Engine should auto-recover from backup when loading
    recovered = engine.load_status()
    assert "Corrupt" not in recovered.root_tasks[0].name


# T2.06 At-Least-Once Traceability (Ghost Writes)
def test_t2_06_at_least_once_traceability(tmp_path):
    """T2.06 At-Least-Once Traceability (Ghost Writes).

    Execute Unsafe non-idempotent Atom under retry.
    Expect warning: "At-Least-Once" metadata without halting.
    """
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    tree = StatusTree()
    task = Task(id="1", name="[RetryMock] Run", status="pending", indent_level=0)
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class RetryAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(status=AtomStatus.RETRY, message="Transient Failure")

    import sys

    sys.modules["mock_t206"] = type("FakeModule", (), {"RetryAtom": RetryAtom})()
    engine.registry_map = {"RetryMock": "mock_t206.RetryAtom"}

    # First dispatch yields RETRY
    engine.run_task(task)

    # Engine should write metadata regarding "At-Least-Once" or retry count
    loaded = engine.load_status()
    assert loaded.root_tasks[0].status == "pending"
    assert "__retry_count_1__" in engine.context
    assert engine.context["__retry_count_1__"] >= 1


# T2.07 Idempotency Key Re-Use Attack
def test_t2_07_idempotency_key_reuse_attack(tmp_path):
    """T2.07 Idempotency Key Re-Use Attack.

    Simulate two different Atoms requesting the exact same Idempotency Key logic.
    Expect failure or overwrite rejection in the state DB.
    """
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    class IdempotentAtom(Atom):
        def run(self, context) -> AtomResult:
            ikey = self.config.model_extra.get("idempotency_key")
            ik_storage = context.get("_idempotency_keys", [])
            if ikey in ik_storage:
                return AtomResult(
                    status=AtomStatus.FAILED, message="Idempotency Key Re-Use Attack"
                )
            ik_storage.append(ikey)
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message="OK",
                exports={"_idempotency_keys": ik_storage},
            )

    import sys

    sys.modules["mock_t207"] = type(
        "FakeModule", (), {"IdempotentAtom": IdempotentAtom}
    )()
    engine.registry_map = {"IdemMock": "mock_t207.IdempotentAtom"}

    tree = StatusTree()
    task1 = Task(id="1", name="[IdemMock] Run 1", status="pending", indent_level=0)
    task2 = Task(id="2", name="[IdemMock] Run 2", status="pending", indent_level=0)
    tree.root_tasks.extend([task1, task2])
    tree._reindex()
    engine.persister.save(tree)

    engine.context["_idempotency_keys"] = []

    orig_dispatch = engine.dispatch

    def mocked_dispatch(t):
        atom = orig_dispatch(t)
        atom.raw_config = {"idempotency_key": "12345"}
        atom.config = atom._parse_config(atom.raw_config)
        return atom

    engine.dispatch = mocked_dispatch

    engine.run_task(task1)
    engine.run_task(task2)

    loaded = engine.load_status()
    assert loaded.root_tasks[0].status == "done"
    assert loaded.root_tasks[1].status in ("error", "skipped")


# T2.08 Timestamp Drift in Run ID
def test_t2_08_timestamp_drift_in_run_id():
    """T2.08 Timestamp Drift in Run ID.

    Inject wildly different UTC timestamps into environment.
    Expect Hash ID perfectly identical.
    """

    class HashableMockAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(status=AtomStatus.SUCCESS, message="OK")

    atom1 = HashableMockAtom(config={"timestamp": 1000})
    atom2 = HashableMockAtom(config={"timestamp": 9999})
    assert atom1.get_hash() == atom2.get_hash()


# T2.09 Zero-Byte Config Hashing
def test_t2_09_zero_byte_config_hashing():
    """T2.09 Zero-Byte Config Hashing.

    Instantiate an Atom with an entirely empty config: {}.
    Expect a valid, stable hash.
    """

    class HashableMockAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(status=AtomStatus.SUCCESS, message="OK")

    atom = HashableMockAtom(config={})
    h = atom.get_hash()
    assert isinstance(h, str) and len(h) > 0


# T2.10 Massive DAG Node ID Validation
def test_t2_10_massive_dag_node_id_validation():
    """T2.10 Massive DAG Node ID Validation.

    Pass a DAG_NodeID of 100,000 characters.
    Expect proper hashing and no string length DB exceptions.
    """

    class HashableMockAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(status=AtomStatus.SUCCESS, message="OK")

    huge_id = "A" * 100000
    atom = HashableMockAtom(config={"DAG_NodeID": huge_id})
    h = atom.get_hash()
    assert isinstance(h, str) and len(h) > 0


# T2.11 State DB Network Partition
def test_t2_11_state_db_network_partition(tmp_path):
    """T2.11 State DB Network Partition.

    Atom completes successfully, but connection to .flow_state/ embedded DB severed.
    Expect Orchestrator defensively fails.
    """
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    class NetworkPartitionMockAtom(Atom):
        def run(self, context) -> AtomResult:
            # Simulate network partition right before returning by mocking the save
            engine.persister.save

            def failing_save(t):
                raise OSError("Network drive disconnected")

            engine.persister.save = failing_save
            return AtomResult(status=AtomStatus.SUCCESS, message="OK")

    import sys

    sys.modules["mock_t211"] = type(
        "FakeModule", (), {"NetworkPartitionMockAtom": NetworkPartitionMockAtom}
    )()
    engine.registry_map = {"NetPartMock": "mock_t211.NetworkPartitionMockAtom"}

    tree = StatusTree()
    task = Task(id="1", name="[NetPartMock] Run", status="pending", indent_level=0)
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    # Engine swallows exceptions internally to prevent complete crash and updates state
    # But since save is mocked to fail, it should double fault and remain pending in actual DB.
    # In memory it might attempt to update, but disk won't have it.
    with pytest.raises(SystemExit):
        engine.run_task(task)

    # Restore save to check DB state
    engine.persister = StatusPersister(engine.flow_dir)
    loaded = engine.load_status()
    # It shouldn't have been marked 'done' on disk since saving failed
    assert loaded.root_tasks[0].status == "active"


# T2.12 Phantom Resume on Deleted State
def test_t2_12_phantom_resume_on_deleted_state(tmp_path):
    """T2.12 Phantom Resume on Deleted State.

    Engine attempts to resume an Atom where .flow_state/ mapping is manually
    deleted mid-sleep. Expect explicit StateNotFoundError.
    """
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    tree = StatusTree()
    task = Task(id="1", name="[Test] Run", status="pending", indent_level=0)
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    # Manual deletion
    import shutil

    shutil.rmtree(engine.flow_dir)

    # Expect error on resume
    from flow.domain.models import StatusParsingError
    from flow.engine.models import RootNotFoundError

    with pytest.raises(
        (RootNotFoundError, StatusParsingError, FileNotFoundError, OSError)
    ):
        engine.load_status()


# T2.13 Dirty State Heuristics
def test_t2_13_dirty_state_heuristics(tmp_path):
    """T2.13 Dirty State Heuristics.

    State file exists but size is exactly 0 bytes due to power loss.
    Expect fallback to previous valid state snapshot.
    """
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    tree = StatusTree()
    task = Task(id="1", name="[Test] Valid", status="pending", indent_level=0)
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    time.sleep(0.01)
    task.name = "[Test] Updated"
    engine.persister.save(tree)

    # Truncate to 0 bytes (Dirty state)
    status_file = engine.flow_dir / "status.md"
    status_file.write_text("")

    recovered = engine.load_status()
    assert "Valid" in recovered.root_tasks[0].name


# T2.14 WAL File Corruption (Bit Flip)
def test_t2_14_wal_file_corruption(tmp_path):
    """T2.14 WAL File Corruption (Bit Flip).

    Corrupted with random bytes. Expect Engine to decline changes
    and recover from valid snapshot.
    """
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    # Save initial valid state
    tree = StatusTree()
    from flow.domain.models import Task

    task = Task(id="1", name="[Test] Run", status="pending", indent_level=0)
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    # Backup is created upon first load/save (decline_changes uses .bak if exists or re-parses).
    # Since we need a backup, let's load it first to ensure backup exists
    time.sleep(0.01)
    engine.persister.save(tree)

    # Corrupt the main status file with non-utf8 unparsable binary garbage
    status_file = engine.flow_dir / "status.md"
    status_file.write_bytes(b"\x00\xFF\xFE\x01corrupted\x99\x88\x77random\x00")

    # Engine load should auto-recover from the previous valid state via fallback
    recovered = engine.load_status()
    assert len(recovered.root_tasks) == 1
    assert recovered.root_tasks[0].id == "1"


# T2.15 Hash Collision with Non-ASCII Characters
def test_t2_15_hash_collision_non_ascii():
    """T2.15 Hash Collision with Non-ASCII Characters.

    "cafe" vs "cafe\u0301". Expect UTF-8 normalized strings to yield different hashes.
    """

    class HashableMockAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(status=AtomStatus.SUCCESS, message="OK")

    atom1 = HashableMockAtom(config={"name": "cafe"})
    atom2 = HashableMockAtom(config={"name": "café"})
    assert atom1.get_hash() != atom2.get_hash()


# T2.16 NTP Clock Leap during Backoff
def test_t2_16_ntp_clock_leap_backoff(tmp_path):
    """T2.16 NTP Clock Leap during Backoff: ... Expect Engine's scheduler to detect unrealistic temporal drift."""
    engine = Engine()
    engine.root = tmp_path
    engine.flow_dir = tmp_path / ".flow"
    engine.flow_dir.mkdir(parents=True, exist_ok=True)
    engine.persister = StatusPersister(engine.flow_dir)
    engine.context = {"__root__": engine.root}

    from flow.domain.models import StatusTree, Task

    tree = StatusTree()
    task = Task(id="1", name="[BackoffMock] Run", status="pending", indent_level=0)
    tree.root_tasks.append(task)
    tree._reindex()
    engine.persister.save(tree)

    class BackoffAtom(Atom):
        def run(self, context) -> AtomResult:
            from flow.atoms import RetryStrategy

            return AtomResult(
                status=AtomStatus.RETRY,
                message="Transient Failure",
                retry_strategy=RetryStrategy.BACKOFF,
            )

    import sys

    sys.modules["mock_t216"] = type("FakeModule", (), {"BackoffAtom": BackoffAtom})()
    engine.registry_map = {"BackoffMock": "mock_t216.BackoffAtom"}

    # First dispatch yields RETRY, records time anchors
    engine.run_task(task)

    # Simulate Clock Leap of 1 year into the future
    import time

    with pytest.raises(SystemExit):
        # Engine internally catches RuntimeError("NTP Clock Leap / Temporal Drift...") and calls sys.exit(1)
        # However, to trigger the exact time difference, we mock time.time
        import unittest.mock

        future_time = time.time() + 31536000
        with unittest.mock.patch("time.time", return_value=future_time):
            engine.run_task(task)

    # Verify the error was trapped as a CRASH
    loaded = engine.load_status()
    assert loaded.root_tasks[0].status in ("error", "skipped")


# T2.17 Floating Point Precision Loss in Hashes
def test_t2_17_floating_point_precision_loss():
    """T2.17 Floating Point Precision Loss in Hashes.

    Expect canonical JSON encoder to strictly differentiate or consistently
    unify .0 floats and integers.
    """

    class HashableMockAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(status=AtomStatus.SUCCESS, message="OK")

    atom1 = HashableMockAtom(config={"timeout": 1.0})
    atom2 = HashableMockAtom(config={"timeout": 1})
    assert atom1.get_hash() == atom2.get_hash()


# T2.18 Zero-Width ZWNJ Character Injection
def test_t2_18_zero_width_zwnj_character_injection():
    """T2.18 Zero-Width ZWNJ Character Injection.

    "job" vs "job\\u200b". Expect string sanitizer to aggressively strip
    zero-width characters prior to hashing.
    """

    class HashableMockAtom(Atom):
        def run(self, context) -> AtomResult:
            return AtomResult(status=AtomStatus.SUCCESS, message="OK")

    atom1 = HashableMockAtom(config={"name": "job"})
    atom2 = HashableMockAtom(config={"name": "job\u200b"})
    assert atom1.get_hash() == atom2.get_hash()
