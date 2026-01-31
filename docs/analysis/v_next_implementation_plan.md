# Implementation Plan: Flow Manager V-Next Phase 1 (Python)

## 1. Safety Strategy (The "Safe Harbor")
We will use a **Parallel Execution Model** to ensure no disruption to existing work.

### 1.1 The "V7 Freeze"
*   **Action**: Move all current `workflow_core` files (except `tests/`) into `workflow_core/legacy_v7/`.
*   **Shim**: Create a new `main.py` that, by default, forwards all calls to `legacy_v7.main.py`.
*   **Toggle**: `flow start --v-next` will route to the new engine.

### 1.2 The "Empty Project" Requirement
**Problem**: Current system assumes a populated repo.
**Requirement**:
1.  `flow init`:
    *   Creates `.flow/config.json`.
    *   Creates `status.md` (Level 1 Root).
    *   Creates directories: `docs/analysis`, `docs/protocols`.
2.  **Verification**: New E2E test `tests/e2e/test_init_fresh.py` that runs in a temp dir.

---

## 2. Refactoring Steps (TDD Loop)

### Step 1: Package Structure
*   Create `pyproject.toml` (poetry).
*   Define dependencies: `pydantic`, `jinja2`, `typer` (CLI).

### Step 2: The Domain Model (Status Parsing)
*   **Test**: `tests/unit/domain/test_status_document.py`
    *   Case: `parse_simple_status`
    *   Case: `parse_nested_status`
    *   Case: `round_trip_safety` (Parse -> Save -> Parse = Identical)
*   **Impl**: `src/domain/status.py` using a proper recursive parser (no regex hacks).

### Step 3: The Engine Shell
*   **Test**: `tests/unit/engine/test_executor.py` (Mocked atoms).
*   **Impl**: `src/engine/core.py`.

---

## 3. Verification Plan

### 3.1 Automated Tests
*   **Unit**: `pytest tests/unit/domain` (Target: 100% Coverage for Domain Model).
*   **Integration**: `pytest tests/integration/v_next` (Verify Atom wiring).
*   **E2E**: `pytest tests/e2e` (The "Fresh Install" scenario).

### 3.2 Manual Verification
1.  Run `flow --v-next init` in a temp folder.
2.  Verify `status.md` is created.
3.  Add a task manually to `status.md`.
4.  Run `flow --v-next start` and verify it picks up the task.

### 3.3 Critical Test Gaps (Must Cover in V-Next)
**The "Junior Mistakes" we must fix:**
1.  **Parser Edge Cases**:
    *   Malformed Markdown (missing spaces, bad indentation).
    *   Unicode/Emoji support in task names.
    *   Concurrency (File locking on `status.md`).
2.  **Engine Resilience**:
    *   **Atom Failure**: Verify state persistence *before* crash.
    *   **Context Isolation**: Ensure atoms cannot overwrite system variables (`config.root`).
    *   **Infinite Loops**: Cycle detection in workflow graph.
3.  **Expert Logic**:
    *   **Conflict Resolution**: Logic for disparate expert opinions (currently missing).
    *   **Resumption**: Verify starting at Expert N, not Expert 1, on resume.
    *   **Config Integrity**: Fail fast if `core_teams.json` references missing personas.
