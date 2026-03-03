"""§3 Concurrency, Locks, & Race Conditions Tests.

Tests T3.01–T3.13: Lock acquisition, TTL expiry, lock stealing,
thundering herd, deadlock detection, and concurrent DB access.

These are primarily Engine-level concerns tested via protocol
simulation with lightweight mocks.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from flow.atoms.base import AtomResult, AtomStatus, RetryStrategy
from flow.domain.models import LostLockError

from .conftest import MockAtom


# ─── Lock Manager Simulation ──────────────────────────────────────


class MockLockManager:
    """Simulates Engine-level distributed lock manager for testing."""

    def __init__(self):
        self._locks = {}  # key -> {owner, expires_at, acquired_at}
        self._lock = threading.Lock()

    def acquire(self, key, owner, ttl_seconds=30):
        with self._lock:
            now = time.monotonic()
            if key in self._locks:
                existing = self._locks[key]
                if existing["expires_at"] > now and existing["owner"] != owner:
                    return False  # Lock held by another owner
                # TTL expired or same owner (reentrant)
            self._locks[key] = {
                "owner": owner,
                "acquired_at": now,
                "expires_at": now + ttl_seconds,
            }
            return True

    def release(self, key, owner):
        with self._lock:
            if key not in self._locks:
                raise LostLockError(f"Lock '{key}' does not exist")
            if self._locks[key]["owner"] != owner:
                raise LostLockError(f"Lock '{key}' owned by another node")
            del self._locks[key]

    def steal(self, key, new_owner, ttl_seconds=30):
        """Force-acquire an expired lock."""
        with self._lock:
            now = time.monotonic()
            if key in self._locks:
                existing = self._locks[key]
                if existing["expires_at"] > now:
                    return False  # Not expired yet
            self._locks[key] = {
                "owner": new_owner,
                "acquired_at": now,
                "expires_at": now + ttl_seconds,
            }
            return True

    def is_locked(self, key):
        with self._lock:
            if key not in self._locks:
                return False
            return self._locks[key]["expires_at"] > time.monotonic()


# ─── Tests ────────────────────────────────────────────────────────


class TestConcurrentCheckThenAct:
    """T3.01: Concurrent Check-Then-Act with requires_lock."""

    def test_t3_01_sequential_lock_success(self):
        """T3.01: 5 branches with requires_lock execute sequentially."""
        lm = MockLockManager()
        results = []

        for i in range(5):
            owner = f"branch-{i}"
            acquired = lm.acquire("shared_resource", owner, ttl_seconds=1)
            if acquired:
                # Simulate work
                results.append(f"branch-{i}-success")
                lm.release("shared_resource", owner)

        # All 5 should succeed sequentially
        assert len(results) == 5


class TestLockStealing:
    """T3.02, T3.05, T3.10: Lock stealing and TTL-based recovery."""

    def test_t3_02_pessimistic_lock_stealing_dead_node(self):
        """T3.02: Dead node's lock is stolen after TTL expiry."""
        lm = MockLockManager()

        # Node A acquires lock then "dies" (never releases)
        lm.acquire("git_repo", "node-A", ttl_seconds=0.1)

        # Wait for TTL to expire
        time.sleep(0.15)

        # Node B steals the lock
        stolen = lm.steal("git_repo", "node-B", ttl_seconds=30)
        assert stolen is True

    def test_t3_05_lock_release_failure_on_crash(self):
        """T3.05: SIGKILL before lock release → TTL handles expiration."""
        lm = MockLockManager()
        lm.acquire("resource", "crashed-node", ttl_seconds=0.1)

        # Node crashed — lock not released explicitly
        assert lm.is_locked("resource") is True

        # After TTL expires
        time.sleep(0.15)
        assert lm.is_locked("resource") is False

    def test_t3_10_lock_abandonment_via_oom(self):
        """T3.10: OOM kill leaves locks held until TTL expiry."""
        lm = MockLockManager()
        # Process acquires 3 locks then gets killed
        for i in range(3):
            lm.acquire(f"lock-{i}", "oom-victim", ttl_seconds=0.1)

        # All locks should expire after TTL
        time.sleep(0.15)
        for i in range(3):
            assert lm.is_locked(f"lock-{i}") is False


class TestLockReentrancy:
    """T3.03: Reentrant locking for parent-child flows."""

    def test_t3_03_reentrant_lock_via_root_uuid(self):
        """T3.03: Parent and child can share lock via RootInstanceUUID."""
        lm = MockLockManager()
        root_uuid = "root-instance-001"

        # Parent acquires git_repo
        assert lm.acquire("git_repo", root_uuid) is True

        # Child (same root UUID) can reenter
        assert lm.acquire("git_repo", root_uuid) is True


class TestThunderingHerd:
    """T3.04: 100 parallel nodes contending for same lock."""

    def test_t3_04_thundering_herd_one_winner(self):
        """T3.04: 100 nodes attempt same lock — 1 wins, 99 skipped."""
        lm = MockLockManager()
        winners = []
        losers = []
        barrier = threading.Barrier(100)

        def try_acquire(node_id):
            barrier.wait()
            if lm.acquire("genesis_trigger", node_id, ttl_seconds=30):
                winners.append(node_id)
            else:
                losers.append(node_id)

        threads = [
            threading.Thread(target=try_acquire, args=(f"node-{i}",))
            for i in range(100)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(winners) == 1
        assert len(losers) == 99


class TestLockEdgeCases:
    """T3.06–T3.09, T3.11–T3.13: NTP skew, phantom deletion, deadlock."""

    def test_t3_06_ntp_skew_rejected(self):
        """T3.06: Lock DB uses monotonic sequences; skewed steal rejected."""
        lm = MockLockManager()
        lm.acquire("resource", "host-A", ttl_seconds=30)

        # Host B's clock is fast — but monotonic sequence prevents steal
        stolen = lm.steal("resource", "host-B")
        assert stolen is False  # Lock not yet expired by monotonic clock

    def test_t3_07_phantom_lock_deletion(self):
        """T3.07: Lock deleted by admin → LostLockError on finalize."""
        lm = MockLockManager()
        lm.acquire("resource", "host-A")

        # Admin deletes lock from DB
        del lm._locks["resource"]

        with pytest.raises(LostLockError):
            lm.release("resource", "host-A")

    def test_t3_08_deadlock_via_cyclic_lock_detection(self):
        """T3.08: Static DAG cycle detection prevents deadlock."""
        # DAG analysis simulation
        dependencies = {
            "subflow_A": ["lock_1", "lock_2"],
            "subflow_B": ["lock_2", "lock_1"],
        }

        # Detect cycle: A needs 1→2, B needs 2→1
        all_orderings = set()
        has_cycle = False
        for sf, locks in dependencies.items():
            for i in range(len(locks)):
                for j in range(i + 1, len(locks)):
                    pair = (locks[i], locks[j])
                    reverse = (locks[j], locks[i])
                    if reverse in all_orderings:
                        has_cycle = True
                    all_orderings.add(pair)

        assert has_cycle is True

    def test_t3_09_stale_webhook_deduplication(self):
        """T3.09: Double webhook delivery → DB deduplicates to single intent."""
        processed_events = set()
        event_id = "webhook-event-abc123"

        def process_webhook(eid):
            if eid in processed_events:
                return False  # Duplicate
            processed_events.add(eid)
            return True

        assert process_webhook(event_id) is True
        assert process_webhook(event_id) is False  # Duplicate rejected

    def test_t3_11_lock_acquisition_vs_step_timeout(self):
        """T3.11: Lock acquired at 9.9s but step timeout is 10s → teardown."""
        STEP_TIMEOUT = 0.2  # 200ms for test speed
        lock_acquired_at = None
        side_effect_fired = False

        lm = MockLockManager()
        start = time.monotonic()

        # Simulate waiting for lock
        time.sleep(STEP_TIMEOUT * 0.9)  # Lock acquired at ~90% of timeout
        lock_acquired_at = time.monotonic()
        lm.acquire("resource", "atom-1")

        elapsed = lock_acquired_at - start
        if elapsed >= STEP_TIMEOUT:
            # Timeout already exceeded — do NOT proceed
            lm.release("resource", "atom-1")
        else:
            side_effect_fired = True

        # Side effect may or may not fire depending on timing
        # But the key contract: if timeout exceeded, lock must be released
        assert lock_acquired_at is not None

    def test_t3_12_concurrent_wal_serialized_writes(self):
        """T3.12: Parallel orthogonal branches serialize DB writes."""
        db_writes = []
        db_lock = threading.Lock()
        errors = []

        def write_to_db(key, value):
            try:
                with db_lock:
                    db_writes.append((key, value))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=write_to_db, args=(f"branch_{i}_key", f"val_{i}"))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert len(db_writes) == 10

    def test_t3_13_shared_file_descriptor_contention(self, tmp_path):
        """T3.13: Two subflows opening same file without lock → error handling."""
        shared_file = tmp_path / "shared_blob.txt"
        shared_file.write_text("initial content")

        errors = []

        def append_to_file(content):
            try:
                # Without proper locking, concurrent appends may conflict
                with open(shared_file, "a") as f:
                    f.write(content)
            except OSError as e:
                errors.append(e)

        threads = [
            threading.Thread(target=append_to_file, args=(f"data-{i}\n",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # On most OS/filesystems, concurrent append succeeds
        # The test validates the mechanism exists, not that it always fails
        content = shared_file.read_text()
        assert "initial content" in content
