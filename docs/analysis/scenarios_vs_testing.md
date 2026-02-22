# Analysis of Scenario Evaluation and Orchestration for Flow Manager

## Executive Summary
This document synthesizes key architectural strategies and testing paradigms extracted from prior technical discussions regarding Agentic Scenarios. As Flow Manager evolves into a "High-Assurance Orchestrator", shifting our testing methodology from deterministic plumbing to scenario-based trajectory evaluation is critical for validating autonomous multi-agent interactions safely.

---

## 1. Scenario Evaluation vs. Testing Strategy

### 1.1 Distinguishing Plumbing from Reasoning
*   **Concept**: In an Agentic codebase, classical Unit/Integration testing evaluates "Plumbing" (determinist tooling). Scenarios evaluate stochastic "Reasoning" and trajectory execution.
*   **Application for Flow Manager**:
    *   **Testing**: Validating deterministic components like `FileTool`, `SubprocessTool`, or Tree-sitter extracts using standard assertions.
    *   **Scenarios**: Utilizing "Golden Datasets" to evaluate stochastic trajectories. 
    *   **LLM-as-a-Judge**: Instead of rigid boolean assertions, an isolated LLM evaluates the agent's logic.
        *   *Best Practice - Clear Rubrics*: The Judge LLM must be provided strictly defined criteria (e.g., "Score 1-5 on factual adherence to the retrieved specification").
        *   *Best Practice - Multi-Step Reasoning*: Prompt the Judge to break down complex judgments and provide a rationale/explanation before outputting a final score.
        *   *Best Practice - Bias Mitigation*: Guard against position bias and self-preference by swapping ordering in pairwise comparisons and calibrating prompts.

---

### 1.2 Trajectory Evaluation Metrics
When the LLM-as-a-Judge evaluates a scenario trajectory, it must score against standardized, observable metrics:
*   **Task Success Rate**: Did the agent achieve the final objective?
*   **Tool Selection & Execution Accuracy**: Did the agent pick the correct tool for the sub-task, provide the right parameters, and handle output correctly?
*   **Reasoning and Plan Quality**: Was the agent's logic sound? Did it adhere to the generated implementation plan rather than wandering?
*   **Intent Resolution**: Did the agent correctly interpret the underlying intent of the ambiguous user request?

### 1.3 Human-in-the-Loop (HITL) Calibration
*   **Concept**: An LLM-as-a-Judge is not infallible and can suffer from its own hallucinations or drift.
*   **Application**: Periodically, test runs and scenario evaluations must explicitly block and request expert human review. The human's score acts as a calibration baseline (Ground Truth) to refine the Judge's prompt rubrics, ensuring the automated evaluation pipeline remains rigorous and trustworthy.

---

## 2. Orchestration & State Management for Scenarios

### 2.1 From Session to Daemon Service
*   **Concept**: Transitioning Flow Manager from a blocking CLI script to an Asynchronous Task Graph running as a Daemon enables complex scenario execution in the background.
*   **Application**: 
    *   Maintain a unified API stream (WebSocket/FastAPI) that the CLI or Web UI attach to as "dumb terminals".
    *   Isolate Agent context via Virtual Workspaces (git worktrees) to avoid Resource Contention when parallelizing scenario evaluations.
    *   Track State globally via a Dependency Graph indicating which ongoing features or scenarios rely on others natively.
