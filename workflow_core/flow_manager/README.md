# Flow Manager V7

The **Flow Manager** is the CLI entry point for the Gemini Workflow System. It wraps the core engine and provides strict process control.

## Usage

```bash
bash flow_manager.sh [command] [task_id]
```

### Commands

| Command | Description |
| :--- | :--- |
| `start` | Begins a new task. Looks for `Plan.*` or `Design.*` prefixes to trigger Planning Mode. |
| `resume` | Resumes the currently active task (`[/]`). Uses Smart Dispatch to determine mode. |
| `status` | Shows the active task, file location, and detected workflow mode. |
| `reset` | **[NEW]** Reverts a task to `[ ]` (Pending). Useful if you get stuck or need to restart logic. |
| `reopen` | Moves a completed task `[x]` back to `[/]` for bug fixes. |
| `validate` | **[NEW]** Runs a full system health check (Status File Valid + Config Integrity). |

## Smart Dispatch

Flow Manager V7 removes the need for manual `[Exec]` tags. instead, it infers the workflow from the **Task Prefix**.

*   **Planning Mode**: `Plan.*`, `Design.*`, `Init.*`, `Review.*`
*   **Execution Mode**: `Impl.*`, `Valid.*`, `Git.*`, `Gate.*`, `Refactor.*`, `Doc.*`

## Strict Status Parser

The system treats `status.md` as **Source Code**. It enforces:
1.  **Valid Structure**: Proper indentation and Markdown list format `- [ ] ID Name`.
2.  **Unique IDs**: No duplicate task IDs allow.
3.  **Single Focus**: Only **ONE** active task `[/]` is allowed at a time. The system will refuse to run if multiple tasks are active.

## Architecture

*   `main.py`: Entry point and command router.
*   `status_parser.py`: The "Compiler" for `status.md`.
*   `engine/`: The core execution logic (Planning/Execution loops).
