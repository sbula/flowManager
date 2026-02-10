# Test Inventory: Deferred / Re-allocation (01_0x)

This file contains test cases removed from `01_04_tooling_spec.md` because they belong to other architectural components (Engine, Status Domain, etc.) or future phases.

## 1. Engine & Context Concerns
*   **T4.02 Task Context Parsing**:
    *   *Original Context*: KnowledgeTool.
    *   *Reason*: Parsing `status.md` to build context is a core Engine responsibility (or Status Domain), not a Tool capability. The Tool should just *receive* the context.
    *   *Test*:
        *   Input: `status.md` with nested tasks.
        *   Expect: Engine parses and injects correct `TaskContext` object into the Tool runtime.

## 2. State Management Concerns
*   **T11.05 Unserializable State (Pickle Bomb)**:
    *   *Original Context*: Tool Resilience.
    *   *Reason*: The *Engine* fails when saving state. While the Tool causes it, the *fix/test* belongs to the Engine's State Manager integration tests.
    *   *Test*:
        *   Input: Tool returns un-pickleable object.
        *   Expect: State Manager sanitizes or discards the object before persistence, logging a warning.
