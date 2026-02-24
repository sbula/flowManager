# 01_05 Test Specification: Atoms
> **Status**: DRAFT (V-Next Validations)
> **Target**: `src/flow/atoms/` 

## 1. Goal
This document defines the strict test inventory for all `Atom` implementations. Tests must validate domain logic, distributed systems fault tolerance, and the "Paranoid Architecture" constraints outlined in the `01_05_atoms_critique.md`.

**Testing Philosophy (Chaos Engineering):**
Atoms must be tested under hostile conditions. Mocks are acceptable for external API calls, but Engine-level interactions (OS signals, OOM simulations, stale lock files) MUST be integration-tested using real subprocesses where feasible.

---

## T1. Core Mechanics & State Transitions
These tests validate the base `Atom` abstract class and standard execution patterns.

*   **T1.01 Hash Determinism**: 
    *   *Setup*: Instantiate an Atom twice with identical Config, Parent Flow ID, and Loop Index.
    *   *Operation*: Calculate `Run ID`.
    *   *Expectation*: IDs must be perfectly identical.
*   **T1.02 Hash Divergence**:
    *   *Setup*: Instantiate the same Atom but increment the `Loop Index` by 1.
    *   *Expectation*: IDs must be completely different (no collisions).
*   **T1.03 State Transition - Success**:
    *   *Setup*: Execute a passing `AssertionAtom`.
    *   *Expectation*: Returns `AtomResult(status=SUCCESS)` and merges expected data into `exports`.
*   **T1.04 State Transition - Waiting/Pause**:
    *   *Setup*: Execute a `ManualReviewAtom`.
    *   *Expectation*: Returns `WAITING`. Context/exports must be strictly isolated and not mutated during the wait phase.
*   **T1.05 Re-entrant Loop Hydration (`AgentAtom`)**:
    *   *Setup*: Inject a mock `call_stack` showing 3 completed Tool calls into the `context`. Invoke `AgentAtom.run()`.
    *   *Expectation*: The Atom skips the initial prompt compilation, successfully rehydrates the LLM scratchpad from the 3 prior tools, and yields the 4th action.

---

## T2. Isolation & Resource Sandboxing
Validating the protective boundaries around the Orchestrator Engine.

*   **T2.01 The OOM Defense (String Size Limit)**:
    *   *Setup*: Create a mocked `TransformAtom` that maliciously attempts to return a 500MB string payload in `AtomResult.exports`.
    *   *Expectation*: The Base `Atom` or Executor wrapper intercepts the return, raises a `PayloadTooLargeError`, trims the string, and transitions the Atom to `FAILED` instead of crashing the Engine.
*   **T2.02 Blob Overflow Write Failure**:
    *   *Setup*: Mock the filesystem to simulate `Disk Full` (IOError). Execute an Atom trying to write a 1MB blob to `.flow/artifacts/`.
    *   *Expectation*: The Atom catches the `IOError`, does not crash the Orchestrator, and returns `FAILED` with the IO stack trace in the `error` dictionary.
*   **T2.03 Context Immutability (Read-Only Guard)**:
    *   *Setup*: Inject a `MappingProxyType` context into an Atom. The Atom attempts to execute `context["new_key"] = "value"`.
    *   *Expectation*: Raises `TypeError`. Atom must fail safely. State pollution is blocked.

---

## T3. Fault Domains & Exception Bleeding
Validating the Engine's "Iron Wall" against bad code.

*   **T3.01 Synchronous Exception Trapping**:
    *   *Setup*: Atom `run()` purposefully raises `KeyError`.
    *   *Expectation*: Executor wrapper catches the error, logs the trace, and returns `FAILED`. Orchestrator remains online.
*   **T3.02 Async / Coroutine Leakage**:
    *   *Setup*: Atom spawns an async task that throws an unhandled exception outside the main `run()` stack.
    *   *Expectation*: The Engine's event loop supervisor traps the orphaned exception and attributes it to the correct `Run ID`, failing the Atom.
*   **T3.03 Subprocess Fate Sharing (Zombie Prevention)**:
    *   *Setup*: `ScriptAtom` spawns an infinite `while true` bash script.
    *   *Operation*: The Engine sends a `SIGTERM` / teardown signal to the Atom's `cleanup()` hook.
    *   *Expectation*: `cleanup()` uses Job Objects/process groups to assert a `SIGKILL`, ensuring the child bash script is destroyed instantly.

---

## T4. Advanced Resumption & Chaos Patterns
Validating the critical edge cases identified in the Paranoid Critique.

*   **T4.01 LLM Memoization Cache (Idempotency)**:
    *   *Setup*: Engine executes `AgentAtom`. LLM generates Response A. Engine simulates a crash *before* the Atom saves state. Engine restarts, recovering the old `Run ID`.
    *   *Expectation*: The Engine intercepts the LLM query using the `Run ID` and returns the cached Response A. No new network calls are made.
*   **T4.02 Atomic Append (Check-Then-Act)**:
    *   *Setup*: `Loom` edit attempts to append "Footer" to a file. The network drops before success is reported. Engine restarts and tries again.
    *   *Expectation*: `Loom` detects "Footer" is already present, counts matches, recognizes the operation is statically complete, and returns a cached `SUCCESS` without adding a duplicate "Footer".
*   **T4.03 Git-Backed Rollback (`compensate`)**:
    *   *Setup*: Orchestrator initiates a destructive Flow. Simulated file deletions occur. Flow fails. Engine invokes `compensate()`.
    *   *Expectation*: `compensate()` executes `git reset --hard <checkpoint>` and `git clean -fd`. Final filesystem state perfectly matches the initial pre-flight commit structure.
*   **T4.04 Graceful Teardown Deadlock Break**:
    *   *Setup*: Orchestrator receives `SIGTERM`. Invokes Atom `cleanup()`. A mocked database socket inside `cleanup()` purposefully hangs indefinitely.
    *   *Expectation*: The Orchestrator asserts a hard absolute timeout (e.g., via `signal.alarm`) and aborts the hung thread, successfully tearing down the main Engine process.
*   **T4.05 Version Hash Collision Detection**:
    *   *Setup*: Engine suspends a `ManualReviewAtom`. While suspended, developer modifies the underlying YAML flow definition (e.g., changes `retries: 3` to `retries: 5`). User clicks 'Approve'.
    *   *Expectation*: Engine recalculates `Run ID` hash, detects a configuration mismatch against the suspended state, blocks resumption, and throws a `ConfigVersionMismatchError`.
