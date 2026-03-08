# SpecWeaver Roadmap: From Current State to Functional Product

> **Date**: 2026-03-08
> **Status**: ACTIVE
> **Context**: Step-by-step plan to evolve FlowManager into a functional product (SpecWeaver). Designed for spare-time development with AI agent assistance. First 5 steps are precise; later steps are intentionally blurry.

> [!IMPORTANT]
> **The Core Principle**: Make it work → Make it right → Make it fast → Make it smart.
> Every step must produce something *runnable*. No step is "just spec work."

---

## Current State (Step 0)

**What exists:**
- ✅ Domain Model: Status parser, models, persister — tested, working
- ✅ LLM Layer: Factory, provider protocol, adapters (Gemini, OpenAI, Anthropic, Ollama) — working
- ✅ Atoms: 7 types (Agent, Assertion, Script, Transform, Webhook, Git, Base) — implemented
- ✅ Skills: Base class + validators (31KB) — no concrete skills yet
- ✅ Tools: File, Shell, Knowledge, System — directory structure, partial implementation
- ✅ Specs: 10 specs (~350KB total) — comprehensive but ahead of implementation
- ⚠️ Engine Core: `engine/core.py` (28KB) — exists but flow execution is unproven
- ❌ Flows: No flow has ever been executed end-to-end
- ❌ Validation Gate: Spec exists, no implementation
- ❌ RAG: Spec exists, no implementation

**What doesn't exist:**
- No flow has ever run from definition → execution → state persistence → resumption
- No Skill has been invoked through the AgentAtom → Skill dispatch path
- No real project has been orchestrated by FM

---

## Step 1: Freeze 01_08 — Define the V1 Boundary

> **Goal**: Stop refining. Define what's buildable *now* with JSON files.

### What To Do
1. Add a **V1 Scope** section at the top of `01_08_flows_spec.md`
2. Tag every section/feature as `[V1]` or `[V2-DB]`
3. The V1 profile includes:
   - Sequential flow execution (no parallel fan-out)
   - Sub-flow invocation (depth ≤ 5)
   - `${step_id.key}` variable resolution
   - Export maps (simple + complex with `required`/`as`)
   - `on_failure`: `fail`, `skip`, `retry` (with `max_retries`)
   - State persistence to JSON files (`.flow_state/`)
   - Crash recovery (resume from last completed step)
   - `WAITING` state (human approval gates)
   - `input_schema` / `output_schema` validation (JSON Schema Draft 7)
4. V2 (deferred until SQLite WAL) includes:
   - Parallel fan-out / fan-in (`map` steps)
   - Mutex / `requires_lock` coordination
   - Two-Phase Commit on sub-flow genesis
   - `total_retry_budget` across nested flows
   - Event sourcing / lineage tracking

### Deliverable
- Updated `01_08_flows_spec.md` with clear V1/V2 markers
- A human-readable summary of "what V1 can do" in 10 bullet points

### Estimated Effort
- 1-2 sessions (agent-assisted tagging + review)

### Lesson Learned from 01_08 Review Cycles
The `spec_review_pipeline.md` failed on 01_08 because 107KB is too large for any single review pass. **For future specs**: max 20-30KB per spec document. If a spec grows beyond that, split it into independent sub-specs (e.g., `01_08a_flow_schema.md`, `01_08b_flow_execution.md`, `01_08c_flow_state.md`).

---

## Step 2: Steel Thread — 3-Level Nested Flow Execution

> **Goal**: Prove the recursive engine works. This is the single most important step.

### What To Do
1. Define a minimal 3-level flow in JSON:
   ```
   RootFlow (parent)
     → Step 1: ScriptAtom (echo "hello")
     → Step 2: ChildFlow (sub-flow)
         → Step 2.1: ScriptAtom (echo "from child")
         → Step 2.2: GrandchildFlow (sub-sub-flow)
             → Step 2.2.1: ScriptAtom (echo "from grandchild")
     → Step 3: ScriptAtom (echo "back in root")
   ```
2. Make the engine execute this flow sequentially, step by step
3. After each step, persist state to `.flow_state/<task_id>.json`
4. Test: kill the process after Step 2.1, restart, verify it resumes at Step 2.2
5. Test: verify all 3 levels complete and the flow reports `COMPLETED`

### Key Engineering Decisions
- State file format: one JSON file per flow instance (not per step)
- Sub-flow state: nested inside parent state (tree structure), not separate files
- Step identity: `flow_name.step_id` (e.g., `RootFlow.step_2.ChildFlow.step_2_1`)

### Deliverable
- A passing test: `tests/integration/test_steel_thread.py`
- The test covers: execute, persist, crash (simulated), resume, complete

### Estimated Effort
- 2-4 sessions. This is the hard part — wiring the engine's recursive execution.

---

## Step 3: Variable Resolution + Export Maps

> **Goal**: Make data flow through the flow graph.

### What To Do
1. Wire up `${step_id.key}` placeholder resolution in step `args`
2. Implement the `export` mechanism: step outputs → parent context
3. Test data flowing **down** into sub-flows (parent injects `${input.x}` into child)
4. Test data flowing **up** from sub-flows (child exports → parent reads `${child_step.result}`)
5. Test the `required: true` export constraint (flow fails if export missing)

### Test Scenario
```
RootFlow:
  Step 1: ScriptAtom(cmd="echo 42") → export: { stdout: "magic_number" }
  Step 2: ChildFlow(input: ${step_1.magic_number})
    → Step 2.1: ScriptAtom(cmd="echo received: ${input.magic_number}")
       → export: { stdout: "child_result" }
  Step 3: AssertionAtom(assert: ${step_2.child_result} contains "42")
```

### Deliverable
- A passing test: `tests/integration/test_variable_flow.py`
- Covers: downward injection, upward export, missing required export → FAILED

### Estimated Effort
- 1-3 sessions. Mostly wiring the resolver and export merger.

---

## Step 4: Real Atom Execution — Run `pytest` via Flow

> **Goal**: Close the loop from "flow definition" → "real work done on a real project."

### What To Do
1. Define a `RunTests` flow that uses `ScriptAtom` to run `pytest` on the SpecWeaver codebase itself
2. Capture test output (stdout/stderr), pass/fail status, coverage percentage
3. Export structured results into the flow context
4. Add an `AssertionAtom` step that fails the flow if test coverage < 70%

### Why ScriptAtom (Not a New Skill)
`ScriptAtom` already exists (`src/flow/atoms/script.py`). It runs shell commands with process isolation. We don't need a new "ScriptSkill" abstraction — that's the LLM-facing layer, which comes later. For now, the flow directly invokes atoms. This is the simplest path to real work.

### Test Scenario
```
RunTests flow:
  Step 1: ScriptAtom(cmd="python -m pytest tests/ --tb=short -q")
     → export: { exit_code: "test_exit_code", stdout: "test_output" }
  Step 2: AssertionAtom(assert: ${step_1.test_exit_code} == 0)
```

### Deliverable
- A flow definition: `.flow/flows/run_tests.json`
- A passing integration test that runs the flow and verifies results

### Estimated Effort
- 1-2 sessions. Mostly integration work.

---

## Step 5: Dogfooding — SpecWeaver Reviews Its Own Specs

> **Goal**: Use the engine to do something *actually useful* on its own codebase.

### What To Do
1. Define a `ReviewSpec` flow:
   ```
   ReviewSpec flow:
     Step 1: ScriptAtom — read the target spec file
     Step 2: ScriptAtom — run a linting/validation check (e.g., markdown structure, cross-ref check)
     Step 3: ScriptAtom — output a structured review report to `.flow/reviews/`
   ```
2. Run this flow on one of the smaller specs (e.g., `01_02_status_domain_spec.md`)
3. The review output should be a real, useful markdown document

### Stretch Goal
If the LLM layer is already wired, replace Step 2 with an `AgentAtom` that uses an LLM to review the spec. This would be the first LLM-in-the-loop flow.

### Deliverable
- A flow definition: `.flow/flows/review_spec.json`
- Flow runs successfully on a real spec
- **This is the "product works" moment** — the first time SpecWeaver does something useful

### Estimated Effort
- 1-2 sessions.

---

## Step 6: Rename to SpecWeaver

> **Goal**: Solidify the identity now that the engine runs.

### What To Do
1. Rename `pyproject.toml`: `name = "specweaver"`
2. Rename `src/flow/` → `src/specweaver/` (or `src/sw/`)
3. Update all imports
4. CLI entry point: `sw` (short, fast to type)
5. Update `README.md`, `00_MASTER_OVERVIEW.md`
6. `workflow_core/` → `archive/workflow_core_v7/` with a README tombstone

### Estimated Effort
- 1 session (mostly search-and-replace + import fixes)

---

## Step 7: First LLM-Powered Flow

> **Goal**: An LLM generates or reviews code within a SpecWeaver flow.

### What To Do
1. Wire the `AgentAtom` → LLM provider dispatch path (01_06 bindings are already implemented)
2. Define a `CodeReview` flow:
   ```
   Step 1: ScriptAtom — read a Python file
   Step 2: AgentAtom(persona="Architect", skill="CodeReviewSkill") — review the file
   Step 3: ScriptAtom — write the review to .flow/reviews/
   ```
3. This is the first flow that involves an LLM — the moment SpecWeaver becomes an *agentic* tool

### Estimated Effort
- 2-3 sessions. Wiring AgentAtom → LLM → SkillResult → export.

---

## Step 8: Validation Gate MVP

> **Goal**: The highest-leverage unique feature — deterministic hallucination prevention.

### What To Do
1. `SymbolExtractor` using Python `ast` module — extract all function/class/method signatures
2. `IndexManager` — deterministic JSON output (`.machine-doc/symbols.json`)
3. `ValidationGate.validate()` — symbol existence check, signature compatibility
4. Integrate into the write path: agent output → gate → file write
5. Structured JSON errors back to the agent on failure

### Estimated Effort
- 3-5 sessions. This is real engineering, but well-scoped for Python-only.

---

## Step 9-12: The Blurry Future (Months 3-6)

These steps depend on learnings from Steps 1-8. Order and scope will shift.

| Step | What | Why | Blurriness |
|------|------|-----|------------|
| **9** | Persona system wired end-to-end | Expert personas hydrated into LLM calls with temperature presets, checklist injection | Medium |
| **10** | Spec readiness gate (`sw check`) | Static analysis tool (~200 LOC) implementing the [5 readiness tests](../architecture/spec_methodology.md) with [static automation](../analysis/static_spec_readiness_analysis.md). Catches the 01_08 problem before LLM tokens are spent. | Medium |
| **11** | SQLite WAL state backend | Replace JSON files when parallel execution is needed | High |
| **12** | First external project | Use SpecWeaver on a real, non-SpecWeaver target project | High — depends on all prior steps |

---

## Timeline Estimate (Spare-Time + Agents)

```
Step 1: Freeze V1         ████                     (~1 week)
Step 2: Steel Thread       ████████                 (~2 weeks)
Step 3: Variable Flow        ██████                 (~1-2 weeks)
Step 4: Real Atoms             ████                 (~1 week)
Step 5: Dogfooding               ████               (~1 week)
Step 6: Rename                     ██               (~2-3 days)
Step 7: LLM Flow                    ██████           (~2 weeks)
Step 8: Validation Gate               ████████████   (~3-4 weeks)
                          ─────────────────────────────────────
                          Week 1    Week 4    Week 8    Week 12
```

> [!TIP]
> **Agent leverage**: Steps 2-4 (engine wiring) are prime candidates for agent-assisted implementation. The specs are detailed enough to serve as prompts. Steps 7-8 require more human judgment.

---

## Success Criteria

The product is "functional" when you can:
1. ✅ Define a flow in JSON
2. ✅ Run it via CLI (`sw run <flow>`)
3. ✅ It executes atoms, passes data between steps
4. ✅ It survives a crash and resumes
5. ✅ It can invoke an LLM to generate or review code
6. ✅ The Validation Gate catches hallucinated symbol references
7. ✅ You've used it on a real project that isn't SpecWeaver itself

When criteria 1-5 are met, the tool is **usable**. When 6-7 are met, it's **useful**.
