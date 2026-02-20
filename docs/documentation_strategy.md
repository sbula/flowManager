# Documentation Strategy & Consolidation Proposal

## 1. Problem Statement
Knowledge is currently distributed across `protocols`, `analysis`, `design`, and `specs` directories. This fragmentation risks "State Drift" where the implementation (Code) diverges from the definition (Docs), or where different documents contradict each other.

## 2. Proposed Document Types (Taxonomy)

We need a strict taxonomy to know *where* to look and *where* to write.

### 2.1. Specifications (`docs/specs/`) - **The "Law"**
**Purpose**: Authoritative, versioned, and strictly testable requirements. If it's in a Spec, it MUST be implemented and tested.
*   **Audience**: Developers, QA, Agents.
*   **Format**: numbered `01_XX_name_spec.md`.
*   **Lifecycle**: Living documents. Updated *with* the code.

**Proposed Specs**:
*   `01_01_architecture_spec.md`: (NEW) System-wide constraints, directory structure rules, and high-level data flow.
*   `01_02_status_domain_spec.md`: (KEEP) The "Database" behavior.
*   `01_03_engine_core_spec.md`: (KEEP) The Runtime behavior.
*   `01_04_tooling_spec.md`: (KEEP) The Tool interfaces and Security.
*   `01_05_agent_orchestration_spec.md`: (MERGE) Consolidate `protocols/01_Agent_Orchestration.md` here.
*   `01_06_knowledge_system_spec.md`: (MERGE) Consolidate RAG and Knowledge specs.

### 2.2. Architecture (`docs/architecture/`) - **The "Map"**
**Purpose**: High-level understanding. Explains the "Big Picture" concepts that cross multiple specs.
*   **Audience**: Architects, New Onboarders.
*   **Format**: Topic-based (e.g., `fractal_design_patterns.md`).
*   **Content**:
    *   Diagrams (Data Flow, Component Interaction).
    *   Core Concepts (e.g., "What is a Fractal Workflow?").
    *   Design Philosophy.

### 2.3. Analysis (`docs/analysis/`) - **The "Why"**
**Purpose**: Decision logs, trade-off studies, and research. "Show your work".
*   **Audience**: Future Archaeologists (Why did we choose Python over Rust?).
*   **Lifecycle**: Static after completion. **Do not update** once the decision is made.
*   **Content**:
    *   `python_vs_rust.md` (Existing)
    *   `complexity_analysis.md`

### 2.4. Proposals / RFCs (`docs/proposals/`) - **The "Future"**
**Purpose**: Staging area for new ideas.
*   **Lifecycle**: Draft -> Review -> Approved (Merged to Spec) OR Rejected (Archived).
*   **Content**:
    *   `v_next_roadmap.md`

## 3. Consolidation Plan (Immediate Actions)

We will migrate "Knowledge" from scattered folders into the **Specs**.

1.  **Merge** `docs/protocols/01_Agent_Orchestration.md` -> `docs/specs/01_05_agent_orchestration_spec.md`
    *   *Rationale*: How agents are prompted is a hard system rule, not just a "protocol".
2.  **Merge** `docs/analysis/fractal_workflow_design.md` -> `docs/architecture/fractal_patterns.md` AND `docs/specs/01_03_engine_core_spec.md`.
    *   *Rationale*: The *Design* concepts go to Architecture. The *Implementation* interactions (Mixins, Inheritance logic) belong in the Engine Spec.
3.  **Merge** `docs/design/rag_system_design.md` -> `docs/specs/01_06_knowledge_system_spec.md`.
    *   *Rationale*: The RAG design is now a concrete part of the system.

## 4. Archive (`docs/archive/`)
Move all "Drafts", "Old Protocols", and "Obsolete Analyses" here to reduce noise.
