# Flow Manager V2: deep_specification.md

## 1. The Data Plane: The Lifecycle of a Plan

The **Development Plan** is not just a text file; it is the **State Object** for the entire lifecycle of a task. It allows the system to be stateless between runs because all necessary state is serialized into the document itself.

### 1.1 The Interconnected Data Model

The Plan Document (YAML Frontmatter) drives the entire engine. Here is how the sections connect and drive logic:

```yaml
---
# 1. METADATA: The "Driver" (Read-Only by Agents, Managed by Engine)
plan_metadata:
  task_id: "4.3.2"        # -> Used by Manifest_Parse to determine depth (L4)
  planning_level: 4       # -> Selects Template "plan_l4.j2"
  status: "DRAFT"         # -> State Machine Transition Guard (e.g., Only DRAFT can be REVIEWED)
  parent_plan: "../..."   # -> Context_Gather reads this file to inject "Parent Intent"

# 2. CONTEXT: The "Input" (Injected into Triage Agent & Prompts)
context:
  phase: "Phase 5"             # -> Prompt: "You are working in Phase 5..."
  service: "Market Data"       # -> RAG Filter: `service == 'Market Data'`
  expert_set: "AlphaSquad"     # -> Triage Agent Hint: "Prefer experts from AlphaSquad"
  constraints: ["Low Latency"] # -> Triage Agent: "Add 'Performance' capability requirement"

# 3. TRACKING: The "Write-Back Log" (Updated by Execution Engine)
tracking:
  current_iteration: 1
  agents:
    - role: "Quant_Dev"     # -> Engine knows this role was assigned
      status: "COMPLETED"   # -> Engine skips this agent on retry
      output_ref: "tmp/..." # -> Synthesis Agent reads from here
---
```

### 1.2 Data Flow Cycle

1.  **Initialization**:
    *   **Input**: `status.md` line `4.3.2 Impl: MACD`.
    *   **Action**: `Manifest_Parse` atom creates the YAML skeleton.
    *   **Logic**: Parses `4.3.2` -> Level 4. Finds parent folder -> Sets `parent_plan`.
    *   **Result**: A file on disk with `plan_metadata` and `context` populated, `tracking` empty.

2.  **Execution (Read)**:
    *   **Input**: The YAML file.
    *   **Action**: Engine reads `context` to hydrate the `{{ context }}` variable in prompts.
    *   **Action**: Engine reads `tracking` to determine *resume* vs *start*.

3.  **Completion (Write-Back)**:
    *   **Input**: Agent Output (Markdown).
    *   **Action**: `Trans_Write` atom appends the Markdown to the body.
    *   **Action**: `Update_State` atom updates `tracking.agents` to mark specific roles as `COMPLETED`.

---

## 2. The Agent Plane: Triage & Execution

The **Triage Agent** is the dynamic configuration engine. It removes the need for hardcoded expert lists.

### 2.1 The Triage Agent

**Role**: "The Manager who assigns the work."
**Input**:
*   `Task Name`: "Implement MACD Strategy"
*   `Context`: "Market Data Service, Low Latency"
*   `Available Capabilities`: List of all registered expert capabilities.

**Process (The Logic)**:
1.  **Analyze Complexity**: Is this a simple docs update or a complex algorithm?
2.  **Select Capabilities**: "Needs `python`, `statistics` (for MACD), `rust` (for performance)."
3.  **Match Experts**: Queries `expert_registry.yaml` for best fit.
4.  **Routing**: Decides `execution_mode` (Parallel vs Sequential).

**Output Payload (JSON)**:
```json
{
  "complexity": "HIGH",
  "recommended_model": "gemini-1.5-pro",
  "execution_strategy": "parallel_blind",
  "selected_experts": [
    {
      "role_id": "quant_dev",
      "reason": "MACD requires statistical validation",
      "focus_directives": ["Check for look-ahead bias"]
    },
    {
      "role_id": "rust_engineer",
      "reason": "Implementation target is Rust",
      "focus_directives": ["Ensure zero-copy deserialization"]
    }
  ]
}
```

### 2.2 Using the Triage Output

The output above is **NOT** just for logging. It is the **Configuration Object** for the next step in the workflow:

```json
// workflow_definition.json
{
  "steps": [
    {
      "id": "triage",
      "atom": "Triage_Agent",
      "export_to": "triage_result" // Saves JSON to flow state
    },
    {
      "id": "execute",
      "atom": "Multi_Agent_Parallel",
      "input_config": "${triage_result}" // <--- DYNAMIC CONFIGURATION
    }
  ]
}
```

**The `Multi_Agent_Parallel` Atom Logic**:
1.  Reads `${triage_result}`.
2.  Iterates `selected_experts`.
3.  For each expert, spawns a job:
    *   **Load Persona**: From `experts.yaml` using `role_id`.
    *   **Inject Directive**: Adds `focus_directives` to the system prompt.
    *   **Execute**: Runs the agent in isolation.

---

## 3. The Execution Plane: Step-by-Step Implementation

How do we actually code this? Here is the flow.

### 3.1 Step 1: `Manifest_Parse` (The Bootloader)

**Code Logic**:
```python
def execute(status_file_path):
    # 1. Find active task in status.md
    task_line = find_active_task(status_file_path) # "- [ ] 4.3.2 ..."
    
    # 2. Derive Metadata
    task_id = extract_id(task_line) # "4.3.2"
    level = len(task_id.split('.')) # 3 dots = Level 4
    
    # 3. Derive Context (Walk up the indentation tree)
    parents = get_parent_hierarchy(task_line)
    service = parents[1].name # e.g., "Market Data"
    
    # 4. Construct YAML
    metadata = {
        "task_id": task_id,
        "planning_level": level,
        "parent_plan": f"file://{parents[-1].path}"
    }
    
    return {"plan_metadata": metadata, "context": {"service": service}}
```

### 3.2 Step 2: `RAG_Context_Gather` (The Librarian)

**Code Logic**:
```python
def execute(query, context, filters):
    # 1. Build Search Filters
    db_filters = {"service": context['service']}
    
    # 2. HyDE (Hypothetical Document Embeddings) Optimization
    # Ask LLM: "What would the code for 'MACD Implementation' look like?"
    hypothetical_code = llm.generate(f"Write a placeholder for {query}")
    
    # 3. Vector Search
    # Search for code similar to the *hypothetical* code, not just the query keywords
    results = chroma_db.query(
        embedding=embed(hypothetical_code),
        where=db_filters,
        n_results=5
    )
    
    return {"rag_context": format_results(results)}
```

### 3.3 Step 3: `Trans_Write` (The Safe Writer)

**Code Logic**:
```python
def execute(target_path, content, tracking_update):
    # 1. Write to Temp
    temp_path = f"tmp/session/{target_path}"
    write_file(temp_path, content)
    
    # 2. Update Tracking (In Memory)
    # We must inject the tracking update into the YAML Frontmatter BEFORE writing
    final_content = inject_yaml_tracking(content, tracking_update)
    
    # 3. Validation Gate
    if not validate_yaml_schema(final_content):
        raise ValidationError("Agent corrupted the YAML frontmatter!")
    
    # 4. Commit
    move_file(temp_path, target_path)
    return {"status": "SUCCESS"}
```

---

## 4. Addressing "Open Questions"

### Q: How are files physically organized?
**A:**
```
project_root/
├── .flow/                  # Engine Internal State
│   ├── experts.yaml        # The Registry
│   ├── state.json          # Current Resume Checkpoint
│   └── workflows/          # JSON Definitions
├── docs/
│   └── phase_5/            # User Content
│       └── 4_3_Market/
│           ├── planning.md # L2 Plan
│           └── 4.3.2.md    # L4 Plan (The YAML+MD file)
└── tmp/
    └── session_123/        # Transactional Workspace
        ├── mailbox/        # Agent Outputs
        └── workspace/      # Draft Files
```

### Q: What exactly IS the Triage Agent prompt?
**A:**
```text
SYSTEM: You are the Workflow Manager.
INPUT:
  Task: {{ task_name }}
  Context: {{ context }}
  Available Experts: {{ registry_dump }}

INSTRUCTIONS:
1. Analyze task complexity (LOW/MED/HIGH).
2. Select 1-3 experts who possess the necessary capabilities.
3. For each expert, write a specific "Focus Directive" (what they should look for).
4. Output JSON only.

EXAMPLE OUTPUT:
{ "selected_experts": [ { "role_id": "quant", "focus": "Check math" } ] }
```

### Q: How does the system handle an agent failing?
**A:**
1.  `Multi_Agent_Parallel` atom catches the exception.
2.  It logs the failure to `flow_state.json`.
3.  It updates the `tracking` section of the Plan Document: `status: FAILED`.
4.  The engine halts (or retries if configured).
5.  On Resume: The engine reads `tracking`, sees `FAILED`, and only re-runs that specific agent (because others are marked `COMPLETED` in `tracking`).

This document provides the specific mechanical linkages between data, agents, and execution that were missing. It defines the implementation logic for the critical path components.