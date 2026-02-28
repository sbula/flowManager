# 01_08 Flows Specification

> **Status**: DRAFT
> **Owner**: Architecture Team
> **Context**: Definition of the orchestration logic (Workflows) that binds the system together.

## 1. Overview
**Flows** are directed, acyclic graphs (DAGs) – or linear sequences – of **Atoms** and **Skills**. They define the lifecycle of a request, from user input to final result.

**Key Characteristics:**
1.  **Declarative**: Defined in JSON/YAML (Policy as Code).
2.  **Stateful**: Flows maintain a `FlowContext` that persists across steps.
3.  **Resumable**: Execution can be paused (e.g., for human intervention) and resumed.

---

## 2. The Flow Schema (`workflow_registry.json`)

The `workflow_core/config/workflows` directory contains the definitions.

### 2.1 Schema Structure

```json
{
  "WorkflowName": {
    "TaskSet": "DomainIdentifier",
    "ExpertSet": "RoleIdentifier",
    "Description": "Human-readable intent",
    "steps": [
      {
        "id": "step_1",
        "type": "atom | skill | flow",
        "target": "AtomName",
        "args": {
          "param1": "{context.var}",
          "param2": "static_value"
        },
        "on_failure": "halt | retry | ignore"
      }
    ]
  }
}
```

### 2.2 Context Variable Injection
Flows support dynamic variable injection using `{}` syntax.
*   `{input.query}`: User input.
*   `{step_1.output}`: Result from a previous step.
*   `{config.model}`: System configuration.

---

## 3. Orchestration Engine (`WorkflowEngine`)
Located at: `workflow_core.engine.core.engine`

### 3.1 Execution Loop
1.  **Load**: Reads the Flow definition.
2.  **Initialize**: Creates the `FlowContext`.
3.  **Step**:
    *   Resolve `next_step`.
    *   Interpolate arguments (`args`).
    *   Instantiate Atom/Skill.
    *   `result = atom.run(context, **args)`.
    *   Update Context with `result.exports`.
4.  **Complete**: Return final Context state.

### 3.2 State Persistence
*   **Status File**: `status.md` acts as the visible state ledger.
*   **Checkpoint**: The Engine can save context to disk (`.flow/context.json`) to support resume-on-failure.

### 3.3 Sub-Workflow Orchestration & Hydration
When a Flow triggers another Flow (Sub-Flow), the Engine manages the boundary.
*   **Reconciliation Principle**: The Engine MUST NOT spawn a subflow without first checking if a `SubFlow_ID` for that exact DAG node already exists in an `IN_PROGRESS` or `COMPLETED` state. This prevents orphaned subflows during Parent crash recoveries. **CRITICAL (Split-Brain Defense)**: Sub-Flow genesis MUST involve a pre-flight transactional lock or a Two-Phase Commit on the state DB (e.g., Parent writes "Starting Child X", Child confirms) so a crash during process spin-up does not result in an untracked, competing child.
*   **Deep Hydration (Context Re-Merge)**: When resuming a paused Subflow, the Engine MUST dynamically hydrate it by re-merging `Parent_Context_Live + Child_Local_Context_Live`. The Subflow MUST NOT rely on a stale context snapshot taken at the exact millisecond it was instantiated. This guarantees any out-of-band administrative fixes applied to the Parent context while the child was paused are immediately inherited.

---

## 4. Standard Flows

### 4.1 `AskCodebase`
*   **Trigger**: User Query via CLI.
*   **Steps**:
    1.  `RagRetrievalAtom` (Query Knowledge Base).
    2.  `AgentAtom` (Synthesize Answer).

### 4.2 `ImplementFeature`
*   **Trigger**: `start_task` command.
*   **Steps**:
    1.  `PlanningSkill` (Draft Implementation Plan).
    2.  `ManualInterventionAtom` (Wait for Approval).
    3.  `CodingSkill` (Execute Changes).
    4.  `TestVerificationSkill` (Run Tests).

---

## 5. Extensibility
*   **Custom Flows**: Users can add new JSON files to `config/workflows`.
*   **Dynamic Loading**: The Registry scans the directory at startup.
