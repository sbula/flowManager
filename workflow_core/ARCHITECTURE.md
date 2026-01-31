# Quantivista Flow Manager Architecture (V3)

> **Status**: Active / Hybrid V3
> **Core Principle**: Separation of Orchestration, Logic, and Configuration.

## 1. Overview
The Flow Manager is the "Operating System" for the development workflow. It enforces the **Zero-Argument Protocol**, where the system deduces the context (Task) from `status.md` and guides the developer through the `Plan -> Implement -> Verify -> Review` cycle.

V3 introduces a strict separation of concerns, moving hardcoded logic out of the "God Object" (`reconciler.py`) into dedicated engines and configuration files.

## 2. Component Architecture

```mermaid
graph TD
    CLI[flow_manager.sh] --> Main[main.py]
    Main --> Reconciler[reconciler.py]
    
    subgraph "Hybrid V3 Core"
        Reconciler --> RulesEngine[RulesEngine (Role/Council)]
        Reconciler --> RevOrch[ReviewOrchestrator (The Gauntlet)]
        Reconciler --> TplFactory[TemplateFactory (Rendering)]
    end
    
    subgraph "Configuration (workflow_core/config/)"
        RulesEngine -.-> RulesConfig[rules.json]
        RevOrch -.-> ModulesConfig[modules.json]
        TplFactory -.-> ModulesConfig
    end
    
    subgraph "State"
        Reconciler -.-> StatusFile[status.md]
        RevOrch -.-> ReviewFile[reviews/*.md]
    end
```

### 2.1. The Reconciler (`reconciler.py`)
*   **Role**: The High-Level Dispatcher.
*   **Responsibilities**:
    *   Parses `status.md` to identify the Active Task.
    *   Determines the current `Phase` (Plan, Design, Code, etc.).
    *   Delegates complex logic to sub-engines.
    *   Manages the "HUD" (User Output).

### 2.2. Rules Engine (`engine_v2/core/rules_engine.py`)
*   **Role**: The Decision Maker for Roles and Councils.
*   **Source of Truth**: `workflow_core/config/rules.json`.
*   **Key Logic**:
    *   **Author Resolution**: `(ServiceType, Tags) -> AuthorRole` (e.g., `#Quant` -> Quant Dev).
    *   **Council Resolution**: `(ServiceType, Tags) -> CouncilSet` (e.g., Signal Service -> AlphaSquad).
    *   **Rule Validation**: Ensures strict mapping of tags to expert types.

### 2.3. Review Orchestrator (`engine_v2/core/review_orchestrator.py`)
*   **Role**: The State Machine for "The Gauntlet" (Sequential Expert Review).
*   **Responsibilities**:
    *   **State Management**: Tracks which Expert is currently reviewing.
    *   **Dynamic Unlocking**: Only reveals the *next* section in the markdown file when the previous one is signed off.
    *   **Completeness Check**: Ensures all checkboxes in `[ ]` are marked `[x]` before passing.

### 2.4. Template Factory (`template_factory/core.py`)
*   **Role**: The Document Generator.
*   **Source of Truth**: `workflow_core/config/modules.json`.
*   **Key Logic**:
    *   Generates Markdown reports based on "Modules" (Header, Context, Expert Section, Footer).
    *   Supports dynamic rendering (e.g., coloring the header based on status).
    *   **Generic Render**: No longer contains a massive switch statement; iterates over configured modules.

## 3. Configuration Files

### `workflow_core/config/rules.json`
Defines *Who* does *What*.
```json
{
  "AuthorRules": [
    { "Tags": ["Quant"], "Result": "Quant Dev" }
  ],
  "CouncilRules": [
    { "ServiceType": "Signal", "Result": "AlphaSquad" }
  ]
}
```

### `workflow_core/config/modules.json`
Defines *How* documents look.
```json
{
  "ReviewLayouts": {
    "Standard": ["Header", "Context", "Expert_Section", "Footer"]
  },
  "Modules": {
    "Expert_Section": {
      "Type": "Expert",
      "Content": "### Expert Analysis: {Role}..."
    }
  }
}
```

### `workflow_core/config/messages.json`
Defines specific HUD messages for every Phase/Keyword.

## 4. Isolation Principals
*   **No Code Outside `workflow_core`**: The engine is self-contained.
*   **State Separation**: 
    *   `workflow_core/state/.flow_state/` stores engine artifacts.
    *   `status.md` stores project intent.
