# Analysis of Scenario Evaluation and Orchestration for Flow Manager

## Executive Summary
This document synthesizes key architectural strategies and testing paradigms extracted from prior technical discussions regarding Agentic Scenarios. As Flow Manager evolves into a "High-Assurance Orchestrator", shifting our testing methodology from deterministic plumbing to scenario-based trajectory evaluation is critical for validating autonomous multi-agent interactions safely.

---

## 1. Scenario Evaluation vs. Testing Strategy

### 1.1 Distinguishing Plumbing from Reasoning
*   **Concept**: In an Agentic codebase, classical Unit/Integration testing evaluates "Plumbing" (determinist tooling). Scenarios evaluate stochastic "Reasoning".
*   **Application for Flow Manager**:
    *   **Testing**: Validating deterministic tools like `FileTool`, `SubprocessTool`, Tree-sitter extracts.
    *   **Scenarios**: Utilizing "Golden Datasets" of trajectories. Evaluate if the agent called the right tool intuitively, recovered gracefully from exceptions, and maintained goal focus across a sequence of actions.
    *   **RAG Triangulation**: Utilize "LLM-as-a-judge" techniques to score agent logic strictly against retrieved context, thereby checking for hallucination against known specifications rather than rigid boolean assertions.

---

## 2. Orchestration & State Management for Scenarios

### 2.1 From Session to Daemon Service
*   **Concept**: Transitioning Flow Manager from a blocking CLI script to an Asynchronous Task Graph running as a Daemon enables complex scenario execution in the background.
*   **Application**: 
    *   Maintain a unified API stream (WebSocket/FastAPI) that the CLI or Web UI attach to as "dumb terminals".
    *   Isolate Agent context via Virtual Workspaces (git worktrees) to avoid Resource Contention when parallelizing scenario evaluations.
    *   Track State globally via a Dependency Graph indicating which ongoing features or scenarios rely on others natively.
