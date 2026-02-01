# Behavioral Specification: Status Parser (Domain Model)

## 1. Goal
The Status Parser is the **User Interface**. It reads `status.md` (typically located in `.flow/status.md`) into a Domain Tree and writes changes back to disk. It acts as the "Database Driver" for the Markdown format. All project-specific files must reside in the `.flow/` folder.

## 2. Core Grammar (The Rules)
*   **Header**: Key-Value lines. Last write wins. Use `\n`.
*   **Tasks**: 4-space indented list. Markers: `[ ]`, `[/]`, `[x]`, `[-]`, `[v]`.
*   **References**:
    *   Syntax: `- [ ] Name @ path`.
    *   **Anchor Rule**: All paths relative to `.flow/`.
    *   **Security**: No `..` allowed.

## 3. Virtual Addressing (Runtime IDs)
While the file on disk relies solely on **Indentation** for structure, the Parser generates **Virtual IDs** in memory to facilitate precise targeting by the Flow Manager.

*   **Schema**: Hierarchical Dot Notation.
    *   `1` = First Root Task.
    *   `1.1` = First Child of Task `1`.
    *   `1.2` = Second Child of Task `1`.
    *   `2` = Second Root Task.
*   **Coordinate System**:
    *   IDs are **Calculated** strictly by position during the `load()` phase.
    *   IDs are **Ephemeral**: They are not written to the file.
    *   **Usage**: Used for targeting commands (`update(id="1.2")`).
*   **Stability Warning**: Since IDs depend on line order, any insertion/deletion shifts the IDs of subsequent tasks.
    *   **Mitigation**: Operations MUST verify the Target Name (Contextual Anchoring) before executing to prevent "drift".

## 4. Atomic Operations
*   `load(path)`: Returns Tree. Validates syntax/logic. Calculate Virtual IDs.
*   `save(path, tree)`: Overwrites file. Normalizes format. Strips comments.

## 5. Test Plan (Single Player / Strict)

### 5.1 Loading (Read) (T1.xx)
*   **(T1.01) Standard Load**: Input: Valid hierarchy. Expect: Correct Tree object.
*   **(T1.02) Fractal Link**: Input: `@ sub.md`. Expect: `ref="sub.md"`.
*   **(T1.03) Missing Parent**: Input: Missing file. Expect: Empty Tree.
*   **(T1.04) Deep Nesting**: Input: 10 levels. Expect: No Regex Recursion Error.
*   **(T1.05) Mixed Markers**: Input: `[v]`. Expect: `status=DONE`.
*   **(T1.06) Find Cursor (Active)**: Input: Nested `[/]`. Expect: Return deepest active node.
*   **(T1.07) Quoted Path**: Input: `@ "a b.md"`. Expect: `ref="a b.md"`.
*   **(T1.08) Anchor Assumption**: Input: ref `sub.md`. Expect: Validation checks `.flow/sub.md`.
*   **(T1.09) Duplicate Header**: Input: `A:1`, `A:2`. Expect: `A=2`.
*   **(T1.10) Empty File**: Input: 0-byte file. Expect: Valid Empty `StatusTree`.
*   **(T1.11) Smart Resume**: Input: No `[/]`. Expect: Return first `[ ]`.
*   **(T1.12) Virtual Numbering**: Input: Nested Tree. Expect: `1.2.1` IDs generated.

### 5.2 Validation Rules (T2.xx)
*   **(T2.01-03) Indent Errors**: Input: 1sp, 3sp, Tab. Expect: `ValidationError`.
*   **(T2.04) Syntax Error**: Input: Missing `[]`. Expect: `ValidationError`.
*   **(T2.05) Unknown Marker**: Input: `[?]`, `[XX]`. Expect: `ValidationError`.
*   **(T2.06) Logic Conflict (Shallow)**: Input: Done Parent / Pending Child. Expect: `ValidationError`.
*   **(T2.07) Referential Integrity**: Input: Active Task + Missing `.flow/sub.md`. Expect: `ValidationError`.
*   **(T2.08) Sibling Conflict**: Input: Two `[/]` siblings. Expect: `ValidationError`.
*   **(T2.09) Name Conflict**: Input: Duplicate sibling names. Expect: `ValidationError`.
*   **(T2.10) Path Traversal**: Input: `@ ../hack`. Expect: `ValidationError`.

### 5.3 Persistence (Write) (T3.xx - Task 1.2b)
*   **(T3.01) Create New**: Input: New path. Expect: File created.
*   **(T3.02) Sanitize**: Input: Messy formatting. Expect: 4-space output.
*   **(T3.03) Unicode**: Input: 🐍. Expect: Preserved.
*   **(T3.04) Permission Denied**: Input: Read-only file. Expect: `PermissionError`.
*   **(T3.05) Comment Strip**: Input: `<!-- -->`. Expect: Removed in output.
*   **(T3.06) Line Endings**: Input: `\r\n`. Expect: `\n`.
*   **(T3.07) Keyword Preservation**: Input: `Task [Hint]`. Expect: Preserved correctly.
