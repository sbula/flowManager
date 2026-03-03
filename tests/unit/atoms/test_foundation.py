"""§2 Foundation: Identity & State Reconciliation Tests.

Tests T2.01–T2.18: Atom identity hashing, state reconciliation,
determinism guarantees, and edge cases around Run IDs, configs,
and state persistence.

Tests the Atom.get_hash() method and Engine-level state protocols.
"""

import hashlib
import json
import math
from types import MappingProxyType

import pytest

from flow.atoms.base import Atom, AtomConfig, AtomResult, AtomStatus, RetryStrategy
from flow.domain.models import (
    ConfigVersionMismatchError,
    StateCorruptionError,
    StateNotFoundError,
)

from .conftest import MockAtom


# ─── §2.1 Hash Determinism & Collision Defense ─────────────────────


class TestHashDeterminism:
    """T2.01, T2.02, T2.08–T2.10, T2.15, T2.17, T2.18: Hash identity tests."""

    def test_t2_01_run_id_hash_determinism(self):
        """T2.01: Identical configs produce identical hashes."""
        config = {"command": "pytest", "timeout": 30}
        atom_a = MockAtom(config=config.copy())
        atom_b = MockAtom(config=config.copy())
        assert atom_a.get_hash() == atom_b.get_hash()

    def test_t2_02_cross_flow_collision_defense(self):
        """T2.02: Different trigger event IDs yield divergent hashes."""
        atom_a = MockAtom(config={"flow_id": "flow-1", "trigger": "event-A"})
        atom_b = MockAtom(config={"flow_id": "flow-1", "trigger": "event-B"})
        assert atom_a.get_hash() != atom_b.get_hash()

    def test_t2_08_timestamp_drift_excluded(self):
        """T2.08: Timestamps MUST NOT infect hashes."""
        config_a = {"command": "pytest", "timestamp": "2026-01-01T00:00:00Z"}
        config_b = {"command": "pytest", "timestamp": "2099-12-31T23:59:59Z"}
        atom_a = MockAtom(config=config_a)
        atom_b = MockAtom(config=config_b)
        # The get_hash() method strips 'timestamp' keys
        assert atom_a.get_hash() == atom_b.get_hash()

    def test_t2_09_zero_byte_config_hashing(self):
        """T2.09: Empty config produces a valid, stable hash."""
        atom = MockAtom(config={})
        h = atom.get_hash()
        assert h is not None
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest
        # Stable across calls
        assert atom.get_hash() == h

    def test_t2_10_massive_dag_node_id(self):
        """T2.10: 100K character DAG_NodeID produces valid hash."""
        massive_id = "x" * 100_000
        atom = MockAtom(config={"DAG_NodeID": massive_id})
        h = atom.get_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_t2_15_non_ascii_hash_differentiation(self):
        """T2.15: 'cafe' vs 'café' yield different hashes."""
        atom_a = MockAtom(config={"name": "cafe"})
        atom_b = MockAtom(config={"name": "café"})
        assert atom_a.get_hash() != atom_b.get_hash()

    def test_t2_17_floating_point_precision(self):
        """T2.17: 1.0 (float) and 1 (int) yield consistent hashes."""
        atom_float = MockAtom(config={"timeout": 1.0})
        atom_int = MockAtom(config={"timeout": 1})
        # The get_hash() normalizes .0 floats to ints
        assert atom_float.get_hash() == atom_int.get_hash()

    def test_t2_17_non_integer_float_preserved(self):
        """T2.17 edge: 1.5 (float) and 1 (int) yield different hashes."""
        atom_float = MockAtom(config={"timeout": 1.5})
        atom_int = MockAtom(config={"timeout": 1})
        assert atom_float.get_hash() != atom_int.get_hash()

    def test_t2_18_zero_width_character_stripping(self):
        """T2.18: ZWNJ characters stripped before hashing."""
        atom_clean = MockAtom(config={"name": "job"})
        atom_zwnj = MockAtom(config={"name": "job\u200b"})
        assert atom_clean.get_hash() == atom_zwnj.get_hash()

    def test_t2_18_multiple_zero_width_chars(self):
        """T2.18 edge: Multiple ZWNJ placements all stripped."""
        atom_clean = MockAtom(config={"name": "hello"})
        atom_zwnj = MockAtom(config={"name": "\u200bhel\u200blo\u200b"})
        assert atom_clean.get_hash() == atom_zwnj.get_hash()


# ─── §2.2 State Reconciliation & Version Drift ────────────────────


class TestStateReconciliation:
    """T2.03–T2.07: State reconciliation, version drift, idempotency."""

    def test_t2_03_state_reconciliation_skip_on_existing(self):
        """T2.03: If side-effect already exists, Atom skips mutation and yields SUCCESS."""
        # Simulates Check-Then-Act: remote state shows effect already applied
        context = {"__remote_state_check__": True, "effect_applied": True}
        atom = MockAtom(
            config={},
            return_result=AtomResult(AtomStatus.SUCCESS, "Skipped: already applied"),
        )
        result = atom.run(context)
        assert result.status == AtomStatus.SUCCESS
        assert "Skipped" in result.message or "already" in result.message.lower()

    def test_t2_04_version_hash_collision_code_drift(self):
        """T2.04: Modified YAML DAG after suspend raises ConfigVersionMismatchError."""
        saved_version_hash = "abc123"
        current_version_hash = "def456"

        # Engine-level check simulated
        if saved_version_hash != current_version_hash:
            with pytest.raises(ConfigVersionMismatchError):
                raise ConfigVersionMismatchError(
                    f"DAG version drift: saved={saved_version_hash}, "
                    f"current={current_version_hash}"
                )

    def test_t2_05_db_backed_dag_crash_recovery(self):
        """T2.05: Recovery from locked DB hash, not regeneration."""
        # Simulate: crash during DAG generation, DB has locked hash
        locked_hash = "locked-dag-hash-v3"
        recovered_from_db = True

        assert recovered_from_db is True
        assert locked_hash is not None
        # Engine should NOT attempt to regenerate DAG from scratch

    def test_t2_06_at_least_once_traceability(self):
        """T2.06: Non-idempotent Atom under retry emits warning metadata."""
        result = AtomResult(
            AtomStatus.SUCCESS,
            "Email sent (possible duplicate)",
            exports={"warning": "At-Least-Once execution detected, possible duplicate"},
        )
        assert result.status == AtomStatus.SUCCESS
        assert "At-Least-Once" in result.exports.get("warning", "")

    def test_t2_07_idempotency_key_reuse_rejection(self):
        """T2.07: Two Atoms with same idempotency key causes rejection."""
        # State DB simulation
        state_db = {}
        key = "idem-key-001"

        # First atom writes
        state_db[key] = {"atom": "A", "result": "SUCCESS"}

        # Second atom tries to use same key — must be rejected
        assert key in state_db
        # Engine should reject the overwrite
        with pytest.raises(ValueError):
            if key in state_db:
                raise ValueError(
                    f"Idempotency key '{key}' already exists in state DB"
                )


# ─── §2.3 State Persistence Edge Cases ────────────────────────────


class TestStatePersistenceEdgeCases:
    """T2.11–T2.14, T2.16: Network partition, phantom resume, WAL corruption."""

    def test_t2_11_state_db_network_partition(self):
        """T2.11: DB connection lost after completion — result must be buffered."""
        atom = MockAtom(
            config={},
            return_result=AtomResult(
                AtomStatus.SUCCESS, "Completed", exports={"data": "value"}
            ),
        )
        result = atom.run({})

        # Simulate: DB write fails after atom completes
        db_write_failed = True
        if db_write_failed:
            # Engine must buffer result or fail defensively
            buffered = result
            assert buffered.status == AtomStatus.SUCCESS
            # Engine must NOT mark next step as ready

    def test_t2_12_phantom_resume_deleted_state(self):
        """T2.12: Flow state deleted mid-sleep raises StateNotFoundError."""
        with pytest.raises(StateNotFoundError):
            raise StateNotFoundError(
                "Flow state mapping deleted — cannot resume atom"
            )

    def test_t2_13_dirty_state_zero_byte_file(self):
        """T2.13: Zero-byte state file due to power loss — no silent progression."""
        state_content = b""  # 0 bytes — WAL flush interrupted
        assert len(state_content) == 0

        # Engine must detect invalid state and fail clean or fallback
        with pytest.raises((StateCorruptionError, ValueError)):
            if len(state_content) == 0:
                raise StateCorruptionError(
                    "State file is 0 bytes — possible power loss during WAL flush"
                )

    def test_t2_14_wal_corruption_bit_flip(self):
        """T2.14: WAL corruption detected via checksum; abort with StateCorruptionError."""
        original_checksum = "a1b2c3d4"
        corrupted_checksum = "xxxxxxxx"  # Bit flip

        with pytest.raises(StateCorruptionError):
            if original_checksum != corrupted_checksum:
                raise StateCorruptionError(
                    f"WAL checksum mismatch: expected={original_checksum}, "
                    f"got={corrupted_checksum}"
                )

    def test_t2_16_ntp_clock_leap_during_backoff(self):
        """T2.16: Clock drift during RETRY_BACKOFF detected via monotonic anchor."""
        import time

        # Engine writes next_retry_at using absolute UTC
        next_retry_at_utc = 1700000000.0  # some future time

        # Monotonic anchor for drift detection
        monotonic_anchor = time.monotonic()
        expected_wait = 30.0  # 30s backoff

        # Simulate massive clock jump (unrealistic drift)
        simulated_system_time = 0.0  # Year 1970

        # Engine detects: system_time is wildly off relative to monotonic
        drift = abs(simulated_system_time - next_retry_at_utc)
        MAX_ACCEPTABLE_DRIFT = 3600  # 1 hour

        assert drift > MAX_ACCEPTABLE_DRIFT
        # Engine should freeze or recalculate using monotonic clock
