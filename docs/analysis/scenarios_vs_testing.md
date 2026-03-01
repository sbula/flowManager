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

> **Status**: Daemon architecture is **deferred to Phase 3+**. Current architecture uses the Single-Player synchronous CLI model. See [roadmap_2026.md](../proposals/roadmap_2026.md) for phasing.

---

## 3. Adversarial Scenario Design

### 3.1 The Sycophancy Problem
Standard LLM-based reviews tend toward "mode collapse" — all agents converge on polite agreement. This produces uniformly positive evaluations that miss real issues.

### 3.2 Adversarial Scenario Types
To counteract sycophancy, scenarios should include dedicated adversarial configurations:

*   **Devil's Advocate Scenario**: An agent is given a persona that is *structurally forbidden from compliments*. Its output schema requires a minimum number of issues found, with severity ratings.
*   **Contradiction Scenario**: Two agents receive the same code but contradictory instructions (e.g., "optimize for speed" vs. "optimize for readability"). The synthesis agent must identify and resolve the conflict.
*   **Hallucination Trap Scenario**: Agent is given a codebase with deliberately incomplete context. The scenario measures whether the agent admits uncertainty or fabricates solutions.
*   **Regression Scenario**: Agent is given a "fix" that previously introduced a bug. Tests whether the agent catches the regression pattern.

### 3.3 Structured Adversarial Output
Adversarial agents must return structured JSON, not prose:
```json
{
  "issues_found": [
    {
      "severity": "CRITICAL",
      "location": "file.py:42",
      "category": "logic_error",
      "description": "Off-by-one in loop boundary",
      "evidence": "Line 42: `range(0, len(items))` should be `range(0, len(items) - 1)`"
    }
  ],
  "approval_status": "REJECT",
  "min_issues_required": 3,
  "issues_delivered": 5
}
```

---

## 4. The 5-Phase Evaluation Workflow

### 4.1 Architecture
Building on the existing "Iterative Round Table" from [agent_isolation.md](agent_isolation.md), a comprehensive evaluation workflow adds two critical phases:

```
Phase 1: DIVERGENT     → Multiple experts work in STRICT isolation (blind)
Phase 2: CONFLICT      → Synthesis agent identifies contradictions between expert outputs
Phase 3: SYNTHESIS     → Merge non-conflicting findings; resolve conflicts via weighted voting
Phase 4: ADVERSARIAL   → Dedicated "Critic" agent attacks the synthesis (no approvals allowed)
Phase 5: IMPLEMENTATION → Final output produced only after adversarial review passes
```

### 4.2 Phase Gate Criteria
| Phase | Gate | Fail Action |
|:---|:---|:---|
| Divergent → Conflict | All experts returned structured output | Retry failed expert |
| Conflict → Synthesis | Conflicts enumerated with evidence | Add clarifying expert |
| Synthesis → Adversarial | Unified artifact produced | Loop back to Phase 1 |
| Adversarial → Implementation | Critic found < threshold critical issues | Loop back to Phase 3 |
| Implementation → Done | Code passes Validation Gate (01_11) | Loop back to Phase 5 |

### 4.3 Relationship to Complexity Tiers
Not all tasks require all 5 phases:

| Complexity | Phases Used |
|:---|:---|
| Low (parameter tweak) | Phase 1 → Phase 5 (skip 2-4) |
| Medium (feature addition) | Phase 1 → Phase 3 → Phase 5 |
| High (new system design) | All 5 phases mandatory |

---

## 5. Daemon Architecture Considerations (Phase 3+)

> **Status**: DEFERRED — Documented here for future planning. Not part of current Single-Player mode.

### 5.1 Why a Daemon?
The current synchronous CLI model has limitations:
*   Cannot work on Feature A (coding) while drafting specs for Feature B
*   Cannot run scenario evaluations in the background
*   Cannot expose a web UI for status monitoring

### 5.2 Proposed Daemon Architecture
```
┌─────────────┐     ┌────────────────┐     ┌──────────────────┐
│  CLI Client  │────▶│  Flow Daemon   │────▶│   Agent Workers  │
│  (Terminal)  │     │  (Persistent)  │     │  (Isolated VMs)  │
└─────────────┘     └────────────────┘     └──────────────────┘
                         ▲
┌─────────────┐          │
│  Web UI      │──────────┘
│  (Optional)  │
└─────────────┘
```

### 5.3 Communication Protocol
*   **WebSocket**: Real-time bidirectional streaming (agent output, status updates).
*   **gRPC**: Internal service-to-service calls between daemon and agent workers.
*   **FastAPI**: REST surface for external tools and integrations.

### 5.4 Key Invariants
*   CLI and Web UI are "dumb terminals" — they display state but do not hold it.
*   All state lives in the daemon's persistent store (`.flow/` directory or SQLite DB).
*   Agent workers are ephemeral — they can crash without losing workflow progress.

---

## 6. Virtual Workspace Isolation

### 6.1 Git Worktree Strategy
For parallel scenario evaluations or parallel feature work, agents operate in isolated git worktrees:
```bash
git worktree add ../feature-A-workspace feature/A
git worktree add ../feature-B-workspace feature/B
```

### 6.2 Benefits
*   **No resource contention**: Agent A editing `main.py` doesn't conflict with Agent B editing the same file.
*   **Independent state**: Each worktree has its own `.flow/status.md` and `.machine-doc/`.
*   **Git-native merging**: Changes are merged back via standard git workflows.

### 6.3 Limitations
*   **Disk overhead**: Each worktree is a full checkout. For large repos, shallow clones or sparse checkouts may be needed.
*   **Index synchronization**: The `.machine-doc/` index must be reconciled when merging branches.

---

## 7. Validation Gate Integration for Scenarios

### 7.1 Scenario-to-Gate Pipeline
When a scenario involves code generation, the generated code should pass through the Validation Gate (01_11) before being accepted as a valid trajectory step:

```
Agent generates code → Validation Gate → PASS → Scenario step succeeds
                                       → FAIL → Trajectory marked as "validation_failure"
```

### 7.2 Validation as a Scoring Dimension
Add to the trajectory evaluation metrics (§1.2):
*   **Validation Gate Pass Rate**: Percentage of generated code that passes the Validation Gate on the first attempt. Low pass rates indicate the agent is hallucinating APIs or violating architectural boundaries.
*   **Retry Efficiency**: How quickly does the agent self-correct after a gate rejection?

---

## 8. Blinding Protocol for Hidden Scenario Tests

### 8.1 Problem: Teaching-to-the-Test
If the code-writing agent has visibility into the scenario tests (or their structure), it can optimize for passing those specific tests rather than correctly fulfilling the spec. This creates a false sense of quality while hiding architectural gaps.

### 8.2 The Dual-Test Strategy
Generate two parallel test suites for every feature:

1. **Unit Tests** (Visible to Code Agent): Standard TDD-style tests. The code-writing agent sees these, writes code to pass them, and can iterate. These are part of the normal RED-GREEN-REFACTOR loop.
2. **Scenario Tests** (Hidden from Code Agent): Integration and behavioral tests generated by a separate agent. The code-writing agent **never sees** these tests, their assertions, or their trajectory expectations.

### 8.3 Isolation Enforcement via RAG Access Tiers
*   The **scenario test agent** receives only: the structured spec + public API surface (from the Symbol Index).
*   It does NOT receive: implementation source code, unit test code, or any of the code agent's prompt history.
*   The **code agent** does NOT receive: any scenario test content, file paths, or assertion criteria.
*   Enforcement: RAG metadata filtering ensures scenario test files are tagged `visibility: scenario_only` and excluded from any code-agent retrieval query.

### 8.4 Value Proposition
*   The scenario tests act as an **independent quality oracle** — they validate the *intent* of the spec, not just the mechanics of the unit tests.
*   If the code passes unit tests but fails scenario tests, it signals a spec interpretation error or an architectural gap.
*   This creates a genuine **adversarial loop** between the code agent (optimizing for unit tests) and the scenario agent (optimizing for behavioral correctness).


