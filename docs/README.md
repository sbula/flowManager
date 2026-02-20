# Flow Manager Documentation

## 📚 Overview
The Flow Manager is a configuration-driven orchestration engine designed for fractal planning and high-assurance software development.

## 🚀 Getting Started
**👉 [Start Here: Master Overview](00_MASTER_OVERVIEW.md)**
Executive summary, core concepts (Fractal, Agents), and system map.

## 📂 Documentation Structure
The documentation is organized into four sections:

### 1. Plans & Status (`docs/plans/`)
**The Roadmap.** Active execution plans and project dashboard.
*   [Project Status](plans/STATUS.md): **Live Dashboard**.
*   [Current Sprint](plans/current_sprint.md): V-Next Implementation Plan.
*   [Roadmap](plans/roadmap_2026.md): Long-term vision.

### 2. Specifications (`docs/specs/`)
**The "Law".** Authoritative, testable requirements.
*   [Status Domain](specs/01_02_status_domain_spec.md): The "Database" behavior.
*   [Engine Core](specs/01_03_engine_core_spec.md): The Runtime behavior.
*   [Tooling](specs/01_04_tooling_spec.md): The Tool interfaces and Security.
*   [Agent Orchestration](specs/01_10_agent_orchestration_spec.md): How agents and personas interact.
*   [LLM Binding](specs/01_05_llm_binding_spec.md): Unified LLM Interface.
*   [RAG System](specs/01_06_rag_spec.md): Knowledge System Specs.

### 2. Architecture (`docs/architecture/`)
**The "Map".** High-level design patterns and concepts.
*   [Fractal Patterns](architecture/fractal_patterns.md): The L1-L5 recursive planning model.
*   [RAG Architecture](architecture/rag_architecture.md): Design for the retrieval-augmented generation layer.
*   [Agent Isolation](analysis/agent_isolation.md): preventing context leaks. (To be moved?)

### 3. Analysis (`docs/analysis/`)
**The "Why".** Decision logs and trade-off studies.
*   [Language Strategy](analysis/language_strategy_python_vs_rust.md): Python vs Rust decision.
*   [V-Next Implementation Plan](analysis/v_next_implementation_plan.md): Execution roadmap.

### 4. Archive (`docs/archive/`)
**Legacy Context.** Old drafts and protocols.

## 🚀 Getting Started
Start with the **Specs** to understand the requirements, then read **Architecture** for the big picture.
