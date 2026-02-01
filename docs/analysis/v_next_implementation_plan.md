# Implementation Plan: Flow Manager V-Next Phase 1 (Python)

## 1. Safety Strategy (The "Safe Harbor")
We will use a **Parallel Execution Model** to ensure no disruption to existing work.

### 1.1 The "Zero-Touch" Side-by-Side Strategy (Revised)
**Legacy V7**:
*   **Action**: **DO NOT TOUCH**. Leave `workflow_core/` exactly as it is.
*   **Execution**: Continues running via `python -m workflow_core.flow_manager.main`.

**V-Next (Phase 1)**:
*   **Location**: Create a NEW directory `src/` (or `flow_vnext/`).
*   **Isolation**: V-Next will **NOT** import from `workflow_core`. It will have its own independent package structure.
*   **Execution**: Triggered via a new distinct entry point (e.g., `flow-next`).
*   **Benefit**: It is physically impossible to break V7 because we are not modifying its files or its runtime environment.

### 1.2 The "Standalone Tool" Architecture (Global vs Local)
**Goal**: Flow Manager should be an *external tool* (like `git` or `npm`), not a script inside the user's project `src/`.

**Structure**:
*   **The Tool**: Installing `flow-manager` gives you the `flow` binary.
*   **The Project**: A user's repo only needs a `.flow/` folder (config) and `status.md` (state).
*   **Benefit**:
    *   **Safety**: The tool logic is read-only and external. It cannot be broken by project refactoring.
    *   **Multi-Project**: One installed engine manages `Project A`, `Project B`, and `Project C`.



**The Unified Boundary: "Definitions vs. Hydration"**

We treat **Agents**, **Workflows**, and **Prompts** as equal concepts. They all follow the same **Lifecycle**:

1.  **Definition (Config/Templates)**: Static "Recipes" living in `.flow/`.
    *   **Agent Definition**: Role name, System Prompt *Template*, Parameter Schema (e.g., `requires: [language]`).
    *   **Flow Definition**: Step sequence, Parameter Schema (e.g., `requires: [file_path]`).
    *   **Prompt Definition**: Jinja2 string (e.g., `Review code in {{ language }}`).

2.  **Parameters (The Glue)**: Context passed at runtime.
    *   *Source*: CLI args (`--lang=python`), Project Config (`root=...`), or previous step outputs.

3.  **Hydration (The Engine's Job)**:
    *   **The Engine (`src/`)** is the "Hydrator". It takes a **Definition** + **Parameters** -> **Instance**.
    *   *Agent Hydration*: `Template("System Prompt {{ lang }}")` + `nparams(lang="Py")` -> `Instance(Active Agent with "System Prompt Py")`.
    *   *Flow Hydration*: `Flow("Review {{ file }}")` + `params(file="main.py")` -> `Instance(Running Review on main.py)`.

**The Boundary Rule**:
*   **Hardcoded (`src/`)**: The Logic of *How to Hydrate*. (e.g., `jinja2.render()`, `agent.chat()`).
*   **Config (`.flow/`)**: The *Recipes*. (The specific Prompts, Roles, and Steps).
*   **Parameters**: The *Input*.

### 1.3 The "Empty Project" Requirement
**Problem**: Current system assumes a populated repo.
**Requirement**:
1.  `flow init`:
    *   Creates `.flow/config.json`.
    *   Creates `status.md` (Level 1 Root).
    *   Creates directories: `docs/analysis`, `docs/protocols`.
2.  **Verification**: New E2E test `tests/e2e/test_init_fresh.py` that runs in a temp dir.

---

## 2. Refactoring Steps (The "Spec-First" TDD Loop)

**Mandatory Workflow for Every Feature:**
1.  **Spec**: Write a "Behavioral Spec" (Gherkin/English) defining inputs, constraints, and success criteria. **(User Approval Required)**.
2.  **Test**: Write failing tests based *only* on the Spec.
3.  **Impl**: Write code to pass the tests.

### Step 1: Package Structure
*   Create `pyproject.toml` (poetry).
*   Define dependencies: `pydantic`, `jinja2`, `typer` (CLI).

### Step 2: The Domain Model (Status Parsing)
*   **Spec**: Define the exact grammar of a "Valid Status File" and "Invalid Edge Cases" (Unicode, Locks).
*   **Test**: `tests/unit/domain/test_status_document.py`
    *   Case: `parse_simple_status`
    *   Case: `parse_nested_status`
    *   Case: `round_trip_safety` (Parse -> Save -> Parse = Identical)
*   **Impl**: `src/domain/status.py` using a proper recursive parser (no regex hacks).

### Step 3: The Engine Shell
*   **Spec**: Define the "Atom Lifecycle" and "Failure Modes" (Crash vs Swallow).
*   **Test**: `tests/unit/engine/test_executor.py` (Mocked atoms).
*   **Impl**: `src/engine/core.py`.

---

## 3. Verification Plan

### 3.1 Automated Tests
*   **Unit**: `pytest tests/unit/domain` (Target: 100% Coverage for Domain Model).
*   **Integration**: `pytest tests/integration/v_next` (Verify Atom wiring).
*   **E2E**: `pytest tests/e2e` (The "Fresh Install" scenario).

### 3.2 Manual Verification
1.  Run `flow --v-next init` in a temp folder.
2.  Verify `status.md` is created.
3.  Add a task manually to `status.md`.
4.  Run `flow --v-next start` and verify it picks up the task.

4.  Run `flow --v-next start` and verify it picks up the task.

### 3.3 Critical Test Gaps (Must Cover in V-Next)
**The "Junior Mistakes" we must fix:**
1.  **Parser Edge Cases**:
    *   Malformed Markdown (missing spaces, bad indentation).
    *   Unicode/Emoji support in task names.
    *   Concurrency (File locking on `status.md`).
2.  **Engine Resilience**:
    *   **Atom Failure**: Verify state persistence *before* crash.
    *   **Context Isolation**: Ensure atoms cannot overwrite system variables (`config.root`).
    *   **Infinite Loops**: Cycle detection in workflow graph.
3.  **Expert Logic**:
    *   **Conflict Resolution**: Logic for disparate expert opinions (currently missing).
    *   **Resumption**: Verify starting at Expert N, not Expert 1, on resume.
    *   **Config Integrity**: Fail fast if `core_teams.json` references missing personas.

### 3.4 AI Provider Abstraction (Future-Proofing)
**Goal**: The core engine must be **AI Agnostic**. It must not know it is running on "Antigravity" or "Gemini".
**Strategy**: **Port & Adapter Pattern**
*   **Core Interface**: `src/ports/ai_provider.py`
    *   `generate_completion(prompt, context) -> str`
    *   `count_tokens(text) -> int`
*   **Adapters**:
    *   `src/adapters/antigravity_adapter.py` (Default: usage of `google.generativeai` or IDE bridge).
    *   `src/adapters/openai_adapter.py` (Future stub).
    *   `src/adapters/anthropic_adapter.py` (Future stub).
*   **Configuration**: `.flow/config.json` selects the active provider.
    *   `"provider": "antigravity"` (Default)
    *   `"provider": "openai", "api_key_env": "OPENAI_API_KEY"`

### 3.5 Paranoid Security & Architectural Risks (The "Phobic" Review)
**Goal**: Assume the LLM is malicious or hallucinating. Assume the user has sensitive data nearby.

**1. File System "Jail" (Microservice Isolation)**
*   **Context**: Monorepo structure is `<Service>/src`, `<Service>/test`.
*   **Requirement**: "Service Separation". `Service A` must NOT touch `Service B`.
*   **Implementation**: 
    *   **Write Scope**: Strictly limited to `{Current_Service}/*` and `.flow/*` (for task tracking).
    *   **Read-Only**: `Shared/Contracts/` (or equivalent shared API definitions).
    *   **Blocked**: All other `{Other_Service}/*` directories.
    *   **Import Isolation**: 
        *   When running tests/code for Service A, `PYTHONPATH` must include **only** `{Current_Service}/src` and `Shared/`.
        *   Strictly exclude root or other service paths to prevent accidental cross-imports.

**2. Command Injection (Manifest-Driven Permissions)**
*   **Requirement**: "No clicking 'Allow' for every `ls` command".
*   **Strategy**: **Capability-Based Security**.
    *   **Manifest**: The Workflow/Atom declares its needs: `requires: ["pytest", "git_read"]`.
    *   **Policy**: The System Config (`.flow/config.json`) defines the "Trusted Toolset".
    *   **Execution**: If a workflow requests a trusted tool, it runs automatically. If it requests `rm` or `curl` (untrusted), it block/prompts.
    *   **No Shell**: Use `subprocess.run(shell=False)` always.

**3. Secret Leaking (Log Hygiene)**
*   **Risk**: LLM hallucinates `print(os.environ)` or logs contain API keys.
*   **Mitigation**:
    *   **Redactor**: A stream filter that replaces patterns (sk-..., gh-...) with `[REDACTED]` in all logs/outputs.
    *   **No Env Dump**: Never log the full environment variables.

**4. Context Poisoning (Prompt-Driven State)**
*   **Requirement**: "All information must be provided as prompt".
*   **Mitigation**:
    *   **Zero Global State**: The engine instance is created fresh for every run.
    *   **Just-In-Time Loading**: Only files relevant to the current `Service A` task are read into context.
    *   **Ephemeral Cache**: `ctx` object is destroyed after execution.

**5. Dependency Supply Chain**
*   **Risk**: `pip install flow-manager` pulls in a compromised transitive dependency.
*   **Mitigation**:
    *   **Lockfile**: Commit `poetry.lock`.
    *   **Minimal Deps**: Reject heavy frameworks. Use standard library where possible.
