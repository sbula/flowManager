# 04. Tooling & Security System

## Overview
Tools are the "Hands" of the Agent. In this architecture, Tools are simply **Atoms** wrapped in a security layer.

## 1. The Atom Executor (`executor.py`)
The `AtomExecutor` is the gateway. It receives a `StepDefinition` and decides how to run it.

### 1.1 Dispatch Logic
```python
def execute_step(self, step_def, context):
    atom_type = step_def.ref
    
    if atom_type == "run_command":
        return run_command.execute(step_def.args)
    elif atom_type == "write_file":
        return file_system.write(step_def.args)
    ...
```

## 2. Scoped Security
To prevent Agents from destroying the system, we implement **Scope Enforcement**.

### 2.1 File System Scope
The `write_file` atom checks the target path against an `ALLOWED_PATHS` list (defined in `flow_config.json`).
- **Blocked**: `/.env`, `/git`, `outside_project_root/`
- **Allowed**: `src/`, `docs/`, `tests/`

### 2.2 Command Whitelisting
The `run_command` atom is dangerous. It uses a **Whitelisting** approach (or strict regex matching) for high-risk environments.
- *Development Mode*: Looser restrictions (warns on dangerous commands like `rm -rf`).
- *CI/CD Mode*: Strict whitelist (only `pytest`, `npm test`, `gradle build`).

## 3. Git Integration & Checkpoints
The Flow Manager treats Git as a **Transaction Log**.

### 3.1 Auto-Commit (`state_update.py`)
After every "Significant Step" (configurable in workflow), the Engine triggers a Git commit.
- **Message Format**: `[FlowManager] Step {step_id}: {description}`
- **Benefit**: If an Agent messes up a file, you can revert to the exact state before that specific LLM call.

### 3.2 Branch Management
- **Feature Branches**: All Agent work happens on a `feat/task-id` branch.
- **Master Protection**: The Agent *cannot* push to `master`. Merging is a privileged "Human" action (via Pull Request).
