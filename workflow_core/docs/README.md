# Flow Manager V2

The **Flow Manager V2** is a configuration-driven workflow engine designed to enforce strict development protocols within the Quantivista monorepo.

## 1. Architecture

### 1.1 Core Concepts
*   **Engine (`engine.py`)**: The central executor that reads JSON workflow definitions and orchestrates steps.
*   **Atoms**: Atomic units of work (e.g., `Run_Command`, `Git_Command`).
*   **Workflows**: Sequences of steps (Atoms or other Workflows).
*   **Context Binding**: A mechanism to pass data between steps using `${variable}` placeholders.

### 1.2 Directory Structure
```text
workflow_core/
├── engine_v2/           # Core Logic
├── config/
│   ├── workflows/       # JSON Definitions
│   │   ├── common/      # Reusable Flows (TDD, Review)
│   │   ├── features/    # Feature Implementation Flows
│   │   └── gates/       # Validation Gates
│   └── atoms.json       # Registry of Atoms
└── docs/                # Documentation
```

## 2. Context Binding

The Engine maintains a `context_cache` (Global State) for each task.

### 2.1 Resolution (`args`)
You can inject context variables into step arguments using `${var_name}`.

```json
{
    "id": "run_test",
    "type": "atom",
    "ref": "Run_Command",
    "args": {
        "command": "${test_cmd_from_context}"
    }
}
```

### 2.2 Export (`export`)
Steps can export their output to the global context.

```json
{
    "id": "plan_step",
    "type": "workflow",
    "ref": "Planning.Standard",
    "export": {
        "approved_plan_path": "plan_file" 
    }
}
```
*   In this example, if `Planning.Standard` returns `{"approved_plan_path": "..."}`, it is saved as `context["plan_file"]`.

## 3. Meta-Flows

V2 uses a "Meta-Flow" pattern where high-level flows orchestrate sub-flows.

*   `Impl.Feature`: The master flow for feature work.
    *   Step 1: `Planning.Standard`
    *   Step 2: `Execution.TDD`
    *   Step 3: `Gate.Feature`
    *   Step 4: `Git.FeatureCommit`

This ensures that Validation (`Gate.Feature`) is **never skipped**, as it is a hard-coded step in the master flow.
