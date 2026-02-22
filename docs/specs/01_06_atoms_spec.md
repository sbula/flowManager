# 01_07 Atoms Specification

> **Status**: DRAFT
> **Owner**: Architecture Team
> **Context**: Definition of the smallest units of execution in Flow Manager.

## 1. Overview
**Atoms** are the fundamental, indivisible units of work in the Flow Manager ecosystem. Unlike "Tools" (which are passive utilities) or "Agents" (which are autonomous loops), an Atom is a **discrete, deterministic execution block** that performs a specific action and returns a structured result.

**Key Characteristics:**
1.  **Stateless**: Atoms do not maintain internal state between runs.
2.  **Composable**: Atoms can be chained together in Flows.
3.  **Isolated**: Atoms handle their own error boundaries and side effects.
4.  **Typed**: Atoms have strict Input/Output schemas.

---

## 2. The Protocol (`Atom`)
Located at: `flow.engine.atoms.Atom`

All Atoms must inherit from this ABC.

```python
class Atom(ABC):
    @abstractmethod
    def run(self, context: Dict[str, Any], **kwargs) -> AtomResult:
        """
        Executes the atomic unit of work.
        Args:
            context: The shared Flow Context (read-only recommended).
            **kwargs: Atom-specific arguments defined in the Flow.
        Returns:
            AtomResult(success=bool, message=str, exports=Dict)
        """
        pass
```

### 2.1 The Result Contract (`AtomResult`)

```python
class AtomResult:
    success: bool      # Did the action succeed?
    message: str       # Human-readable summary (for logs/status).
    exports: Dict      # Data to write back to the Flow Context.
```

---

## 3. Standard Atoms

### 3.1 `LoomAtom` (Surgical Editing)
*   **Purpose**: Applying precise code edits based on a manifest.
*   **Inputs**: `ref` (Path to JSON operation definition).
*   **Behavior**:
    1.  Reads the JSON op (`insert`, `replace`, `delete`).
    2.  Invokes the Loom engine.
    3.  Verifies the edit (Optimistic Locking).

### 3.2 `RagRetrievalAtom` (Knowledge)
*   **Purpose**: Querying the Knowledge Base.
*   **Inputs**: `query` (str), `profile` (str).
*   **Behavior**:
    1.  Initializes `KnowledgeService`.
    2.  Routes query to `LLMGateway`.
    3.  Returns `{ "answer": "...", "sources": [...] }`.

### 3.3 `AgentAtom` (The "Brain")
*   **Purpose**: The execution unit for an "Agent". It binds an LLM (via `LLMFactory`) with a Persona and Skills.
*   **Inputs**: `prompt` (str), `persona` (str), `allowed_skills` (list).
*   **Behavior (ReAct Loop)**:
    1.  **Context**: Loads the `Persona` system prompt.
    2.  **Reasoning**: Sends prompt + tool definitions to LLM.
    3.  **Action**: If LLM requests a tool call, the Atom executes the corresponding `Skill` or `Tool`.
    4.  **Loop**: Feeds result back to LLM until final answer is generated.
    5.  **Output**: Returns the final response.

**Note**: In this architecture, an **Agent is an Atom**. It is a discrete step in a Flow that possesses "agency" (tool use).

### 3.4 `ManualInterventionAtom` (Human in the Loop)
*   **Purpose**: Pausing execution for user input/verification.
*   **Behavior**:
    1.  Halts the Flow.
    2.  Updates Status to "WAITING".
    3.  Requires user signal to resume.

---

## 4. Lifecycle & Error Handling

1.  **Instantiation**: The Engine instantiates Atoms dynamically based on the Flow definition.
2.  **Execution**: `run()` is called within a `try/catch` block.
3.  **Failure**:
    *   If `AtomResult.success == False`, the Engine checks the Flow's `on_failure` policy.
    *   **Retry**: Specific Atoms may request retries (e.g., transient network errors).
    *   **Halt**: Critical failures stop the Flow.

---

## 5. Security Context
Atoms operate within the `Flow Sandbox`.
*   **File Access**: Restricted by `SafePath` validation (no `../` escapes).
*   **Network Access**: Monitored and restricted (e.g., only whitelisted APIs).
*   **Secrets**: Accessed only via environment variables or sanitized context injection.
