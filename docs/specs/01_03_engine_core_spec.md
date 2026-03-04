## 1. Goal
The **Engine Core** is the runtime orchestrator. It is responsible for "Hydrating" the environment, "Dispatching" tasks via a Smart Router, and "Persisting" state using ACID principles. It strictly adheres to the **"Single Folder" Policy** (`.flow/`) and facilitates an **Event-Driven Architecture**.

## 2. The Hydration Phase (Startup)
Before execution, the Engine sanitizes the environment and loads its configuration.

*   **H1. Root Discovery**:
    *   **Logic**: Scan `CWD` and parents for `.flow/` marker.
    *   **Failure**: Exit with explicit error if not found.
*   **H2. Single Folder Policy (.flow/)**:
    *   **Engine Scope**: The Engine restricts its own *internal* state writes strictly to `.flow/`.
    *   **Project Scope**: Agents may write to the Project Root (`src/`, `tests/`), but ONLY via the **Loom** (See Section 4.3). Direct `write_file` access to the project root is **RESTRICTED**.
    *   **Constraint**: All path resolution MUST use a `SafePath(root, input)` helper.
*   **H3. Explicit Registry (The Whitelist)**:
    *   **Logic**:
        *   **Source**: `.flow/flow.registry.json` is the **Sole Source of Truth**.
        *   **Schema**: Maps `AtomName` -> `PythonClassPath` (e.g., `"git": "atoms.git.GitAtom"`).
        *   **Loading**: The Engine imports *only* the classes explicitly defined in this file.
    *   **Security**: Anything NOT in the registry **does not exist**. This eliminates the need for risky AST scanning or `importlib` wildcards.
    *   **Deprecation Notice**: The `workflow_core` directory is **DEPRECATED**. All new logic MUST reside in `src/flow`.

## 3. The Execution Loop (Event-Driven)
The Engine operates as an **Event Loop**, not a linear script.

### 3.1. Fetch (The Cursor)
*   **Source**: `StatusTree.get_active_task()`.
*   **Smart Resume**: If no active task, auto-select the first `pending` task (Ordered Depth-First).
*   **Circuit Breaker (Write-Ahead Log)**:
    *   **Intent**: Write `intent.lock` with `{task_id, attempt_n}` *BEFORE* Dispatch.
    *   **Limit**: If `retry_count > 3` for the same Task, Mark Task as `FATAL` and Halt.

### 3.2. Smart Dispatch (The Router)
*   **Philosophy**: **Explicit Intent** > **Convention**.
*   **Logic**:
    1.  **Check Metadata**: Does the task have `<!-- type: flow -->`? -> Dispatch to Flow Engine.
    2.  **Check Registry**: Is `Task.name` mapped in `flow.registry.json`?
    *   **Error**: If no match, dispatch to `ManualInterventionAtom`.

### 3.3. Atom Execution (The Worker)
An **Atom** is a Unit of Work.
*   **Contract**:
    *   **Pre-Condition Check**: Verify inputs/state BEFORE acting.
    *   **Execution**: Perform the work.
    *   **Atomic Result**: Return `Success`, `Failure`, or `Error`.
*   **No Implicit Side-Channels**: Atoms communicate ONLY via the `AtomResult` return object.
*   **Idempotency Contract**:
    *   **Requirement**: All Atoms MUST be idempotent OR implementing `check_completion()`.
    *   **Crash Recovery**: If the Engine resumes a step marked "IN_PROGRESS" (Zombie State), it MUST first call `atom.check_completion()`.
        *   If `True`: Mark Success and skip execution.
        *   If `False`: Re-execute safest path.

### 3.4. Flow Execution (The Orchestrator)
A **Flow** describes a Control Structure (Sequence, Branch, Loop).

> **Roadmap Note**: State persistence is currently file-based. The embedded ACID database (SQLite WAL) is a **prerequisite for Flows (01_08)** — sub-flow reconciliation, parallel branch isolation, and lock coordination require ACID transactions. See `roadmap_2026.md` (Phase 1.5). The DB can be introduced for flow state first, without migrating the status domain (01_02).

*   **State Persistence**:
    *   **Mechanism**: **Synchronous Atomic Write**.
    *   **Step**: Write `flow_state_{id}.tmp` -> `fsync` -> Atomic Rename.
    *   **No Debounce**: We prioritize Data Safety (ACID) over throughput.

### 3.4.0 Sub-Flow Delegation (Escaping the Flat Execution Model) [FUTURE V2]
*   **Mechanism**: An Atom or Skill may realize the current task is too complex for a single step and requires a full workflow.
*   **Action**: It can return an intent (e.g., `status=DELEGATE`, `flow_ref="SecurityAudit"`).
*   **Engine Handling**: The Orchestrator safely parks the current step, spawns the requested sub-flow natively, waits for it to complete via the event loop, and then resumes the parent step.

### 3.4.1 Context Propagation
*   **Mechanism**: **Explicit Overlay**.
*   **Logic**:
    *   `AtomResult.exports` (Dict) is merged into `WorkflowState.context_cache`.
    *   **Collision Policy**: **Overwrite**. The latest step takes precedence.
    *   **Namespacing**: Atoms SHOULD return namespaced keys (e.g., `git.status` instead of `status`) to avoid accidental collisions.

### 3.4.2 Nested State (Run-in-Place)
*   **Problem**: Sub-workflows (Fractal Zoom) need independent but linked state.
*   **Schema**:
    *   **Parent State**: `flow_state_{id}.json` tracks `current_step = {type: "workflow", ref: "sub_id"}`.
    *   **Child State**: `flow_state_{id}#{sub_id}.json`.
*   **Resume Logic**:
    *   On `flow resume {id}`:
    *   Check `current_step`. If it is a Sub-Workflow and status is `IN_PROGRESS`:
    *   **Recursively Load** child state and resume execution *inside* the child at its specific step.

### 3.4.3 Parallel Execution (Map / Fan-Out & Fan-In)
*   **Problem**: Sibling steps running concurrently will cause race conditions if they blind-write to the exact same `context_cache`.
*   **Mechanism**:
    *   **Fan-Out (Map)**: The Engine spins up isolated parallel scopes for each branch, feeding them a read-only view of the parent context.
    *   **Isolation**: Each parallel step writes its `AtomResult.exports` to its own temporary namespace (e.g., `context.outputs.[branch_id]`).
    *   **Fan-In (Reducer)**: Once all branches complete, the Engine applies a **Reducer Configuration** (e.g., concatenate arrays, merge dictionaries, or map results to specific keys) to safely merge the isolated namespaces back into the dominant `WorkflowState.context_cache` sequentially. It is strictly an Engine-level concern, not an Atom-level concern.

### 3.4.4 Resource Locking (Mutexes)
*   **Problem**: Certain Atoms (or Sub-Flows) manipulate shared external state (e.g., external databases, git repositories) and cannot safely run concurrently, even if the DAG allows it. Putting Mutex logic inside an `Atom` breaks the stateless principle.
*   **Mechanism**: **Engine-Level Routing Coordination**.
    *   **Declaration**: Flows/Steps declare their locking needs in `config` (e.g., `requires_lock: ["git_repo", "prod_db"]`).
    *   **Acquisition**: The Engine Router intercepts the step. Before dispatching the Atom, the Engine attempts to acquire the required global locks. If unavailable, the Engine places the step in a `WAITING_FOR_LOCK` queue.
    *   **Release**: The Engine strictly guarantees lock release *after* the Atom yields its `AtomResult` or if the Engine crashes/traps `SIGTERM`.
    *   **Deadlock Prevention**: Locks must have a defined TTL (Time-To-Live). The engine implements a lock-stealing heartbeat mechanism upon startup to clear zombie locks left by hard OOM/SIGKILL crashes.

### 3.5. Update & Events (The Bus)
*   **Mechanism**: The Engine emits **Structured Events**.
*   **Payload Reference Pattern**:
    *   **Threshold**: `MAX_INLINE_SIZE = 8KB`.
    *   **Logic**:
        *   If `sizeof(payload) <= 8KB`: Embed directly in Event.
        *   If `sizeof(payload) > 8KB`:
            1.  Write payload to `.flow/artifacts/blob_{uuid}.json`.
            2.  Emit Event with `{"ref": "blob_{uuid}.json", "type": "blob_ref"}`.
    *   **Benefit**: Keeps the Event Bus lightweight while supporting massive generative outputs.
*   **Persistence**: Stream events to `.flow/logs/events.jsonl` (Append-Only).
*   **Garbage Collection (Blob GC)**:
    *   **Policy**: Blobs are ephemeral run artifacts.
    *   **Trigger**: On Workflow `COMPLETED` or `CANCELLED`.
    *   **Action**: Delete all `blob_*.json` files referenced in the run, UNLESS `preserve=True` was set in the Event.

### 3.6. Fractal Zoom (The Scope Shifter)
*   **Logic**: `flow zoom in <id>` creates explicitly linked sub-file (`sub_flows/task_{id}.md`).

### 3.7. Composition
*   **Logic**: Inherit -> Merge -> Mixin.

## 4. Safety & Resilience

### 4.1. The Crash Barrier (Error Boundaries)
*   **Behavior**: Catch Exception -> Mark `ERROR` -> Save State -> Exit(1).
*   **Recovery**: User can fix the issue and run `flow resume --retry <id>`.
*   **Graceful Teardown (SIGINT / SIGTERM)**:
    *   **Signal**: Engine traps `SIGINT` (Ctrl+C) and `SIGTERM`.
    *   **Action**:
        1.  Mark current step `INTERRUPTED`.
        2.  Call `atom.cleanup()` (or `skill.cleanup()`). **[FUTURE V2] Time-boxed execution**: The Engine MUST wrap this in a strict 5-second timeout. If it hangs (e.g., deadlocked thread or long network IO), the Engine MUST force-kill the thread/process.
        3.  Flush State to disk.
        4.  Exit(0).

### 4.4. Infinite Retry Prevention & Schema Poisoning [FUTURE V2]
*   **Problem**: If an LLM-driven Skill returns `RETRY` due to bad parameters, it might guess wrong forever.
*   **Mechanism**:
    *   **Feedback Loop**: When an execution yields `RETRY` (or fails Schema Validation), the Engine MUST append the exact validation error or failure reason to the active `WorkflowState.context_cache` so the LLM Agent can read *why* it failed before trying again.
    *   **Circuit Breaker**: Follows the global retry limit (Section 3.1). Max 3 retries before escalating to `FATAL`.

### 4.2. Immutable Context
*   **Constraint**: Atoms receive a **Read-Only** view of the Context (`types.MappingProxyType`).

### 4.3. The Loom (Surgical File Editing)
*   **Problem**: LLMs often accidentally truncate files when trying to edit them ("Lazy Rewrite").
*   **Solution**: Direct `write_file` is **RESTRICTED** for Agents. Instead, they MUST use the **Loom Atom**.
*   **Operations**:
    *   `Insert(path, anchor_text, new_content, position="after")`: Safe injection.
    *   `ReplaceBlock(path, start_marker, end_marker, new_content)`: Targeted update.
    *   `Append(path, content)`: Safe add.
*   **Safety Check**: The Loom verifies that the `anchor_text` exists and is unique before applying changes. If ambiguous, it Fails Safe.
*   **Agent Isolation**:
    *   **STRICT**: Loom Access Denied.
    *   **PARTIAL/SHARED**: Loom Access Granted to Whitelisted Paths.
*   **Resilience (Fuzzy Fallback)**:
    *   If `Insert` fails due to "Ambiguous Anchor", Loom returns a **Structured Error** containing line numbers of all matches.
    *   **Agent Retry strategy**: Agent can then call `ReplaceLine(path, line_number, content)` using the hint.

## 5. Test Plan (Engine Core)
*   **T1.xx Hydration**: Verify Auto-Discovery and Path Security.
*   **T2.xx Smart Dispatch**: Test Metadata/Registry/Regex priority.
*   **T3.xx Resilience**: Simulate crashes and verify `ERROR` state + persistence.
*   **T4.xx Concurrency**: (Bonus) Verify file integrity under parallel scheduling.
