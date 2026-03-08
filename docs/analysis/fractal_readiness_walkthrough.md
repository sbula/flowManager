# Fractal Readiness Tests — Walkthrough

> **Status**: DRAFT
> **Date**: 2026-03-08
> **Related**: [Spec Methodology §8](../architecture/spec_methodology.md) — defines the fractal application of readiness tests
> **Purpose**: Concrete demonstration of the 5 readiness tests applied at each level (Feature → Module → Class → Function), using real examples from the SpecWeaver project.

---

## L1: Feature Level — "Flow Execution"

**Subject**: The capability described by `01_08_flows_spec.md` — defining and executing declarative workflows.

### Test 1: One-Sentence

> *Can you describe this feature in one sentence?*

**Attempt**: "Flow Execution allows users to define multi-step workflows in YAML/JSON, execute them sequentially or in parallel, persist state for crash recovery, coordinate sub-flows with variable passing, handle errors with configurable retry policies, and manage mutex locks for shared resources."

**Result**: ❌ **FAIL**. That sentence has 6 "and" clauses. It's at least 4 features pretending to be one:
- Defining workflows (schema)
- Executing workflows (engine behavior)
- Crash recovery (state persistence)
- Error handling and retries (policy)

**Action**: Split into 4 sub-features. Re-test each.

**After splitting**:
- "Flow Definition lets users describe multi-step workflows as JSON/YAML files." → ✅ One sentence, one job.
- "Flow Execution runs a flow definition step-by-step, dispatching each step to an Atom or Sub-Flow." → ✅
- "Flow State persists the execution progress to disk so flows survive process crashes." → ✅
- "Flow Policies configure error handling, retry strategies, and timeout behavior." → ✅

### Test 2: Single Test Setup

> *Does testing this feature require only one kind of test environment?*

**Analysis of 01_08**:
- Schema validation → needs JSON fixtures
- Sequential execution → needs a running engine
- Crash recovery → needs process kill simulation
- Parallel fan-out → needs concurrency environment
- Mutex coordination → needs lock infrastructure

**Result**: ❌ **FAIL**. Five distinct test environments. Confirms the split from Test 1.

**After splitting**: Each sub-feature needs only one environment:
- Flow Definition → JSON fixture files ✅
- Flow Execution → engine with mock atoms ✅
- Flow State → filesystem + simulated crash ✅ (borderline — two concerns, but tightly coupled)
- Flow Policies → config files + error injection ✅

### Test 3: Stranger Test

> *Could a new team member understand this feature from 01_08 alone?*

**Result**: ❌ **FAIL**. To understand 01_08, you must also read:
- `01_03` (Engine Core) — to understand dispatch, parallel execution, blob GC
- `01_05` (Atoms) — to understand what steps invoke
- `01_02` (Status Domain) — to understand how status is tracked
- `01_04` (Tooling) — to understand security boundaries on file writes
- `01_07` (Skills) — to understand how AgentAtom invokes skills

That's 5 external dependencies. A stranger reading 01_08 would be constantly lost.

**After splitting**: Flow Definition spec is self-contained (only references JSON Schema). ✅

### Test 4: Dependency Direction

> *Does this feature only depend on things below it?*

**Analysis**: 01_08 references:
- Engine Core (01_03) — **peer** ❌
- Atoms (01_05) — **below** ✅
- Status Domain (01_02) — **below** ✅
- Tooling (01_04) — **peer** ❌
- Skills (01_07) — **peer** ❌

**Result**: ❌ **FAIL**. 3 peer dependencies. The spec is entangled with its siblings.

**After splitting**: Flow Definition depends only on JSON Schema (below). Flow Execution depends on Atoms (below). ✅

### Test 5: Day Test

> *Could one developer implement 01_08 in one day?*

**Result**: ❌ **FAIL**. 107KB spec. 824 lines. 15+ review cycles. Even after 3 months of spec work, no implementation exists. This is not a "day" of work — it's months.

---

### L1 Summary

| Test | Before Split | After Split (each sub-feature) |
|------|-------------|-------------------------------|
| One-Sentence | ❌ 6 conjunctions | ✅ One sentence each |
| Single Test Setup | ❌ 5 environments | ✅ 1 environment each |
| Stranger | ❌ 5 external deps | ✅ 0-1 external dep each |
| Dependency Direction | ❌ 3 peer deps | ✅ Downward only |
| Day Test | ❌ months | ✅ days to 1 week each |

---

## L2: Module Level — `engine/core.py`

**Subject**: The file `src/flow/engine/core.py` (28KB), which is the current engine implementation.

### Test 1: One-Sentence

> *Can you describe what this module does in one sentence?*

**Attempt**: "The engine core executes flows step by step, resolves variables in step arguments, persists state to disk after each step, and dispatches events to listeners."

**Result**: ❌ **FAIL**. Four distinct verbs = four responsibilities:
- Execute flows (orchestration)
- Resolve variables (data transformation)
- Persist state (I/O)
- Dispatch events (pub/sub)

**Action**: Split into 4 modules:
- `executor.py` — "Processes a flow definition step by step, calling atoms or sub-flows." ✅
- `resolver.py` — "Replaces `${step.key}` placeholders with concrete values from the flow context." ✅
- `state_store.py` — "Saves and loads flow execution state to JSON files." ✅
- `event_bus.py` — "Forwards engine events (step started, step completed, flow failed) to registered listeners." ✅ (this may already exist as `events.py`)

### Test 2: Single Test Setup

> *Does testing `core.py` require only one kind of test fixture?*

**Analysis**:
- Testing execution → needs mock atoms, flow definitions
- Testing variable resolution → needs template strings, context dicts
- Testing state persistence → needs filesystem, temp dirs
- Testing events → needs mock listeners

**Result**: ❌ **FAIL**. Four different fixture types. Each decomposed module would need only one.

### Test 3: Stranger Test

> *Could a new developer understand `core.py` from its code alone?*

**Result**: ⚠️ **BORDERLINE**. At 28KB, a single file is readable with effort — but a new developer would struggle to find where "variable resolution" ends and "state persistence" begins within the file. The responsibilities are interleaved, not cleanly sectioned.

### Test 4: Dependency Direction

> *Does `core.py` only import from lower-level modules?*

**Expected imports**: atoms (below ✅), domain/models (below ✅), LLM provider (peer ⚠️), tools (peer ⚠️), skills (peer ⚠️).

**Result**: ⚠️ **BORDERLINE to FAIL**. A monolithic engine file tends to import everything — it's the "god module" anti-pattern. After splitting, `executor.py` imports from `resolver.py` and `state_store.py` (both below it) — clean direction.

### Test 5: Day Test

> *Could one developer implement this module in one day?*

**Result**: ❌ **FAIL**. 28KB is roughly 700-900 lines of Python. That's at least a week of focused work, plus testing.

**After splitting**: Each sub-module is ~150-250 lines → each is a day or less. ✅

---

### L2 Summary

| Test | `core.py` (monolith) | After Split (4 modules) |
|------|---------------------|------------------------|
| One-Sentence | ❌ 4 verbs | ✅ One verb each |
| Single Test Setup | ❌ 4 fixture types | ✅ 1 each |
| Stranger | ⚠️ Readable but tangled | ✅ Clear boundaries |
| Dependency Direction | ⚠️ God-module imports | ✅ Clean layers |
| Day Test | ❌ ~1 week | ✅ ~1 day each |

---

## L3: Class Level — `FlowExecutor`

**Subject**: After the L2 split, suppose `executor.py` contains a `FlowExecutor` class.

### Well-Sized Example (Passes All Tests)

```python
class FlowExecutor:
    """Processes a flow definition step by step, calling atoms or sub-flows."""
    
    def __init__(self, resolver: VariableResolver, state: StateStore):
        self.resolver = resolver
        self.state = state
    
    def execute(self, flow: FlowDefinition, context: FlowContext) -> FlowResult: ...
    def _execute_step(self, step: StepDef, context: FlowContext) -> StepResult: ...
    def _dispatch_atom(self, step: StepDef, resolved_args: dict) -> AtomResult: ...
    def _dispatch_subflow(self, step: StepDef, resolved_args: dict) -> FlowResult: ...
    def _apply_exports(self, step: StepDef, result: AtomResult, context: FlowContext): ...
```

| Test | Result | Reasoning |
|------|--------|-----------|
| One-Sentence | ✅ | "Processes a flow definition step by step." |
| Single Test Setup | ✅ | One fixture: a mock resolver + mock state store + sample flow definition. |
| Stranger | ✅ | Constructor declares dependencies. Methods are self-explanatory. |
| Dependency Direction | ✅ | Depends on `VariableResolver` and `StateStore` (both injected, both below). |
| Day Test | ✅ | 5 methods, ~100-150 LOC. Implementable in hours. |

**Verdict**: ✅ Ready to implement. No split needed.

### Bloated Example (Fails Tests)

Suppose instead `FlowExecutor` also handled state persistence internally:

```python
class FlowExecutor:
    """Processes flows AND manages state persistence."""
    
    def execute(self, flow, context) -> FlowResult: ...
    def _execute_step(self, step, context) -> StepResult: ...
    def _dispatch_atom(self, step, args) -> AtomResult: ...
    def _dispatch_subflow(self, step, args) -> FlowResult: ...
    def _apply_exports(self, step, result, context): ...
    def save_state(self, task_id, state: dict): ...        # ← state concern
    def load_state(self, task_id) -> dict: ...              # ← state concern
    def _compute_checkpoint(self, context) -> dict: ...     # ← state concern
    def _recover_from_crash(self, task_id) -> FlowContext:  # ← state concern
    def _cleanup_stale_state(self, max_age_hours): ...      # ← state concern
```

| Test | Result | Reasoning |
|------|--------|-----------|
| One-Sentence | ❌ | "Processes flows AND manages state persistence." Two jobs. |
| Single Test Setup | ❌ | First 5 methods need mock atoms. Last 5 need temp filesystem. Two setups. |
| Stranger | ⚠️ | 10 methods — reader must figure out which group does what. |
| Dependency Direction | ❌ | Now imports both `atoms` (for dispatch) AND `os`/`json` (for state I/O) — unrelated concerns. |
| Day Test | ⚠️ | 10 methods, ~250 LOC. Implementable in a day, but testing both concerns together is fragile. |

**Verdict**: ❌ Split. Extract `StateStore` as a separate class.

---

## L4: Function Level — `resolve_variable()`

**Subject**: A single function inside `resolver.py`.

### Well-Sized Example (Passes All Tests)

```python
def resolve_variable(template: str, context: dict) -> str:
    """Replace ${key.subkey} placeholders with values from context.
    
    Args:
        template: String containing ${...} placeholders
        context: Flat or nested dict of available values
    
    Returns:
        String with all placeholders replaced
    
    Raises:
        UnresolvedVariableError: if a placeholder references a missing key
    """
```

| Test | Result | Reasoning |
|------|--------|-----------|
| One-Sentence | ✅ | "Replaces `${key}` placeholders with values from context." |
| Single Test Setup | ✅ | Input: template string + context dict. Output: resolved string. One setup. |
| Stranger | ✅ | Signature + docstring tells you everything. |
| Dependency Direction | ✅ | Pure function. Depends on nothing. |
| Day Test | ✅ | ~20-30 LOC. Minutes to implement. |

**Verdict**: ✅ Ready to implement.

### Bloated Example (Fails Tests)

```python
def resolve_and_validate_and_persist(template: str, context: dict, 
                                      schema: dict, state_path: str) -> str:
    """Replace placeholders, validate result against schema, 
    and persist the resolved context to disk."""
```

| Test | Result | Reasoning |
|------|--------|-----------|
| One-Sentence | ❌ | Three verbs: resolve, validate, persist. Three jobs. |
| Single Test Setup | ❌ | Needs context dicts (for resolution), JSON Schema (for validation), AND temp filesystem (for persistence). |
| Stranger | ❌ | What does this function actually DO? Is it a resolver? A validator? A persister? |
| Dependency Direction | ❌ | Imports `jsonschema` (for validation) AND `os`/`json` (for persistence) — unrelated deps for unrelated jobs. |
| Day Test | ✅ | Probably still < 50 LOC. But fragile — testing requires 3 concerns. |

**Verdict**: ❌ Split into: `resolve_variable()`, `validate_against_schema()`, `persist_context()`.

---

## Cross-Level Comparison

| Aspect | L1: Feature | L2: Module | L3: Class | L4: Function |
|--------|------------|-----------|-----------|-------------|
| **Unit of decomposition** | User story / capability | File / package | Class / struct | Function / method |
| **"Too big" indicator** | Multiple user stories in one doc | Multiple test fixture types in one file | Multiple unrelated method groups | Multiple verbs in function name |
| **"Too tangled" indicator** | > 5 spec cross-references | God-module imports | Constructor with > 5 dependencies | > 3 parameters from different domains |
| **Split produces** | Sub-features (each gets own spec) | Sub-modules (each gets own file) | Helper classes (extract + inject) | Helper functions (extract + call) |
| **Anti-signal (don't split)** | Sub-features can't be tested independently | Sub-modules constantly import each other | Extracted class has only 1 caller | Extracted function is called once from one place |
| **Time to implement** | Weeks → Days | Week → Day | Day → Hours | Hours → Minutes |
| **Test isolation** | Integration test per sub-feature | Unit test file per module | Unit test class per class | One or few test cases per function |
| **Who decides split?** | Architect / PO | Senior developer / Architect | Developer | Developer |
| **Typical failure pattern** | "God spec" (01_08) | "God module" (core.py) | "God class" (does everything) | "God function" (100+ LOC, 10 params) |
