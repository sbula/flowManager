# Test Inventory: Engine Core (Task 1.3)

This file tracks **ALL** identified test cases for the V1.1 "Paranoid Hardened" Engine.

## 1. Hydration & Security (Startup)
*   **T1.01 Root Discovery (Standard)**:
    *   Input: CWD is strictly inside `.flow/`.
    *   Expect: `ctx.root` is correctly identified.
*   **T1.02 Root Missing (Strict)**:
    *   Input: CWD has no `.flow/`.
    *   Expect: Exit with `RootNotFoundError`.
*   **T1.03 Path Resolution (Safe)**:
    *   Input: `SafePath(root, "subdir/file.txt")`.
    *   Expect: Returns absolute path.
*   **T1.04 Jailbreak Attempt (Parent)**:
    *   Input: `SafePath(root, "../../etc/passwd")`.
    *   Expect: Raises `SecurityError` (Path Traversal).
*   **T1.05 Jailbreak Attempt (Symlink)**:
    *   Input: `SafePath` with symlink pointing to `/Windows/System32`.
    *   Expect: Raises `SecurityError` (Symlink Escape).
*   **T1.06 Explicit Registry Loading**:
    *   Input: `flow.registry.json` maps "git"->"GitAtom". "GitAtom" class exists.
    *   Expect: Atom loaded successfully.
*   **T1.07 Unregistered Atom (Security)**:
    *   Input: `malware.py` exists in `atoms/` but is NOT in `flow.registry.json`.
    *   Expect: Engine is completely unaware of its existence. Cannot be dispatched.
*   **T1.08 Root Symlink Loop**:
    *   Input: `child` links to `parent`. Run engine.
    *   Expect: `MaxRecursionDepth` or explicit loop detection. NO Hang.
*   **T1.09 Root Is File**:
    *   Input: `.flow` exists but is a FILE.
    *   Expect: `InvalidRootError` (must be directory).
*   **T1.12 Null Byte Path**:
    *   Input: `filename\u0000.ext`.
    *   Expect: `SecurityError` or `ValueError`.
*   **T1.13 CWD Deleted During Scan**:
    *   Input: Delete CWD while engine is initializing.
    *   Expect: `RootNotFoundError` (Graceful).
*   **T1.15 Windows Device Paths**:
    *   Input: `SafePath(root, "CON")` or `"PRN.txt"`.
    *   Expect: `SecurityError` or OS-level `ValueError`.
*   **T1.16 UNC Path Injection**:
    *   Input: `SafePath(root, "\\\\Server\\Share")`.
    *   Expect: `SecurityError` (Must be strictly within root).
*   **T1.17 Nested Roots (Ambiguity)**:
    *   Input: CWD is `repo/.flow/subrepo/.flow`.
    *   Expect: Engine resolves to NEAREST parent (`subrepo/.flow`) or strictly scans UP.
*   **T1.18 Atom Import Crash**:
    *   Input: Registry valid, but Atom module raises Schema/Import Error.
    *   Expect: Graceful error (Atom marked BROKEN), Engine startup continues if possible, or Fatal error.
*   **T1.19 Circular Atom Dependency**:
    *   Input: Atom A imports Atom B; Atom B imports Atom A.
    *   Expect: `ImportError` handling during hydration.
*   **T1.20 Permission Denied (Parent)**:
    *   Input: `CWD=/a/b/c`. `/a` has `chmod 000`. Scan up.
    *   Expect: `RootNotFoundError` (Stop scan), NO Crash (`PermissionError`).

## 2. Smart Dispatch
*   **T2.01 Explicit Metadata Match**:
    *   Input: Task `<!-- type: flow -->`. Registry has Atom match too.
    *   Expect: Dispatches to `FlowEngine` (Metadata Priority).
*   **T2.02 Registry Exact Match**:
    *   Input: Task "[Git] Commit". Registry maps "Git" -> `GitAtom`.
    *   Expect: Dispatches to `GitAtom`.
*   **T2.03 Dispatch Failure (Safe)**:
    *   Input: Task "Unknown Task". No Registry match.
    *   Expect: Dispatches to `ManualInterventionAtom`.
*   **T2.04 Atom Init SideEffect**:
    *   Input: Atom `__init__` raises Exception.
    *   Expect: Engine correctly catches error, marks atom `BROKEN`.
*   **T2.05 Non Atom Class**:
    *   Input: Registry maps to `subprocess.Popen`.
    *   Expect: Engine verifies `issubclass(Atom)` before instantiation.
*   **T2.07 Metadata In False Context**:
    *   Input: `<!-- type: flow -->` inside a Python string or Markdown code block.
    *   Expect: Dispatch IGNORING the false flag.
*   **T2.08 Registry Case Sensitivity**:
    *   Input: Registry has "Git", Task says "[git]".
    *   Expect: Strict match (Fail) or Normalization (Pass). Defined Policy: STRICT match usually.
*   **T2.09 Regex ReDoS Handling**:
    *   Input: Evil Regex Metadata pattern.
    *   Expect: Timeout or Safe Regex implementation.
*   **T2.10 Invisible Character Dispatch**:
    *   Input: Task `[Git\u200b]`. Registry `Git`.
    *   Expect: Normalization -> Match `GitAtom`.

## 3. Resilience & Execution
*   **T3.01 Smart Resume (Pending)**:
    *   Input: Tree [x], [ ], [ ].
    *   Expect: Selects 2nd task.
*   **T3.02 Circuit Breaker (Trigger)**:
    *   Input: Task `A` has `retry_count=4`.
    *   Expect: Task marked `FATAL`. Execution Halts.
*   **T3.03 Write-Ahead Log (Recovery)**:
    *   Input: `intent.lock` exists on boot.
    *   Expect: `retry_count` incremented for that task. Lock cleared.
*   **T3.04 Crash Handling**:
    *   Input: Atom raises `Exception`.
    *   Expect: Catch -> Log -> Mark `ERROR` -> Save State -> Exit(1).
*   **T3.05 Context Propagation (Merge)**:
    *   Input: Context `{"a": 1}`. Atom returns exports `{"a": 2, "b": 3}`.
    *   Expect: Context becomes `{"a": 2, "b": 3}` (Overwrite Policy).
*   **T3.06 Invalid Atom Return**:
    *   Input: Atom returns `None` (not `AtomResult`).
    *   Expect: Contract Violation Error.
*   **T3.07 Task ID Disappeared**:
    *   Input: Status file updated externally, active ID missing.
    *   Expect: Fallback to Smart Resume scan.
*   **T3.08 Check Completion Crash**:
    *   Input: `check_completion()` raises Exception during recovery.
    *   Expect: Treated as `Failure` (Safe).
*   **T3.09 Multiple Active Tasks**:
    *   Input: Status Tree has two `[x] ... [/] ... [/]` (Two In-Progress).
    *   Expect: Validator fails load OR Engine picks first.
*   **T3.10 Non-Serializable Export**:
    *   Input: Atom returns `{"file": <open file 'x'>}`.
    *   Expect: Serialization Error caught before State Corruption.
*   **T3.11 Lock Stale PID (Zombie)**:
    *   Input: `intent.lock` exists, PID inside is dead.
    *   Expect: Engine claims lock (Steal).
*   **T3.12 System Context Immutable**:
    *   Input: Atom exports `{"config": "hacked"}`.
    *   Expect: Engine ignores/logs warning. `ctx.config` unchanged.

## 4. Persistence & IO
*   **T4.01 Atomic Write (State)**:
    *   Input: Update state.
    *   Expect: `flow_state.tmp` created -> flushed -> renamed.
*   **T4.02 Windows Lock Avoidance**:
    *   Input: Target file is open by another reader.
    *   Expect: `MoveFileEx` (or retry logic) handles collision safely.
*   **T4.04 AV File Lock Simulation**:
    *   Input: `os.rename` raises `PermissionError` (locked).
    *   Expect: Retry loop succeeds after mock release.

## 5. Events & Observability
*   **T5.01 Payload Inline (< 8KB)**:
    *   Input: Emit Event with 2KB payload.
    *   Expect: Payload embedded in Event JSON.
*   **T5.02 Payload Reference (> 8KB)**:
    *   Input: Emit Event with 50KB text.
    *   Expect:
        1. file written to `.flow/artifacts/blob_xyz.json`.
        2. Event contains `{"ref": "blob_{uuid}.json"}`.
        3. No data size error.
*   **T5.03 JSONL Streaming**:
    *   Input: Emit Event.
    *   Expect: Line appended to `events.jsonl`.
*   **T5.04 Payload Boundary (8KB)**:
    *   Input: Emit Event with exactly 8192 bytes.
    *   Expect: Inline. (8193 bytes triggers Blob Reference).
*   **T5.05 Blob Write Failure**:
    *   Input: `.flow/artifacts` is Read-Only. Emit huge event.
    *   Expect: Warning logged, Event emitted with "Payload truncated" or Error. NO Crash.
*   **T5.06 Circular Payload**:
    *   Input: Event data `d={}; d['self']=d`.
    *   Expect: Safe serialization (Reference or Error).
*   **T5.07 Log Rotation**:
    *   Input: `events.jsonl` > 10MB.
    *   Expect: Rotation to `events.jsonl.1` or safe Truncation.

## 6. The Loom (Surgical Editing)
*   **T6.01 Surgical Insert**:
    *   Input: File has `def foo():\n  pass`. Loom `Insert(anchor="pass", content="  print('hi')")`.
    *   Expect: File updated correctly. Indentation preserved.
*   **T6.02 Ambiguous Anchor (Safety)**:
    *   Input: File has two instances of `def foo():`. Loom `Insert(anchor="def foo():")`.
    *   Expect: **FAIL SAFE**. Refuse to edit. Error: "Ambiguous Anchor".
*   **T6.03 Loom vs WriteFile**:
    *   Input: Agent attempts `Context.write_file("src/main.py")`.
    *   Expect: **DENIED**. Suggest `Loom.edit(...)`.
*   **T6.04 Loom Project Scope**:
    *   Input: Agent attempts `Loom.edit("src/main.py")`.
    *   Expect: **ALLOWED** (if path in Whitelist).
*   **T6.05 Anchor Not Found**:
    *   Input: File does not contain anchor text.
    *   Expect: **FAIL SAFE**. Refuse to edit. Error: "Anchor Not Found".
*   **T6.06 Whitespace Mismatch**:
    *   Input: Anchor has Spaces, File has Tabs.
    *   Expect: Loom normalizes whitespace and matches correctly.
*   **T6.07 Loom Encoding (Latin1)**:
    *   Input: File is ISO-8859-1. Loom attempts edit.
    *   Expect: Graceful failure or detection. NO Garbage injection.
*   **T6.09 Loom Large File Limit**:
    *   Input: Edit 2GB log file.
    *   Expect: `FileTooLargeError` or Memory limit check.
*   **T6.10 Optimistic Locking (Race)**:
    *   Input: User modifies file between Loom Read and Loom Write.
    *   Expect: `ContentChangedError`. Abort.
*   **T6.11 EOL Preservation**:
    *   Input: File uses CRLF. Loom inserts text.
    *   Expect: Result uses CRLF. No mixed endings.
*   **T6.12 Encoding Mismatch (BOM)**:
    *   Input: File is UTF-8-SIG (BOM).
    *   Expect: Loom preserves BOM.
*   **T6.08 Regex Literal Safety**:
    *   Input: Anchor text "func(a, *args)".
    *   Expect: Literal match (not Regex `*`).
*   **T6.13 Loom Whitespace Normalization**:
    *   Input: Anchor has extra trailing space.
    *   Expect: Match found (Lenient whitespace).
*   **T6.14 Case Insensitive Path Scope**:
    *   Input: Whitelist `src/secret`. Write `src/Secret`.
    *   Expect: **DENIED** (on Windows/Mac) or STRICT match.

## 7. Edge Cases & QA Torture Tests
*   **T7.01 Stale Intent Lock**:
    *   Input: `intent.lock` timestamp is 24h old (Previous crash).
    *   Expect: Treated as valid crash. Retry Count incremented.
*   **T7.02 Corrupt State File**:
    *   Input: `flow_state_{id}.json` is garbage/truncated.
    *   Expect: Engine detects corruption. Discards state (starts fresh) or Errors.
*   **T7.03 Empty Registry File**:
    *   Input: `flow.registry.json` exists but is empty `{}`.
    *   Expect: Engine defaults to empty config (No Atoms). Dispatch fails for everything (Manual).
*   **T7.04 Maximum Path Length**:
    *   Input: Nested path > 260 chars (Windows limit).
    *   Expect: `SafePath` or OS raises Error. Engine catches and reports "Path too long".
*   **T7.05 High Concurrency Events**:
    *   Input: 5 Threads emitting events simultaneously.
    *   Expect: Event Bus is Thread-Safe (Locked). No data loss in Buffer.
*   **T7.06 SIGINT Handling (Graceful)**:
    *   **Input**: Long running step. Send `SIGINT` (Ctrl+C).
    *   **Expect**:
        1. Process catches signal.
        2. State saved as `INTERRUPTED`.
        3. Process exits cleanly (0).
*   **T7.07 Nested Resume (Russian Doll)**:
    *   **Input**: `Parent -> Child -> Grandchild`. Crash in `Grandchild`.
    *   **Action**: `flow resume Parent`.
    *   **Expect**: Engine detects nested state, drills down, and resumes `Grandchild` at exact failure step.
*   **T7.08 Disk Full (Panic Save)**:
    *   **Input**: `save_state` mock raises `OSError(ENOSPC)`.
    *   **Expect**:
        1. Emergency dump to `stderr`.
        2. Previous `state.json` is **NOT** corrupted (rename guarantees).
        3. Exit(1).
*   **T7.09 Circular Dependency**:
    *   **Input**: Workflow A includes B; B includes A.
    *   **Expect**: Parser detects cycle or Runtime hits `MAX_RECURSION_DEPTH` (e.g. 10) and fails safe.
*   **T7.11 Registry Schema Invalid**:
    *   Input: `flow.registry.json` is a List, not Dict.
    *   Expect: `ConfigError` on startup.
*   **T7.14 Save State Double Fault**:
    *   Input: Engine Crash -> Save State Crash.
    *   Expect: Exit(1). Log to Stderr. No loop.
*   **T7.15 Recursion Bomb**:
    *   Input: Workflow calls itself.
    *   Expect: `MaxRecursionDepth` Error.
*   **T7.16 Dual Engine Contention**:
    *   Input: Two Engines start on same `.flow`.
    *   Expect: First locks `intent.lock`. Second waits/fails.


