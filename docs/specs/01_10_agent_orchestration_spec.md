# 01. Agent Orchestration Mechanics

## Overview
The Flow Manager does not use "Prompt Engineering" in the traditional sense. It uses **Structured Context Injection**. The behavior of an Agent is the product of three variables:
1.  **Identity** (Immutable Persona)
2.  **Context** (Just-in-Time Data)
3.  **Template** (Jinja2 Logic)

This document details the code path `Config -> Sequencer -> Context -> Jinja2 -> Agent`.

## 1. The Configuration Layer
The "Brain" of the orchestration is defined in two static JSON files.

### 1.1 Expert Personas (`workflow_core/config/expert_personas.json`)
Defines the **Immutable Identity** of an expert. Detailed definition of "WHO" they are, independent of "WHAT" they do.

*Example (Quant Dev)*:
```json
"Quant Dev": {
    "Focus": "correctness, numeric stability, corner cases",
    "Checklist": [
        "1. MATH: Is the formula correct?",
        "2. CORNER CASES: Are NaN, Inf, and Zero handled explicitly?"
    ]
}
```

### 1.2 Expert Sets (`workflow_core/config/core_teams.json`)
Defines **Teams** (Collections of Roles) mapped to specific business functions.

*Example (AlphaSquad)*:
```json
"AlphaSquad": [
    "Quantitative Trader",
    "Data Scientist",
    "ML Engineer",
    "Risk Officer"
]
```

## 2. The Sequencer Engine (`expert_sequencer.py`)
This Atom (`atoms/expert_sequencer.py`) acts as the Conductor. It does not "think"; it executes a deterministic loop.

### 2.1 Resolution Logic (`_resolve_experts`)
1.  **Input**: `expert_set` name (e.g., "AlphaSquad").
2.  **Lookup**: Reads `core_teams.json` to get the list of roles.
3.  **Filtering**: Removes the `author_role` (to prevent an expert from reviewing themselves).
4.  **Output**: A list of `Role` strings.

### 2.2 The Drafting Loop (Code Walkthrough)
When running in `mode='draft'`, the sequencer iterates through the resolved list:

```python
# expert_sequencer.py (Simplified)

for role in required_roles:
    # 1. Fetch Persona Config
    persona_data = personas_config.get(role, {})
    
    # 2. Construct Prompt Context
    prompt_ctx = {
        "role": role,
        "persona": persona_data,   # <--- The Full JSON object injected here
        "current_content": active_document_text
    }
    
    # 3. Render Template
    final_prompt = prompt.render_string(template_string, prompt_ctx)
    
    # 4. Execute Agent
    response = agent.query(final_prompt)
```

## 3. The Rendering Layer (`prompt.py`)
We use **Jinja2** to fuse the Context with the Template.

### 3.1 The Template Structure (`.j2`)
The template does not hardcode the expert's behavior. It iterates over the injected `persona` object.

*conceptual_template.j2*:
```jinja
You are a {{ role }}.
Your primary focus is: {{ persona.Focus }}

Review the following content based on your mandatory checklist:
{% for item in persona.Checklist %}
- {{ item }}
{% endfor %}

Content to Review:
{{ current_content }}
```

### 3.2 The Result
For a **Quant Dev**, the rendered prompt becomes:
> You are a Quant Dev.
> Your primary focus is: correctness, numeric stability, corner cases
> Review the following content...
> - 1. MATH: Is the formula correct?

For a **Product Owner**, the *same template* renders:
> You are a Product Owner.
> Your primary focus is: Value, Scope, Usability
> ...
> - 1. SCOPE CREEP: Does the Plan include features NOT in the original Task?

## 4. Key Takeaway
**We do not write prompts for experts.**
We write **Personas** (Data) and **Templates** (Logic). The System *generates* the prompt at runtime. This guarantees that a "Quant Dev" behaves consistently across Research, Implementation, and Review phases, because they are always instantiated from the same `expert_personas.json` source of truth.

---

## 5. Adversarial Review Phase

> **Full specification**: See [Agent Isolation Analysis §8](../analysis/agent_isolation.md)

After the standard synthesis phase, an optional **adversarial step** introduces a "Critic" agent that is *structurally forbidden from approving*. This counteracts LLM sycophancy (mode collapse toward agreement).

**Key properties:**
*   Output schema has NO "APPROVE" option — only structured issue lists
*   Configurable `min_issues_required` threshold
*   Clean Slate Protocol: critic has NO history of the collaborative discussion
*   Gated by task complexity: skipped for low, optional for medium, mandatory for high/critical

---

## 6. Rubric-Based Scoring

> **Full specification**: See [Agent Isolation Analysis §9](../analysis/agent_isolation.md)

Expert output includes self-assessment scores against a rubric with weighted dimensions:
*   **Completeness** — Are all deliverables present?
*   **Specificity** — Are findings grounded in file/line references?
*   **Actionability** — Can findings be acted on without clarification?
*   **Risk Identification** — Are non-obvious risks called out?

The Synthesis Agent validates scores against `min_threshold` per dimension. Below threshold → automatic loop back. After `max_loops` → Human-in-the-Loop escalation.

---

## 7. [PROPOSAL] IDE-Native Parallel Agent Execution (ADK Integration) / Dispatcher Pattern

To dramatically reduce execution time, prevent "lazy simulation," and avoid API costs when running locally, orchestration should leverage IDE-native parallel execution (like the Antigravity `Agent Development Kit (ADK)`).

**The Problem: Mode Collapse / Lazy Simulation**
If reviewers (e.g., SRE, Architect) run sequentially and share context, the latter agents tend to fall into "groupthink," mimicking the tone and agreeing with the previous expert rather than critically analyzing the code.

**The Solution: Parallel Blind Reviews (Dispatcher Pattern)**
Instead of a sequential loop or a custom Python threading solution, the orchestrator detects if it is running within an IDE context (e.g., Antigravity). If so, it acts as a "Dispatcher" and dispatches isolated "Sub-Agents" (e.g., Architect, SRE, Security) simultaneously via the native `ParallelAgent` class.
*   **Isolation (Clean Slate Protocol)**: IDE-native parallel agents receive copies of the prompt and share ZERO subsequent chat history. They physically cannot see each other's output during the generation phase.
*   **File-Based I/O**: Instead of outputting to a shared chat context, agents write their critiques to isolated temporary files (e.g., `.reviews/architect_review.md`).
*   **Cost**: Uses the IDE's authenticated active session (e.g., Gemini Ultra quota) rather than external API keys.
*   **Synthesis**: A final `Product Owner` (PO) or `Synthesis` Agent reads all the isolated review files, detects conflicts, and merges them into a final specification/document.

---

## 8. Model Parameter Overrides

> **Full specification**: See [Agent Isolation Analysis §10](../analysis/agent_isolation.md)

Expert personas may include `model_params` for per-role LLM configuration:

```yaml
model_params:
  temperature: 0.1  # Very low for analytical work
  top_p: 0.9
  top_k: 40
```

**Guidelines:**
| Role Category | Temperature |
|:---|:---|
| Analytical (QA, SRE, Quant) | 0.0 – 0.2 |
| Structural (Architect, Backend) | 0.2 – 0.4 |
| Creative (UI/UX, Product) | 0.4 – 0.7 |
| Adversarial (Critic) | 0.0 – 0.2 |

**Precedence**: Default → Persona → Expert Set (highest).

---

## 8. Evidence-Grounded Output

> **Full specification**: See [Agent Isolation Analysis §11](../analysis/agent_isolation.md)

Expert findings MUST include evidence citations with:
*   `file` — validated via SafePath
*   `line_start` / `line_end` — must be within actual file bounds
*   `snippet` — must match content at those lines

Ungrounded claims (severity ≥ MEDIUM without evidence) are downgraded in rubric scoring and flagged as "UNGROUNDED" by the synthesis agent.

