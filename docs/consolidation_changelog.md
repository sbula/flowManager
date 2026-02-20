# Documentation Consolidation Change Log

**Purpose**: Track the movement and consolidation of documentation files. Use this log to update code, tests, or prompts that reference specific file paths.

## Status: In Progress

| Original File | New Location / Status | Rationale | Code References to Check |
| :--- | :--- | :--- | :--- |
| **(New)** | `docs/MANIFEST.md` | Single source of truth for doc structure. | N/A |
| **(New)** | `docs/architecture/` | Directory for high-level design maps. | N/A |
| `analysis/rag_system_design.md` | `architecture/rag_architecture.md` | RAG is a permanent system component, not just analysis. | `specs/01_06_rag_spec.md`, `specs/01_04_tooling_spec.md` |
| `analysis/fractal_workflow_design.md` | `architecture/fractal_patterns.md` | Core architectural pattern documentation. | `specs/01_03_engine_core_spec.md` (conceptually) |
| `protocols/01_Agent_Orchestration.md` | `specs/01_10_agent_orchestration_spec.md` | Elevated to formal Specification. | `README.md` |
| `specs/01_05_llm_binding_spec.md` | (Restored) | Header corruption fixed. | N/A |
| `specs/01_04_tooling_spec.md` | (Updated) | Reference updated to `rag_architecture.md`. | N/A |
| `README.md` | (Updated) | Structure updated to reflect changes. | N/A |
| **(New)** | `docs/00_MASTER_OVERVIEW.md` | "Start Here" guide and Base Concepts. | `README.md` |
| **(New)** | `docs/plans/` | Dedicated directory for active plans. | `MANIFEST.md` |
| `analysis/v_next_implementation_plan.md` | `plans/current_sprint.md` | Promoted to active plan. | `plans/STATUS.md` |
| `analysis/roadmap.md` | `plans/roadmap_2026.md` | Promoted to active plan. | `plans/STATUS.md` |
| **(New)** | `docs/plans/STATUS.md` | Live Project Dashboard. | `README.md` |
| **(New)** | `docs/architecture/00_system_map.md` | System Architecture Diagram. | `MANIFEST.md` |
