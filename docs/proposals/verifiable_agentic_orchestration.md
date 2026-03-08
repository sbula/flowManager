# Proposal: Verifiable Agentic Orchestration

> **Status**: DRAFT  
> **Author**: System Architecture  
> **Date**: 2026-03-06  
> **Context**: This document distills complex "Astronaut Architecture" concepts into pragmatic, actionable strategies for `flowManager`. It refines the "Verifiable Agentic Operating System" vision to align tightly with our `01_08` Flows framework, incorporating the core strengths of the recent architectural review and the essential clarification of the top-down fractal RAG approach.

---

## 1. The "Steel Thread" Integration (Execution First)

**The Concept:** Avoid building infrastructure (like SQLite state persistence or advanced telemetry) until the core recursive execution engine is unequivocally proven.
**The Action:** Build a minimalist "Execution Skeleton." Implement a `Flow -> Sub-Flow -> Atom` stack (at least 3 levels deep). Provide it with an in-memory or raw JSON state context. 
**Why it matters:** If the engine can sequentially execute, dive into a sub-flow, pass variables down, modify the JSON state, and surface the output back up to the parent flow successfully, the core recursive logic is solved. Only *after* this instruction cycle is bulletproof should the durable database layer be wired in.

## 2. Macro-Context RAG (The "Top-Down Fractal" View)

**The Concept:** Agents suffer from "Contextual Blindness." If you give an agent a single Python file, it might optimize it perfectly while breaking the broader feature it belongs to, because it lacks macro architectural intuition.
**The Refined Action:** We do *not* burden the system with exhaustive, micro-level YAML metadata for every function. Instead, our RAG strategy indexes the **APIs, abstract service definitions, and high-level system architectural descriptions**.
*   **How it works:** When an agent is assigned to work on Microservice A, the RAG provides the detailed internal classes of A, but *only* the abstract descriptions and top-level APIs of Microservice B. 
*   **The Benefit:** The agent grasps the "Top-Down Fractal" landscape. If the agent realizes Class Z in Microservice B is related to its task, it can navigate the fractal hierarchy and explicitly request to "zoom in" to retrieve that specific class. This provides "Architectural Intuition" without blowing out the token context window or creating impossible maintenance overhead.

## 3. The "3-Line Pragma" (Deterministic Contracts)

**The Concept:** Prose is often too fuzzy for an LLM to strictly adhere to when reasoning about state changes. LLMs need to know the explicit *Intent* of a module and the *Rules* it must follow.
**The Action:** Every `Atom` and `Flow` should enforce a strict, minimalist docstring or YAML header comprising:
1.  **Intent:** What business value does this unit achieve?
2.  **Pre-conditions:** What must be true in the `FlowContext` before execution begins?
3.  **Post-conditions:** What state mutation is definitively guaranteed when execution ends?
**Why it matters:** This allows FlowManager to evaluate correctness *deterministically* using code assertions in the framework, rather than asking another LLM if the flow "looks right." If a Sub-Flow completes but its post-condition fails, the engine halts immediately, preventing silent cascading failures.

## 4. Deterministic Blast Radius (Locality Enforcement)

**The Concept:** "Collateral Damage" is a common failure mode where agents try to fix a bug but inadvertently reformat unrelated logic, prune neighboring imports, or modify sibling classes due to context bias.
**The Action:** Implement AST (Abstract Syntax Tree) Locality checks or strict `export` maps (introduced in `01_08`) for file modification tools. 
**How it works:** When an agent issues a `patch` tool call, the tool calculates the LOC (Lines of Code) locality. If the agent's authorized task is to modify the `calculateAlpha()` function, but the generated diff attempts to touch lines in the unrelated `saveToDatabase()` function, the tool categorically rejects the call: `"Error: Locality violation. You modified lines outside your assigned scope."`

## 5. The Anti-Lazy Test Protocol (Mutation Testing)

**The Concept:** LLMs frequently write "tautological" tests—tests that assert hardcoded mocks equal themselves, just to get a passing grade on the test suite without actually executing the logic.
**The Action:** Introduce Mutation Testing (e.g., `pitest`, `cargo-mutants`, `mutmut`) as a first-class Verification Gate Atom.
**How it works:** When an agent writes implementation code and unit tests, the `MutationTestAtom` injects small logic bugs (operator swaps, boundary shifts) into the diff. If the agent's tests pass anyway (failing to catch the mutant), the test suite is flagged as fraudulent, and the execution step fails. This is a deterministic, math-based guardrail that requires zero extra LLM inference overhead.

## 6. Cross-Model Shadow Reviewers

**The Concept:** Relying on the same model to formulate and review its own code leads to "Collaborative Hallucination." The model will justify its own mistakes because its chat history contains its native rationalizations.
**The Action:** Utilize the natural execution isolation of `01_08` Flows to chain different Expert Personas safely.
*   **Step 1:** The `CodingAtom` runs using Persona *Claude-Sonnet* and outputs a git diff to the `FlowContext`.
*   **Step 2:** The `ReviewAtom` runs using Persona *Gemini-Pro*. It receives *only* the diff and the original requirements, with none of the preceding chat history.
**Why it matters:** This native workflow sequencing gives us a "Blind Auditor" for free. It enforces architectural integrity through genuine independence and fresh context windows.

---

### Conclusion

These refined strategies shift the burden of verification away from expensive, non-deterministic "LLMs checking LLMs" and heavily toward **deterministic code checking LLMs** (Locality Enforcements, Pre/Post Assertions, Mutation Testing). This approach pairs perfectly with the recursive, state-managed sequencing primitives already defined in the `01_08` specification, paving the way for a highly verifiable Agentic Operating System.
