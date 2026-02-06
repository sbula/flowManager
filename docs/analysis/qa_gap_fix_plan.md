# Implementation Plan - QA Gap Fixes

## Goal Description
Address the critical gaps identified during the "Paranoid QA" audit of the Status Domain (01_02) and Engine Core (01_03). The primary goal is to elevate the system from "Unit Tested" to "Production Hardened" by implementing missing integration scenarios, recursive workflows, and concurrency protection.

## User Review Required
> [!IMPORTANT]
> **New Directory Structure**: I will be creating a `tests/integration` directory to strictly separate integration tests from unit tests, as per your global rules.

> [!WARNING]
> **Loom Behavior Change**: I propose enforcing an "Optimistic Lock" in the Loom Atom. It will assume the operation fails if the file modification time changes between Read and Write. This might cause flakiness if the filesystem is very active (e.g., heavily watched by other tools), but it prevents data loss.

## Proposed Changes

### 1. Integration Test Suite (`tests/integration`)
Currently, tests are mixed or mocked. I will create a dedicated suite for "Real World" scenarios.

#### [NEW] [test_lifecycle.py](file:///c:/development/pitbula/flowManager/tests/integration/test_lifecycle.py)
*   **Purpose**: Test the full cycle: `Hydrate -> Load Status -> Dispatch -> Execute -> Persist`.
*   **Scenarios**:
    *   `test_full_run_success`: End-to-end run of a 3-step workflow.
    *   `test_crash_recovery_e2e`: Simulate process death and verify `intent.lock` recovery on next run.

### 2. Engine Core Hardening (`src/flow/engine`)

#### [MODIFY] [core.py](file:///c:/development/pitbula/flowManager/src/flow/engine/core.py)
*   **Fix T3.09 (Ambiguous Focus)**: Add a `validate_state()` method that runs after loading `status.md`. It must raise `StateError` if multiple active tasks exist, even if the Parser accepted them (Defense in Depth).
*   **Fix T7.07 (Fractal Zoom)**: Update `find_active_task()` to be recursive.
    *   *Current*: Returns the active task in the current tree.
    *   *New*: If the active task has `ref` pointing to a sub-flow, **load that sub-flow** and traverse down until a leaf task is found. This enables "Run-in-Place" for deep hierarchies.

### 3. Loom Safety (`src/flow/engine/loom.py`)

#### [MODIFY] [loom.py](file:///c:/development/pitbula/flowManager/src/flow/engine/loom.py)
*   **Fix T6.10 (Optimistic Locking)**:
    1.  Capture `os.stat(path).st_mtime_ns` before reading content.
    2.  Perform the text insertion in memory.
    3.  **Verify**: Check `os.stat(path).st_mtime_ns` again.
    4.  **Write**: Only write if timestamps match. Else raise `LoomError("Content Changed")`.

## Verification Plan

### Automated Tests
*   **Unit**: Update `test_resilience.py` and `test_loom_advanced.py` to match new strict behaviors.
*   **Integration**: Run `pytest tests/integration` to verify the new e2e suite.

### Manual Verification
*   None required. The new Integration suite serves as the proof.
