# 02. Flow Engine Architecture

## Overview
The Flow Engine (`workflow_core/engine/core/engine.py`) is a **State-Persistent Workflow Orchestrator**. It executes a directed graph of steps defined in JSON/YAML.

## 1. The State Machine
The Engine does not keep state in memory. It persists state to disk (`.flow_state/`) after *every* step. This ensures crash recovery and "Time Travel" capabilities.

### 1.1 State Schema (`WorkflowState`)
```python
class WorkflowState:
    task_id: str              # Correlation ID
    current_step_index: int   # Pointer to active step
    context_cache: Dict       # Global Variable Store
    steps_history: Dict       # Audit Log of every executed atom
```

## 2. Atom Resolution (`_resolve_args`)
Before an Atom is executed, the Engine performs **Variable Substitution**.
It uses a Regex resolver to map `${namespace.key}` placeholders to values in the `context_cache`.

*Code Trace*:
1.  **Definition**: `"target_file": "${artifact_dir}/${task_id}_Plan.md"`
2.  **Context**: `{"artifact_dir": "./docs", "task_id": "4.2"}`
3.  **Resolution**: `engine._resolve_args` -> `"target_file": "./docs/4.2_Plan.md"`

**Crucial**: Atoms *never* see placeholders. They always receive fully resolved paths and values.

## 3. The Execution Loop (`_execute_steps`)
The heart of the system is a `while` loop in `engine.py`.

```python
while state.current_step_index < total_steps:
    step_def = workflow_def.steps[state.current_step_index]
    
    # 1. Check if already done (Idempotency)
    if step_state.status == "COMPLETED":
        continue
        
    # 2. Execute Atom
    output = executor.execute_step(step_def, context)
    
    # 3. Handle Blocking
    if output.status == "WAITING":
        return  # Exit Loop, persist state
        
    # 4. Context Export
    if step_def.export:
        context.update(output.exported_vars)
        
    # 5. Advance
    state.current_step_index += 1
```

## 4. The Workflow Registry (`workflow_registry.json`)
This file maps Intent to Definition. It allows the CLI to say "Start Planning" without knowing *how* planning is implemented.

*Structure*:
- **ID**: Unique key (e.g., `Planning.Standard`)
- **Type**: `sequential` | `parallel`
- **Steps**: List of Atoms or Sub-Workflows.

This structure allows **Composition**. A "Feature Implementation" workflow can verify itself by including the "Standard Review" workflow as a sub-step.
