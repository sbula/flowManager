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

## 3. Persistence (Writing)
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
