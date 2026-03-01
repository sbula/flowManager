# Flow Manager: Core Engine Architecture

## 1. Background Daemon & State Machine
The Flow Engine (`workflow_core/engine/core/engine.py`) is a **State-Persistent Workflow Orchestrator** designed to run as a **Background Daemon**, rather than a synchronous foreground script. This ensures decoupled interfaces (CLI and Web UI act as thin clients) and agent survivability across terminal closures.

### 1.1 State Schema (`WorkflowState`)
The Engine does not keep state in memory. It persists state to disk (`.flow_state/`) after *every* step. This ensures crash recovery, multiplexing (working on multiple features simultaneously via the daemon), and "Time Travel" capabilities.
```python
class WorkflowState:
    task_id: str              # Correlation ID
    current_step_index: int   # Pointer to active step
    context_cache: Dict       # Global Variable Store
    steps_history: Dict       # Audit Log of every executed atom
```

### 1.2 The Execution Loop (`_execute_steps`)
The heart of the system is the execution loop. It relies on idempotency to safely resume tasks.
```python
while state.current_step_index < total_steps:
    step_def = workflow_def.steps[state.current_step_index]
    
    # 1. Check if already done (Idempotency)
    if step_state.status == "COMPLETED": continue
        
    # 2. Execute Atom
    output = executor.execute_step(step_def, context)
    if output.status == "WAITING": return  # Exit Loop, persist state
        
    # 3. Context Export & Advance
    if step_def.export: context.update(output.exported_vars)
    state.current_step_index += 1
```

## 2. Atom Resolution & Tooling System

### 2.1 Variable Substitution (`_resolve_args`)
Before an Atom is executed, the Engine performs **Variable Substitution** using a Regex resolver to map `${namespace.key}` placeholders to values in the `context_cache`.
**Crucial**: Atoms *never* see placeholders. They always receive fully resolved paths and values.

### 2.2 Scoped Security
Tools are the "Hands" of the Agent. Tools are simply **Atoms** wrapped in a security layer enforced by the `AtomExecutor`.

1.  **File System Scope**: The `write_file` atom checks target paths against an `ALLOWED_PATHS` list (e.g., Blocked: `/.env`, Allowed: `src/`).
2.  **Command Whitelisting**: The `run_command` uses Whitelisting for high-risk environments (e.g., CI/CD only allows `pytest`, `npm test`).

## 3. Cognitive Layer & Context Injection

The interface between the structured Engine and the unstructured LLM is handled via the declarative context building approach.

### 3.1 The Context Cache & Export Mechanism
To prevent context pollution, data must be *explicitly* exported from one atom to be available to the LLM in the next.
```json
{
    "id": "analyze_repo",
    "export": { "summary": "repo_analysis_summary" }
}
```

### 3.2 Prompt Templates & Token Management
Templates are **Jinja2** files (`workflow_core/config/prompts/`) supporting inheritance (`{% extends "base.j2" %}`).
To avoid exceeding token limits (The "Context Window"), the system uses **Just-In-Time Loading**. Files are read immediately before the prompt step rather than dumping the whole repo into context.

## 4. Lifecycle & Runtime Management

### 4.1 Resumption Logic (`PersistenceManager`)
When `resume <task_id>` is called:
1.  **Load**: Reads `.flow_state/<task_id>.json`.
2.  **Deserialize**: Restores `current_step_index` and `context_cache`.
3.  **Execute**: Loop skips completed steps and resumes instantly at the breakpoint.

### 4.2 Crash Recovery
- **Hard Crash (OOM/Power)**: `.json` state limits loss to the *last completed step*. `resume` provides **At-Least-Once** delivery.
- **Logical Stuck (Bad LLM Output)**: `reset <task_id>` deletes the state. Files remain, so the Agent sees previous work as "Draft".

## 5. Git Integration (The Transaction Log)

The Flow Manager treats Git as a **Transaction Log**.
- **Auto-Commit (`state_update.py`)**: After "Significant Steps", the Engine triggers a Git commit (`[FlowManager] Step {step_id}: {desc}`). Allows reversion to exact states before bad LLM calls.
- **Branch Management**: Agent work happens on a feature branch. The Agent *cannot* push to `master`. Merging is a privileged "Human" action.

---

## 6. The Core MVP Execution Loop

The "Happy Path" flowchart for Flow Manager feature execution emphasizes structural safety over raw generation:

1. **Structured Spec Input**: Human defines constraints in a structured schema.
2. **Graph Retrieval**: RAG retrieves specific, relevant symbols within a tight Controlled Operational Boundary (COB).
3. **Agent Edit**: Agent leverages Context to generate a discrete file patch.
4. **Validation Gate**:
   - **[FAIL]**: Gate rejects structurally invalid code and feeds structured error back to the Agent.
   - **[PASS]**: Gate writes file AND atomically updates the `.machine-doc/` Semantic Mirror index.
5. **Visible Unit Tests**: An agent writes verification tests that the implementation agent can see.
6. **Hidden Scenario Tests**: A distinct agent writes integration tests that the implementation agent *cannot see* to prevent adversarial gaming of test coverage.
