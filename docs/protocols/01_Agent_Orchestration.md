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
