# Flow Manager: Master Overview

> **Start Here**: This document explains what the Flow Manager is, why we built it, and the core concepts you need to understand.

> [!CAUTION]
> ## Deployment Isolation (Non-Negotiable)
> In production, Flow Manager **MUST NOT** reside inside the target project's directory tree. It is installed and executed from a **separate, protected location** (e.g., a system-wide install, a dedicated tooling directory, or a container). This is a **security invariant**, not a convenience preference.
>
> **Why**: If Flow Manager lives inside the project it orchestrates, the agents it controls could modify, fake, or disable Flow Manager's own code — including the Validation Gate, SafePath, the Symbol Index, and the RAG manifest. This would completely destroy the trust boundary. The orchestrator must be **untouchable** by the agents it governs.
>
> **Rule**: Agents may read/write files in the **target project** only. They have **zero access** to Flow Manager's own source, config, or engine code.

## 1. What is the Flow Manager?

The Flow Manager is an **Agentic Orchestration Engine** designed for **High-Assurance Software Development**.

Unlike standard "Chat with Code" tools that are reactive and stateless, the Flow Manager is:
1.  **Plan-Driven**: It thinks before it acts (Planning Phase).
2.  **Fractal**: It uses the same process for high-level architecture (L1) as it does for single-function implementation (L5).
3.  **Stateful**: It maintains a persistent "World Model" (`.flow/status.md`) so it can resume work after a crash or a coffee break.
4.  **Process-Aware**: It enforces rigorous engineering standards (TDD, Code Review, Security Scans) via code, not just prompt suggestions.

---

## 2. Core Concepts (The Vocabulary)

To work with this system, you must understand these four pillars:

### I. The Fractal Workflow (L1-L5)
We break down complexity using a recursive "Zoom In" model.
*   **L1 (Strategic)**: The 10,000ft view. "Build a Trading Platform".
*   **L2 (System)**: "Build the Order Execution Service".
*   **L3 (Component)**: "Implement the WebSocket Listener".
*   **L4 (Feature)**: "Handle Reconnection Logic".
*   **L5 (Atomic)**: "Write the `connect()` function".

**Key Insight**: The *process* (Research -> Plan -> Implement -> Review) is the same at every level. The only difference is the Context.

### II. The Agentic Orchestra (Identity & Roles)
We do not use a generic "AI Assistant". We use specific **Personas** defined in `config/expert_personas.json`.
*   **The Architect**: Cares about system boundaries and data flow.
*   **The Quant Dev**: Cares about numeric stability and edge cases.
*   **The SRE**: Cares about observability and failure modes.
*   **The Product Owner**: Cares about value and scope creep.

The Engine "hydrates" these personas just-in-time. When you ask for a Code Review, you get the *specific* strictness of the required role.

### III. Flows & Atoms (The Runtime)
*   **Flow**: A sequence of steps (like a script). Defined in JSON. Resumable.
    *   *Example*: `ImplementFeature` = `Plan` -> `Approval` -> `Code` -> `Test`.
*   **Atom**: The smallest unit of work. A Python class that does one thing perfectly.
    *   *Example*: `GitCommit`, `RenderTemplate`, `RunTest`.
*   **Skill**: A collection of Atoms (e.g., "Coding Skill" or "Research Skill").

### IV. The Knowledge System (RAG)
The "System 2" Brain.
*   **Local RAG**: We index your codebase into a vector database (ChromaDB) locally.
*   **Context-Aware**: When an agent works on `OrderService`, it automatically retrieves the relevant `OrderExecution` protocols without you pasting them.

---

## 3. Directory Structure (Where things live)

> **Note**: In production, Flow Manager is **not** located inside the target project. The directories below describe Flow Manager's *own* structure, deployed separately from the software it orchestrates. Only the `.flow/` directory exists inside the target project as the bridge between FM and the project.

*   **`docs/specs/`**: The **Laws**. Hard requirements that must be met.
*   **`docs/architecture/`**: The **Map**. Diagrams and patterns.
*   **`docs/plans/`**: The **Roadmap**. Active execution plans.
*   **`src/`**: The **Engine**. The Python code that runs the show.
*   **`.flow/`**: The **Project State**. Lives inside the *target project*. Your local configuration and status.

## 4. Getting Started

1.  **Check the Status**: Look at `docs/plans/STATUS.md` to see what we are building.
2.  **Read the Specs**: Start with `docs/specs/01_02_status_domain_spec.md` to understand how we track work.
3.  **Run a Task**: Use the CLI to start a workflow (e.g., `flow start 1.2`).
