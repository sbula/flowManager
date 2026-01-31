# 05. Lifecycle Management

## Overview
This document explains the runtime lifecycle of the Flow Manager process itself: Boot, Resume, and Crash Recovery.

## 1. Boot Sequence (`flow_manager.sh`)
The Bash script is the entry point. It sets up the environment to ensure Python receives a clean state.
1.  **Environment Sync**: Loads `.env` (API Keys).
2.  **VirtualEnv Check**: Activates the correct `.venv`.
3.  **PYTHONPATH**: Sets `PYTHONPATH` to the project root (Crucial for module imports).
4.  **Launch**: Executes `python -m workflow_core.flow_manager.main`.

## 2. CLI Entry Point (`cli.py`)
The Python process starts here.
1.  **Parser**: Parses `start`, `resume`, `reset` commands.
2.  **Engine Init**: Instantiates `WorkflowEngine(config_root, state_root)`.
3.  **Command Dispatch**: Calls `engine.run_workflow()`.

## 3. Resumption Logic (`PersistenceManager`)
When `resume <task_id>` is called:
1.  **Load**: Reads `.flow_state/<task_id>.json`.
2.  **Deserialize**: Rebuilds the `WorkflowState` object, restoring `current_step_index` and `context_cache`.
3.  **Validation**: Checks if `workflow_registry.json` has changed since the state was saved. (Warns on strict version mismatch).
4.  **Execute**: Calls `_execute_steps()`. Since `current_step_index` is restored, the loop skips all previously completed steps and resumes instantly at the breakpoint.

## 4. Crash Recovery
### 4.1 The "Hard Crash" Scenario
If the Python process is killed (OOM, Power Failure):
- **Disk State**: The `.json` state file contains the progress up to the *last completed step*.
- **Recovery**: Running `resume` will restart the *current* (interrupted) step from the beginning. It is **At-Least-Once** delivery.

### 4.2 The "Logical Stuck" Scenario
If an Agent is in a loop or produces bad output:
- **Command**: `reset <task_id>`
- **Action**: Deletes `.flow_state/<task_id>.json`.
- **Result**: Next `start` command treats it as a fresh task (but files on disk remain, so the Agent sees existing work as "Draft").
