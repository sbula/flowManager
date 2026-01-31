# Workflow Configuration

This directory contains the configuration files for the **Quantivista Flow Manager**.
The configuration is **Modular** and **Domain-Driven**.

## Core Configuration

*   **`core_teams.json`**: Defines Expert sets (Squads) and their members.
*   **`core_topics.json`**: The "Knowledge Graph" mapping Topics -> Experts (Authoring).
*   **`core_mappings.json`**: Global defaults.
*   **`core_routes.json`**: Process Routing (Task -> Handbook Directives).
*   **`review_rules.json`**: Dynamic Injection Rules (Context/Topic -> Expert Reviewers).
*   **`rules.json`**: **(V3)** Core Rules Engine configuration (Role & Council Resolution).
*   **`modules.json`**: **(V3)** Template Factory configuration (Document Layouts & Modules).
*   **`messages.json`**: **(V3)** HUD Message Templates.

## Domain Configuration (`domains/*.json`)
Instead of monolithic files, configuration is split by domain:
*   `domains/planning.json`: Planning tasks (P*).
*   `domains/execution.json`: Implementation tasks (I*).
*   `domains/quality.json`: Verification tasks (V*).
*   `domains/git_ops.json`: Branching/Merging workflows.
*   `domains/bootstrap.json`: Project initialization workflows.

## Critical Maintenance
*   **`service_context_map.json`**: Maps Services to their Documentation Context. Update this when adding new services.

## Validation
To verify configuration integrity:
```bash
python workflow_core/config_validator.py
```
