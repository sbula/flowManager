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
*   **State Persistence**:
    *   **Mechanism**: **Synchronous Atomic Write**.
    *   **Step**: Write `flow_state_{id}.tmp` -> `fsync` -> Atomic Rename.
    *   **No Debounce**: We prioritize Data Safety (ACID) over throughput.

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
*   **Graceful Teardown (SIGINT)**:
    *   **Signal**: Engine traps `SIGINT` (Ctrl+C) and `SIGTERM`.
    *   **Action**:
        1.  Mark current step `INTERRUPTED`.
        2.  Call `atom.cleanup()` (if implemented).
        3.  Flush State to disk.
        4.  Exit(0).

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
