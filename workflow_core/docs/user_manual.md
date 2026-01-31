# Quantivista Flow Manager V7 - User Manual

## Overview
The **Flow Manager** is the mandatory interface for all development work in the Quantivista monorepo. It enforces process discipline, ensures data integrity, and manages the Agent-User collaboration lifecycle.

> **Protocol V7** (Jan 2026): Config-Driven, Smart Dispatch, and Robust Validation.
> **Protocol V8.5** (Recovery): Sequential Scribing & Narrative Synthesis.

## Protocol V8.5: Sequential Scribing
The **Planning Phase** now utilizes an "Append-Only" workflow.
1.  **Drafting**: The system creates a Plan Header.
2.  **Council Execution**: The Expert Sequencer iterates through the required "Council of Experts".
3.  **Appender Logic**: Each expert reads the current file and **appends** their analysis.
    -   *No Placeholders are used.*
    -   *No Templates are filled.*
    -   *Pure Narrative Build.*

## Core Commands

All commands are executed via the wrapper script in the root directory:
```bash
bash flow_manager.sh [command] [args]
```

### 1. `start [task_id]`
Begins a new task or switches context.
- **Workflow**: Auto-detected via Smart Dispatch (e.g., `Plan.*` -> Planning, `Impl.*` -> Execution).
- **Validation**: Enforces `status.md` integrity before checking for next pending.
- **Usage**: `bash flow_manager.sh start` (Auto-detects next pending task) OR `bash flow_manager.sh start 1.2` (Explicit).

### 2. `resume`
Continues the currently active task (marked with `[/]`).
- **Autopilot**: Inherits the workflow mode from the active task's prefix.
- **Validation**: Checks if `status.md` is valid.

### 3. `status`
Displays the current context, including:
- Active File path
- Active Task ID & Name
- Detected Workflow Mode
- **Validation Status**: Warns if the status file is corrupt.

### 4. `validate`
**[NEW in V7]** strictly checks the `status.md` file for compliance.
- **Rules**:
    - No duplicate Task IDs.
    - Exactly one (or zero) active tasks (`[/]`).
    - **Prefix Compliance**: Active task must have a recognized prefix defined in `flow_config.json`.
    - Correct indentation/hierarchy (warnings).
- **Use Case**: Run this if you suspect the Markdown file is broken.

### 5. `reset [task_id]`
Safely clears a task's progress (`[/]` or `[x]` -> `[ ]`).
- **Backup Rotation**: Automatically creates `status.md.bak`, `status.md.bak.1`, etc., before modifying the file.
- **Use Case**: Retrying a failed implementation or restarting a plan.

### 6. `reopen [task_id]`
Re-activates a completed task (`[x]` -> `[/]`) for hotfixes.

## Configuration (`flow_config.json`)
Configuration is strictly managed in `workflow_core/config/flow_config.json`.
- **Root Markers**: Files used to identify the repo root (e.g., `gemini.md`, `claude.md`).
- **Prefixes**: Mapping of Task ID prefixes to Workflows.
    - **Planning**: `Plan`, `Design`, `Init`, `Review`
    - **Execution**: `Impl`, `Valid`, `Git`, `Test`

## Troubleshooting

### "Status Validation Failed"
The system refuses to run if `status.md` is corrupt (e.g., two tasks marked as `[/]`).
**Fix**:
1. Run `bash flow_manager.sh validate` to see the error.
2. Edit `status.md` manually to fix the conflict (e.g., uncheck one task).

### "Repository Root Not Found"
The system looks for `gemini.md` or `.git`. Ensure you are running from the monorepo root.

### Logs
Logs are written to `flow.log` in the root directory. V7 enables **Log Rotation** (Max 5MB, 3 backups) to prevent disk bloat.
