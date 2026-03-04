# 01_05 Test Specification: Atoms
> **Status**: DRAFT (Paranoid QA V-Next Validations)
> **Owner**: Senior QA Architecture Team
> **Target**: `src/flo

## 1. Goal & QA Philosophy
This document defines the strict, DAU-resistant (Dumbest Available User) test inventory for all `Atom` implementations. 

As a Senior QA team, we assume the system *will* fail violently. Hardware will die in the middle of disk writes, network cables will be pulled during LLM streams, junior developers will return raw socket handles instead of JSON, and sub-workflows will be nested infinitely by recursive LLM hallucinations. 

Our core philosophy: **"There is no happy path; there are only tolerated fault states."**

---

## 2. Foundation: Identity & State Reconciliation
These tests ensure the Engine correctly identifies, tracks, and conceptually heals the state.

*   **T2.01 Run ID Hash Determinism**: Instantiate Atom twice identically. Expect identical IDs.
*   **T2.02 Cross-Flow Collision Defense**: Natively instantiate parallel `TriggerEventIDs`. Expect divergent Hash IDs.
*   **T2.03 State Reconciliation Verification**: Simulate crash after mutating Atom side-effect but BEFORE local state save. On restart, expect Atom to check remote state, skip mutation, and yield `SUCCESS`.
*   **T2.04 Version Hash Collision (Code Drift)**: Suspend flow, modify YAML DAG, resume. Expect `ConfigVersionMismatchError`.
*   **T2.05 Database-Backed DAG Serialization**: Force crash during dynamic DAG generation. Expect recovery from locked database hash, not a regeneration attempt.
*   **T2.06 At-Least-Once Traceability (Ghost Writes)**: Execute `Unsafe` non-idempotent Atom under retry. Expect `warning: "At-Least-Once"` metadata without halting.
*   **T2.07 Idempotency Key Re-Use Attack**: Simulate two different Atoms requesting the exact same Idempotency Key logic. Expect failure or overwrite rejection in the state DB.
*   **T2.08 Timestamp Drift in Run ID**: Inject wildly different UTC timestamps into the environment properties during two identical instantiations. Expect the Hash ID to remain perfectly identical (timestamps must not infect hashes).
*   **T2.09 Zero-Byte Config Hashing**: Instantiate an Atom with an entirely empty `config: {}`. Expect a valid, stable hash, not `NoneType` or validation crashes.
*   **T2.10 Massive DAG Node ID Validation**: Pass a `DAG_NodeID` of 100,000 characters. Expect proper hashing and no string length DB exceptions.
*   **T2.11 State DB Network Partition**: Atom completes successfully, but the connection to the `.flow_state/` embedded DB is severed before writing results. Expect Atom result is buffered or Orchestrator defensively fails *before* marking next step.
*   **T2.12 Phantom Resume on Deleted State**: Engine attempts to resume an Atom where `.flow_state/` mapping is manually deleted mid-sleep. Expect explicit `StateNotFoundError`, forcing flow into `FAILED` rather than corrupting memory.
*   **T2.13 Dirty State Heuristics**: State file exists but size is exactly 0 bytes due to power loss during WAL flush. Expect fallback to previous valid state snapshot or clean failure, NO silent progression.
*   **T2.14 WAL File Corruption (Bit Flip)**: The SQLite `.flow_state/` WAL file is corrupted with random bytes by a failing disk controller. On load, expect the Engine to detect checksum failure and abort Flow execution immediately with `StateCorruptionError`, preventing hallucinated progress.
*   **T2.15 Hash Collision with Non-ASCII Characters**: Two Atoms have identical configs, except one uses `name: "cafe"` and the other `name: "café"`. Expect the UTF-8 normalized strings to yield different deterministic hashes, preventing state collision.
*   **T2.16 NTP Clock Leap during Backoff**: Atom yields `RETRY` with `RETRY_BACKOFF` and Engine writes `next_retry_at` using absolute UTC time. While paused, the host NTP client forces a massive clock update (e.g. year jumps to 1970 or 2038). Expect Engine's scheduler to detect unrealistic temporal drift against a monotonic clock anchor and either safely freeze or recalculate, preventing instant DDoS of the retry target.
*   **T2.17 Floating Point Precision Loss in Hashes**: JSON normalization destroying Run ID determinism due to float vs integer casting. A DAU Developer passes `timeout: 1.0` in YAML which maps to Python `float`. Expect the canonical JSON encoder to strictly differentiate or consistently unify `.0` floats and integers to prevent hashing mismatches during Break/Restart.
*   **T2.18 Zero-Width ZWNJ Character Injection**: Two parallel Atoms are spawned, one with `name: "job"` and the other `name: "job\u200b"`. Expect the string sanitizer to aggressively strip zero-width characters prior to hashing to prevent invisible cache misses or silent state collisions.

---

## 3. Concurrency, Locks, & Race Conditions
Validating structural orthogonality, mutual exclusion, and high-contention traffic.

*   **T3.01 Concurrent Check-Then-Act Orthogonal Fan-Out**: 5 branches execute non-unique DB creates. With `requires_lock`, expect sequential Check-Then-Act success.
*   **T3.02 Pessimistic Lock Stealing (Dead Node)**: Simulate hard Orchestrator power loss holding a lock. On TTL expiry, expect active node to aggressively steal the lock.
*   **T3.03 Lock Reentrancy (The Deadly Embrace)**: Parent acquires `git_repo`, calls Sub-Flow requiring `git_repo`. Expect reentrant success via `RootInstanceUUID` hierarchy matching without deadlock.
*   **T3.04 Thundering Herd Lock Contention**: 100 parallel nodes attempt identical Genesis trigger. Expect 1 winner, 99 graceful `SKIPPED` yields.
*   **T3.05 Lock Release Failure on Crash**: Node completes work but `SIGKILL` hits *before* releasing lock. Expect TTL to correctly handle expiration.
*   **T3.06 NTP Clock Skew vs TTL**: Host A acquires lock with 30s TTL. Host B's clock is 40s fast. Host B attempts to steal. Expect Lock DB (using strictly monotonic sequences or centralized DB time) to reject the skewed steal attempt.
*   **T3.07 Phantom Lock Deletion (Splitted Network)**: Host A has lock. DB drops lock due to DB operator admin action. Host A attempts to finalize step. Expect DB write failure (`LostLockError`) preventing phantom writes.
*   **T3.08 Deadlock via Cyclic Lock Request**: Setup Subflow A requiring Lock 1 then Lock 2, parallel Subflow B requiring Lock 2 then Lock 1. Expect Engine router to detect static DAG cycle during parse, preventing execution.
*   **T3.09 Stale Webhook Parallelism (Double Delivery)**: AWS delivers the same webhook twice simultaneously to two Orchestrator instances. Expect DB transaction constraints to deduplicate perfectly, launching only a single intent.
*   **T3.10 Lock Abandonment via OOM**: Process acquires 3 locks then gets SIGKILL from Linux OOM Killer (no graceful teardown). Expect locks to remain held until exact TTL expiry, then stolen by queue.
*   **T3.11 Lock Acquisition vs Step Timeout Race Condition**: An Atom waits 9.9s to acquire a lock and succeeds, but the global step timeout is 10.0s. The Atom triggers its side-effect at 10.1s. Expect the Engine to prioritize the timeout signal over the lock acquisition success, tearing down the newly acquired lock immediately before the side-effect executes.
*   **T3.12 Un-Synchronized State DB Writes (Orthogonal Bypass)**: Two parallel orthogonal branches execute within the same Flow, bypassing locks because they write to different schema keys. However, the SQLite WAL flush occurs concurrently. Expect the Engine's DB access layer to natively serialize the writes (e.g. via connection pooling/mutex) preventing `database is locked` operational failures.
*   **T3.13 Deadlock via Shared File Descriptors**: Two parallel Subflows attempt to open the exact same physical `.flow/artifacts/blob_X.txt` in append mode simultaneously without declaring overlapping `requires_lock`. Expect the Engine's sandbox to either enforce strict POSIX file locks (`flock`) throwing `ResourceBusyError`, or for the Atom's isolated wrapper to catch the OS `EWOULDBLOCK` and yield `RETRY_BACKOFF`.

---

## 4. Cognitive Engine & Tool Orchestration 
Defending against stochastic responses, malicious prompts, and broken tools. Grouped by fault domain.

### 4.1 AgentAtom Context Storage & Memory Limits (The Blob Defenses)
*   **T4.1.01 `AgentAtom` Context Overflow Blob Promotion**: Force an `AgentAtom` to generate a 250KB context scratchpad over 10 loops. Expect the Atom wrapper to automatically detect the >128KB threshold, write the history to a deterministic `.flow/artifacts/blob_{Run_ID}.txt`, and export only the pointer, preventing Orchestrator DB lag.
*   **T4.1.02 Resumption from Blob Pointer**: The Engine restarts and reads `context.json` containing only a `<blob_ptr>`. Expect the `AgentAtom.run()` to natively hydrate its internal prompt context from disk automatically before engaging the LLM.
*   **T4.1.03 Blob IO Failure on Context Swap**: `AgentAtom` attempts to commit its 250KB context, but the disk hits `ENOSPC` (Disk Full). Expect the Atom to trap the `OSError`, yield an `AtomStatus.FAILED` state, and prevent any corrupted partial state from reaching the DB.
*   **T4.1.04 Context Hydration with Altered Schema**: Engine restarts and loads a Blob pointer for an `AgentAtom`'s context. However, the Developer updated the flow YAML `config` to require a new strict JSON schema. Upon hydration, the JSON from the Blob fails the new Pydantic schema validation. Expect the Atom wrapper to gracefully catch the schema drift, rejecting the resume and failing the step rather than feeding broken context to the LLM.

### 4.2 AgentAtom ReAct Loop Break/Restart (State Reconciliation)
*   **T4.2.01 Mid-Loop Hard Crash (The Split-Brain Test)**: `AgentAtom` yields a Tool execution signal to the Engine. The Engine executes the tool successfully but `SIGKILLs` the entire host before the Atom processes the result. On restart, expect the `AgentAtom` to re-forge the specific deterministic `Sub-Run ID`, query the cache, and instantly restore the required tool output without re-invoking the LLM.
    *   **Note (01_07 Cross-Ref)**: When Skills are part of the ReAct loop (01_07 §4.1 Path 2), this test MUST also verify: crash during `skill.execute()` → AgentAtom rehydrates history → detects missing tool response → re-invokes the Skill. The Skill's Check-Then-Act guarantee (01_07 §4.3) and the idempotency token (01_07 §8.1, `tool_call_index = len(rehydrated_history)`) prevent duplicate side-effects.
*   **T4.2.02 Sub-Run ID Forgery Consistency**: Inject noise (whitespace, dict key ordering) into a simulated ReAct loop request. Expect the `AgentAtom` wrapper to normalize the payload before hashing the `Sub-Run ID`, ensuring deterministic cache hits.
*   **T4.2.03 Context Truncation on Resume**: Flow is paused. The underlying model limits change. Upon resuming the `AgentAtom`, the previously valid context now exceeds max tokens. Expect the `AgentAtom` wrapper to catch the token validation failure *before* network I/O, yielding a structured `FAILED_PARSE` to the Engine.
*   **T4.2.04 Sub-Run ID vs Loop Count Drift**: Flow pauses while the `AgentAtom` is on loop offset 3. Developer explicitly mutates the DB state cache to delete the cached result of loop 2. On resume, the Engine attempts to hydrate the state. Expect the deterministic Sub-Run ID generation sequence to detect the missing cache gap, cleanly rolling back its internal offset or failing explicitly with `CacheContinuityError`.

### 4.3 AgentAtom Exception Trapping (The Iron Wall)
*   **T4.3.01 Hallucinated Subflow Dispatch Rejection**: The inner LLM loop generates a structurally valid directive to orchestrate an entire new Flow DAG. Expect the `AgentAtom` wrapper's output parser to instantly throw an `UnauthorizedSubflowError`, injecting the failure back into the LLM context or failing the Atom entirely, enforcing the "Atoms don't route DAGs" rule.
    *   **Note (01_07 Cross-Ref)**: This test MUST differentiate between: (a) Agent trying to orchestrate a raw sub-flow → `UnauthorizedSubflowError` (this test), and (b) Skill returning `SkillResult(status=PAUSED_FOR_EXPANSION)` → **valid** V1 behaviour, triggers Engine pause (see 01_07 §8.5 and 01_07_skills_test.md T4.07). The `_active_skill` tracking contract tests (01_05 §3.3.1) belong in the 01_07 test spec, not here, to avoid circular test dependencies.
*   **T4.3.02 LLM Yields Valid JSON but Invalid Atom Output Schema**: The LLM successfully completes its task and outputs a perfect JSON response block. However, the keys in that JSON do not match the expected `exports` schema defined in the DAG configuration. Expect the wrapper to intercept the output, inject a localized schema validation failure back into the LLM context, and trigger an automatic retry without failing the Orchestrator step (until `max_loops`).
---

## 5. Sub-Flows & Fractal Deep Resumption
Recursive architecture testing. This covers Break/Restart and Workflow-in-Workflow mechanics.

### 5.1 Sub-Flow Initialization & Execution
*   **T5.1.01 Maximum Depth Exceeded (Infinite Recursion)**: Flow unconditionally spawns itself. Expect `max_depth` trip (e.g. 10), violently halting branch with `FATAL_LOOP`.
*   **T5.1.02 Cross-Subflow Variable Type Shadowing**: Parent defines `targets` as array, Child defines `targets` as string. Expect strict merge schema validation preventing silent coercion.
*   **T5.1.03 Extreme Fan-out Subflow Orchestration**: Single map step spawns 10,000 subflows. Expect Engine Router to queue/paginate execution to prevent memory swap.
*   **T5.1.04 Un-Serializable Context in Subflow Export**: Subflow completes, but its context contains custom objects. Expect Parent's merge logic to catch TypeError before polluting Parent state.
*   **T5.1.05 Parent Context Mutation While Child Active**: Parent flow spawns an async child subflow, but a DAU developer attempts to mutate the parent's `context` directly in a parallel branch. Expect the Engine to enforce rigid `MappingProxyType` immutability on the parent context while any child is resolving, throwing a `RuntimeError` on the mutation attempt to prevent irreconcilable merge conflicts.
*   **T5.1.06 Topological Merge Conflict**: Two parallel Subflow branches complete at the exact same millisecond, exporting identical dictionary keys but with differing values (e.g., `Branch_A` exports `result: "A"`, `Branch_B` exports `result: "B"`). Expect the Orchestrator's Fan-In Reducer to reject the ambiguous dict-merge and fail the parent Flow with `SchemaCollisionError` rather than silently favoring the last-write-wins.

### 5.2 Deep Hydration, Break & Restart (State Consistency)
*   **T5.2.01 Crash Exactly Between Child Atoms**: Subflow completes Atom A, crashes before starting Atom B. Parent Flow is actively WAITING. On restart, Engine loads Parent -> loads Child -> skips A -> perfectly executes B.
*   **T5.2.02 Subflow Deep Resume (Step Jump)**: Hard crash while Sub-flow is on Step 4. Parent restarts, queries Engine. Expect Child to jump perfectly to Step 4, skipping 1-3.
*   **T5.2.03 Parent Deletes SubFlow State (DAU)**: Admin deletes `.flow_state/` for SubFlow but leaves Parent state. On resume, expect Parent to realize Child ID is gone, failing the Parent with `MissingSubflowStateError`.
*   **T5.2.04 Context Re-Merge Resistance**: Pause Subflow. Mutate Parent's context via CLI. Resume. Expect Subflow to receive newly merged global context upon resuming from paused state.
*   **T5.2.05 Network Drop During Parent Return**: Subflow completes final step, returns SUCCESS, network drops before Parent acknowledges. Expect Idempotency/Check-Then-Act validation to prevent Subflow from re-running; Parent syncs from Subflow DB state.
*   **T5.2.06 Parent Teardown While Child Active**: Parent Flow receives `SIGTERM`. Child Subflow is mid-execution of a Tool. Expect recursive teardown signal traversing downward into Child's `cleanup()`.
*   **T5.2.07 Orphaned Child Subflow Reconnection**: Orchestrator host dies while Child is paused. Parent restarts on Node A, Child resumes concurrently on Node B due to queue polling. Expect locks/lineage to maintain consistency.
*   **T5.2.08 Subflow in Subflow Disconnect (L3 Resumption)**: Crash while L3 Subflow is computing. Expect seamless "walk down" pointer resolution (Root -> A -> B -> Active Atom) without manual intervention.
*   **T5.2.09 Child Subflow Modifies Shared Context (Break/Restart)**: Child executes a mutating step modifying a shared dict. Crash happens before Parent syncs. On Resume, expect Parent to fetch the exact final state of Child without re-triggering the Child's execution.
*   **T5.2.10 DAG Version Drift During Deep Pause**: L1 Flow starts L2 Subflow. L2 hits a `WAITING` state. While paused, DAU developer pushes a new YAML DAG for L2 omitting the current step. On Resume, expect a strict `ConfigVersionMismatchError` stopping the execution rather than arbitrary jump behavior.
*   **T5.2.11 Subflow-in-Subflow Cyclic Deadlock (DAU)**: DAU configures `Flow_A` to call `Flow_B`, and `Flow_B` to call `Flow_A`. Expect the Engine's DAG analyzer to catch this cyclic reference either strictly during initialization or natively enforce a tight `max_depth` to fail violently without causing `RecursionError` Stack Overflow.
*   **T5.2.12 Unserializable Child Context on Break/Restart**: Child subflow pauses. During the pause, a developer deploys a new Atom that injects an unserializable object (e.g., a raw DB connection) into the child's context. On resume, the Engine attempts to resync parent and child state. Expect the deep serialization scanner to catch the object, forcefully failing the child subflow and rolling its state back to the last valid snapshot before propagating the failure.
*   **T5.2.13 Subflow Orphan Re-Parenting (DAU Attack)**: Admin manually modifies `.flow_state/` to attach a disconnected, successfully completed L2 Subflow directly to a newly launched, unrelated L1 Flow ID. Upon L1 reaching the Subflow node, expect the cryptographic lineage verification (Parent_UUID -> Child_UUID binding) to instantly reject the hijacked cache and execute a fresh Subflow instance instead.

---

## 6. Data Contracts & Serialization (DAU Defenses)
Defending against malformed state and developer oversights.

*   **T6.01 Context Immutability (Read-Only Guard)**: Try to mutate `context["new_key"] = "x"` inside Atom via `MappingProxyType`. Expect `TypeError`.
*   **T6.02 Invalid Return Type Safety**: Custom Atom returns `True` instead of `AtomResult`. Expect Engine wrapper to raise `TypeError` and fail step without crashing DAG router.
*   **T6.03 JSON Serialization Barrier**: Atom returns `set()` or `FileHandle` in `exports`. Expect `json.dumps()` check to catch TypeError, yield `FAILED` with serialization warning.
*   **T6.04 Administrative Context Mutation (Poison Pill Bypass)**: Admin executes `flow mutate-context` to fix broken schema. On Resume, expect successful re-verification and continuation.
*   **T6.05 Self-Referential (Cyclic) Context Injection**: DAU Developer injects a cycle `a = {}; a["self"] = a` into Context. Expect cycle detection during serialization, failing the Atom instead of triggering maximum recursion depth stack crash.
*   **T6.06 NaN / Infinity Injection**: Custom Python tool returns `float('inf')` or `float('nan')`. Standard JSON validator traps it (as JSON spec lacks Infinity). Expect serialization failure.
*   **T6.07 Massively Nested JSON (Stack Overflow Vector)**: Context payload contains JSON nested 10,000 layers deep. Expect DAG validation parsing to catch `Max_Nesting_Exceeded` warning before polluting DB.
*   **T6.08 Escape Sequence Poisoning**: String in context contains raw null bytes `\0` or terminal escape codes `\x1b[2J`. Expect Engine redactors to strip or sanitize terminal manipulation chars prior to audit log emission.
*   **T6.09 Invalid Atom Schema Declaration**: DAU Developer defines an Atom where `required` Config schema fields list contains a field that is completely missing from `properties`. Expect the Engine to strictly reject the Atom during DAG compilation, preventing runtime ambiguity.
*   **T6.10 Un-Hashable Custom Object Injection**: Atom explicitly bypasses standard returns and exports a raw custom Python class instance (not a scalar/dict). Expect `AtomResult` constructor to catch it or the Engine to reject it during dict-serialization, preventing database corruption.
*   **T6.11 Dictionary Key Type Coercion Anomaly**: DAU Atom exports `{1: "value", True: "bool"}`. Standard JSON coerces these to strings, breaking strict schema hashing. Expect strict validation on the `exports` boundary to enforce String-keys-only before merging to global state.
*   **T6.12 Serialization Deep Hash Poisoning**: Atom context generates a deep dictionary mapping where a key is `__class__` or standard Python dunder methods. JSON serialization naturally accepts this, but engine internal mapping might break. Expect explicit structural rejection or sandboxing of dunder keys within `exports` payloads.
*   **T6.13 Export Key Masking Core Engine Properties**: An Atom attempts to export a key named `_engine_metadata` or `run_id`, attempting to overwrite immutable or reserved Orchestrator state variables. Expect the context-merge operation to throw `ReservedKeyCollisionError` and fail the Atom prior to polluting the upstream global context.
*   **T6.14 The Tuple-List Rehydration Failure**: An Atom intentionally exports a Python `tuple` in its `exports`. The JSON state serializer converts this to a `list` upon writing to disk. On Engine break/restart, the state is hydrated as a `list`. Expect the Atom's strict input validation (if expecting a `tuple`) to reject the coerced list, simulating a Poison Pill. The Engine's export validation MUST recursively intercept and reject non-JSON-native structures (like `tuple`, `set`) prior to the initial state write.
*   **T6.15 MRO (Method Resolution Order) Injection**: A custom object is returned in `exports` that uses multiple inheritance or overrides `__class__` logic specifically to bypass Pydantic base model checks but behaves maliciously during iteration. Expect the Engine's deep state serializer to ignore class methods entirely and only serialize pure dict schemas, effectively neutering the MRO attack during transit to the next Atom.

---

## 7. Resource Limits & Denial of Service Defenses
Hardware limits and environment starvation.

*   **T7.01 The OOM Defense (String Size Limit)**: Atom returns 500MB string payload in `exports`. Expect `PayloadTooLargeError`, string truncation, and Atom yields `FAILED`.
*   **T7.02 Blob Overflow Write Failure (Hardware Fault)**: Mock `Disk Full` via `ENOSPC`. Atom attempts to write Blob. Expect Atom to return `FAILED`. Engine freezes instantly to prevent WAL corruption.
*   **T7.03 Memory Bomb Restriction (cgroups/OOMKiller)**: Atom consumes 100GB RAM internally. Expect OS OOM Killer to kill child process. Engine registers process termination as specific `FAILED_OOM` status.
*   **T7.04 File Descriptor/Handle Exhaustion**: DAU Atom opens 5,000 files without closing them in a loop. Expect `OSError: [Errno 24] Too many open files`. Atom fails, Engine gracefully catches and surfaces error.
*   **T7.05 Read-Only Filesystem Trap**: Container loses write permissions to `.flow/artifacts/` mid-flight. Expect Atom generating output to fail on IO, Orchestrator cleanly logs failure to stderr and freezes workflow.
*   **T7.06 CPU Starvation / Infinite While Loop**: Atom executes `while True: pass` in Python. Since it never yields to async loop, expect External Watchdog thread to measure non-responsiveness and trigger `SIGKILL` after 60s hard timeout.
*   **T7.07 Fork Bomb Defense**: `ScriptAtom` attempts to recursively spawn subprocesses utilizing a well-known bash fork bomb. Expect OS `pids.max` or Job Object limits to contain blast radius. Parent Orchestrator logs PIDs exceeded and fails.
*   **T7.08 Inode Exhaustion**: Disk has space but no Inodes (zero-byte files). Atom tries to write small file. Expect `ENOSPC`, handled identically to Disk Full.
*   **T7.09 ScriptAtom stdout/stderr Firehose (Disk Flood)**: DAU bash script runs `cat /dev/urandom` inside `ScriptAtom`. Expect `ProcessSupervisor` to enforce a hard cap (e.g., 50MB) on stream capture out of the pipe before issuing an automatic `SIGKILL` to prevent host disk flooding.
*   **T7.10 Native Socket / Port Exhaustion (EADDRINUSE)**: A DAU Atom spins up a localhost background mock server on port 8080 and leaks it. The next time the Atom runs, it tries port 8080 again. Expect strict OS-level `OSError`, handled natively via Python try/except inside the Atom bounds, yielding `FAILED` and avoiding bringing down the entire Orchestrator routing thread.
*   **T7.11 Ghost Asyncio Task Leakage**: A custom Atom launches a background `asyncio.create_task()` fire-and-forget job but returns `SUCCESS` before it resolves. The step completes, but the task lives on. Expect the Orchestrator's internal thread tracking to detect the leaked coroutine upon Atom completion, forcefully cancelling it to prevent memory corruption or delayed side-effects.
*   **T7.12 Python Sub-interpreter Thread Starvation**: An Atom spawns 1,000 threads. Instead of cleanly hitting an OS maximum PID limit, it just starves the global Python GIL, bringing the Orchestrator to a crawl. Expect an external Watchdog (in a disjoint OS process) to detect the Heartbeat failure of the primary Orchestrator loop and issue a `SIGTERM` to self-heal the container.
*   **T7.13 C-Extension Memory Leaks (The Numpy Trap)**: A DAU Atom imports a C-extension library (like `numpy` or `lxml`) and intentionally allocates massive structs outside the Python garbage collector's visibility before throwing an error. Expect the Engine to natively isolate these high-risk mathematical/native Atoms via `ScriptAtom` subprocesses, as native memory leaks within the main Orchestrator loop cannot be reclaimed by the Python GC, eventually triggering a slow OOM death.

---

## 8. Fault Domains, Signals & Graceful Teardown
Validating signal reactions, partial cleanups, and teardown logic.

*   **T8.01 Synchronous Exception Trapping**: Atom throws `KeyError`. Expect wrapper to catch, log trace, and fail Atom cleanly.
*   **T8.02 Async / Coroutine Leakage Trap**: Naked async task throws unhandled exception outside main stack. Expect Event Loop supervisor to trap, log against correct `Run ID`.
*   **T8.03 Unhandled Exception in `cleanup()`**: `cleanup()` has a typo raising `AttributeError` on `SIGTERM`. Expect isolated `try/except` wrapper; teardown of other atoms continues gracefully.
*   **T8.04 Cascading Teardown Timeout Budgets**: Leaf Atom takes 4000ms to teardown against 3000ms Global Budget. Expect abandonment of leaf and forceful `SIGKILL` at exactly 3000ms.
*   **T8.05 Subprocess Fate Sharing (Zombie Prevention)**: `ScriptAtom` runs infinite bash. Engine gets `SIGTERM`. Expect OS Kernel Job Objects to instantaneously reap child.
*   **T8.06 Maximum Retry Circuit Breaker (Fatal Loop)**: Atom continuously yields `RETRY IMMEDIATE`. Expect `Max_Retries` trip, yielding `FATAL_LOOP` halt.
*   **T8.07 Out-Of-Order / High-Frequency Signals**: User spams `Ctrl+C` (SIGINT -> SIGTERM -> SIGINT). Expect Engine to lock-latch teardown once. Subsequent signals within 5000ms are mocked/ignored.
*   **T8.08 Uncatchable Panic / Segmentation Fault in Engine**: The core Python event loop itself segfaults. Expect container orchestrator (e.g., K8s) to restart Pod. State DB remains uncorrupted due to WAL/ACID guarantees, flows resume on spin-up.
*   **T8.09 SIGQUIT (Core Dump) Handling**: Engine receives `SIGQUIT`. Expect generation of core dump without firing normal `cleanup()` hooks, intentionally leaving exact state for forensic debugging.
*   **T8.10 Network Socket Hang in Cleanup**: `cleanup()` attempts HTTP DELETE to remote server which silently drops packets (no TCP RST). Expect internal `cleanup()` thread watchdog to truncate execution after 2000ms to allow parent `SIGTERM` completion.
*   **T8.11 Partial Teardown Success (The 50% Clean)**: Atom possesses 3 resources. `cleanup()` releases 1st, hangs on 2nd. Expect Supervisor to enforce timeout, killing process, but explicitly logging which resources leaked.
*   **T8.12 External Process Orphan Defense**: Tool launches detached background daemon (`nohup &`) and cleanly exits. Engine tears down Atom. Expect daemon to SURVIVE if explicitly detached, OR be killed if enforcing strict cgroups containment.
*   **T8.13 Atom `cleanup()` Hanging Isolation**: The Engine receives `SIGTERM` while an Atom is executing. The Atom's specific `cleanup()` logic hangs. Expect the Engine to enforce a strict sub-timeout on the Atom's cleanup, severing the thread/process before the Orchestrator's global container timeout is reached.
*   **T8.14 Atom Emitting Rogue Background Threads**: A DAU Python Atom creates several `threading.Thread(daemon=False)` instances and yields `SUCCESS`. Engine proceeds. Expect the Orchestrator event loop to continue, but upon `SIGTERM`, ensure these leaked non-daemon threads do not block the main Python interpreter from exiting.
*   **T8.15 System Shutdown During Synchronous Atom Execution**: The Orchestrator receives `SIGTERM` while a procedural Atom is heavily computing a matrix (holding the GIL). Expect the signal handler (running in the main thread) to still register the shutdown request and gracefully force the Engine router to skip the *next* execution step once the GIL is freed, transitioning the Flow to `PAUSED` rather than `FAILED`.
*   **T8.16 SIGTERM During SQLite Commit**: Engine receives `SIGTERM` exactly while performing a synchronous commit to `.flow_state/` database. Expect SQLite WAL mechanisms to ignore the interrupt or the Python wrapper to shield the `commit()` call, ensuring the write either completes fully or rolls back cleanly without leaving the database locked or corrupted.
*   **T8.17 Double Fault in Wrapper Crash Handling**: An Atom throws `IndexError`. The Engine's standard exception wrapper catches it and attempts to serialize the Error object to disk. However, the serialization itself throws `TypeError` (Double Fault). Expect a secondary fallback `try/except` around the state persister to catch the meta-failure, emitting a hardcoded safe `FAILED_CRITICAL` status without crashing the global Orchestrator thread.

---

## 9. DAU & Hostile Integration Defenses
Testing the Engine's resilience against internal developers actively (or accidentally) sabotaging the framework's runtime environment from within custom Atoms.

*   **T9.01 `sys.stdout` Hijacking**: Developer implements a custom Atom that overwrites `sys.stdout = open('my_log.txt', 'w')`. Expect the Engine's isolated classloader or execution context to prevent this from affecting the global Orchestrator logging stream, or forcefully fail the specific step with an `EnvironmentPollutionError`.
*   **T9.02 Dynamic `os.environ` Mutation**: A custom Atom executes `os.environ['AWS_KEY'] = 'hacked'`. Expect the Engine to execute Atoms within a context where `os.environ` is either a deep-copy or strictly immutable (`MappingProxyType` or eBPF jail), protecting the credential integrity of subsequent or parallel Atoms.
*   **T9.03 Monkey-Patching Core Classes**: An Atom uses `unittest.mock.patch` or direct assignment to dynamically replace the Engine's `AtomResult` or `DBConnector` class definition in memory. Expect strict module-level read-only protections or separate Sub-Interpreter execution to contain the patch exclusively to the offending Atom's lifespan.
*   **T9.04 The Infinite `__getattr__` Trap**: A DAU returns an object in `exports` where `__getattr__` recursively returns itself. When the Engine attempts to serialize or merge this object, expect the recursion depth parser to catch the trap cleanly instead of blowing the C stack.
*   **T9.05 OS Signal Handler Sabotage**: A custom Atom attempts to call `signal.signal(signal.SIGTERM, signal.SIG_IGN)` during its `run()`, effectively ignoring the Orchestrator's teardown mechanism. Expect the Engine to execute Atom logic on a secondary thread (where `signal()` throws a native `RuntimeError` due to main-thread restrictions) or rely on a container-level uncatchable `SIGKILL` watchdog.
*   **T9.06 Deep Module Monkeypatching (Global Side-Effects)**: A DAU attempts to patch the global `ssl._create_default_https_context` to bypass SSL verification for their Atom, forgetting to revert it. Expect the Engine to execute Atoms within strict Sub-Interpreters (`PEP 684`) or dedicated subprocesses so that global standard library mutations DO NOT infect parallel or subsequent Atoms.

---

## 10. Future Proposals (V-Next+1)
Features beyond current CI requirements.

*   **P10.01 Sub-Run/Tool Call Caching**: Feature to cache individual Tool Call outputs within an `AgentAtom` execution, so multi-tool arrays don't re-run successful tools simply because a sibling crashed.
*   **P10.02 Sub-workflow Independent Progress Syncing**: Push subworkflow context updates continuously to the parent rather than waiting for completion, enabling "Streamed Subflow Outputs".
*   **P10.03 Secrets Exfiltration Defense**: Validate `{secrets.API_KEY}` via Engine Vault is definitively excluded from state blobs and `audit.jsonl`.
*   **P10.04 D-State (Uninterruptible Sleep) Watchdog**: Move intensive disk IO to IPC worker processes to ensure Orchestrator event loop never hangs on infinite NFS/CIFS network block.
*   **P10.05 Unified Stale-State Sweeper**: Central Cron DB job automatically sweeps workflows locked in `WAITING_FOR_APPROVAL` for >30 days without single flow instantiation required.
*   **P10.06 Fuzz Testing Engine Bounds**: Utilize Python Hypothesis or similar fuzzing to blast Context inputs and YAML specs with completely randomized Unicode/Binary payloads to ensure bulletproof schema validation.
*   **P10.07 Chaos Mesh Integration**: Randomly terminate pods, drop DB packets, and inject artificial API latency to continuously prove State Reconciliation idempotency under actual load. 
*   **P10.08 DB-Backed Flow Versioning System**: Strict enforcement of DAG compilation matching the current Database Version mapping (e.g. `FlowHash_v3` -> `DB_Schema_v3`) to prevent drift execution failures entirely.
*   **P10.09 Dynamic Atom Type Killswitch**: Allow Admins to disable a specific Atom Type globally (e.g., if a crucial internal SaaS API goes down) without pausing all unrelated Flows. Flows attempting to step into that Atom would receive a global `AtomOfflineError` and gracefully transition to `WAITING`.
*   **P10.10 ScriptAtom Sandboxing (Wasm/V8)**: Migrate the execution of third-party or custom Python `ScriptAtoms` into hard WebAssembly (Wasm) or V8 isolates, providing literal memory and CPU instruction boundaries, eliminating the reliance on Linux-specific cgroups for OOM containment.
*   **P10.11 Strict `seccomp`/eBPF Profiles per Atom Type**: Applying strict Linux kernel capabilities at the individual Atom level (e.g., `WebhookAtom` can only open sockets to approved CIDRs, `TransformAtom` cannot open sockets at all) to contain Supply Chain attacks within specific dependencies.
*   **P10.12 In-Memory Context Encryption**: Enforcing that `context` payloads are encrypted with a rotating Flow-specific Envelope Key while traversing the Engine, ensuring memory dumps of the Orchestrator cannot trivially leak sensitive intermediate states.
