# 01_08 Flows Specification

> **Status**: DRAFT
> **Owner**: Architecture Team
> **Context**: Definition of the orchestration logic (Workflows) that binds the system together.

## 1. Overview

**Flows** are linear sequences of **Atoms** and **Sub-Flows**. They define the lifecycle of a request, from user input to final result. **Sub-Flows** (Flows calling Flows) are the primary mechanism for **reusability** — a `TestVerification` flow can be composed into `ImplementFeature`, `FixBug`, and `Refactor` without duplication.

> [!NOTE]
> **Skills vs. Atoms in Flows**: Skills are consumed by **Agents** (via `AgentAtom`) during their reasoning loops — they are NOT direct flow step targets. When a flow needs cognitive work (planning, coding, analysis), it dispatches an `AgentAtom` configured with the appropriate Skill and Toolset. See `01_05` §3 and `01_07`.

> [!IMPORTANT]
> **Parallelism & Branching**: V1 Flows are strictly **linear sequences with sub-flow delegation**. True DAG parallelism (Fan-Out/Fan-In) and conditional branching (if/else steps) are deferred to V2 — see `roadmap_2026.md` Phase 2. Linear sequences + sub-flows cover >90% of use cases.

**Key Characteristics:**
1.  **Declarative**: Defined in JSON/YAML (Policy as Code).
2.  **Composable**: Flows invoke other Flows as reusable building blocks.
3.  **Stateful**: Flows maintain a `FlowContext` that persists across steps.
4.  **Resumable**: Execution can be paused (e.g., for human intervention) and resumed — including deep inside nested sub-flows.

---

## 2. The Flow Definition Schema

Flow definitions are stored in `.flow/flows/` (project-local) or in the Engine's built-in library.

> [!WARNING]
> **Deprecation**: The `workflow_core/config/workflows` directory is **DEPRECATED** (see `01_03` §H3). All new flow definitions MUST use the path above.

### 2.1 Schema Structure

```json
{
  "name": "ImplementFeature",
  "flow_version": "1.0.0",
  "description": "End-to-end feature implementation with planning, approval, and testing.",
  "input_schema": {
    "type": "object",
    "properties": {
      "task_description": {
        "type": "string",
        "description": "Human-readable description of the feature to implement."
      }
    },
    "required": ["task_description"],
    "additionalProperties": false
  },
  "steps": [
    {
      "id": "plan",
      "type": "atom",
      "target": "AgentAtom",
      "args": {
        "task_scope": "${input.task_description}",
        "skill": "PlanningSkill",
        "persona": "Architect"
      },
      "export": {
        "plan_output": "implementation_plan"
      },
      "on_failure": "halt"
    },
    {
      "id": "approve",
      "type": "atom",
      "target": "ManualInterventionAtom",
      "args": {
        "artifact": "${plan.implementation_plan}"
      },
      "on_failure": "halt"
    },
    {
      "id": "code",
      "type": "atom",
      "target": "AgentAtom",
      "args": {
        "task_scope": "${input.task_description}",
        "plan": "${plan.implementation_plan}",
        "skill": "CodingSkill",
        "persona": "Senior Backend Developer"
      },
      "export": {
        "changed_files": "changed_files"
      },
      "on_failure": "halt"
    },
    {
      "id": "test",
      "type": "flow",
      "target": "TestVerification",
      "target_version": "1.x",
      "args": {
        "test_dir": "${config.test_path}",
        "source_files": "${code.changed_files}"
      },
      "export": {
        "test_result": {
          "as": "verification_status",
          "required": true
        },
        "coverage": {
          "as": "coverage_pct"
        }
      },
      "on_failure": "retry",
      "max_retries": 2
    }
  ]
}
```

**Field Definitions:**

| Field | Required | Description |
|:---|:---:|:---|
| `name` | Yes | Unique flow identifier. |
| `flow_version` | Yes | Semantic version. Engine validates on resume (see §3.5). |
| `description` | Yes | Human-readable intent. |
| `input_schema` | Yes | **[B3 Fix]** Strict Pre-condition. JSON Schema definition of required input variables (see §2.5). Engine MUST validate parameters against this schema *before* acquiring locks or entering the first step. |
| `output_schema` | No | **[NEW]** JSON Schema definition of the flow's guaranteed output contract (see §2.6). If present, the Engine validates the flow's final exported context against this schema *after* all steps complete and *before* returning to the parent. |
| `steps` | Yes | Ordered list of step definitions. Non-empty (see §3.6). |
| `steps[].id` | Yes | Unique within this flow. Used for context variable namespacing. |
| `steps[].type` | Yes | `atom` or `flow`. Skills are NOT direct step targets — they are consumed by `AgentAtom` (see `01_05` §3). |
| `steps[].target` | Yes | Registry name of the Atom or Flow to invoke. MUST be static (no `${...}` interpolation allowed) to enable load-time validation. |
| `steps[].target_version`| If `type: flow` | Semantic version constraint for Sub-Flows. Supports two forms only: **exact** (`"1.0.0"` — exact match) or **major-pinned** (`"1.x"` — any `1.y.z` matches). No range operators, no npm/pip-style constraints. Prevents version drift on nested resume. **[Pre-Release Exclusion]**: Major-pinned matching (`1.x`) MUST exclude pre-release versions (e.g., `1.2.0-beta`, `1.0.0-rc.1`). Pre-release versions are only matched by exact version strings. This follows SemVer §11 — pre-release versions have lower precedence and indicate instability. Without this rule, a production parent flow pinned to `"1.x"` would silently pick up a `1.3.0-alpha` sub-flow definition, causing untested code to execute in a production pipeline. |
| `steps[].args` | No | Key-value map injected into the step's context. Supports `${var}` interpolation. |
| `steps[].export` | No | Export configuration map. See §2.3. |
| `steps[].timeout_seconds` | No | **[B1 Fix]** Explicit execution timeout per step in seconds. For `type: atom`, enforced via thread watchdog. For `type: flow`, enforced via isolated cancellation token (see §6.3) to prevent orchestrator process termination. |
| `steps[].on_failure` | No | Failure strategy: `halt` (default), `retry`, `ignore`, `catch`. See §3.3. **[B4 Fix]** For `type: flow`, `retry` **restarts the sub-flow from scratch** (clearing the child's call stack frame and generating a new Run ID). It does NOT resume from the last checkpoint. See §3.3 for full rationale. |
| `steps[].catch_rules` | If `catch` | Error-routing rules for `on_failure: catch`. See §3.3 for full schema and matching semantics. |
| `steps[].max_retries` | No | Max retry attempts when `on_failure: retry`. Default: 3 (per `01_03` §3.1). Subject to `total_retry_budget` (§3.3.1). |

### 2.2 Context Variable Injection

Flows support dynamic variable injection using `${namespace.key}` syntax.
*   `${input.query}`: User input passed at flow invocation.
*   `${plan.implementation_plan}`: Result exported by step `plan`.
*   `${config.model}`: System configuration.

**Resolution Rules**:
1.  The Engine resolves all `${...}` placeholders *before* dispatching to the Atom or Sub-Flow.
2.  If a **strict** reference `${var}` cannot be resolved, an immediate `PreconditionFailed` / `SchemaError` MUST be raised, halting the step. The raw placeholder MUST NOT be preserved as a literal string (poison pill schema violation). **[CRITICAL FIX] Optional Reference Syntax (`${?var}`)**: The Variable Resolver MUST also support the optional reference syntax `${?var}`. When the Resolver encounters `${?var}` and the referenced key does not exist in the context (e.g., because the producing step was `SKIPPED` via `on_failure: ignore`), it MUST inject `null` (JSON) / `None` (Python) instead of raising `PreconditionFailed`. The standard `${var}` syntax retains the strict fail behavior. This rule is the resolver-level implementation of the `on_failure: ignore` optional reference handling defined in §3.3. Without this rule documented here, an implementer building the Variable Resolver from §2.2 alone will treat `${?var}` as an invalid identifier character (`?`) and either crash with a parse error or silently strip the `?` — causing every optional reference to either fail silently or behave identically to a strict reference, making `on_failure: ignore` non-functional for any step with downstream consumers.
3.  Resolution uses dot-notation for nested lookups (e.g., `${config.llm.model}`).
4.  **[U2 Fix] Blob Pointer Hydration**: The Variable Resolver MUST seamlessly intercept blob references (e.g., `{"ref": "blob_{uuid}.json", "type": "blob_ref"}`). If a resolved value is a blob pointer, the resolver MUST read the blob from disk and inject the **deserialized** value into the step's `args` at runtime. The target Atom/Sub-Flow remains completely ignorant of the underlying artifact blobbing mechanism. **[Hydration ↔ Type-Preservation Resolution]**: If the blob file contains valid JSON, the resolver MUST `json.loads()` its content and inject the resulting typed value (dict, list, int, etc.) — NOT the raw JSON string. If the blob file is NOT valid JSON, the content is injected as a plain string. This ensures blob hydration and type-preserving injection (rule 6) never conflict: both paths produce typed values for single-placeholder substitution. **[Blob Path Traversal Guard]**: Before reading any blob file, the Variable Resolver MUST validate that the `ref` path resolves strictly within `.flow/artifacts/` using `SafePath` (per `01_04` §3.3). A `ref` value pointing outside `.flow/artifacts/` (e.g., `{"ref": "../../.env", "type": "blob_ref"}`) is a path traversal attack. The resolver MUST reject it with `ContextHydrationError("Blob ref resolves outside .flow/artifacts/. Rejected.")` and mark the step `FAILED`. This is consistent with the identical guard in `01_07` §8.4.
5.  **[M1 Fix] Hydration Failure**: If a dehydrated blob pointer points to a file that no longer exists (e.g., deleted by an OS-level cleanup script or disk error), hydration fails. The Variable Resolver MUST catch the underlying `FileNotFoundError` and raise a managed `ContextHydrationError`. The Engine marks the step `FAILED` rather than crashing the Orchestrator loop.
6.  **[B5 Fix] Type-Preserving Injection**: If a JSON string value consists *entirely* of a single placeholder (e.g., `"count": "${config.max_items}"`), the Variable Resolver MUST substitute the *raw typed value* (integer, boolean, array, object) into the AST, rather than casting it to a string. String casting MUST ONLY occur if the placeholder is embedded within other text (e.g., `"file_${id}.json"`). This prevents `jsonschema` strict validation failures when passing non-string variables across Sub-Flow boundaries. **Ordering Note**: Type-preserving injection (this rule) applies AFTER blob hydration (rule 4). By the time a value reaches this rule, blob pointers have already been resolved to their deserialized typed content.

### 2.3 Export Configuration

The `export` block supports detailed mapping to handle missing data and ignore scenarios.

```json
"export": {
  "child_key": "parent_key_simple",
  "critical_child_key": {
    "as": "parent_key_complex",
    "required": true
  }
}
```

*   **Simple Map**: `"child_key": "parent_key"` behaves identically to `"required": false`, using the `fail` strategy.
*   **Required Flags**: If `required: true`, the Engine MUST raise a `SchemaError` and mark the step `FAILED` if the child finishes (or is skipped via `on_failure: ignore`) without providing `child_key`. This prevents silent data loss from crippling downstream steps.
*   **[B1 Fix] Merge Strategies (`merge_strategy`)**: For advanced mapping (e.g., aggregating results from a recursive or looping Sub-Flow), the `export` object accepts a `merge_strategy` field:
    *   `fail` (default): If the parent key already exists, raise `SchemaError`. Forces explicit intent on overwrites.
    *   `overwrite`: Last write wins. Replaces the parent key entirely. Must be explicitly chosen.
    *   `append_to_list`: If the parent key exists and is a list, the child value is appended to it. If it doesn't exist, it creates a list. If it exists but is not a list, it raises a `SchemaError`.
    *   `deep_merge`: If both parent and child values are dictionaries, they are recursively merged. Otherwise, throws `SchemaError`.

**Merge Strategy Scope Clarification**: Because step exports are namespaced by step `id` (§2.4), collisions between *different* steps do not occur (step A exports to `${A.key}`, step B to `${B.key}`). The `merge_strategy` primarily governs:
1.  **Same-step retry overwrites**: When a step retries and re-exports the same key, `merge_strategy` determines whether the retry's export replaces or fails against the previous attempt's export.
2.  **Sub-flow export mapping**: When a sub-flow's `export` map writes to a parent key that already exists from a prior step's export (e.g., two sub-flows both exporting to the same parent key `summary`).

### 2.4 Step ID Uniqueness & Scoping

*   Step `id` fields MUST be unique **within their flow**. Two different flows may each have a step named `validate` without conflict.
*   Context exports are namespaced to the step `id` that produced them. `${validate.result}` in Flow A refers to Flow A's `validate` step, not a sub-flow's.
*   Sub-flow internal step IDs are **invisible** to the parent. The parent only sees keys explicitly exposed via the `export` map.

### 2.5 Input Schema Validation

The `input_schema` field defines a JSON Schema specifying the required input variables for a flow. This serves as the **pre-condition contract** — a flow MUST NOT begin execution unless its inputs are valid.

**Validation Rules** (aligned with `01_07` §5.2):
1.  **Schema format**: MUST be a valid JSON Schema (Draft 7). The Engine validates using `jsonschema.Draft7Validator.check_schema()` at load time.
2.  **Top-level type**: MUST be `"object"` with `"additionalProperties": false`. Degenerate schemas (`{}`, `{"type": "string"}`) are rejected with `SchemaError`.
3.  **Load-time validation**: The Engine validates the `input_schema` itself at flow load time (is the schema well-formed?).
4.  **Invocation-time validation**: The Engine validates the provided `args` against the `input_schema` at invocation time — both for root flows (CLI `args`) and sub-flows (parent step's `args`). Failure raises `PreconditionFailed` before any step executes.
5.  **Sub-flow contract**: When a parent invokes a sub-flow, the parent's resolved `args` are validated against the child flow's `input_schema`. This makes sub-flows **strict typed functions**: schema in → exports out.

### 2.6 Output Schema Validation (Post-Condition Contract)

The optional `output_schema` field defines a JSON Schema specifying the **guaranteed output contract** of a flow. This is the post-condition dual of `input_schema` (§2.5).

**Why This Exists**: Without `output_schema`, sub-flow exports are structurally untyped. The `export` map (§2.3) controls *which* keys are exposed, but not *what type or shape* those values must have. A sub-flow can silently export `{"coverage": "not_a_number"}` when the parent expects an integer. The parent step's downstream logic fails at runtime with a cryptic type error — far from the source of the bug.

**Validation Rules:**
1.  **Schema format**: Same constraints as `input_schema` — valid JSON Schema (Draft 7), top-level `type: "object"`, `additionalProperties: false`.
2.  **Enforcement point**: After all steps in the flow have completed (or been `SKIPPED`), and *before* the Engine applies the `export` map to the parent context, the Engine MUST validate the flow's final `variables` snapshot against `output_schema`. **[C4 Fix] Dehydration Interaction**: The `output_schema` validation MUST run against the **pre-dehydration** `variables` snapshot — i.e., the snapshot must contain the actual typed values, not `blob_ref` pointers. This means the Engine MUST execute validation *before* the sub-flow export boundary dehydration (§3.2 rule 6). If validation ran after dehydration, a flow that correctly exports `{"coverage": 85}` (integer, matching `output_schema`) would be dehydrated to `{"coverage": {"ref": "blob_xxx.json", "type": "blob_ref"}}` — the `output_schema` validator would then see an object where an integer was expected and reject it with `OutputSchemaViolation`. The correct enforcement ordering is: (1) all steps complete → (2) `output_schema` validates `variables` → (3) auto-dehydration runs on export candidates → (4) `export` map applies to parent context. Without this ordering guarantee, any flow with large exports and a strict `output_schema` becomes non-functional — it passes during initial small-scale testing but fails in production when exports exceed `MAX_INLINE_SIZE` (8KB) and trigger dehydration.
3.  **Failure semantics**: If validation fails, the flow is marked `FAILED` with `OutputSchemaViolation` error code. The parent step's `on_failure` strategy applies. No partial exports leak to the parent.
4.  **Scope**: `output_schema` validates the flow's *own* context keys — not the parent-mapped names. The `export` map renames keys *after* `output_schema` validation passes.
5.  **Optional for V1**: Flows without `output_schema` behave exactly as today — no post-condition check. This preserves backward compatibility. However, the `flow validate --strict` command (§7) SHOULD warn when a sub-flow lacks `output_schema`, as it indicates a weak contract boundary.
6.  **[All-SKIPPED Flow Guard]**: If a flow reaches `COMPLETED` status with **all** steps in `SKIPPED` state (i.e., no step produced any exports), and an `output_schema` is defined with `required` properties, the Engine MUST fail the flow with `OutputSchemaViolation`. An all-SKIPPED flow inherently produces an empty `variables` snapshot, which cannot satisfy any non-trivial `output_schema`. Without this explicit guard, a flow where every step failed and was ignored via `on_failure: ignore` silently reaches `COMPLETED` and returns to the parent with zero exports — the parent then crashes at a downstream step when it tries to reference an exported key that was never produced, far from the actual root cause. Additionally, if a flow has `output_schema` defined but NO `required` properties and ALL steps are SKIPPED, the Engine MUST log a `WARNING`: `"Flow '<name>' completed with all steps SKIPPED and output_schema has no required fields. The flow produced no exports."` This is a valid but suspicious configuration that deserves operator visibility.

---

## 3. Flow Execution Contracts

> **Note**: The flow execution engine is defined in `01_03_engine_core_spec.md` §3.4. This section defines **flow-specific** behavioral contracts on top of that engine.

### 3.1 Flow Lifecycle States

Flows use the existing `StateStatus` enum from `01_03`:

```
PENDING → IN_PROGRESS → COMPLETED
                      → FAILED (permanent, after retries exhausted)
                      → INTERRUPTED (SIGTERM / SIGINT received)
                      → CANCELLED (explicit admin cancellation via `flow cancel <id>`)
                      → WAITING (human approval / external event)
                              → TIMED_OUT (TTL expiry — see 01_05 §5.1)
```

**`CANCELLED` State**: A flow enters `CANCELLED` when an admin explicitly invokes `flow cancel <id>`. `CANCELLED` is a terminal state — the flow is not resumable. It is distinct from `FAILED` (which indicates an operational error) and `INTERRUPTED` (which is resumable). Blob GC eligibility rules (§10.16) reference this state.

**Step-Level Status: `SKIPPED`**

`SKIPPED` is a **step-level-only** terminal status, distinct from flow-level lifecycle states. A step enters `SKIPPED` when it fails and its `on_failure` policy routes to `ignore` (directly or via `catch_rules`). `SKIPPED` steps:
*   Do NOT produce exports — their `export` map is not applied.
*   Are NOT re-evaluated on resume — once `SKIPPED`, always `SKIPPED`.
*   Are persisted in the call stack with `status: SKIPPED` for audit purposes.
*   A flow with `SKIPPED` steps can still reach `COMPLETED` — the completion condition is: all steps are `COMPLETED` or `SKIPPED`.

**Transition Rules:**
*   A flow enters `IN_PROGRESS` when its first step begins execution.
*   A flow enters `COMPLETED` only when **all** steps reach `COMPLETED` or `SKIPPED`.
*   A flow enters `FAILED` if any step with `on_failure: halt` fails permanently (retries exhausted).
*   A flow enters `INTERRUPTED` if a `SIGTERM`/`SIGINT` is received. See §3.4.
*   A flow enters `WAITING` if the current step returns `WAITING` (e.g., `ManualInterventionAtom`).
    *   **[E1 Fix] Max Staleness Check**: Every transition *out* of `WAITING` MUST enforce a `max_staleness` check (default 24h, configurable per flow via `"waiting_ttl_hours": N`). If the flow has been waiting longer than the threshold, the Engine MUST mandate a state-refresh or ask the human to explicitly confirm the context is still valid before resuming execution.
    *   **TTL Enforcement Mechanism**: The Engine's background heartbeat loop (the same loop that renews mutex leases — see §6.2) checks all `WAITING` flows every 60 seconds. If `now - waiting_since > waiting_ttl`, the flow transitions to `TIMED_OUT`. This is a garbage-collection mechanism for abandoned flows.

### 3.2 The FlowContext

The `FlowContext` is the **typed** runtime state shared between steps within a single flow.

**Schema (Typed Definition)**:
```python
@dataclass
class FlowContext:
    flow_id: str                            # Unique identifier for this flow invocation
    run_id: str                             # Deterministic Run ID (per 01_05 §1.2)
    step_index: int                         # Current instruction pointer
    variables: Dict[str, Any]               # User-defined step data (exports, args)
    system: SystemContext                   # Read-only engine metadata (see below)
    frozen_genesis_args: Optional[Dict[str, Any]] = None  # Frozen args snapshot for sub-flows (see §4.4)
    cancellation_requested: bool = False    # Set by Engine on SIGTERM/SIGINT
    timeout_cancelled: bool = False          # Set by Engine on sub-flow timeout (§6.3). Distinct from cancellation_requested.
    abort_event: Optional[str] = None               # [V2 RESERVED] Fan-Out abort signal.
    # IMPLEMENTATION NOTE: This field MUST NOT use `threading.Event` or any
    # non-JSON-serializable type. The FlowContext (including this field) is
    # serialized to JSON on every step completion (§5.1) and during teardown
    # (§6.2). A `threading.Event` would cause `TypeError: Object of type Event
    # is not JSON serializable` on the first state persistence attempt, crashing
    # the Orchestrator. V2 will use a string-based event ID that maps to an
    # in-memory Event registry at runtime, keeping the persisted state clean.

@dataclass
class SystemContext:
    task_id: str                            # Correlation ID
    config: Dict[str, Any]                  # Read-only .flow/config.json snapshot
    flow_definition_hash: str               # SHA256 of flow definition at genesis
    nesting_depth: int                      # Current call stack depth (0 = root)
    # NOTE: total_retry_count and total_retry_budget are NOT per-flow state.
    # They live in the Engine's call stack metadata record (see §3.3.1).
    # They are listed here for documentation completeness only — the Engine
    # reads/writes them from the shared task record, never from the sub-flow's
    # local SystemContext. See §3.3.1 "Named Exception" for rationale.
```

> [!IMPORTANT]
> **`frozen_genesis_args` Persistence**: For sub-flows (`nesting_depth > 0`), the Engine MUST populate `frozen_genesis_args` with the fully resolved `args` snapshot at sub-flow genesis time and persist it in the call stack frame (see §5.1). This is the **only** source of truth for resume (§5.2 step 5) and `--rehydrate-args` (§4.4). For root flows (`nesting_depth == 0`), this field is `None` — root flows receive args directly from the CLI. Without this field persisted in the call stack, the resume algorithm has no mechanism to reinstate frozen genesis parameters, causing it to silently re-evaluate args against the parent's current context (violating §4.4 Temporal Consistency).

**Rules:**
1.  **Population**: Steps populate `variables` via their `export` map. Only keys listed in `export` are written.
2.  **[U1 Fix] Implicit Garbage Collection (Scoping)**: Context keys are implicitly scoped to the step that created them and die when the step dies, UNLESS they are explicitly mapped in the `export` block. Manual `drop_keys` arrays are an anti-pattern and should not be relied upon to prevent overall OOM context bloat.
3.  **Collision Policy**: Governed by the step's `merge_strategy` (§2.3). Default is `fail` — a collision raises `SchemaError`. Explicit `merge_strategy: overwrite` enables last-write-wins with a `WARNING` logged.
4.  **Immutable View**: Atoms receive a **read-only** projection of the context (via `types.MappingProxyType` per `01_03` §4.2). They write back exclusively through `AtomResult.exports`.
5.  **Max Context Size**: The cumulative serialized context (`variables` + `system`) MUST NOT exceed **512 KB**.
    *   **Auto-Dehydration Policy**: When cumulative context size exceeds 512 KB, the Engine MUST auto-dehydrate the oldest exports (by step order) to blob pointers until below the threshold.
    *   To prevent OOM failures on large context tasks, the Orchestrator MUST seamlessly intercept any string export > 8KB (`MAX_INLINE_SIZE`), write it to `.flow/artifacts/blob_{uuid}.json`, and inject a lightweight `{"ref": "blob_{uuid}.json", "type": "blob_ref"}` pointer into the DB state.
    *   The LLM Gateway and Tools are responsible for hydrating these pointers *only* when requested explicitly.
    *   **[Dehydration Ordering Guarantee]**: Auto-dehydration MUST occur **after** the current step's Variable Resolution phase completes and **before** the post-step state serialization. If dehydration runs between two phases of the same step's execution (e.g., during a mid-step checkpoint in a long-running Atom), the step could observe a typed value in its `args` at dispatch time but a `blob_ref` pointer in the context on resume — violating the transparent hydration contract (§2.2 rule 4). The Engine MUST NOT dehydrate any export that is referenced by the `args` template of the **currently active** step or any **future** step in the same flow. Dehydration candidates MUST be restricted to exports from steps whose consumers have already completed or been skipped. Without this ordering guarantee, a crash-and-resume scenario after dehydration but before the Variable Resolver runs produces a `blob_ref` dict where a typed value was expected — causing `jsonschema` validation failures or silent type coercion bugs that only manifest on resume, never during initial execution.
    *   **[Consumer Tracking Mechanism]**: To implement the dehydration safety constraint above, the Engine MUST build a **static consumer map** at flow load time. For each step `S` and each `${var}` reference in `S.args`, the Engine records `var → set(consuming_step_ids)`. At dehydration time, the Engine iterates candidate exports oldest-first and skips any export key `K` where `consumers[K]` contains a step whose status is NOT `COMPLETED` or `SKIPPED`. This is a load-time computation (O(steps × args_keys)) — NOT a runtime scan. Without this map, the "oldest-first" eviction policy and the "MUST NOT dehydrate future-referenced exports" constraint are mutually contradictory: the Engine cannot know whether the "oldest" export is safe to dehydrate without knowing which future steps consume it. An implementer following only the "oldest-first" rule would dehydrate an export still needed by step N+5, causing a `blob_ref` dict where a typed value was expected on resume. **[CRITICAL FIX] Consumer Map Rebuild on Resume**: The consumer map MUST be rebuilt whenever the Engine resumes a flow from a persisted call stack (§5.2). The map is a load-time in-memory structure — it is NOT persisted in the call stack JSON. After a crash, the Engine deserializes the call stack from disk, but the consumer map is gone. If the Engine proceeds to the next step's dehydration phase without rebuilding the map, it has zero consumer information — causing one of two failures: (a) the Engine has no map at all and applies naive "oldest-first" eviction, dehydrating exports still needed by future steps (data corruption on resume), or (b) the Engine initializes an empty map, sees no consumers for any export, and dehydrates everything aggressively (all future steps get `blob_ref` dicts). The rebuild MUST account for the current `step_index`: steps already `COMPLETED` or `SKIPPED` are excluded from the consumer set, reflecting the resumed flow's actual progress. Without this incremental rebuild, the consumer map tracks consumers that already ran, making every export appear still-referenced and blocking all dehydration — the 512 KB context limit is eventually breached with an opaque `ContextSizeError`. **[C3 Fix] `${config.*}` Exclusion**: The consumer map MUST NOT track `${config.*}` references as consumers of export keys. `config` is a read-only snapshot from `.flow/config.json` (§3.2 `SystemContext.config`) — it is injected by the Engine at flow genesis and is immutable for the flow's lifetime. It is never written to `variables`, never modified by step exports, and therefore never a dehydration candidate. An implementer who naively scans all `${...}` tokens in `args` templates would register `${config.test_path}` as a consumer of a non-existent export key `config`, which: (a) pollutes the consumer map with phantom entries that never resolve, causing the dehydration loop to skip every candidate (nothing can be dehydrated because `config` is never `COMPLETED`), or (b) triggers a `KeyError` at dehydration time when the Engine looks up `consumers["config"]` and finds no matching step. The consumer map MUST restrict its scan to `${step_id.key}` patterns where `step_id` matches an actual step `id` in the current flow. References to `${input.*}`, `${config.*}`, and `${system.*}` are Engine-provided namespaces and MUST be excluded from consumer tracking.
6.  **Sub-Flow Export Boundary**: The 128KB aggregate export limit from 01_05 §2.3 applies at every sub-flow boundary. Exports exceeding this are auto-dehydrated to blob pointers before being merged into the parent context.

### 3.3 Failure Strategies

Each step declares an `on_failure` policy. The semantics are:

| Strategy | Behavior |
|:---|:---|
| `halt` (default) | Mark step `FAILED`. Mark flow `FAILED`. Propagate failure to parent flow (if this is a sub-flow). Engine stops. |
| `retry` | **For `type: atom`**: Re-execute the step from scratch up to `max_retries` (default: 3). The Engine appends the failure reason to context (`__last_error__`) so the next attempt can self-correct (per `01_03` §4.4). **[`__last_error__` Collision Exemption]**: The `__last_error__` key is an Engine-reserved internal key that is **exempt** from the `merge_strategy` collision policy (§3.2 rule 3). The Engine MUST unconditionally overwrite `__last_error__` on each retry attempt without triggering `SchemaError`. Without this exemption, a second retry attempt would write `__last_error__` into a context where it already exists from the first retry, the default `fail` merge strategy would raise `SchemaError`, and the retry mechanism would kill itself — an implementer would discover this only at runtime on the second retry of any step. **[C1 Fix] `__last_error__` Cleanup on Success**: When a retry attempt **succeeds** (step transitions to `COMPLETED`), the Engine MUST **delete** the `__last_error__` key from the flow's `variables` before proceeding to the next step. Without this cleanup, `__last_error__` persists from the last failed attempt and leaks into downstream context. This causes three concrete failures: (a) If a downstream step's `args` template references `__last_error__` (e.g., for conditional logic), it receives stale error data from a *resolved* issue, producing incorrect behavior. (b) If the flow's `output_schema` uses `additionalProperties: false` (§2.6), the presence of the undeclared `__last_error__` key causes `OutputSchemaViolation` — the flow *succeeds* at executing all steps but *fails* at the output gate because of a leftover infrastructure artifact. (c) If a parent flow exports sub-flow context keys via a `deep_merge` strategy (§2.3), `__last_error__` from the child's resolved retry leaks into the parent's context, polluting it with error state from an operation that ultimately succeeded. If retries exhausted → behaves as `halt`. **[Error Fast-Fail]**: If the failure is deterministic (e.g., `SchemaError`, `ConfigParamSchemaMismatch`), the engine MUST bypass `retry` and immediately escalate to `halt` to prevent instant budget exhaustion. **For `type: flow`**: The Engine MUST restart the sub-flow from scratch (clearing the child's call stack frame and generating a new Run ID). It does NOT resume from the last checkpoint. Because the child flow already failed permanently internally (e.g., exhausted its own retries or hit a `halt`), resuming it with the exact same frozen genesis arguments and local state guarantees an infinite failure loop. The `max_retries` count applies to the number of full sub-flow restart attempts. **[`__last_error__` Scope on Sub-Flow Retry]**: When a `type: flow` step is retried, the Engine MUST write `__last_error__` into the **parent** flow's context ONLY — it MUST NOT inject it into the child sub-flow's `frozen_genesis_args` or whitelist-injected `args`. The child sub-flow is a pure function (§4.1) that receives only explicitly declared `args`. Injecting `__last_error__` into the child would violate whitelist isolation by smuggling parent-scoped infrastructure state into the child's business context, potentially causing `input_schema` validation failures (the child's schema does not declare `__last_error__` as a valid input) or downstream data corruption if the child inadvertently exports it. The parent's retry logic can read `__last_error__` from its own context if needed for logging; the child starts clean. **[Sub-Flow Restart Version Re-Validation]**: When the Engine restarts a sub-flow (new Run ID, new frame), it MUST re-resolve `target_version` (§2.1) against the current Flow Registry and re-compute the `flow_definition_hash` for the new frame. If the flow definition has changed since the parent flow was started (e.g., a hot-reload occurred between retry 1 and retry 2), the new frame captures the updated hash. However, the Engine MUST also validate that the re-resolved flow version still satisfies the parent step's `target_version` constraint. If the new version falls outside the constraint (e.g., `target_version: "1.x"` but the registry now only has `2.0.0`), the Engine MUST fail the retry with `RegistryError` rather than silently executing an incompatible sub-flow definition. Without this re-validation, a sub-flow retry after a registry hot-reload could silently execute a structurally incompatible flow definition under the parent's old `target_version` contract. |
| `ignore` | Log a `WARNING`. Mark step `SKIPPED` (see §3.1 — Step-Level Status). Advance to the next step. The skipped step's `export` map is **NOT** applied — no partial data enters the parent context. If a downstream step references a key that would have been exported by the skipped step, variable resolution MUST raise `PreconditionFailed` (not silently inject an empty value). **[CRITICAL FIX] Optional Reference Handling**: The `PreconditionFailed` behavior applies ONLY to `${var}` references in the `args` block where `var` is a *required* key (i.e., the consuming step's logic cannot function without it). To enable practical use of `on_failure: ignore` for optional processing stages, the Engine MUST support an `${?var}` optional reference syntax in `args` templates. When the Variable Resolver encounters `${?var}` and the key does not exist in the context (because the producing step was `SKIPPED`), it MUST inject `null` (for JSON) or `None` (for Python) instead of raising `PreconditionFailed`. The standard `${var}` syntax retains the strict `PreconditionFailed` behavior. Without this mechanism, `on_failure: ignore` is practically unusable: any step that *might* be skipped cannot have *any* downstream consumer — even optional ones — without the entire flow crashing on `PreconditionFailed`. This forces flow authors into contorted designs where skippable steps are always terminal (no downstream references), severely limiting the composability that §4 is designed to enable. **Load-time validation (§7)**: The `flow validate --strict` command MUST verify that any step with `on_failure: ignore` or `on_failure: catch` (with all-ignore catch rules) has NO downstream `${var}` (strict) references to its exports — only `${?var}` (optional) references are permitted. This is a static check that catches the `PreconditionFailed` trap before runtime. |
| `catch` | **[B2 Fix]** Allows trapping specific errors via `catch_rules` while defaulting to `halt` for unexpected errors. See **Catch Rules Schema** below. Without `catch_rules` populated, `catch` behaves identically to `halt`. |

**Catch Rules Schema:**

When `on_failure: catch` is used, the step MUST include a `catch_rules` array defining error-specific routing. **[U2 Fix] State Isolation**: The Catch execution path receives a `FlowContext` snapshot from *immediately before* the failed step began execution. It MUST NOT ingest any partial or corrupted exports produced by the failure.

```json
"catch_rules": [
  {"error": "FILE_NOT_FOUND", "action": "ignore"},
  {"error": "PERMISSION_DENIED", "action": "halt"}
]
```

| Field | Type | Description |
|:---|:---|:---|
| `error` | `string` | Matched against `AtomResult.error.code` (exact string equality). **[Sub-Flow Error Code Mapping]**: For `type: flow` steps, sub-flows do NOT return `AtomResult`. Instead, the Engine synthesizes an error code from the sub-flow's terminal state: `SUBFLOW_FAILED` (sub-flow reached `FAILED`), `SUBFLOW_TIMED_OUT` (sub-flow reached `TIMED_OUT` via §6.3), or `SUBFLOW_CANCELLED` (sub-flow was explicitly cancelled). The `catch_rules` entry's `error` field matches against these synthesized codes. Without this mapping, an implementer would attempt to match against `AtomResult.error.code` on a `type: flow` step, find no `AtomResult` object, and either crash with `AttributeError` or silently fall through to the default `halt` — making `on_failure: catch` non-functional for all sub-flow steps. |
| `action` | `string` | One of `ignore` or `halt`. `retry` is NOT valid here — use step-level `on_failure: retry` instead. |

**Matching Rules:**
1.  **First-match-wins**: The Engine iterates `catch_rules` in order. The first entry where `error` matches the `AtomResult.error.code` determines the action.
2.  **No match → halt**: If no `catch_rules` entry matches the error, the step behaves as `on_failure: halt`. **[CRITICAL FIX] Unmatched Error Diagnostic**: When no `catch_rules` entry matches the actual error code and the Engine falls through to the default `halt` behavior, the Engine MUST log a `WARNING` with severity `HIGH`: `"Step '<id>' has on_failure: catch but error code '<actual_code>' matched no catch_rules entry. Falling through to default halt. Defined catch_rules error codes: [<list>]. Consider adding a wildcard catch_rules entry."` Without this diagnostic, an `on_failure: catch` step that encounters an unexpected error code silently behaves exactly like `on_failure: halt` — the flow author wrote `catch` intending to handle errors gracefully, but a new error code (e.g., `SUBFLOW_TIMED_OUT` from §3.3 Sub-Flow Error Code Mapping, or `ContextHydrationError` from §10.8) silently falls through the catch rules and crashes the flow. The operator has no indication that the catch block was even evaluated. **Wildcard Entry**: The Engine MUST support a special `"error": "*"` wildcard entry in `catch_rules` that matches any error code not explicitly listed. The wildcard MUST be the **last** entry in the array — if placed elsewhere, the Engine MUST raise `SchemaError` at load time (§7): `"Wildcard '*' in catch_rules must be the last entry."` This enables defensive error handling: `[{"error": "FILE_NOT_FOUND", "action": "ignore"}, {"error": "*", "action": "halt"}]` — known errors are handled specifically, while unknown errors still halt but with explicit intent documented in the flow definition.
3.  **`action: ignore` → SKIPPED**: The step is marked `SKIPPED` (§3.1). Exports are NOT applied, identical to `on_failure: ignore` behavior.
4.  **`action: halt` → FAILED**: The step is marked `FAILED`. The flow halts with failure propagation.

**Circuit Breaker**: The `retry` strategy inherits the Same-Error Abort behavior from the `verification_gates_backlog.md` (F1). If 3 consecutive retries produce the identical error hash, the Engine aborts immediately without waiting for `max_retries`.

#### 3.3.1 Total Retry Budget (Exponential Retry Defense)

To prevent exponential retry multiplication in nested flows (e.g., root `retry: 3` × sub-flow `retry: 3` × atom `retry: 3` = 27 attempts), the Engine enforces a **global `total_retry_budget`** (default: 27).

**Rules:**
1.  Every retry attempt at any nesting depth increments the global `total_retry_count`.
2.  When `total_retry_count >= total_retry_budget`, ALL retries at ALL levels immediately halt. The innermost step fails with `halt` behavior regardless of its `on_failure` setting.
3.  The budget is configurable per root flow via `"total_retry_budget": N` in the flow definition. Sub-flows MUST NOT declare their own `total_retry_budget` — the root flow's budget governs the entire task tree.
4.  The budget is inherited by sub-flows (they decrement the parent's budget, not their own).

> [!IMPORTANT]
> **Named Exception to Whitelist Injection (§4.1)**: The `total_retry_count` and `total_retry_budget` are Engine-mediated global state that **intentionally bypasses** the sub-flow isolation model. Sub-flows are "pure functions" with respect to *business data* (args in → exports out), but the retry budget is an *infrastructure safety mechanism* — it is NOT business data. This is analogous to how a CPU's interrupt handler can halt any userspace process regardless of process isolation boundaries.

**Synchronization Mechanism**: Both values are tracked in the Engine's **per-task metadata** (the call stack record in the state store), NOT in any flow's `FlowContext.system` or `local_context`. The Engine reads and writes these values from the shared task record at every nesting level. Sub-flows never see, read, or interact with the retry counter directly — the Engine mediates all access.

**Implementation Contract**: When constructing a child sub-flow's `FlowContext`, the Engine MUST NOT copy `total_retry_count` or `total_retry_budget` into the child's `SystemContext`. Instead, the Engine checks the shared task record *before* each retry attempt at any depth. If the global ceiling is reached, the Engine short-circuits the retry regardless of the current flow's local `on_failure` policy.

---

## 4. Sub-Flow Contracts (Composition & Reusability)

> [!IMPORTANT]
> Sub-Flows are the **primary reusability mechanism** in V1. A flow step with `"type": "flow"` invokes another flow as a composable building block. This section defines the boundary contracts.

### 4.1 Sub-Flow Invocation (Whitelist Injection)

When a parent flow invokes a sub-flow, the child receives a **clean, isolated context**. The child does NOT inherit the parent's full context.

**The child receives:**
1.  Its own `config` (from its flow definition).
2.  Whatever the parent explicitly passes via the step's `args` field.
3.  **Nothing else.**

This makes sub-flows **pure functions**: `args` in → `exports` out. No ambient context leaking.

```json
{
  "id": "run_tests",
  "type": "flow",
  "target": "TestVerification",
  "args": {
    "test_dir": "${config.test_path}",
    "source_files": "${code.changed_files}"
  },
  "export": {
    "test_result": "verification_status",
    "coverage": "coverage_pct"
  }
}
```

In this example, `TestVerification` receives only `test_dir` and `source_files`. It cannot see `code.prompt_history`, `config.llm_api_key`, or any other parent context key.

### 4.2 Sub-Flow Output Mapping (Explicit Export)

When a sub-flow completes, its internal exports are **not** automatically merged into the parent context. The parent step's `export` field explicitly maps child output keys to parent context keys.

**Rules:**
1.  The `export` map on a `type: flow` step maps **sub-flow context keys** → **parent context keys**.
2.  Only keys explicitly listed in `export` are visible to the parent. All other sub-flow internal state is discarded.
3.  **Strict Atomicity**: If a Sub-Flow step fails or is aborted prematurely, its partial exports are completely discarded. The parent context MUST NOT be polluted with half-finished state.
4.  If a required key (defined via `export.child_key.required: true`) does not exist in the sub-flow's final context, the Engine MUST log an Error and mark the parent step `FAILED`.

### 4.3 Sub-Flow Reconciliation (Split-Brain Defense)

The Engine MUST NOT spawn a sub-flow without first checking if a `SubFlow_ID` for that exact step already exists in an `IN_PROGRESS` or `COMPLETED` state. This prevents orphaned sub-flows during parent crash recoveries.

**Target Design (ACID DB — Phase 1.5)**: Sub-flow genesis MUST involve a pre-flight transactional lock or a Two-Phase Commit on the state DB:
1.  Parent writes "Starting Child X" → DB commit.
2.  Child spins up and confirms → DB commit.
3.  If crash occurs between (1) and (2): on restart, parent sees the intent record, checks if child is alive, and either attaches to it or aborts it.

> [!IMPORTANT]
> **MVP (Steel Thread) Interim**: Before the ACID DB is available, the MVP uses a single-writer JSON approach with intent files: the Engine writes a `{step_id}_intent.json` marker before spawning a sub-flow and removes it on successful completion. On restart, the Engine checks for dangling intent files and reconciles. This provides crash-safety for the common case (single worker, sequential execution) without requiring DB transactions. The Two-Phase Commit design above is the target state for Phase 1.5. See `external_strategy_review.md` T1.4 (Steel Thread Build Strategy).

### 4.4 Frozen Hydration (Static Genesis Params)

When a sub-flow is invoked, the parent's `args` injection is resolved and passed into the child's context.

**CRITICAL (Temporal Consistency)**: The parent arguments MUST be resolved and frozen at Sub-Flow genesis. 
If a sub-flow is paused and later resumed, the Engine MUST use the exact `args` snapshot it was originally created with. It MUST NOT re-evaluate the arguments against the parent's mid-flight context, as this destroys deterministic execution and reproducibility.

> [!WARNING]
> **Supersession Notice**: `01_05` §5.2 ("Deep Resume Hydration Trap") describes a legacy design where atoms inside a sub-flow receive a dynamically re-merged parent context on resume. **That behavior is explicitly superseded by this section.** Under the Whitelist Injection model (§4.1), sub-flows are pure functions — they receive only their frozen genesis `args` and their own `local_context`. Parent context mutations (including Administrative Overrides via `flow mutate-context`) do NOT automatically propagate into a paused sub-flow's context.
> 
> **[Resume Drift Fix]**: If an admin *intentionally* updates parent context and needs those changes to cascade into a suspended child sub-flow, they MUST explicitly invalidate the child's frozen genesis arguments using `flow resume <task_id> --rehydrate-args`. Without this flag, the child enforces the frozen parameters, preserving deterministic execution.
> 
> **[Rehydration Schema Guard]**: When `--rehydrate-args` is used, the Engine MUST re-resolve the parent step's `args` block against the parent's current context and then re-validate the resulting args against the child flow's `input_schema` (§2.5) **before** replacing the child's `frozen_genesis_args`. If the re-resolved args violate the child's schema (e.g., the admin mutated a parent context key from an integer to a string), the Engine MUST raise `PreconditionFailed` and abort the rehydration — leaving the original frozen args intact. Without this guard, `--rehydrate-args` silently injects schema-violating data into the child flow, causing type errors or data corruption in downstream child steps.

### 4.5 Recursive Flows & Runtime Depth Limits

Flows natively support recursive calling (Flow A calls Flow A) for bounded iterative tasks like pagination or expanding searches.

> [!NOTE]
> Recursive sub-flow invocation is a **V1 feature**. The runtime depth limit (`MAX_CALL_STACK_DEPTH`), the `MaxRecursionError` with stack trace dump, the total retry budget defense (§3.3.1), the Two-Phase Commit for sub-flow genesis (§4.3), and the INTERRUPTED propagation algorithm (§6.1) all assume recursive nesting is available and are fully specified as V1 contracts. The "V2" label that previously appeared here was a vestigial tag from an earlier draft.

**Protection Mechanism:**
1.  Static (load-time) DFS cycle detection is removed. It is perfectly valid for a Flow to recursively call itself (e.g., paginating results).
2.  Instead, the Engine enforces a `MAX_CALL_STACK_DEPTH` at runtime (default: 50).
3.  **[E3 Fix] Stack Trace Dump**: If a recursive invocation attempts to push a 51st frame onto the call stack, the Engine immediately aborts the innermost flow with a `MaxRecursionError`. This error MUST clearly dump the exact frame stack trace to the user, not just a generic failure, allowing the user to distinguish between an infinite loop bug and a legitimately deep recursive task.

### 4.6 Resource Locks & Mutex Reentrancy (V2 Reserved)

Flows that declare `requires_lock: ["resource_name"]` reserve exclusive access to that resource.
**[U1 Fix] Mutex Reentrancy**: To prevent the "Deadly Embrace" where a parent flow holds a lock and blocks its own child sub-flow from acquiring it, lock ownership MUST be tied to the `Root_Run_ID` or the Call Stack hierarchy, not just the isolated Step ID. Child flows MUST be granted re-entrant access to locks already held by their direct ancestors in the call stack.

---

## 5. State Persistence & Resume

> [!WARNING]
> **Database Target State**: Flow state persistence (checkpointing, sub-flow tracking, lock coordination in §4.3) will eventually require the embedded ACID database (SQLite WAL) for full production hardening. See `roadmap_2026.md` Phase 1.5.
>
> **MVP (Steel Thread) Strategy**: The initial implementation MUST use **JSON file-based state persistence** with atomic writes (write → fsync → rename, per `01_03` §3.4). This proves the recursive flow logic (dive → surface → state handoff → crash → resume) works correctly before introducing DB complexity. Once the 3-level flow stack (Parent → Sub-Flow → Atom) is proven with JSON files, the migration to SQLite WAL follows as a persistence backend swap behind the `StateStoreInterface` protocol. See `external_strategy_review.md` T1.4: *"A working engine with messy files is a product; a perfect database with a broken engine is a paperweight."*

### 5.1 The Call Stack Model

The Engine persists flow execution state as a **call stack** (per `01_04` §1.3.1):

```json
{
  "task_id": "req-42",
  "root_flow": "ImplementFeature",
  "total_retry_budget": 27,
  "total_retry_count": 4,
  "stack": [
    {
      "flow": "ImplementFeature",
      "flow_version": "1.0.0",
      "flow_definition_hash": "sha256:a1b2c3...",
      "step_index": 3,
      "status": "IN_PROGRESS",
      "local_context": {"task": "add-auth-module"},
      "frozen_genesis_args": null
    },
    {
      "flow": "TestVerification",
      "flow_version": "1.0.0",
      "flow_definition_hash": "sha256:d4e5f6...",
      "step_index": 2,
      "status": "IN_PROGRESS",
      "local_context": {"test_dir": "tests/auth/"},
      "frozen_genesis_args": {"test_dir": "tests/auth/", "source_files": ["src/auth.py"]}
    }
  ],
  "checksum": "sha256:..."
  // ↑ See Checksum Contract below
}
```

**Rules:**
*   Each stack frame represents a flow invocation with its own `step_index`, `local_context`, `flow_version`, and `flow_definition_hash`.
*   The `flow_definition_hash` is a SHA256 hash of the flow definition JSON at the time the frame was created. This enables config-drift detection on resume (see §5.3).
*   When a `type: flow` step is dispatched, a new frame is pushed onto the stack.
*   When a sub-flow completes, its frame is popped and exports are mapped to the parent (per §4.2).
*   The stack is persisted to the state DB after **every** step completion.
*   **[Retry Budget Persistence]**: The `total_retry_budget` and `total_retry_count` fields are persisted at the **task level** (top-level of the call stack JSON, not inside individual frames). These values MUST survive Engine crashes and be restored on `flow resume`. Without persistence, a crash after 20 retries resets the counter to 0, granting the task another full budget of 27 retries — effectively defeating the exponential retry defense (§3.3.1). The Engine MUST increment `total_retry_count` in the persisted state *before* dispatching the retry attempt, not after. This ensures a crash mid-retry still counts against the budget.
*   **[Checksum Contract]**: The `checksum` field is a SHA256 hash of the **entire serialized call stack JSON excluding the `checksum` field itself** (i.e., `sha256(json_serialize(stack_doc without 'checksum' key))`). **[Canonical Serialization Requirement]**: The JSON serialization used for checksum computation MUST be **canonical** — deterministic key ordering (`sort_keys=True`), no trailing whitespace, consistent Unicode escaping (`ensure_ascii=False`), and compact separators (`separators=(',', ':')` — no spaces). Without canonical serialization, Python's `json.dumps()` default output is non-deterministic with respect to dictionary key ordering (CPython 3.7+ preserves insertion order, but insertion order can vary between serialization and deserialization cycles if intermediate dict operations reorder keys). Two functionally identical call stack objects can produce different JSON strings, causing false `StateCorruptionError` on resume — the operator sees a corruption alert for a perfectly valid state file, loses trust in the integrity mechanism, and starts habitually using `--force` flags that bypass the guard entirely. Conversely, if a tampered file happens to use the same key order as the original, a non-canonical checksum might fail to detect the tampering. The Engine MUST use the **same** canonical serialization function for both checksum computation and state file writing. The Engine MUST compute and write this checksum on every state persistence operation. On `flow resume`, the Engine MUST recompute the hash and compare it against the persisted value. A mismatch indicates the state file was corrupted (disk error, manual file tampering, incomplete write). On mismatch, the Engine MUST raise `StateCorruptionError` with the file path, expected hash, and actual hash. The operator may use `flow restart <task_id> --force` to discard the corrupted checkpoint. **Interaction with `flow mutate-context`**: The `flow mutate-context` command (§5.4) MUST recompute and update the `checksum` after applying any mutation — using the **same** canonical serialization function. Without this, every admin mutation would invalidate the checksum, causing the next `flow resume` to reject the file with `StateCorruptionError` — making the administrative override mechanism non-functional. **`--force-resume` does NOT bypass checksum**: The `--force-resume` flag (§10.13) bypasses only the `flow_definition_hash` check (§5.3 check 2). It MUST NOT bypass checksum validation. `--force-resume` does not modify the persisted call stack state — the checksum remains valid because only the external flow definition file changed. Bypassing the checksum here would allow a corrupted or tampered state file to be silently accepted whenever `--force-resume` is also specified, defeating the integrity mechanism entirely. If a legitimate `flow mutate-context` has been applied (which updates the checksum), the checksum will already match on resume.

### 5.2 Resume Algorithm (Independent State DB Tracking)

On `flow resume <task_id>`:

1.  **Load** the call stack from the state DB.
2.  **[M4 Fix] Verify Worker Mutex (Concurrency Guard)**: The Engine MUST verify that no active `Worker_ID` currently holds an unexpired lease on this flow's DB record. If another worker is actively processing it, raise a `ConcurrencyError` to prevent split-brain execution logic. **[U3 Fix] Generational Fencing Token**: For Phase 1.5 DB implementation, worker leases MUST utilize a Generational ID / Fencing Token. If a worker attempts to flush a state update but the DB's token generation has advanced (meaning another worker took over the lease), the original worker MUST immediately self-terminate its processing loop to prevent duplicate split-brain side-effects.
3.  **Walk to the deepest** stack frame (the innermost active sub-flow).
4.  **Check** the current step's state against the DB:
    *   If the child object is marked `COMPLETED` in the DB: do not re-run. Re-read final exports and finish the Parent merge. This guarantees idempotency if the system crashed during the merge phase. **[CRITICAL FIX] Type-Aware Export Retrieval**: The export retrieval path MUST distinguish between `type: atom` and `type: flow` steps. **For `type: atom`**: The Engine reads the persisted `AtomResult.exports` from the state store (the Atom's serialized output). **For `type: flow`**: The Engine reads exports from the child's call stack frame `local_context` and applies the parent step's `export` map (§4.2). Attempting to read `AtomResult` from a completed sub-flow step will crash with `AttributeError` — sub-flows do not produce `AtomResult` objects; their outputs are context keys. This is the `COMPLETED`-state counterpart of the `IN_PROGRESS` zombie fix ([R1 Fix]) — the same atom-vs-flow distinction applies. Without this fix, a crash between sub-flow completion and parent merge produces a `COMPLETED` sub-flow step that the resume algorithm cannot correctly process: it calls the atom export path on a flow step and crashes, making every crash-recovery of a multi-flow pipeline non-functional.
    *   If the step is `IN_PROGRESS` (zombie from crash):
        *   **For `type: atom`**: call `atom.check_completion()` (per `01_03` §3.3). If true → mark `COMPLETED` and advance. If false → re-execute.
        *   **[R1 Fix] For `type: flow` (sub-flow zombie)**: The Engine MUST NOT call `check_completion()` — sub-flows do not implement this interface. Instead, the Engine MUST inspect the child's call stack frame. If the child frame exists and its status is `COMPLETED`, the Engine re-reads the child's exports and merges them into the parent (idempotent merge). If the child frame is `IN_PROGRESS` or `INTERRUPTED`, the Engine recurses into the child's call stack to resume it at its deepest active frame (standard recursive resume). If no child frame exists (crash before frame creation), the Engine checks for an intent file (§4.3 MVP interim) — if an intent file exists with no corresponding child, the intent is aborted and the step is re-executed from scratch. This distinction is critical: calling `check_completion()` on a `type: flow` step would crash the Engine with `AttributeError` because flows are not Atoms and do not expose this method.
    *   **[U3 Fix] Atomic Idempotency Result**: For a step to be declared `COMPLETED` successfully via `check_completion()` logic without a full rerun, the complete `AtomResult` (specifically the mapped `exports`) MUST be available. If the step is marked complete by the Atom but the DB lacks the required serialized exports to satisfy the parent map, the step MUST be treated as incomplete and re-run to reconstruct the necessary data stream.
    *   If `WAITING`: check TTL. If expired → `TIMED_OUT`. If valid → remain paused.
    *   **[CRITICAL FIX] If `TIMED_OUT`**: A step or flow in `TIMED_OUT` state has already transitioned via TTL expiry (§3.1 TTL Enforcement Mechanism). The resume algorithm MUST treat `TIMED_OUT` as a terminal failure equivalent to `FAILED` for the purposes of flow advancement: the Engine MUST apply the step's `on_failure` strategy against a synthesized error code `TTL_EXPIRED`. If `on_failure: halt` → flow remains `FAILED`. If `on_failure: retry` → the Engine MAY restart the step (if budget allows). If `on_failure: ignore` → mark `SKIPPED` and advance. If `on_failure: catch` → evaluate `catch_rules` against `TTL_EXPIRED`. Without this explicit branch, a flow that timed out while `WAITING` (e.g., `ManualInterventionAtom` exceeded `waiting_ttl_hours`) falls through all resume conditionals — the Engine either crashes with `"Unrecognized step state: TIMED_OUT"` or silently skips the step without applying any failure strategy, causing downstream data loss and inconsistent flow state.
    *   **[R3 Fix] If `FAILED`**: The step previously exhausted its retries or hit a `halt` condition. The resume algorithm MUST re-apply the step's `on_failure` strategy: if `on_failure: halt`, the flow remains `FAILED` and the Engine raises `FlowAlreadyFailed` with the step ID and original error. If `on_failure: retry` and the `total_retry_budget` (§3.3.1) still has capacity, the Engine MAY restart the step (using a fresh retry, NOT resuming from the failed state). If `on_failure: ignore`, the step transitions to `SKIPPED` and the flow advances. If `on_failure: catch`, the Engine re-evaluates `catch_rules` against the persisted error code. Without this branch, an implementer's resume algorithm silently falls through the `COMPLETED`/`IN_PROGRESS`/`WAITING` conditionals and produces undefined behavior — either skipping the failed step entirely (data loss) or crashing with an unhandled state error.
    *   **[R3 Fix] If `CANCELLED`**: `CANCELLED` is a terminal state (§3.1). The Engine MUST NOT attempt to resume any step in `CANCELLED` state. If the deepest frame is `CANCELLED`, the Engine MUST raise `FlowCancelled`: `"Flow <id> was explicitly cancelled and cannot be resumed. Use 'flow restart <id> --force' to start from scratch."` Without this branch, the resume algorithm would treat a `CANCELLED` step as unrecognized state and either crash or silently skip it.
    *   **[C2 Fix] If `SKIPPED`**: `SKIPPED` is a step-level terminal state (§3.1). A step that was previously marked `SKIPPED` (via `on_failure: ignore` or `catch_rules` routing to `ignore`) MUST NOT be re-evaluated or re-executed on resume. The Engine MUST treat `SKIPPED` identically to `COMPLETED` for flow-advancement purposes: advance `step_index` past the skipped step and continue to the next step. Without this explicit branch, an implementer's resume algorithm falls through the `COMPLETED`/`IN_PROGRESS`/`WAITING`/`FAILED`/`CANCELLED` conditionals and reaches a catch-all that either crashes with `"Unrecognized step state: SKIPPED"` or — worse — silently re-executes the step that was deliberately skipped, undoing the `on_failure: ignore` decision and potentially causing side-effects on a step that already demonstrated it cannot succeed. This is especially dangerous for non-idempotent Atoms: the original failure may have partially written files or triggered external API calls, and re-execution on resume would duplicate those side-effects.
5.  **Frozen Re-hydration**: The Engine reinstates the exact genesis args for any paused sub-flow (per §4.4). **[Resume Schema Re-validation]**: After reinstating the frozen genesis args, the Engine MUST re-validate them against the child flow's current `input_schema` (§2.5). If the flow definition was modified between suspension and resume (e.g., via `--force-resume` per §5.3, or a hot-reload that changed the child flow's `input_schema`), the frozen args may silently violate the new schema — causing type errors, `jsonschema` validation failures, or data corruption in downstream child steps that assume schema-compliant inputs. On validation failure, the Engine MUST halt with `PreconditionFailed`: `"Frozen genesis args for sub-flow '<name>' fail input_schema validation after flow definition change. Use 'flow resume <id> --rehydrate-args' to re-resolve args from parent context, or revert the schema change."` This check runs ONLY on resume, not on initial invocation (where `input_schema` validation already occurs at §2.5).
6.  **Pop** completed sub-flow frames and return to the parent, applying the export map.

### 5.3 Version Mismatch & Config Drift on Resume

On resume, the Engine performs **two** validation checks per stack frame:

1.  **`flow_version` check**: Compares the persisted `flow_version` against the current flow definition's `flow_version`. Mismatch halts with `VERSION_DRIFT` error.
2.  **`flow_definition_hash` check** (P0 — per 01_07 §8.5 "Step Pointer Safety on Resume"): Compares the persisted `flow_definition_hash` against a freshly computed hash of the current flow definition. This catches changes that don't bump `flow_version` (e.g., reordering steps, modifying args, adding/removing steps).

**On mismatch (either check):**
*   The Engine MUST halt with `ConfigVersionMismatchError`. It MUST NOT silently continue with a potentially incompatible definition.
*   The error message MUST include: the flow name, the persisted hash, the current hash, and the step index at which the flow was paused.
*   Manual intervention is required: `flow mutate-context <task_id>` (§5.4), SRE unblocking, or `flow restart <task_id> --force` (discards checkpoint, restarts from step 0).

### 5.4 The "Poison Pill" Administrative Override

**[E2 Fix] Context Mutation**: If a buggy flow injects schema-violating JSON into the state store (a "poison pill"), subsequent runs will crash instantly during deserialization or validation. Restarting the Engine does not clear the persisted state. 
*   The system MUST define a CLI command `flow mutate-context <task_id> [...]` to allow System reliability engineers (SREs) or admins to surgically rewrite, delete, or append values directly into the serialized Flow Context without losing the task's valid cryptographic execution history.
*   **State Guard**: `flow mutate-context` MUST reject mutations on flows in `IN_PROGRESS` state. It MUST only operate on flows in `WAITING`, `INTERRUPTED`, or `FAILED` states. Mutating the context of a running flow risks data corruption mid-step — the running step's assumptions about its context would be silently violated. **[R2 Fix] Child Frame Guard**: Before accepting a mutation on a parent flow in `FAILED` state, the Engine MUST walk the call stack and verify that NO child sub-flow frame is currently `IN_PROGRESS`. In a multi-worker scenario (Phase 1.5), a parent can be `FAILED` while a child sub-flow spawned by a prior step is still executing on another worker (e.g., the parent's step N failed, but step N-1's sub-flow is a long-running process that hasn't been reaped). Mutating the parent's context while a child is running corrupts the child's export merge path — the child will attempt to write exports into a context that has been surgically altered without its knowledge. If any child frame is `IN_PROGRESS`, the Engine MUST reject the mutation with: `"Flow <id> has child sub-flow <child_id> in IN_PROGRESS state. Cancel or wait for the child to complete before mutating parent context."`
*   **[Cryptographic Audit Integrity]**: Any execution of `flow mutate-context` MUST generate an `AdminMutationEvent`. This event MUST contain the exact diff of the mutation, the identity/auth of the invoking operator, and a mandatory reason code. It MUST be cryptographically signed and injected into the append-only `audit.jsonl` log. Modifying the state without this verifiable log entry breaks the cryptographic chain of custody between step inputs and outputs and is considered a critical security failure.

---

## 6. Graceful Teardown

### 6.1 INTERRUPTED Propagation Algorithm (Nested Sub-Flows)

When the Engine receives `SIGTERM`/`SIGINT` or a parent cancellation, it MUST propagate the interruption through the entire call stack using a **top-down traversal**:

```
Propagation Order (TOP-DOWN):
  1. Engine sets root_flow.cancellation_requested = True
  2. Engine walks call_stack from ROOT → LEAF (top → bottom)
  3. At each frame: set sub-flow status to INTERRUPTED (UNLESS frame is `WAITING` — see [M2 Fix] below)
  4. At the LEAF frame: call cleanup() on the active Atom/Skill
  5. Unwind back up, marking INTERRUPTED state at each active level in memory
  6. On resume: Engine walks call_stack, finds deepest INTERRUPTED frame, resumes there
```

**State invariants during teardown:**
*   Every active frame in the call stack MUST be set to `INTERRUPTED` — never `FAILED`.
*   **[M2 Fix] Exemption for WAITING**: If a frame is currently in the `WAITING` state, its state MUST NOT be overwritten to `INTERRUPTED`. `WAITING` is already a safe, suspended state that requires human intervention or external triggers; overwriting it destroys that semantic contextual meaning.
*   **[B2 Fix]**: Marking a gracefully interrupted sub-flow as `FAILED` instead of `INTERRUPTED` corrupts the resume algorithm, potentially triggering unwarranted retries or error propagation upon restart.
*   Each frame's `local_context` is persisted as-is (partial state is valid for `INTERRUPTED`).
*   The call stack itself is flushed to the DB as a single atomic write after all frames are updated.

### 6.2 The Teardown Sequence
When the Engine receives `SIGTERM` or `SIGINT` (or a cascading cancellation) during flow execution:

1.  **Signal the current Atom**: Call `cleanup()` on the active Atom (per `01_05` §6.2). If the Atom is an `AgentAtom` with an active Skill, the cleanup propagates to the Skill (per `01_05` §3.3.1).
2.  **Nested Time Budget Formula** (cross-ref: `01_07` §8.3): The teardown cascade uses a nested budget. Each level in the call stack gets its own cleanup budget:
    *   **Skill cleanup**: 5 seconds (per `01_05` §6.2).
    *   **AgentAtom cleanup**: 10 seconds (includes Skill propagation, per `01_07` §8.3).
    *   **Per-level overhead**: 2 seconds (for state persistence and frame update).
    *   **SIGKILL watchdog formula**:
    ```
    SIGKILL_timeout = base_timeout + (nesting_depth × per_level_budget)
    Default: 15s + (depth × 12s)  →  depth 1: 27s, depth 3: 51s, depth 5: 75s
    ```
    *   **[Watchdog Deficit Fix]**: The Engine MUST bound the calculated `SIGKILL_timeout` to be strictly less than the OS-level SIGKILL window. The OS grace period is read from `.flow/config.json` key `os_grace_period_seconds` (default: **25 seconds** — conservative for Kubernetes default 30s `terminationGracePeriodSeconds` minus 5s safety margin). If the formula `base_timeout + (depth × per_level_budget)` exceeds `os_grace_period_seconds`, the Orchestrator MUST clamp `SIGKILL_timeout = os_grace_period_seconds - 2` and execute a hard-stop, violently severing leaf nodes at `T-minus 2 seconds` from the OS deadline to guarantee parent Mutexes are released and state is flushed before the OS obliterates the process. **[CRITICAL FIX] Implementation Note**: For `nesting_depth >= 1`, the default formula already exceeds the 25s budget (`15 + 1×12 = 27s > 25s`). At depth >= 1 the Engine MUST log a `WARNING` at flow genesis: `"Nesting depth {depth} exceeds SIGKILL budget. Teardown will be truncated to {os_grace_period_seconds - 2}s. Inner cleanup() calls may be skipped. Increase os_grace_period_seconds or reduce nesting."` and switch to a **fast-path teardown** that calls `cleanup()` ONLY on the leaf-most active Atom/Skill (skipping intermediate frame persistence) before flushing the entire call stack as `INTERRUPTED` in a single DB write. **[Arithmetic Proof]**: `depth=0: 15+0=15s ✓ (within 25s)`. `depth=1: 15+12=27s ✗ (exceeds 25s)`. The previous threshold of `depth >= 2` left depth=1 in a silent failure window where the formula yields 27s but the clamping logic never triggers — the OS SIGKILLs the process at T=25s, 2 seconds before the Engine's own watchdog fires, aborting state persistence and lock release (§6.2 steps 3-4). This is a data corruption scenario: the flow is left `IN_PROGRESS` with held locks and no persisted `INTERRUPTED` state.
    *   The Engine MUST configure the SIGKILL watchdog using `FlowContext.system.nesting_depth` at flow genesis. The watchdog timer is set ONCE at the start of teardown and does not change during the cascade.
3.  **Persist State** (MUST happen BEFORE lock release): Walk the call stack top-down, marking each active frame as `INTERRUPTED`. Flush the entire call stack to the DB atomically. **[Teardown Ordering Fix]**: State persistence MUST complete *before* lock release (step 4). If locks are released first and the Engine crashes before state is flushed, the flow is in `IN_PROGRESS` state with no lock — the next resume attempt proceeds without the mutex, allowing a concurrent worker to also acquire the lock and process the same flow. This creates a split-brain: two workers executing the same flow simultaneously. By persisting state first, the worst case on crash is a held lock that expires via the 60-second TTL (step 5) — a temporary delay, not data corruption.
4.  **[M3 Fix] Explicit Lock Release**: The Engine MUST explicitly and immediately release any routing Mutexes (`requires_lock`) owned by the terminating frame. It MUST NOT wait for the 60-second DB lease to expire organically, as this unnecessarily blocks other waiting flows.
5.  **Leased Mutex Expiry (Deadlock Prevention)**: If a Flow acquires a lock (`requires_lock`), it holds a DB "lease" valid for exactly 60 seconds. The Engine runs a background thread generating 30-second heartbeats to renew the lease. If the Flow hard-crashes (bypassing `cleanup()`), the heartbeat dies. The DB lease naturally expires within 60 seconds, preventing permanent deadlock. No sweeper cron jobs are required.
6.  **Exit(0)**: Clean shutdown.

On next `flow resume`, the resume algorithm (§5.2) handles recovery by finding the deepest `INTERRUPTED` frame.

### 6.3 Sub-Flow Timeout Isolation

When `steps[].timeout_seconds` is applied to a step with `type: flow` (a Sub-Flow), the Engine MUST NOT enforce the timeout using the global Orchestrator `SIGKILL` watchdog. Terminating the entire Orchestrator process merely because a single Sub-Flow exceeded its time limit is an unhandled panic that destroys the parent flow's capability to recover.

**Enforcement Mechanism:**
1. **Isolated Signal**: The Engine MUST set `timeout_cancelled = True` **specifically on the local Sub-Flow's `FlowContext`**, without triggering the global Orchestrator teardown sequence. **[Signal Disambiguation]**: The Engine MUST use the `timeout_cancelled` flag (NOT `cancellation_requested`) for step-level timeouts. `cancellation_requested` is reserved exclusively for Engine-level `SIGTERM`/`SIGINT` propagation (§6.1). Using the same flag for both timeout and SIGTERM creates a critical ambiguity: on resume, the Engine cannot distinguish a sub-flow that was timed out (should be `FAILED` and trigger `on_failure`) from one that was gracefully interrupted by SIGTERM (should be `INTERRUPTED` and resumable). The Atom's cooperative shutdown loop (per `01_05` §6.1) MUST check `context.cancellation_requested OR context.timeout_cancelled` — either signal triggers graceful halt, but the Engine uses the flag identity to determine the correct post-halt state assignment.
2. **Graceful Timeout**: When the `timeout_seconds` threshold is reached for the Sub-Flow step, the Engine trips this local `timeout_cancelled` flag.
3. **Inner Abort**: The currently executing Atom *inside* the Sub-Flow detects its local `context.timeout_cancelled` flag (or `context.cancellation_requested` for SIGTERM), halts gracefully, and the Sub-Flow's call stack frame collapses.
4. **[R4 Fix] Frame Collapse Mechanism**: When the inner Atom halts due to `timeout_cancelled`, the Engine MUST execute the following sequence to collapse the sub-flow frame: (a) Mark the inner Atom's step as `FAILED` with error code `SUBFLOW_TIMED_OUT`. (b) Walk the sub-flow's remaining steps and mark them all as `SKIPPED` — they will never execute. (c) Mark the sub-flow frame's status as `FAILED`. (d) Pop the sub-flow frame from the call stack. (e) Discard all partial exports from the sub-flow — the `export` map is NOT applied (consistent with §4.2 rule 3, Strict Atomicity). (f) Persist the updated call stack atomically (single write). Without this explicit sequence, the timed-out sub-flow frame remains on the call stack in an ambiguous state. On crash-recovery resume (§5.2), the Engine walks to the deepest frame and finds the orphaned timed-out frame still marked `IN_PROGRESS` — it attempts to resume the sub-flow instead of recognizing it already timed out, causing the parent's `on_failure` strategy to never fire.
5. **Parent Scope Rescue**: The Sub-Flow step returns to the parent Orchestrator marked as `FAILED` (due to timeout). The parent flow remains fully alive, continues executing, and triggers the step's defined `on_failure` strategy (e.g., `retry` or `ignore`). **[SIGTERM Precedence]**: If a global `SIGTERM` arrives while a sub-flow timeout is already in progress (i.e., `timeout_cancelled` is set and the sub-flow is shutting down), the Engine MUST override the sub-flow's state to `INTERRUPTED` (not `FAILED`). SIGTERM takes precedence because the entire Engine is shutting down — the parent flow cannot execute `on_failure` recovery anyway. The `INTERRUPTED` state ensures correct resumability on next startup.

---

## 7. Flow Definition Validation

Before execution, the Engine MUST validate every loaded flow definition:

| Check | Failure Action |
|:---|:---|
| All `target` references exist in the Atom or Flow registry. | `RegistryError` — abort. |
| All step `id` values are unique within the flow. | `SchemaError` — abort. |
| `steps` array is non-empty. | `SchemaError` — abort. |
| `flow_version` field is present and valid semver. | `SchemaError` — abort. |
| `description` field is present and a non-empty string. | `SchemaError` — abort. |
| `on_failure` values are one of `halt`, `retry`, `ignore`, `catch`. | `SchemaError` — abort. |
| `input_schema` is a valid JSON Schema (Draft 7) with `type: "object"` and `additionalProperties: false` (§2.5). | `SchemaError` — abort. |
| `output_schema` (if present) is a valid JSON Schema (Draft 7) with `type: "object"` and `additionalProperties: false` (§2.6). | `SchemaError` — abort. |
| `catch_rules` entries have valid `action` values (`ignore` or `halt` only) and non-empty `error` strings (§3.3). **[Strict Action Whitelist]**: The Engine MUST reject ANY `action` value not in the set `{"ignore", "halt"}`. In particular, `"retry"` MUST be rejected with: `"catch_rules action 'retry' is not valid. Use step-level on_failure: retry instead."` This is not merely a documentation note — without explicit whitelist validation, an implementer could add custom action strings (e.g., `"skip"`, `"escalate"`, `"restart"`) that pass schema validation but produce undefined runtime behavior because only `ignore` and `halt` have defined Engine semantics (§3.3 matching rules 3-4). | `SchemaError` — abort. |
| **[R5 Fix]** Steps with `on_failure: catch` MUST have a non-empty `catch_rules` array. The §2.1 field table states `catch_rules` is required when `on_failure: catch`, and §3.3 states that without `catch_rules` populated, `catch` behaves identically to `halt`. However, the runtime fallback is a trap — an implementer writes `on_failure: catch` intending to add catch rules later, forgets, and the step silently behaves as `halt` with no diagnostic. The Engine MUST enforce this at load time: if `on_failure: catch` and `catch_rules` is missing, empty, or not an array, raise `SchemaError`: `"Step '<id>' has on_failure: catch but catch_rules is empty or missing. Either add catch_rules or use on_failure: halt."` | `SchemaError` — abort. |
| `requires_lock` values (if present) reference valid resource names. [V2 RESERVED] | `SchemaError` — abort. |
| `total_retry_budget` (if specified) is a positive integer. | `SchemaError` — abort. |
| Steps with `on_failure: ignore` MUST NOT have `required: true` exports (§10.4). | `SchemaError` — abort. |
| Steps with `on_failure: catch` where ALL `catch_rules[].action` values are `ignore` MUST NOT have `required: true` exports (§10.4). | `SchemaError` — abort. |
| If `catch_rules` contains a wildcard entry `{"error": "*", ...}`, it MUST be the **last** entry in the array (§3.3 matching rule 2). A wildcard in any other position shadows all subsequent entries, making them unreachable dead code. | `SchemaError` — abort. |
| Steps with `on_failure: ignore` (or `catch` with all-ignore rules) MUST NOT have downstream `${var}` (strict) references to their exports. Only `${?var}` (optional) references are permitted (§3.3 `ignore` — Optional Reference Handling). This is a `--strict` validation check. | `SchemaError` — abort (under `--strict`). |

Validation runs **once** at flow load time. A future `flow validate --dry-run` CLI command can perform this without executing any steps (see `fractal_patterns.md` §8.2).

**[U1 Fix] Static Analysis (The `--strict` Flag):**
A standalone `flow validate --strict <flow_id>` command is REQUIRED for CI/CD checks. This command must perform a deep static trace of variable assignments across sub-flow boundaries. It validates that parent args injections statically satisfy the child's `input_schema` prior to any runtime value lookup, catching schema drift between flow definitions immediately. The `--strict` flag MUST also trace `args` mappings through sub-flow invocations and verify that every sub-flow's `input_schema` is satisfiable by its parent's available context keys at the point of invocation.

---

## 8. Standard Flows

### 8.1 `AskCodebase`
*   **Trigger**: User Query via CLI.
*   **Steps**:
    1.  `RagRetrievalAtom` (Query Knowledge Base).
    2.  `AgentAtom` (Synthesize Answer).

### 8.2 `ImplementFeature`
*   **Trigger**: `start_task` command.
*   **Steps**:
    1.  `AgentAtom` configured with `PlanningSkill` (Draft Implementation Plan).
    2.  `ManualInterventionAtom` (Wait for Approval).
    3.  `AgentAtom` configured with `CodingSkill` (Execute Changes).
    4.  `TestVerification` **[Sub-Flow]** (Run Tests → see §8.3).

### 8.3 `TestVerification` (Reusable Sub-Flow)
*   **Purpose**: Reusable test execution flow, composed into multiple parent flows.
*   **Parameters** (received via parent's `args`):
    *   `test_dir`: Path to test directory.
    *   `source_files`: List of files to verify.
*   **Steps**:
    1.  `ScriptAtom` (Run `pytest` on `test_dir`).
    2.  `AssertionAtom` (Verify `coverage >= 80%`).
*   **Exports**: `test_result`, `coverage`.

---

## 9. Extensibility

*   **Custom Flows**: Users add JSON files to `.flow/flows/`.
*   **Registry Loading**: The Engine scans the flow directory at startup and validates all definitions (§7).
*   **[B6 Fix] Registration Errors (Fail-Fast)**: Invalid flow definitions MUST cause Engine startup to abort with `SchemaError`, consistent with the Explicit Registry principle applied to Atoms (`01_03` §H3), Skills (`01_07` §5.2), and LLM Providers (`01_06` §3). Silent exclusion via `WARNING` logs violates the security invariant and enables "silent drift" (`bad_ideas_and_traps_to_avoid.md` §2).
    *   **Development Override**: The CLI flag `flow start --warn-invalid-flows` MAY downgrade flow validation failures to `WARNING` (with the invalid flow excluded from the registry). This flag is intended for development environments only and MUST NOT be used in production (enforced via documentation and operational runbooks, not code).
    *   **Rationale**: A flow definition with a typo (e.g., `"on_failure": "retyr"`) would previously be silently dropped. The operator sees "Engine started successfully" with no indication that one of their flows was rejected. The first symptom is a `FlowNotFoundError` at invocation time — hours or days later — with no link back to the validation failure.

---

## 10. Known Edge Cases

> [!NOTE]
> The following are known non-obvious failure modes discovered during architectural review. Each MUST be addressed during implementation or documented as an explicit accepted risk.

### 10.1 Orphan Sub-Flow After Parent Crash (Two-Phase Commit)

If the parent flow crashes *after* spawning a sub-flow but *before* persisting the call stack update, the sub-flow may complete successfully — but the parent has no record of it. On resume, the parent re-enters the sub-flow step, spawning a *second* instance.

**Impact**: Data corruption. Duplicate side-effects. Inconsistent state.

**Target Mitigation (Phase 1.5)**: This is exactly why the ACID database is the target state (§5). The sub-flow creation and parent call-stack update **must** be a single atomic transaction (Two-Phase Commit, §4.3). The Engine MUST:
1.  Write "Starting Child X" intent record to DB.
2.  Spawn child flow.
3.  Child confirms start → DB commit.
4.  If crash between (1) and (3): on restart, parent sees intent record, checks child status, and either attaches or aborts.

**MVP (Steel Thread) Interim**: Before the ACID DB, the single-writer JSON approach with intent files (§4.3) provides crash-safety for the common case. The intent file mechanism detects orphans on restart and reconciles them. This is sufficient for V1's single-worker, sequential execution model.

### 10.2 Circular Resource Lock Deadlock

If sub-flow A acquires a lock on `git-repo` and then invokes sub-flow B, which tries to acquire the same lock, the system deadlocks.

**Mitigation** [V2 — Phase 1.5]: Add a `requires_lock: ["resource_name"]` field to flow step definitions. The Engine acquires locks in **sorted order** (alphabetical by resource name) before entering a sub-flow, preventing deadlocks via consistent lock ordering. Further, strict **Mutex Reentrancy** (§4.6) must be enforced so a child flow can safely re-enter a lock held by its parent. For V1, the leased mutex expiry (§6.2, 60-second TTL) is the backstop.

### 10.3 Context Size Explosion Across Steps

If a flow has 20+ steps, each exporting 64KB, the `FlowContext.variables` grows beyond the 512KB limit (§3.2 rule 5). Without auto-dehydration, the entire context is serialized on every step completion, causing I/O bottlenecks and LLM context window overflow.

**Mitigation**: The auto-dehydration policy (§3.2 rule 5) handles this by promoting the oldest exports to blob pointers when the 512KB threshold is exceeded. However, implementers MUST be aware that dehydrated values are no longer directly usable in `${var}` interpolation — the Variable Resolver (§2.2 rule 4) must hydrate them on access.

### 10.4 `ignore` on Failure + Required Exports

If a step has `on_failure: ignore` and its `export` block contains `required: true` entries, the Engine encounters a contradiction: the step was skipped, but downstream steps depend on its exports.

**Resolution**: The Engine MUST raise `SchemaError` at **load time** if a step with `on_failure: ignore` contains any `required: true` exports. These two configurations are mutually exclusive. This is a static validation check (§7). The same contradiction applies to `on_failure: catch` when **all** `catch_rules[].action` entries resolve to `ignore` — if every error path skips the step, required exports can never be produced. The Engine MUST raise `SchemaError` at load time for this combination as well.

### 10.5 Blob Pointer Reverse Hydration (Dehydration Trigger)

When a sub-flow exports a 200KB result via its `export` block, the Engine must decide *when* to dehydrate it to a blob pointer. The spec defines hydration (pointer → value, §2.2 rule 4) but the reverse (value → pointer) timing was previously ambiguous.

**Resolution**: Dehydration occurs at the **sub-flow export boundary** (§3.2 rule 6). When the Engine maps sub-flow exports to the parent context, any value exceeding 8KB (`MAX_INLINE_SIZE`) is auto-dehydrated. The parent receives a blob pointer, not the raw data. The Variable Resolver transparently hydrates on `${var}` access.

### 10.6 Resume After Partial Teardown (Half-Interrupted Stack)

If the Engine crashes *during* the SIGTERM teardown sequence (§6) — e.g., after marking frames 1 and 2 as `INTERRUPTED` but before marking frame 3 — the call stack has mixed states on resume.

**Resolution**: The resume algorithm (§5.2) walks to the deepest frame regardless of state. If it finds an `IN_PROGRESS` frame below `INTERRUPTED` frames, it treats the entire stack as needing recovery. The `IN_PROGRESS` frame is the true resume point. The `INTERRUPTED` frames above it are re-evaluated: if their sub-flow completed (check DB), they're marked `COMPLETED`; otherwise, they remain `INTERRUPTED` and are candidates for resume.

### 10.7 Fan-Out Abort Signal Across Sub-Flow Boundaries (V2 Reserved)

When V2 introduces parallel branches inside a sub-flow, the `abort_event` (`threading.Event`) must propagate across the sub-flow boundary. The Engine must inject the **same** `abort_event` reference from the parent flow into all child sub-flows spawned within a Fan-Out operation.

**V1 Action**: The `abort_event` field is **reserved** in `FlowContext` (§3.2) but unused. This prevents a schema-breaking change when V2 parallelism is implemented.

### 10.8 Missing Blob Hydration Failure [M1]

If a dehydrated blob pointer points to a file deleted by an admin or corrupted disk, Variable Resolution crashes the Orchestrator with an unexpected OS error.
**Resolution**: The Variable Resolver MUST catch `FileNotFoundError` and explicitly raise a handled `ContextHydrationError`. This allows the Engine to mark the step as `FAILED` rather than crashing the primary daemon event loop.

### 10.9 Cancellation During WAITING State [M2]

If a flow is paused for human approval (`WAITING`), overwriting its frame with `INTERRUPTED` during `SIGTERM` teardown (§6.1) loses the pending semantic status. On reboot, operators cannot tell if a flow was waiting for input or actively processing.
**Resolution**: Teardown propagation explicitly skips frames that are already `WAITING`.

### 10.10 Step-Level Lock Release on Teardown [M3]

Waiting 60 seconds for a lock lease to naturally expire after a `SIGTERM` (§6.2) unnecessarily delays subsequent restarts or unblocks other flows awaiting that lock.
**Resolution**: The Engine explicitly releases any `requires_lock` resources held by the terminating frame directly during teardown before unwinding.

### 10.11 Worker Concurrency & Split-Brain Resume [M4]

If two CLI users/workers run `flow resume <id>` simultaneously against the shared state DB, they could execute duplicate steps.
**Resolution**: The `IN_PROGRESS` state must be bound to an active `Worker_ID` and `lease_expiry` field inside the DB to deterministically lock the flow to a single execution thread.

### 10.12 Unintended Sub-flow Restarts on `on_failure: retry` [M5]

If a child sub-flow exhausts its `total_retry_budget`, and the parent step specifies `on_failure: retry`, the parent's `retry` strategy would blindly `resume` the child, which would instantly fail again because the global budget is exhausted.
**Resolution**: The `total_retry_budget` acts as an absolute global ceiling. Once hit, it overrides the parent's `retry` instruction, forcing the parent to abruptly `halt` (per §3.3.1 rule 2).

### 10.13 Config Drift Tolerance on Resume [M6]

A strict SHA-256 hash comparison on resume prevents resuming if a comment changes or non-essential args are tweaked by a developer during debug.
**Resolution**: The CLI provides a `--force-resume` flag to bypass the `ConfigVersionMismatchError`. **Scope**: `--force-resume` bypasses ONLY the `flow_definition_hash` check (§5.3 check 2). The `flow_version` check (§5.3 check 1) is **NEVER** bypassed — major version changes indicate breaking structural changes that force-resume cannot safely handle. For version mismatches, the only option is `flow restart <task_id> --force` (full restart from step 0).

**[Stale Args Guard]**: When `--force-resume` is used and the flow definition hash has changed, the Engine MUST check whether any sub-flow frames in the call stack were created with `frozen_genesis_args` that reference `args` templates now absent or structurally changed in the new flow definition. Specifically: for each sub-flow frame with non-null `frozen_genesis_args`, the Engine MUST re-resolve the parent step's `args` block against the *new* flow definition and compare the resulting key set against the persisted `frozen_genesis_args` key set. If the key sets diverge (keys added, removed, or types changed), the Engine MUST raise a `StaleArgsError` for that frame, forcing the operator to either (a) use `--rehydrate-args` on the affected sub-flow, or (b) `flow restart` the task. Without this guard, `--force-resume` after a step restructure silently resumes a sub-flow with arguments that no longer correspond to the parent's intent — the sub-flow executes with stale data while the parent expects the new schema, causing silent data corruption at the export boundary.

**[Security Fix] Mandatory Audit for `--force-resume`**: Every invocation of `--force-resume` MUST generate a `ForceResumeEvent` appended to the `audit.jsonl` log. This event MUST contain: (a) the old `flow_definition_hash`, (b) the new `flow_definition_hash`, (c) the identity of the invoking operator, and (d) the `task_id` and `step_index` being resumed. Without this audit entry, `--force-resume` is equivalent to silently deploying modified code into a running pipeline — a security bypass of the same severity class as undocumented `flow mutate-context` (§5.4). The audit requirement is consistent with the cryptographic chain-of-custody principle established in §5.4.

### 10.14 Recursive Call Stack DB Footprint [M7]

With deep recursion (up to 50 depth), repeatedly serializing and flushing all 50 call stack frames to the state store on every micro-step creates massive write-amplification.
**Resolution**: The Engine should implement delta-writes for the call stack, updating only the actively mutating LEAF frame while maintaining static relational pointers to the unmodified parent frames where possible.

### 10.15 Parent Timeout vs. Child WAITING State Deadlock

If a parent step has `timeout_seconds: 300` and invokes a sub-flow, and the sub-flow enters `WAITING` state (e.g., `ManualInterventionAtom`), the parent's timeout will fire after 300 seconds. However, §6.1 exempts `WAITING` frames from `INTERRUPTED` propagation. This creates a conflict: the parent has timed out, but the child is immune to interruption.

**Resolution**: Parent step-level timeouts (§6.3) override child `WAITING` status. When a parent step's `timeout_seconds` fires on a sub-flow in `WAITING` state, the Engine MUST force-transition the child to `TIMED_OUT` (not `INTERRUPTED`), then apply the parent step's `on_failure` strategy. The §6.1 exemption for `WAITING` applies only to Engine-level `SIGTERM`/`SIGINT` events, NOT to parent step-level timeouts.

### 10.16 Blob Artifact GC for Terminal Flow States

Blob artifacts (`.flow/artifacts/blob_*.json`) are created during auto-dehydration (§3.2 rule 5) and sub-flow export mapping (§3.2 rule 6). The lifecycle of these artifacts for non-COMPLETED terminal states was previously unspecified.

**Resolution** (Blob GC Policy):
| Flow State | Blob Action |
|:---|:---|
| `COMPLETED` | GC eligible — subject to reference check (see below). |
| `CANCELLED` | GC eligible — subject to reference check (see below). |
| `FAILED` | Preserve for `blob_retention_days` (default: 7, configurable in `.flow/config.json`) for forensic analysis, then GC. **[R6 Fix] Administrative Override Recovery Guard**: Before GC'ing blobs for a `FAILED` flow whose retention period has expired, the Engine MUST check whether a `flow mutate-context` command has been applied to the flow (by inspecting the `audit.jsonl` for `AdminMutationEvent` entries referencing this `task_id`). If an admin mutation exists, the flow is a candidate for manual recovery (the admin may transition it to `INTERRUPTED` for resume). Deleting its blobs would make recovery impossible — dehydrated exports would resolve to `ContextHydrationError`. In this case, the Engine MUST defer GC and preserve blobs until the flow is either explicitly cancelled via `flow cancel <id>` or successfully resumed and completed. Without this guard, an admin fixes a flow's context with `flow mutate-context`, schedules a resume, but the 7-day retention expires before the resume runs — the blobs are silently deleted and the resume crashes on hydration. |
| `INTERRUPTED` | Preserve until the flow is either resumed or explicitly cancelled via `flow cancel <id>`. On cancel → GC eligible. |

**[B7 Fix] Reference-Counting GC Guard**: Before deleting any blob artifact, the Engine MUST perform a mark-and-sweep pass against the final `FlowContext.variables` snapshot. A blob file MUST NOT be deleted if any surviving context key still holds a `blob_ref` pointing to it. This prevents data corruption in the following scenario: Step A exports a large value (auto-dehydrated to `blob_A.json`), Step B references `${A.big_data}` but fails with `on_failure: ignore` (→ `SKIPPED`), the flow reaches `COMPLETED`. Without the reference check, GC deletes `blob_A.json`, but the pointer in `variables` is still live — any downstream audit, re-inspection, or administrative query that resolves it triggers a `ContextHydrationError`.

**Implementation**: The GC pass iterates `FlowContext.variables` recursively, collecting all `blob_ref` values into a `live_refs: Set[str]`. Only blob files NOT in `live_refs` are eligible for deletion. This is a O(n) scan over the context, not a file system walk.

### 10.17 Deep Recursion Memory Guard

With the `MAX_CALL_STACK_DEPTH` of 50 (§4.5) and the 512 KB context limit per frame (§3.2 rule 5), the theoretical maximum memory for a fully loaded call stack is approximately 25 MB. As long as the auto-dehydration policy is working correctly, this should not cause issues.

**Accepted Risk (V1)**: No explicit `MAX_CALL_STACK_MEMORY` guard is implemented in V1. The depth limit and per-frame context limit provide an implicit cap. If real-world usage reveals memory exhaustion from deep stacks, a memory-based guard can be added in a future version.

### 10.18 Config Injection Risk via `${config}` Interpolation [FUTURE — Phase 1.5]

The `${config.X}` interpolation syntax (§2.2) resolves values from `.flow/config.json`, which is user-editable. If a user injects malicious content into their config (e.g., SQL injection strings), and a downstream Atom uses this value in a database query after the Phase 1.5 DB migration, it becomes a classic injection attack.

**V1 Status**: Not a concern — no SQL database exists. Config values are only used in file paths and Atom arguments, which are validated by SafePath (01_04 §3.3) and the Atom's own input validation.

**Phase 1.5 Action Required**: When the ACID DB (SQLite WAL) is introduced, all Atoms performing SQL operations MUST use parameterized queries. Config values MUST be treated as untrusted input in any database context. String interpolation of `${config}` values directly into SQL is forbidden.

### 10.19 `flow mutate-context` on IN_PROGRESS Flows

If an admin attempts to use `flow mutate-context` on a flow that is currently `IN_PROGRESS` (actively executing a step), the mutation would corrupt the running step's assumptions about its context, potentially causing data loss or inconsistent state.

**Resolution**: `flow mutate-context` MUST reject mutations on `IN_PROGRESS` flows with an explicit error: `"Flow <id> is IN_PROGRESS. Pause or interrupt the flow before mutating context."` See §5.4 State Guard.

---

## 11. Cross-References

| Spec | Relevant Sections |
|:---|:---|
| `01_03_engine_core_spec.md` | **§3.4.0 (Sub-Flow Delegation — BLOCKING amendment, see §11.1)**, §3.4 (Flow Execution), §3.4.1 (Context Propagation — SUPERSEDED for Flows), §3.4.2 (Nested State), §3.4.4 (Mutex), §4.1 (Crash Barrier — BLOCKING amendment: V2 label removal, see §11.1) |
| `01_04_tooling_spec.md` | §1.3 (Deep Resume / Stack Persistence), §1.3.2 (Process Supervision) |
| `01_05_atoms_spec.md` | §2 (AtomResult/exports), §5 (Non-Atoms / Sub-Flows), §6.2 (Graceful Teardown), §8.3 (Version Drift) |
| `01_07_skills_spec.md` | §4.3 (cleanup() contract), §8.3 (Cleanup Budget for Nested Teardown), §8.5 (Step Pointer Safety on Resume) |
| `roadmap_2026.md` | Phase 1.5 (State DB Prerequisite), Phase 2 (DAG Parallelism) |
| `external_strategy_review.md` | T1.4 (Steel Thread Build Strategy), §Cross-Reference (01_08 finding mapping) |
| `verification_gates_backlog.md` | F1 (Same-Error Abort / Circuit Breaker) |

### 11.1 Spec Amendments Ledger

> [!IMPORTANT]
> The following amendments were made to **other** spec documents as a direct consequence of authoring `01_08`. During `01_08` implementation, the implementer **MUST** verify that the corresponding code modules for these specs also reflect these changes. If the code does not match, the documentation is untrustworthy.

| Amended Spec | Section | Amendment | Rationale |
|:---|:---|:---|:---|
| `01_03_engine_core_spec.md` | §3.4.1 (Context Propagation) | Added **⚠️ SUPERSEDED** notice: blanket "Overwrite" collision policy now defers to `01_08` §2.3 `merge_strategy` within Flow context. Legacy overwrite applies only to non-Flow dispatch paths. | §3.4.1 mandated silent last-write-wins; §3.2 rule 3 mandated `fail` on collision. These are mutually exclusive runtime behaviors for the same operation. Without the supersession notice, an implementer following `01_03` would build an Engine that silently overwrites keys, making all `merge_strategy` logic dead code. |
| `01_05_atoms_spec.md` | §5 item 2 (Non-Atoms / Sub-Flows) | Fixed dangling cross-reference: `01_09_flows_spec.md` → `01_08_flows_spec.md`. | The file `01_09_flows_spec.md` does not exist (`01_09` is the RAG spec). Implementers looking for the sub-flow contract would be sent to a nonexistent file, risking ad-hoc sub-flow dispatch inside Atoms — violating `01_05` §1 rule 4. |
| `01_07_skills_spec.md` | §4.1 (Architecture — Path 1) | Removed phantom `"type": "skill"` step type reference. Path 1 now correctly states Skills are executed **indirectly** through `AgentAtom` (`"type": "atom"`, `"target": "AgentAtom"`). Updated Mermaid diagram edge label accordingly. | §4.1 Path 1 claimed `"type": "skill"` was valid and cross-referenced `01_08` §2.1 as authority. But `01_08` §2.1 only allows `atom` and `flow`. The phantom reference would cause implementers to add `"type": "skill"` support, bypassing `AgentAtom`'s cleanup propagation chain and the ReAct loop's idempotency tokens. |
| `01_03_engine_core_spec.md` | §3.4.0 (Sub-Flow Delegation) | **[BLOCKING — MUST FIX BEFORE IMPLEMENTATION]** Remove `[FUTURE V2]` label from `01_03` §3.4.0. Sub-flow delegation as defined in `01_08` is a V1 first-class feature. The V2 label in `01_03` referred to an older, more dynamic delegation model that has been superseded. **If this amendment is not applied, an implementer reading `01_03` alone will skip sub-flow dispatch entirely, making `type: flow` steps non-functional. This is not a cosmetic fix — it is a prerequisite for all of `01_08` §4.** | An implementer reading `01_03` alone would think sub-flows are V2. This contradicts `01_08` §4 which treats sub-flows as the primary V1 reusability mechanism. |
| `01_03_engine_core_spec.md` | §4.1 (Cleanup Timeout) | **[BLOCKING — MUST FIX BEFORE IMPLEMENTATION]** Remove `[FUTURE V2]` label from `01_03` §4.1. The 5-second cleanup timeout is V1 — `01_08` §6.2 specifies the full nested time budget formula as a V1 contract. **If this amendment is not applied, the Engine will not enforce any cleanup timeout, Skill `cleanup()` calls will hang indefinitely on blocking I/O, and the SIGKILL watchdog (§6.2) has no inner budget to work with.** | §4.1 says cleanup timeout is V2; §6.2 mandates it for V1 nested teardown. These are contradictory. The teardown budget formula is mandatory for correct sub-flow teardown. |
| `fractal_patterns.md` | §3.1 (Workflow Composition) | **[PENDING]** Add note that workflow inheritance (`extends`), mixins (`include`), and templates (`from_template`) are **V2+ features**. V1 flow composition uses only `type: flow` sub-flow invocation as defined in `01_08` §4. | `fractal_patterns.md` predates `01_08` and proposes composition primitives that do not exist in the `01_08` flow definition schema. Without a V2+ annotation, an implementer might attempt to implement these during V1. |
