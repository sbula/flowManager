"""Shared fixtures and helper classes for Atoms test suite.

Provides mock atoms, engine wrappers, and common fixtures for testing
the base Atom protocol, AgentAtom, and Engine-level contracts defined
in 01_05_atoms_spec.md and 01_05_atoms_test.md.
"""

import json
import threading
import time
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from flow.atoms.base import Atom, AtomConfig, AtomResult, AtomStatus, RetryStrategy


# ─── Mock Atoms ─────────────────────────────────────────────────────


class MockAtom(Atom):
    """A simple concrete Atom for base protocol tests."""

    def __init__(self, config=None, return_result=None):
        super().__init__(config)
        self._return_result = return_result or AtomResult(
            AtomStatus.SUCCESS, "Mock completed"
        )

    def run(self, context: Dict[str, Any]) -> AtomResult:
        return self._return_result


class CrashingAtom(Atom):
    """An Atom that raises a specified exception in run()."""

    def __init__(self, exception=None, config=None):
        super().__init__(config)
        self._exception = exception or KeyError("simulated crash")

    def run(self, context: Dict[str, Any]) -> AtomResult:
        raise self._exception


class BadReturnAtom(Atom):
    """An Atom that returns a non-AtomResult value."""

    def __init__(self, return_value=True, config=None):
        super().__init__(config)
        self._return_value = return_value

    def run(self, context: Dict[str, Any]):
        return self._return_value


class SlowCleanupAtom(Atom):
    """An Atom whose cleanup() hangs for a specified duration."""

    def __init__(self, cleanup_delay=5.0, config=None):
        super().__init__(config)
        self._cleanup_delay = cleanup_delay
        self._cleanup_called = False
        self._cleanup_completed = False

    def run(self, context: Dict[str, Any]) -> AtomResult:
        return AtomResult(AtomStatus.SUCCESS, "Done")

    def cleanup(self) -> None:
        self._cleanup_called = True
        time.sleep(self._cleanup_delay)
        self._cleanup_completed = True


class CrashingCleanupAtom(Atom):
    """An Atom whose cleanup() raises an exception."""

    def __init__(self, config=None):
        super().__init__(config)
        self.cleanup_called = False

    def run(self, context: Dict[str, Any]) -> AtomResult:
        return AtomResult(AtomStatus.SUCCESS, "Done")

    def cleanup(self) -> None:
        self.cleanup_called = True
        raise AttributeError("typo in cleanup: self.nonexistent_attr")


class InfiniteRetryAtom(Atom):
    """An Atom that always yields RETRY IMMEDIATE."""

    def __init__(self, config=None):
        super().__init__(config)
        self.call_count = 0

    def run(self, context: Dict[str, Any]) -> AtomResult:
        self.call_count += 1
        return AtomResult(
            AtomStatus.RETRY,
            f"Retry attempt {self.call_count}",
            retry_strategy=RetryStrategy.IMMEDIATE,
        )


class EnvironmentPollutingAtom(Atom):
    """An Atom that tries to sabotage the runtime environment."""

    def __init__(self, sabotage_type="stdout", config=None):
        super().__init__(config)
        self._sabotage_type = sabotage_type

    def run(self, context: Dict[str, Any]) -> AtomResult:
        if self._sabotage_type == "stdout":
            import sys
            sys.stdout = open("nul" if hasattr(__builtins__, '__IPYTHON__') else "/dev/null", "w")
        elif self._sabotage_type == "environ":
            import os
            os.environ["SABOTAGED_KEY"] = "hacked"
        return AtomResult(AtomStatus.SUCCESS, "Sabotaged")


# ─── Engine Wrapper (Simulates Engine's Atom execution contract) ────


class EngineWrapper:
    """Simulates the Engine's try/except wrapper around Atom execution.

    Per spec §6.1: run() is wrapped in aggressive try/except Exception.
    Per spec §6.2: cleanup() has strict timeout and isolated try/except.
    """

    MAX_RETRIES = 5
    CLEANUP_TIMEOUT_MS = 2000

    def __init__(self, atom: Atom):
        self.atom = atom
        self.last_result: Optional[AtomResult] = None
        self.last_error: Optional[Exception] = None
        self.cleanup_errors: list = []
        self._cleanup_timed_out = False

    def execute(self, context: Dict[str, Any]) -> AtomResult:
        """Execute atom with Engine-level exception trapping."""
        try:
            result = self.atom.run(context)

            # T6.02: Validate return type
            if not isinstance(result, AtomResult):
                raise TypeError(
                    f"Atom.run() must return AtomResult, got {type(result).__name__}"
                )

            # T7.01: Validate exports payload size
            if result.exports:
                payload = json.dumps(result.exports, default=str)
                if len(payload) > 128 * 1024:
                    from flow.domain.models import PayloadTooLargeError
                    raise PayloadTooLargeError(
                        f"Exports payload {len(payload)} bytes exceeds 128KB limit"
                    )

            self.last_result = result
            return result

        except Exception as e:
            self.last_error = e
            # T8.17: Double fault protection — try to serialize error
            try:
                error_info = {"type": type(e).__name__, "message": str(e)}
                self.last_result = AtomResult(
                    AtomStatus.FAILED,
                    f"Atom crashed: {type(e).__name__}: {e}",
                    error=error_info,
                )
            except Exception:
                # Double fault: serialization itself failed
                self.last_result = AtomResult(
                    AtomStatus.FAILED,
                    "FAILED_CRITICAL: Double fault in error handling",
                )
            return self.last_result

    def execute_with_retries(
        self, context: Dict[str, Any], max_retries: int = None
    ) -> AtomResult:
        """Execute with retry loop and circuit breaker."""
        max_r = max_retries if max_retries is not None else self.MAX_RETRIES
        for attempt in range(max_r + 1):
            result = self.execute(context)
            if result.status != AtomStatus.RETRY:
                return result
            if attempt == max_r:
                return AtomResult(
                    AtomStatus.FAILED,
                    f"FATAL_LOOP: Max retries ({max_r}) exceeded",
                )
        return result

    def teardown(self, timeout_ms: int = None) -> bool:
        """Execute cleanup() with timeout and isolation."""
        timeout = (timeout_ms or self.CLEANUP_TIMEOUT_MS) / 1000.0

        cleanup_thread = threading.Thread(target=self._run_cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        cleanup_thread.join(timeout=timeout)

        if cleanup_thread.is_alive():
            self._cleanup_timed_out = True
            return False
        return len(self.cleanup_errors) == 0

    def _run_cleanup(self):
        try:
            self.atom.cleanup()
        except Exception as e:
            self.cleanup_errors.append(e)

    @property
    def cleanup_timed_out(self) -> bool:
        return self._cleanup_timed_out


# ─── Export Validation Helpers ──────────────────────────────────────


def validate_exports(exports: Dict[str, Any]) -> None:
    """Validates that exports are JSON-serializable and safe.

    Checks for:
    - Non-serializable types (set, file handles, custom objects)
    - Cyclic references
    - NaN/Infinity floats
    - Non-string dict keys
    - Reserved Engine keys
    - Excessive nesting depth
    """
    RESERVED_KEYS = {"_engine_metadata", "run_id", "_internal_state"}
    MAX_NESTING = 100

    # Reserved key check (T6.13)
    for key in exports:
        if key in RESERVED_KEYS:
            from flow.domain.models import DomainError

            class ReservedKeyCollisionError(DomainError):
                pass

            raise ReservedKeyCollisionError(
                f"Export key '{key}' collides with reserved Engine property"
            )

    # Non-string key check (T6.11)
    _check_string_keys(exports)

    # Dunder key check (T6.12)
    _check_dunder_keys(exports)

    # Serialization check with cycle/NaN/depth detection (T6.03, T6.05, T6.06, T6.07)
    _check_serializable(exports, max_depth=MAX_NESTING)


def _check_string_keys(obj, path="", _seen=None):
    """Ensures all dict keys are strings."""
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if isinstance(obj, (dict, list)) and obj_id in _seen:
        return  # Cycle detected — handled by _check_serializable
    if isinstance(obj, (dict, list)):
        _seen.add(obj_id)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"Export dict keys must be strings, got {type(k).__name__} at {path}"
                )
            _check_string_keys(v, f"{path}.{k}", _seen)
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            _check_string_keys(item, f"{path}[{i}]", _seen)


def _check_dunder_keys(obj, path="", _seen=None):
    """Rejects dunder keys in exports."""
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if isinstance(obj, (dict, list)) and obj_id in _seen:
        return  # Cycle detected — handled by _check_serializable
    if isinstance(obj, (dict, list)):
        _seen.add(obj_id)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith("__") and k.endswith("__"):
                raise ValueError(
                    f"Dunder key '{k}' is forbidden in exports at {path}"
                )
            _check_dunder_keys(v, f"{path}.{k}", _seen)
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            _check_dunder_keys(item, f"{path}[{i}]", _seen)


def _check_serializable(obj, max_depth=100, _depth=0, _seen=None):
    """Deep serialization check with cycle, NaN, infinity, and tuple detection."""
    if _seen is None:
        _seen = set()

    if _depth > max_depth:
        raise RecursionError(f"Max_Nesting_Exceeded: depth {_depth} > {max_depth}")

    obj_id = id(obj)
    if isinstance(obj, (dict, list)):
        if obj_id in _seen:
            raise ValueError("Cyclic reference detected in exports")
        _seen.add(obj_id)

    if isinstance(obj, float):
        import math
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"NaN/Infinity not allowed in exports: {obj}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _check_serializable(v, max_depth, _depth + 1, _seen)
    elif isinstance(obj, (list,)):
        for item in obj:
            _check_serializable(item, max_depth, _depth + 1, _seen)
    elif isinstance(obj, tuple):
        raise TypeError(
            "Tuple is not JSON-native; exports must use list instead"
        )
    elif isinstance(obj, set):
        raise TypeError(
            "Set is not JSON-serializable; exports must use list instead"
        )
    elif isinstance(obj, (str, int, bool, type(None))):
        pass  # JSON-native
    else:
        # Custom objects, file handles, etc.
        raise TypeError(
            f"Non-serializable type '{type(obj).__name__}' in exports"
        )

    if isinstance(obj, (dict, list)):
        _seen.discard(obj_id)


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def basic_context():
    """Returns a minimal valid context dict."""
    return {"__task_id__": "test-task-001", "__root__": "."}


@pytest.fixture
def basic_config():
    """Returns a minimal valid atom config dict."""
    return {"run_id": "test-run-001"}


@pytest.fixture
def tmp_flow_dir(tmp_path):
    """Returns a temporary .flow directory structure."""
    flow_dir = tmp_path / ".flow"
    flow_dir.mkdir()
    artifacts_dir = flow_dir / "artifacts"
    artifacts_dir.mkdir()
    state_dir = tmp_path / ".flow_state"
    state_dir.mkdir()
    return flow_dir


@pytest.fixture
def immutable_context(basic_context):
    """Returns a read-only MappingProxyType context (spec §5.1.05)."""
    return MappingProxyType(basic_context)


@pytest.fixture
def engine_wrapper():
    """Factory fixture for creating EngineWrapper instances."""
    def _make(atom):
        return EngineWrapper(atom)
    return _make
