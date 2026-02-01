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

## 2.1 Security & Ambiguity
To prevent "Hidden Script" attacks or parser confusion:
*   **Ambiguity**: Status Markers (`[ ]`, `[x]`) are ONLY recognized at the start of the line. Markers inside the text are treated as literal text.
*   **Protocol Safety**: Reference paths (`@ path`) must be filesystem paths. dangerous protocols (`javascript:`, `data:`) are banned.
*   **Hidden Content**: HTML Comments (`<!-- -->`) are **DELETED** on save (T3.05). This removes the vector for "hidden instructions".

## 2.2 Integrity & Backup (Tamper Proofing)
To prevent unauthorized modification (Human or Agent bypassing the Tool):
*   **Sidecar Metadata**: A `.flow/status.meta` JSON file stores the SHA256 hash of the valid `status.md`.
*   **Validation**: `load()` calculates `hash(status.md)`. If it differs from `.meta`, raises `IntegrityError`.
    *   *Recovery*: CLI may offer "Restore from Backup" or "Force Accept" (Admin override).
    *   **Resolution API**:
        *   `accept_changes()`: Updates `.meta` with new hash.
        *   `decline_changes()`: Restores `status.md` from `.flow/backups/latest`. Raises Error if no backup.
*   **Backup Strategy**: Before every `save()`, the previous `status.md` is copied to `.flow/backups/status_<timestamp>.md`.

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
    *   **Mitigation**: Operations MUST verify the Target Name (Contextual Anchoring) before executing to prevent "drift".

## 4. Atomic Operations

### 4.1. Load (Read)
*   `load(path)`: Returns Tree. Validates syntax/logic. Calculate Virtual IDs.

### 4.2. Save (Write) - The "Safe Rewrite" Contract
*   `save(path, tree)`: Overwrites file. Normalizes format. Strips comments.
*   **Directive 1: Deterministic Rewriting**:
    *   File is regenerated from Tree. Strict 4-space indent.
    *   Markers normalized: `[/]`, `[ ]`, `[x]`, `[-]`.
*   **Directive 2: Content Fidelity**:
    *   `Task.name` is treated as **Immutable Binary Data**.
    *   **NO** AI Processing, Summarization, or Grammar correction.
    *   Example: "Fix bug... maybe?" is written exactly as-is.
*   **Directive 3: Lossy Comments**: 
    *   `<!-- partial comment -->` is stripped (Parser ignores it, so Persister drops it).

    *   `<!-- partial comment -->` is stripped (Parser ignores it, so Persister drops it).

## 5. Domain Operations (CRUD) - The "Smart Tree"
To ensure "Safe Writes", the `StatusTree` exposes atomic operations that maintain internal consistency (IDs, hierarchy).

## 5. Domain Operations (CRUD) - The "Smart Tree"
To ensure "Safe Writes", the `StatusTree` exposes atomic operations that maintain internal consistency (IDs, hierarchy).

*   `get_active_task()`: Returns the deepest `[/]` node (The "Cursor").
*   `find_task(id)`: Returns Task or raises IDError.
*   `add_task(parent_id, name, status="pending", index=None)`:
    *   **Logic**:
        *   If `index` is None: Append to list.
        *   If `index` provided: Insert at specific position (0-based) among siblings.
    *   **Validation**:
        *   **Cycle Detection**: Ensures added task (if subtree) does not contain Parent.
        *   **Deep State**: Validates *all* nodes in added subtree (e.g. no Active Child if Parent Pending).
        *   **Duplicate Name**: Raises `ValueError` if name exists among siblings.
    *   **ID Invalidation**: All Virtual IDs are considered **Invalid** after this operation. Caller MUST re-index or reload if they need IDs. (T4.15).
*   `update_task(id, name=None, status=None, context_anchor=None)`:
    *   **Anchor Check**: If `context_anchor` provided, must match current `task.name`.
    *   **State Logic (Strict)**: 
        *   If `status="active"`:
            *   **Sibling Check**: Raises `StateError` if any *other* sibling is already `active`. (Single Focus Rule).
            *   **Parent Check**: Raises `StateError` if Parent is NOT `active` (Hierarchy Rule).
            *   **Parent Check**: Raises `StateError` if Parent is NOT `active` (Hierarchy Rule).
            *   *Note*: To switch focus, User must explicitly Suspend old task first. To dive deep, User must Activate parent first.
            *   **Re-Open Workflow**: If Parent is `[x]`, User must explicitly `update_task(parent, status="active")` BEFORE activating the child. (No implicit auto-reopen).
*   `remove_task(id)`:
    *   Removes node.
    *   (Re-indexing happens on next Load).

## 6. Test Plan (Single Player / Strict)
**Source of Truth**: The full list of Test Cases (Inputs/Expectations) is maintained in `01_02_test_inventory.md`.

*   **T1.xx**: Loading & Parsing (Read).
*   **T2.xx**: Validation Guardrails (Read).
*   **T3.xx**: Persistence & Fidelity (Write).
*   **T4.xx**: Domain Operations & State Logic (CRUD).
