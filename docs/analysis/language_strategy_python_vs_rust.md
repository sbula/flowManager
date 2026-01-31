# Language Strategy: Python vs. Rust for Flow Manager V-Next

## Executive Summary
The Flow Manager is a "High-Assurance Orchestrator". Its job is to be the stable foundation for AI Agents. If the foundation cracks (runtime errors), the agents fall.

**Recommendation**: **Stick to Python for V-Next (Phase 1)** to stabilize the *Domain Model* and *Protocols*. Shift to **Rust for V-Next (Phase 2)** once the architecture is proven.

---

## 1. The Comparison

| Feature | Python (Current) | Rust (Candidate) | Impact |
| :--- | :--- | :--- | :--- |
| **Iteration Speed** | 🚀 **High**. Dynamic types allow rapid prototyping of new agent patterns. | 🐢 **Medium**. Compile times and strict typing slow down "exploratory" coding. | Python wins for *Design Phase*. |
| **Reliability** | ⚠️ **Low**. Runtime Type Errors (`NoneType`), messy deps (`pip`). | 🛡️ **Critical**. "If it compiles, it works". No runtime crashes. | Rust wins for *Production*. |
| **Deployment** | ❌ **Messy**. Requires venv, python executable, strict paths. | ✅ **Perfect**. Single static binary. Drop anywhere. | Rust wins for *Ops*. |
| **Ecosystem** | 🌟 **Native**. Jinja2, LangChain, rich LLM tooling. | ⚠️ **Good**. Tera (Jinja clone) exists, but LLM libs are younger. | Python wins for *Integration*. |
| **Text Processing** | 😐 **Good**. Regex is slow but easy. | ⚡ **Best**. Zero-copy string parsing (Nom/Pest). | Rust wins for *Parsing*. |

## 2. The Case for Rust (Why switch?)
The Flow Manager has reached a complexity where Python's looseness is hurting us.
1.  **Orchestrator Stability**: A crash in `expert_sequencer.py` after 30 minutes of agent work is unacceptable. Rust guarantees memory safety and error handling (Result<T, E>).
2.  **Deployment**: Users just want `flow build`. They don't want `poetry install && source .venv/bin/activate`.
3.  **Concurrency**: Rust's async/await is perfect for running 5 Agents in parallel without the GIL.

## 3. The Case for Waiting (Why not now?)
We are currently in a **Design Restructuring** phase.
*   We are still inventing the "Fractal Domain Model" (Task/Status/Workflow objects).
*   If we switch to Rust *now*, we will fight the *Borrow Checker* while trying to figure out the *Architecture*. This is "Fighting on two fronts".
*   Refactoring a Python class is 5 minutes. Refactoring a Rust Crate structure is 2 hours.

## 4. The "Strangle Pattern" Roadmap

We should treat Python as the **"Reference Implementation"** and Rust as the **"Production Engine"**.

### Phase 1: The "Clean Python" (Now)
*   **Goal**: Define the *Interface* and *Domain Logic*.
*   **Action**: Rewrite `workflow_core` in strict, typed Python (Pydantic).
*   **Why**: It forces us to define the *Schemas* (JSON/YAML) that Rust will eventually deserialize.
*   *Duration*: 1-2 weeks.

### Phase 2: The "Rust Core" (Next)
*   **Goal**: Replace the Engine, keep the Config.
*   **Action**: Write a Rust CLI that reads the *exact same* Configuration/Status files we defined in Phase 1.
*   **Transition**:
    1.  `flow-py status` (Python) -> Validates logic.
    2.  `flow-rs status` (Rust) -> Replaces it.
    3.  `flow-rs run` (Rust) -> Takes over execution.

## 5. Decision Matrix

**Do Implementation First in Python?**
✅ **YES**.
*   **Reason**: You are still discovering the "V-Next" requirements (e.g., Fractal Status). Doing this discovery in Rust is expensive.
*   **Risk**: If we write "Bad Python" again, we gain nothing.
*   **Mitigation**: We must write **"Rust-like Python"**.
    *   Use `Pydantic` for strict schemas.
    *   Use `Result` patterns instead of Exceptions.
    *   Zero global state.

**When to switch?**
*   **Trigger**: When the *Specification* (Protocols/01-05) is implemented and stable in Python.
*   When we stop changing the *Architectural Design* and start optimizing for *Reliability*.

## 6. Conclusion
**Battle-test the Logic in Python. Enforce the Architecture in Rust.**

Start V-Next in Python today. But write it as a *Specification for the future Rust rewrite*.
