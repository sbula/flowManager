# Documentation Manifest (The Map)

> **To Future Agents**: This directory is the **Source of Truth** for the project. Do not create random files. Follow this structure strictly.

## 1. Directory Structure

### `docs/` (Root Documentation)
*   `00_MASTER_OVERVIEW.md`: **Start Here**. Executive summary and core concepts.
*   `README.md`: Directory index.
*   `MANIFEST.md`: This file (The Map).
*   `consolidation_changelog.md`: Audit trail of changes.

### `docs/plans/` (The Roadmap)
**Content**: Active execution plans and project status.
**Rule**: Living documents tracked by the team.
*   `STATUS.md`: **Project Dashboard**. Current focus and risks.
*   `current_sprint.md`: Detailed plan for the current phase.
*   `roadmap_2026.md`: Long-term vision.

### `docs/specs/` (The Laws)
**Content**: Authoritative, testable requirements.
**Rule**: If a feature is implemented, it MUST be defined here.
**Naming**: `01_XX_name_spec.md`.
*   `01_02_status_domain_spec.md`: The "Database" (Status Tree) behavior.
*   `01_03_engine_core_spec.md`: The Runtime (Engine, Flows) behavior.
*   `01_04_tooling_spec.md`: The Tool interfaces and Security.
*   `01_05_atoms_spec.md`: The Atoms (Unit of Work) specification.
*   `01_06_llm_binding_spec.md`: The Raw LLM Interface (Models, Tokenizers, Provider Abstraction).
*   `01_07_skills_spec.md`: The Skills system specification.
*   `01_08_flows_spec.md`: The Flows (DAG Orchestration) specification.
*   `01_09_rag_spec.md`: The Knowledge System (RAG, Indexing).
*   `01_10_agent_orchestration_spec.md`: How agents and personas interact.
*   `01_11_validation_gate_spec.md`: The Validation Gate (Anti-Hallucination Firewall).

### `docs/architecture/` (The Map)
**Content**: High-level design patterns, data flow diagrams, and architectural decisions.
**Rule**: Explains "How it works" conceptually.
**Naming**: Topic-based (e.g., `fractal_patterns.md`).
*   `00_system_map.md`: High-level system architecture diagram.
*   `methodology_index.md`: **Start Here for Methodology**. Consolidated index of the spec methodology framework.
*   `spec_methodology.md`: Core framework: two-level spec model, 5-section template, 5 structure tests, fractal levels.
*   `completeness_tests.md`: Second axis: 5 completeness tests, two-axis model, static analysis sketches.
*   `lifecycle_layers.md`: DRAFT — layer-specific implementation guides (L1 Business → L6 Deploy).
*   `constitution_template.md`: DRAFT — universal project constitution template. Ref: [DMZ SOUL.md](https://github.com/TheMorpheus407/the-dmz).
*   `review_checklists.md`: DRAFT — project-specific review checklist template. Ref: [DMZ reviewer.md](https://github.com/TheMorpheus407/the-dmz).
*   `spec_review_pipeline.md`: Multi-stage LLM review pipeline (PO → Architect → Junior Dev).
*   `fractal_patterns.md`: The L1-L5 recursive planning model.
*   `rag_architecture.md`: Design for the retrieval-augmented generation layer.

### `docs/analysis/` (The History)
**Content**: Decision logs, trade-off studies (e.g., "Python vs Rust").
**Rule**: Static. Do not update once the decision is executed.

### `docs/proposals/` (The Future)
**Content**: RFCs and Roadmaps.
**Rule**: Living until merged or rejected.
*   `specweaver_roadmap.md`: Evolution plan from FlowManager to SpecWeaver.
*   `mvp_feature_definition.md`: MVP scope — features F1-F7, module map, architecture constraints.

### `docs/archive/` (The Graveyard)
**Content**: Deleted. Valuable information extracted to `docs/analysis/legacy_extraction.md`.

## 2. Information hierarchy
1.  **Specs** (`docs/specs`) override everything.
2.  **Architecture** (`docs/architecture`) explains the Specs.
3.  **Code** must match the Specs.
