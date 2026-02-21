# System Architecture Map

> **The Map**: High-level view of the Flow Manager components and their interactions.

## 1. Component Interaction Diagram

```mermaid
graph TD
    User((Developer)) -->|CLI Commands| Engine[Flow Engine]
    
    subgraph "Core System"
        Engine -->|Reads/Writes| StatusFile[Status Domain (.flow/status.md)]
        Engine -->|Loads| Config[Configuration (.flow/config.json)]
        Engine -->|Orchestrates| Agents[Agent Orchestra]
    end
    
    subgraph "Knowledge System (RAG)"
        Engine -->|Queries| VectorDB[(ChromaDB)]
        VectorDB -->|Retrieves| CodeIndex[Codebase Index]
    end
    
    subgraph "Tooling Layer (Sandboxed)"
        Agents -->|Calls| Tools[Tool Interface]
        Tools -->|Executes| FileSystem[File System]
        Tools -->|Executes| Shell[Shell Execution]
        Tools -->|Accesses| Network[Network (Restricted)]
    end
    
    subgraph "Project Space"
        FileSystem -->|Modifies| SourceCode[src/]
        FileSystem -->|Modifies| Tests[tests/]
        FileSystem -->|Modifies| Docs[docs/]
    end
    
    style Engine fill:#f9f,stroke:#333,stroke-width:4px
    style StatusFile fill:#bbf,stroke:#333,stroke-width:2px
    style VectorDB fill:#bfb,stroke:#333,stroke-width:2px
```

## 2. Key Flows

### A. The Planning Flow (L1-L4)
1.  **Trigger**: User runs `flow start`.
2.  **Engine**: Loads `status.md` to find the active task.
3.  **Agent**: "Planner Persona" analyzes the requirements.
4.  **RAG**: Retrieves relevant architectural patterns.
5.  **Output**: Creates a detailed `implementation_plan.md`.

### B. The Execution Flow (L5)
1.  **Trigger**: User approves the plan.
2.  **Engine**: Hydrates "Developer Persona".
3.  **Agent**: Writes code via `FileTool`.
4.  **Tool**: Runs tests via `ShellTool`.
5.  **Loop**: Iterates until tests pass.

---

## 3. Directory Map

| Path | Purpose |
| :--- | :--- |
| `src/flow/` | **Engine Core**. The Python code that runs the system. |
| `.flow/` | **Project State**. Local config, logs, and status. |
| `docs/specs/` | **The Law**. Hard requirements. |
| `docs/architecture/` | **The Map**. High-level patterns (You are here). Includes [RAG Architecture](rag_architecture.md), [Engine Specs](engine_architecture.md), and [Fractal Workflow Patterns](fractal_patterns.md). |
| `docs/plans/` | **The Roadmap**. Active plans. |
