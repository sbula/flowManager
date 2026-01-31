# Workflow Core (V7)

The **Universal Flow Engine** for the Quantivista monorepo.

## Architecture V7.4 (Strict / Config-Driven)

This module implements the core logic for the Gemini Workflow System.
It has been refactored (Jan 2026) to follow a strict "Clean Architecture" pattern.

### Directory Structure

*   **`entrypoints/`**: adapters for external interfaces.
    *   `cli.py`: The CLI adapter (Main Entry Point) for `flow_manager.sh`.
*   **`core/`**: Pure domain logic.
    *   `context/`: Logic for identifying active work (`StatusReader`, `ContextManager`, `models`).
    *   `engine/`: The orchestration engine (`WorkflowEngine`, `Stage`, `Atom`).
*   **`infrastructure/`**: IO and System interactions.
    *   `logging.py`: Centralized logging configuration.
    *   `config/`: Configuration loading (`ConfigLoader`).
*   **`validators/`**: System integrity checks.

## Usage

Do not call this module directly. Use the root wrapper:

```bash
# From Repo Root
bash flow_manager.sh [command]
```

## Configuration

Configuration is strictly defined in `workflow_core/config/flow_config.json`.
Missing configuration will cause the system to **HALT** (Ironclad Config).