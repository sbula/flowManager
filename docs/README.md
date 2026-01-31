# Flow Manager Documentation

## 📚 Overview
The Flow Manager is a configuration-driven orchestration engine designed for fractal planning and high-assurance software development.

## 📂 Documentation Structure
The documentation is organized into three sections:

### 1. Protocols (`docs/protocols/`)
**The Reference Manual.** Describes the mechanics of the V-Next engine.
*   [Agent Orchestration](protocols/01_Agent_Orchestration.md): How agents, personas, and templates interact.
*   [Flow Engine](protocols/02_Flow_Engine.md): Architecture of the state machine and executor.
*   [Cognitive Layer](protocols/03_Cognitive_Layer.md): Context injection and RAG strategies.
*   [Tooling System](protocols/04_Tooling_System.md): Interface for CLI and sandboxed execution.
*   [Lifecycle Management](protocols/05_Lifecycle_Management.md): Process lifecycle and error handling.

### 2. Analysis (`docs/analysis/`)
**The "Why".** Deep dives into architectural decisions and visionary concepts.
*   [Fractal Workflow Design](analysis/fractal_workflow_design.md): The L1-L5 recursive planning model.
*   [Agent Isolation](analysis/agent_isolation.md): Architecture for preventing context leaks between agents.
*   [V-Next Proposal](analysis/v_next_architecture_proposal.md): Comprehensive architectural review and V-Next proposal.
*   [V-Next Implementation Plan](analysis/v_next_implementation_plan.md): The execution roadmap (Phase 1 Python + Test Gaps).
*   [Language Strategy](analysis/language_strategy_python_vs_rust.md): Decision logic for Python vs Rust.
*   [RAG System Design](analysis/rag_system_design.md): Design for the retrieval-augmented generation layer.
*   [Roadmap](analysis/roadmap.md): Future recommendations and refactoring path.

### 3. Archive (`docs/archive/`)
**Legacy Context.** Previous assessments and historical analysis.
*   Contains V7/V8 assessments and older implementation plans.

## 🚀 Getting Started
To understand the system, we recommend reading `protocols/02_Flow_Engine.md` first.
