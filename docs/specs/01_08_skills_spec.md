# 01_08 Skills and Personas Specification

> **Status**: DRAFT
> **Owner**: Architecture Team
> **Context**: Defining the "Who" (Personas) and the "What" (Skills) of the Agentic System.

## 1. Overview
This specification decouples the **Identity** of an agent from its **Capabilities**.

*   **Persona**: Defines *who* the agent is (Role, Tone, Priorities, Ethics). It is the "Soft Configuration" of the LLM.
*   **Skill**: Defines *what* the agent can do. It is a package of specialized logic, tools, and workflows.

**LLM Agnosticism**:
Both Personas and Skills are defined in standard JSON/YAML. They are **projected** onto the specific LLM (Gemini, OpenAI, etc.) at runtime via the `LLMGateway`. The Core Engine handles the translation of a Skill's tools into the specific function-calling format of the provider.

---

## 2. Personas ("The Who")

A Persona is a named configuration that applies a specific **Lens** to the LLM's reasoning.

### 2.1 Schema (`expert_personas.json`)
```json
{
  "Senior Backend Developer": {
    "Description": "Expert in Python/clean code.",
    "SystemPrompt": "You are a Senior Backend Developer. Prioritize SOLID principles, error handling, and performance.",
    "Focus": ["Code Quality", "Maintainability"],
    "AllowedSkills": ["refactor_code", "write_unit_tests", "debug_error"],
    "AllowedTools": ["read_file", "search_file", "run_test", "git_commits"],
    "Checklist": [
      "Are all inputs validated?",
      "Is the cyclomatic complexity under control?"
    ]
  }
}
```

### 2.2 Usage
When a Flow Step requires an "Expert", the Engine:
1.  Loads the Persona definition.
2.  Injects the `SystemPrompt` into the LLM context.
3.  Injects the `Checklist` as a mandatory validation step.
4.  **Tool Projection**: Combines `AllowedSkills` (High-level) + `AllowedTools` (Low-level) into the LLM's toolset.

---

## 3. Toolset Primitives (from `01_04_tooling_spec.md`)

Skills are composed of (or orchestrate) these fundamental primitives. A Persona can also access them directly.

### 3.1 The Standard Library
*   **FileTool**: `read_file`, `write_file`, `edit_file` (Loom), `search_file`, `list_files`.
*   **ShellTool**: `run_test`, `run_lint`, `git_status`, `git_start_task` (Flow Manager Wrapper), `git_commit`.
*   **KnowledgeTool**: `search_knowledge` (RAG), `find_usage`, `get_task_context`.
*   **SystemTool** (SRE Only): `install_package`, `system_ctl`.

---

## 4. Skills ("The What")

A Skill is a portable unit of capability. It bridges the gap between high-level intent and low-level **Atoms**.

### 4.1 Architecture
```mermaid
graph LR
    A[Agent (Persona)] -->|Invokes| B[Skill]
    B -->|Orchestrates| C[Tools (01_04)]
    B -->|Orchestrates| D[Atoms (01_07)]
    B -->|Generic API| E[LLM Provider]
```

### 4.2 The Standard Skill Protocol
Each Skill must implement a standard definition that allows any LLM to understand and use it.

```python
class Skill(ABC):
    name: str = "refactor_code"
    description: str = "Safely refactors a file using AST-aware methods."
    
    # Dependencies (Tools used by this Skill)
    required_tools: List[str] = ["read_file", "edit_file", "run_test"]

    # The 'Tool Definition' exposed to the LLM
    parameters: dict = {
        "type": "object",
        "properties": {
            "target_file": {"type": "string"},
            "refactoring_type": {"type": "string", "enum": ["extract_method", "rename"]}
        }
    }

    def execute(self, context: Context, **kwargs) -> SkillResult:
        """
        The deterministic logic.
        Example:
        1. Parse file with tree-sitter.
        2. Identify code block.
        3. Use LoomAtom to apply change.
        """
        pass
```

### 4.3 Skill Categories
1.  **Reasoning Skills**: Pure cognitive tasks (e.g., `ArchitecturalReview`, `SecurityAudit`).
2.  **Action Skills**: Side-effect operations (e.g., `GitCommit`, `FileEdit`, `ShellRun`).
3.  **RAG Skills**: Knowledge retrieval (e.g., `ConsultDocumentation`, `SearchCodebase`).

---

## 5. Agnostic Binding Strategy

The Flow Manager uses the `LLMGateway` to translate Skills into the provider's native format.

**Scenario**: A "Backend Developer" Persona wants to use the `refactor_code` Skill.

1.  **Gemini**: Gateway converts `Skill.parameters` -> `genai.types.FunctionDeclaration`.
2.  **OpenAI**: Gateway converts `Skill.parameters` -> JSON Schema `tools` format.
3.  **Anthropic**: Gateway converts `Skill.parameters` -> Claude `tools` format.
4.  **Ollama**: Gateway converts `Skill.parameters` -> Modelfile/Template format.

**Result**: The Skill code is written ONCE (in Python). The LLM interaction is handled dynamically by the Gateway.

---

## 6. Implementation Roadmap

1.  **Registry**: Create `workflow_core/skills/` to house standard skill classes.
2.  **Migration**: Move legacy "Checklists" from `expert_personas.json` into the new Persona Schema.
3.  **Binding**: Update `LLMGateway` to accept a list of `Skill` objects and generate provider-specific tool definitions.
