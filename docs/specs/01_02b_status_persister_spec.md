# Behavioral Specification: Status Persister (Write)

## 1. Goal
The Status Persister (**Task 1.2b**) provides the "Save" capability.
Its Primary Directive is **Content Fidelity**: What is in the Memory Model MUST be written to disk exactly as-is, with no "AI Interpretation" or "Drift".

## 2. Core Rules (The Strict Contract)

*   **Rule 1: Deterministic Rewriting**
    *   The file is regenerated from the `StatusTree` in memory.
    *   **Format**: Strict 4-space indentation.
    *   **Markers**: Normalized to `[ ]` (Pending), `[/]` (Active), `[x]` (Done), `[-]` (Skipped).
    *   **Line Endings**: Always `\n` (LF).

*   **Rule 2: Content Fidelity (The User's "Red Line")**
    *   The `Task.name` string is treated as **Immutable Binary Data** during the write process.
    *   The Persister performs:
        *   **NO** Summarization.
        *   **NO** Grammar Correction.
        *   **NO** Truncation.
        *   **NO** "Helpful" Edits.
    *   If `Task.name` is "Fix bug... maybe?", it is written exactly so.

*   **Rule 3: Safety / Atomic-ish**
    *   Encoding is strictly `utf-8`.
    *   Permission errors must bubble up.
    *   (Future V2: Atomic "Write-Move" for high concurrency).

*   **Rule 4: Lossy Comments (Accepted V1)**
    *   Since Parser 1.2a ignores `<!-- -->`, the Persister will NOT output them.
    *   User accepts this data loss for V1 logic simplicity.

## 3. Test Coverage (T3.xx)
The following tests (defined in `01_02_test_inventory.md`) verify this spec:
*   **T3.01**: Create New (File existence).
*   **T3.02**: Sanitize Formatting (Messy -> Clean).
*   **T3.03**: Unicode Fidelity (Emojis/Foreign content preserved).
*   **T3.04**: Permission Error (Bubbling).
*   **T3.05**: Comment Stripping (Explicit confirmation).
*   **T3.06**: Line Endings (CRLF -> LF).
*   **T3.07**: Keyword Preservation (Brackets/Parens in text).
*   **T3.08**: Stability (Load -> Save -> Diff is Zero).
*   **T3.09**: Content Fidelity (Long text/Special chars preserved 1:1).
