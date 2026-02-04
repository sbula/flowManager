# Test Inventory: Task 1.2 (Status Parser)

This file tracks **ALL** identified test cases (28 Total).
Each case uses the format: **Input** -> **Expected Output**.

## 1. Happy Paths (Loading & Parsing)
*   **T1.01 Standard Load**:
    *   Input: File with `Key: Value` headers and 3-level nested tasks.
    *   Expectation: `load()` returns `StatusTree` with matching headers dict and task hierarchy.
*   **T1.02 Fractal Link Parsed**:
    *   Input: Task line `- [ ] Task @ sub.md`.
    *   Expectation: `Task.ref` == `sub.md`. (Path is relative to `.flow/`).
*   **T1.03 Missing Parent File**:
    *   Input: `load("non_existent.md")`.
    *   Expectation: Returns valid empty `StatusTree` (not None, no crash).
*   **T1.04 Deep Nesting**:
    *   Input: Task list with 10+ indentation levels.
    *   Expectation: Parsed correctly into nested objects without RecursionError.
*   **T1.05 Mixed Markers**:
    *   Input: Tasks with `[x]`, `[X]`, `[v]`.
    *   Expectation: All normalized to `status="done"`.
*   **T1.06 Find Cursor (Active)**:
    *   Input: Tree where `Root > Phase2 > TaskA` is `[/]` (Active).
    *   Expectation: `get_active_task()` returns `TaskA`.
*   **T1.07 Quoted Path (Spaces)**:
    *   Input: `- [ ] A @ "my file.md"`.
    *   Expectation: `Task.ref` == `my file.md`.
*   **T1.08 Anchor Assumption**:
    *   Input: Task with ref `sub/file.md`.
    *   Expectation: Validation passes if `.flow/sub/file.md` exists. Validation fails if only `./sub/file.md` exists.
*   **T1.09 Duplicate Header**:
    *   Input: `Proj: A` followed by `Proj: B`.
    *   Expectation: `tree.headers["Proj"]` == "B".
*   **T1.10 Empty File**:
    *   Input: A 0-byte file.
    *   Expectation: Returns `StatusTree` with empty headers and empty tasks list.
*   **T1.11 Smart Resume (No Active)**:
    *   Input: List `[x] A`, `[ ] B`, `[ ] C`. No `[/]` tags.
    *   Expectation: `get_active_task()` returns `B` (First Pending).
*   **T1.12 Virtual Numbering**:
    *   Input: Nested tree:
        ```
        - [ ] Root 1
            - [ ] Child A
        - [ ] Root 2
        ```
    *   Expectation:
        *   Root 1 ID == "1"
        *   Child A ID == "1.1"
        *   Root 2 ID == "2"
*   **T1.13 Tamper Detection**:
    *   Input: `status.md` modified manually (Hash mismatch with `.meta`).
    *   Expectation: Raises `IntegrityError`.
*   **T1.14 Integrity Accept**:
    *   Input: Tampered file. Call `parser.accept_changes()`.
    *   Expectation: `.meta` updated. Subsequent `load()` succeeds.
*   **T1.15 Integrity Decline**:
    *   Input: Tampered file + Valid Backup. Call `parser.decline_changes()`.
    *   Expectation: `status.md` restored from backup. `.meta` matches restored file.

## 2. Validation (The Strict Guardrails)
*   **T2.01 Indent Error (1-Space)**:
    *   Input: Line starts with 1 space.
    *   Expectation: Raises `ValidationError("Invalid indentation")`.
*   **T2.02 Indent Error (3-Space)**:
    *   Input: Line starts with 3 spaces.
    *   Expectation: Raises `ValidationError`.
*   **T2.03 Indent Error (Tab)**:
    *   Input: Line containing `\t`.
    *   Expectation: Raises `ValidationError` (Strict spaces only).
*   **T2.04 Syntax Error**:
    *   Input: `- Task Name` (Missing `[ ]`).
    *   Expectation: Raises `ValidationError`.
*   **T2.05 Unknown/Bad Marker**:
    *   Input: `- [?]`, `- [xx]`, `- [/x]`, `- [X/]`.
    *   Expectation: Raises `ValidationError`.
*   **T2.06 Logic Conflict (Shallow)**:
    *   Input: Parent `[x]`, Child `[ ]` (Same File).
    *   Expectation: Raises `ValidationError`.
    *   *Note*: Does NOT check sub-files (Fractal Consistency is phase 2).
*   **T2.07 Referential Integrity (Active Only)**:
    *   Input: Task `[/]` with ref `sub.md`. File `.flow/sub.md` does NOT exist.
    *   Expectation: Raises `ValidationError("Missing sub-status")`.
*   **T2.08 Sibling Activity Conflict**:
    *   Input: Two sibling tasks both marked `[/]`.
    *   Expectation: Raises `ValidationError("Ambiguous Focus")`.
*   **T2.09 Duplicate Sibling Name**:
    *   Input: Two sibling tasks both named "Task A".
    *   Expectation: Raises `ValidationError("Duplicate Task Name")`.
*   **T2.10 Path Traversal (Security)**:
    *   Input: `- [ ] Hack @ ../system32/cmd.exe`.
    *   Expectation: Raises `ValidationError("Jailbreak attempt")`.
*   **T2.11 Keyword Ambiguity**:
    *   Input: `- [ ] Task with [x] inside name`.
    *   Expectation: Status="pending", Name="Task with [x] inside name". (Marker parsing is strict).
*   **T2.12 Path Protocol Safety**:
    *   Input: `- [ ] Malicious @ javascript:alert(1)`.
    *   Expectation: Raises `ValidationError("Invalid Protocol")`.

## 3. Persistence (Writing - Task 1.2b)
*   **T3.01 Create New**:
    *   Input: `save(tree, "new_file.md")`.
    *   Expectation: File is created on disk.
*   **T3.02 Sanitize Formatting**:
    *   Input: Load messy valid file (mixed markers). Call `save()`.
    *   Expectation: Output file has strict 4-space indent and normalized `[x]`.
*   **T3.03 Unicode/Special Safety**:
    *   Input: Task name "Hello 🐍".
    *   Expectation: `save()` writes bytes correctly (UTF-8). `load()` reads back "Hello 🐍".
*   **T3.04 Permission Denied**:
    *   Input: `save()` to read-only file.
    *   Expectation: Bubbles `PermissionError`.
*   **T3.05 Comment Stripping**:
    *   Input: File with `<!-- comment -->`.
    *   Expectation: `save()` writes file WITHOUT the comment line.
*   **T3.06 Line Endings**:
    *   Input: File with `\r\n`.
    *   Expectation: `save()` writes file with `\n` (LF) only.
*   **T3.07 Keyword Preservation**:
    *   Input: `- [ ] Task with (Hint) and [Keyword]`.
    *   Expectation: `save()` preserves specific chars properly, ensuring they aren't confused for status markers.
*   **T3.08 Stability (Idempotency)**:
    *   Input: Load a valid file. Immediately `save()` it.
    *   Expectation: The output file content is **Identical** to the input file (assuming input was already normalized). Diff == 0.
*   **T3.09 Content Fidelity**:
    *   Input: Task with long description: `Fix the "Critical" bug in module/path.py where (x > 5) & [y < 10].`
    *   Expectation: Written exactly as-is. No character changes.
*   **T3.10 Invalid Status (Strict)**:
    *   Input: `task.status = "foo"`. Call `save()`.
    *   Expectation: Raises `ValueError` (or similar). No silence.
*   **T3.11 Logic Conflict (Strict)**:
    *   Input: Tree with Done Parent / Pending Child. Call `save()`.
    *   Expectation: Raises `ValueError`.
*   **T3.12 Backup Generation**:
    *   Input: Existing `status.md`. Call `save()`.
    *   Expectation: Copy exists in `.flow/backups/`.
*   **T3.13 Hash Update**:
    *   Input: `save()`.
    *   Expectation: `.flow/status.meta` updated with correct SHA256 of new file.

## 4. Domain Operations (CRUD - Task 1.2b)
*   **T4.01 Find Task**:
    *   Input: `tree.find("1.2")`.
    *   Expectation: Returns correct Task object.
*   **T4.02 Add Task**:
    *   Input: `tree.add_task(parent_id="1", name="New Child")`.
    *   Expectation: Task added to children. `save()` output shows correct indentation.
*   **T4.03 Update Task**:
    *   Input: `tree.update_task("1.1", status="done")`.
    *   Expectation: Task status updated.
*   **T4.04 Update Guard (Context)**:
    *   Input: `tree.update_task("1.1", anchor="Wrong Name")`.
    *   Expectation: Raises `AnchorError`.
*   **T4.05 Remove Task**:
    *   Expectation: Task is gone from `root_tasks` or parent children.
*   **T4.06 Add Sibling (End)**:
    *   Input: `tree.add_task(parent_id="root", name="Z", index=None)`.
    *   Expectation: Task Z appears at end of root list.
*   **T4.07 Add Sibling (Middle/Start)**:
    *   Input: `tree.add_task(parent_id="root", name="A", index=0)`.
    *   Expectation: Task A appears at *start* of root list. Previous Item 1 is now Item 2.
*   **T4.08 Add Subtask (Middle)**:
    *   Input: `tree.add_task(parent_id="1", name="MidChild", index=1)`. (Assume ID 1 has 3 children).
    *   Expectation: New task inserted between Child 1 and Child 2.
*   **T4.09 Find Active Task (Op)**:
    *   Input: `tree.get_active_task()`.
    *   Expectation: Returns specific `[/]` node. (Regression/Interface check).
*   **T4.10 Insert Between (Specific)**:
    *   Input:
        *   Initial: Task A, Task B, Task C, Task D.
        *   Action: `tree.add_task(name="New", index=2)`.
    *   Expectation:
    *   Input: `tree.get_active_task()`.
    *   Expectation: Returns specific `[/]` node. (Regression/Interface check).
*   **T4.10 Insert Between (Specific)**:
    *   Input:
        *   Initial: Task A, Task B, Task C, Task D.
        *   Action: `tree.add_task(name="New", index=2)`.
    *   Expectation:
        *   Order becomes: A, B, New, C, D.
        *   Structure/Indent preserved.
*   **T4.11 Sibling Conflict (Strict)**:
    *   Input: Task A is `[/]`. Call `tree.update_task("Task B", status="active")`.
    *   Expectation: Raises `StateError`. (Must pause A first).
*   **T4.12 Parent Conflict (Strict)**:
    *   Input: Parent is `[ ]`. Call `tree.update_task("Child", status="active")`.
    *   Expectation: Raises `StateError`. (Must activate Parent first).
*   **T4.13 Active Injection Check**:
    *   Input: `tree.add_task(name="New Active", status="active")`.
    *   Expectation: Runs same validation as `update_task` (checks siblings/parent).
*   **T4.14 Re-Open Parent Flow**:
    *   Input: Parent `[x]`, Child `[ ]`.
    *   Action 1: `update(child, active)` -> Raises `StateError` (Parent Done).
    *   Action 2: `update(parent, active)` -> Success (Parent `[/]`).
    *   Action 2: `update(parent, active)` -> Success (Parent `[/]`).
    *   Action 3: `update(child, active)` -> Success (Child `[/]`).
*   **T4.15 ID Invalidation (Safety)**:
    *   Input: Tree with A(1.1), B(1.2). Insert New at 1.1.
    *   Action: access `tree.find("1.2")` immediately?
    *   Expectation: Raises `StaleIDError` or `StateError` because IDs are now dirty.
*   **T4.16 Duplicate Name (Write)**:
    *   Input: Siblings "A", "B".
    *   Action: `add_task("A")`.
    *   Expectation: Raises `ValueError`.
*   **T4.17 (Skipped - Context Anchor covers this)**.
*   **T4.18 Cycle Detection**:
    *   Input: `task_a.add(task_a)`.
    *   Expectation: Raises `ValueError` (Recursion/Cycle).
*   **T4.19 Deep State Validation**:
    *   Action: `tree.add_task(parent)`.
    *   Expectation: Raises `StateError` (Logic Conflict in subtree).

## 5. Domain Policy (Auto-Propagation / Protocol V2)
Goal: Verify **Auto-Activation** and **Auto-Completion**.

*   **T5.01 Activation Bubble**:
    *   Input: Parent `[ ]`. Child `[ ]`.
    *   Action: Update Child -> `[x]`.
    *   Expectation: Parent becomes `[/]` (Active). (Because work happened).
    *   *Correction*: If Child becomes `[x]` and it was the *only* child, Parent becomes `[x]`.
    *   *Scenario B*: Parent `[ ]`, Child 1 `[ ]`, Child 2 `[ ]`. Update Child 1 -> `[x]`.
    *   Expectation: Child 1 `[x]`. Parent `[/]` (Active). Child 2 `[ ]`.
*   **T5.02 Completion Bubble**:
    *   Input: Parent `[/]`. Child 1 `[x]`, Child 2 `[/]`.
    *   Action: Update Child 2 -> `[x]`.
    *   Expectation: Parent automatically becomes `[x]`.
*   **T5.03 Deep Completion Bubble**:
    *   Input: 1.1.1 `[ ]`. (All ancestors `[ ]`).
    *   Action: Update 1.1.1 -> `[x]`.
    *   Expectation:
        *   1.1.1 -> `[x]`
        *   1.1 -> `[x]` (All children done)
        *   1 -> `[x]` (All children done)
*   **T5.04 Deep Activation Bubble**:
    *   Input: 1.1.1 `[ ]`. Ancestors `[ ]`. 1.1.2 `[ ]`.
    *   Action: Update 1.1.1 -> `[x]`.
    *   Expectation: 
        *   1.1.1 -> `[x]`
        *   1.1 -> `[/]` (Since 1.1.2 is mostly pending).
        *   1 -> `[/]` (Since 1.1 is active).
