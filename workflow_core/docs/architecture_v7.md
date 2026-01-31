# Flow Manager V7 Architecture

**Protocol V7** represents a shift from a "Script-Based" utility to a "System Application".

## Key Principles

1.  **Ironclad Configuration**: Setup is strictly loaded from `flow_config.json`. Absence of config is a fatal error. Heuristics (guessing paths) are banned.
2.  **Clean Entry**: The CLI (`entrypoints/cli.py`) is a pure adapter. It parses arguments and dispatches to the internal Domain/Engine. It does NOT contain business logic.
3.  **Single Responsibility**: 
    *   `StatusReader`: Handles File IO and Regex parsing.
    *   `ContextManager`: Decides "What is the active task?" and "Which workflow applies?".
    *   `WorkflowEngine`: Executes the workflow steps.
4.  **Hard Failure**: The system prefers crashing (Exit 1) over incorrect execution.

## Data Flow

1.  **Start/Resume**: User runs `bash flow_manager.sh start`.
2.  **Boot**: `cli.py` initializes `ConfigLoader` and `logging`.
3.  **Context**: `ContextManager` uses `StatusReader` to parse `status.md`.
4.  **Decision**: 
    *   If `start` with ID: `ContextManager` verifies ID exists.
    *   Logic determines "Workflow Mode" (Planning vs Execution) based on Config Prefixes.
5.  **Execution**: `WorkflowEngine` is invoked with `task_id` and `workflow_name`.
6.  **State**: State is persisted to `.flow_state/` (managed by Engine).

## Models

We use Pydantic for rigid validation of the `status.md` structure.

```python
class Task(BaseModel):
    id: str
    mark: Literal[' ', 'x', '/']
    ...
```

## Security

*   **Path Traversal Prevention**: `StatusReader` only allows configured paths.
*   **Backup Rotation**: `StatusReader.update_status` rotates `status.md.bak.N`.
