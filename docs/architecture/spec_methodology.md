# Specification Methodology

> **Status**: DRAFT — Work in progress. Findings consolidated from architectural review; further discussion required.
> **Scope**: Universal. This methodology applies to any project managed by SpecWeaver, including SpecWeaver itself.
> **Date**: 2026-03-08
> **Companion**: [Completeness Tests](completeness_tests.md) — the second axis (detail/implementability), orthogonal to the structure tests defined here.

---

## 1. The Problem This Solves

Specifications tend to grow into monoliths. A spec starts as "define component X" and absorbs every related concern: how X works, how X fails, how X interacts with Y and Z, what X might do in the future. The result is a document that is too large to review, too tangled to implement, and too coupled to test.

**Root cause**: There is no organizing principle that tells the author "this concern belongs HERE, that concern belongs THERE, and when the document hits THIS threshold, split it."

This methodology provides that organizing principle.

---

## 2. Two-Level Spec Model

Specs exist at two levels, corresponding to the fractal decomposition of work.

### Level 1: Feature Spec — "What goes where?"

A Feature Spec decomposes a cross-cutting feature into component-level work items. It is the **single source of truth for the decomposition decision**.

When a stakeholder (customer, PO, architect) requests a feature, it typically crosses component, module, or service boundaries. Before any implementation spec is written, a Feature Spec must answer:

| Section | Question |
|---------|----------|
| **Intent** | What is the feature? What business value does it deliver? |
| **Blast Radius** | Which components does this feature touch? |
| **Change Map** | What is the *nature* of the change in each component? (New interface? Schema change? Behavior change? Configuration?) |
| **Integration Seams** | Where must the component changes agree with each other? (Shared data formats, event contracts, API calls) |
| **Sequence** | What must be built first? What depends on what? |

**Key rule**: The Feature Spec decides *what goes where*. Individual Component Specs do not make this decision — they receive it.

**Analogy**: The Feature Spec is the architect's floor plan. It says "the kitchen goes here, the bathroom goes there, and the plumbing connects them." Individual room specs describe the fixtures and finishes — not where the walls go.

### Level 2: Component Spec — "How does this piece work?"

A Component Spec describes one isolated, implementable unit of the system. It is written **top-down**, driven by the Feature Spec's decomposition — not bottom-up by staring at the component in isolation.

Component Specs use the **5-Section Template** (see §3).

### The Relationship

```
Stakeholder: "I want feature X"
        │
        ▼
┌─────────────────────────────┐
│     FEATURE SPEC            │  ← ONE document per feature
│                             │
│  Intent                     │
│  Blast Radius               │
│  Change Map                 │
│  Integration Seams          │
│  Sequence                   │
│                             │
└─────┬───────┬───────┬───────┘
      │       │       │
      ▼       ▼       ▼
   ┌─────┐ ┌─────┐ ┌─────┐
   │Comp │ │Comp │ │Comp │    ← Component Specs (created or updated)
   │  A  │ │  B  │ │  C  │
   └─────┘ └─────┘ └─────┘
      │       │       │
      ▼       ▼       ▼
   [impl]  [impl]  [impl]    ← Implementation
```

---

## 3. Component Spec Template (5 Sections)

Every Component Spec follows this structure. The sections are not arbitrary — each serves a distinct purpose and prevents a specific failure mode.

### Section 1: Purpose
*One paragraph.* What this component does and why it exists. If this paragraph contains "and" connecting two unrelated responsibilities, the component may need splitting.

### Section 2: Contract
*"What does this component promise?"*

Defines the **shape** of data and interfaces. The component's public face.

- Data models, schemas, field definitions
- Interface definitions (inputs, outputs, invariants)
- Validation rules enforceable at load time (before runtime)
- Examples of valid and invalid inputs

**Boundary test**: Can you validate compliance without running the system? If not, it's behavior, not contract.

### Section 3: Protocol
*"What steps happen and in what order?"*

Defines **runtime behavior** — what the component does when activated.

- Execution sequences and processing loops
- State transitions and their triggers
- Integration points with other components (by interface, never by implementation detail)
- Ordering guarantees

**Boundary test**: Does it describe something that happens over time? If not, it's contract or policy, not protocol.

### Section 4: Policy
*"What constraints are enforced and what's configurable?"*

Defines **rules and tunable parameters** that alter behavior without code changes.

- Configuration schemas with defaults
- Error handling strategies and fallback behaviors
- Limits, thresholds, timeouts
- Override precedence (default → project → component → runtime)

**Boundary test**: Can a non-developer change this via configuration? If not, it's protocol, not policy.

### Section 5: Boundaries
*"What this component does NOT do."*

**This is the most important section.** It prevents scope creep by explicitly listing responsibilities that belong to neighboring components.

- What is NOT this component's job
- Which component owns each excluded responsibility
- Where to look for related concerns

**Why this matters**: When someone (human or agent) wants to add "retry logic" to a data loader spec, Section 5 says *"Error recovery is NOT this component's responsibility — see the Executor component."* Without this section, every spec becomes a magnet for every related concern.

---

## 4. Readiness Tests — "Split or Proceed?"

At any fractal level, before proceeding to implementation, a spec must pass **all five** readiness tests. If any test fails, the spec requires further decomposition.

These tests are **universal** — they do not reference any specific project, technology, or domain.

### Test 1: The One-Sentence Test
> Can you describe what this spec produces in one sentence?

- ✅ *"Takes a file path and returns a validated definition object."*
- ❌ *"Handles loading, executing, persisting state, and recovering from crashes."*

**Failure means**: Multiple responsibilities are bundled. Split by responsibility.

### Test 2: The Single Test Setup Test
> Does testing the entire spec require only one kind of test environment?

- ✅ One fixture type, one mock setup, coherent scope.
- ❌ Part A needs input fixtures, part B needs a running engine, part C needs crash simulation.

**Failure means**: The spec contains multiple components with different testing needs. Split at the test boundary.

### Test 3: The Stranger Test
> Could a competent developer who has **never seen the project** implement this spec by reading only this document plus the interfaces it references?

- ✅ Self-contained. The stranger reads it, understands the contract, writes the code.
- ❌ The stranger must read 4 other specs to understand key concepts. The spec leaks into other domains.

**Failure means**: Insufficient boundary definition. Either define the missing concepts inline or split the spec to reduce cross-references.

### Test 4: The Dependency Direction Test
> Does this spec only depend on components **below** it in the architecture, never on peers or components above?

- ✅ Clean downward dependency (e.g., depends on filesystem, standard library, or lower-level interfaces).
- ❌ Coupled to peers (needs to know how the engine handles retries, how the state store persists, how another module dispatches).

**Failure means**: The spec is entangled with peer components. Split the entangled parts into their respective component specs, or extract the shared concern into its own component.

### Test 5: The Day Test
> Could one developer (or one agent session) implement this spec in roughly one working day?

- ✅ Feels like "sit down, write it, test it, done."
- ❌ Feels like "I'll need multiple sessions, I'll discover unknowns mid-way."

**Failure means**: Too large in scope. Decompose into sub-components that each pass this test.

### Recursive Application

```
Spec under evaluation
  │
  ├─ ALL 5 tests pass → Proceed to implementation
  │
  └─ ANY test fails → Decompose into sub-specs
                         │
                         └─ Run the 5 tests on each sub-spec
                              │
                              └─ Repeat until all pass
```

**Anti-signal** (do NOT split): If the resulting sub-specs would constantly reference each other ("see sub-spec B §3.2"), they are actually one cohesive unit. Reconsider the split boundary.

---

## 5. Size Budgets

Size budgets serve as early warning signals, not hard rules. A spec exceeding its budget almost always indicates mixed concerns.

| Spec Level | Budget | Rationale |
|------------|--------|-----------|
| Feature Spec | ≤ 10KB | Decomposition decisions should be concise. If the mapping is complex, the feature itself may need splitting. |
| Component Spec | ≤ 25KB | A self-contained component should be describable within this budget. Exceeding it suggests the Contract, Protocol, or Policy section has absorbed a concern from another component. |

When a spec exceeds its budget:
1. Check which section is largest
2. Apply the readiness tests to that section alone
3. If it fails any test, extract that concern into its own component

---

## 6. Concern Routing Rules

When writing or reviewing a spec, use these rules to determine where a concern belongs:

| If the paragraph... | It belongs in... |
|---------------------|-----------------|
| Defines the shape of data or an interface | **Contract section** of the component that owns that data |
| Describes what happens at runtime ("when X, then Y") | **Protocol section** of the component that performs the action |
| Describes a configurable parameter or default value | **Policy section** of the component that enforces the constraint |
| Describes what crosses the boundary between two components | **Feature Spec** (Integration Seams section) |
| Describes a future idea or V2 enhancement | **Separate [BLUEPRINT] document** — do not pollute active specs |
| Describes what this component does NOT do | **Boundaries section** of this component |

---

## 7. Automation Potential

> **Detailed analysis**: [Static Spec Readiness Analysis](../analysis/static_spec_readiness_analysis.md)

Most readiness tests can be partially or fully automated using **static code analysis** (no LLM tokens required). The static checks act as a gate: only borderline cases are escalated to an LLM for judgment.

| Test | Static Accuracy | LLM Needed? |
|------|----------------|-------------|
| **One-Sentence** | ~70% (H2 count, verb diversity, conjunction density) | Only for borderline cases |
| **Single Test Setup** | ~85% (keyword category scanning) | No |
| **Stranger** | ~60% (cross-reference count) | For borderline, to judge if refs are necessary vs problematic |
| **Dependency Direction** | ~90% (with component hierarchy map) | No |
| **Day** | ~65% (composite score: size, sections, branches, states) | Only for borderline cases |

**Gate model**: Static checks run on every save/commit (free, instant). LLM is invoked only when static analysis flags a borderline result and the author disputes the flag. Estimated token savings: ~80%.

**Size budget enforcement** is trivially automatable: measure byte count per spec, alert on threshold exceeding.

---

## 8. Fractal Application — Same Tests, Every Level

> **Concrete walkthrough**: [Fractal Readiness Walkthrough](../analysis/fractal_readiness_walkthrough.md) — demonstrates all 5 tests at all 4 levels using real SpecWeaver examples.

The 5 readiness tests are **not specific to specifications**. They are decomposition tests that apply at every level of software architecture. The tests are identical — only the thresholds and input format change.

### 8.1 The Levels

| Level | Unit | Typical Artifact | Example |
|-------|------|-----------------|---------|
| **L1: Feature** | A user-visible capability | Feature Spec | "User authentication with SSO" |
| **L2: Service / Module** | A deployable or importable boundary | Component Spec | "Auth service", "flow_engine module" |
| **L3: Class** | A single abstraction | Source code | `FlowExecutor`, `SymbolIndex` |
| **L4: Function** | A single operation | Source code | `resolve_variable()`, `validate_schema()` |

### 8.2 What Stays the Same (Equalities)

The **test definitions** are identical at every level:

1. **One-Sentence**: Can you describe this unit's single responsibility in one sentence?
2. **Single Test Setup**: Does testing this unit require only one kind of environment/fixture?
3. **Stranger**: Can someone unfamiliar implement/modify this unit from its description + interface alone?
4. **Dependency Direction**: Does this unit only depend on things *below* it, never on peers or above?
5. **Day**: Can one person (or one agent session) complete work on this unit in one sitting?

The **failure response** is also identical at every level: decompose the failing unit into sub-units, then re-test each.

The **anti-signal** is also identical: if the resulting sub-units constantly cross-reference each other, they are one cohesive unit and should not be split.

### 8.3 What Changes (Differences)

#### Thresholds Scale With Level

| Test | L1: Feature | L2: Module | L3: Class | L4: Function |
|------|------------|-----------|-----------|-------------|
| **One-Sentence** conjunctions | ≤ 2 | ≤ 1 | 0 | 0 |
| **Test Setup** categories | ≤ 3 | ≤ 2 | ≤ 1 | 1 |
| **Stranger** cross-references | ≤ 8 | ≤ 5 | ≤ 3 | ≤ 1 |
| **Size** budget | ≤ 10KB (spec) | ≤ 25KB (spec) / ~500 LOC (code) | ~200 LOC | ~30 LOC |
| **Day Test** time scale | weeks | 1 day | hours | minutes |

> [!NOTE]
> Thresholds tighten as you go deeper. A feature is allowed more complexity because it coordinates multiple modules. A function has no excuse for doing two things.

#### Input Format Changes

| Level | Input to Analyze | Parsing Method |
|-------|-----------------|---------------|
| **L1-L2** | Markdown spec (`.md`) | Markdown structure parser (headers, links, keyword scan) |
| **L3** | Source code (`.py`, `.ts`, etc.) | AST parser (class definitions, method count, imports) |
| **L4** | Source code (single function) | AST parser (parameters, branches, calls, LOC) |

The static checks from the [Static Spec Readiness Analysis](../analysis/static_spec_readiness_analysis.md) cover L1-L2. For L3-L4, the same tests use code-level signals:

| Test | Spec Signal (L1-L2) | Code Signal (L3-L4) |
|------|---------------------|---------------------|
| **One-Sentence** | H2 count, verb diversity | Method count per class, function count per module |
| **Single Test Setup** | Environment keyword categories | Fixture count in test file, distinct mock types |
| **Stranger** | Cross-reference count to other specs | Import count from peer modules, undocumented parameters |
| **Dependency Direction** | Links to peer/upper specs | Imports from peer/upper packages |
| **Day** | Composite (size + branches + states) | Cyclomatic complexity + LOC + call depth |

### 8.4 Mapping to Classical Principles

The 5 tests are not new ideas — they unify established software engineering principles under one fractal checklist:

| Readiness Test | Classical Principle | Origin |
|---------------|-------------------|--------|
| One-Sentence | **Single Responsibility Principle** (SRP) | Robert C. Martin, SOLID |
| Single Test Setup | **Cohesion** — things that change together belong together | Larry Constantine, Structured Design (1974) |
| Stranger | **Self-Documentation** / minimal cognitive load | Clean Code, Documentation-Driven Design |
| Dependency Direction | **Dependency Inversion Principle** (DIP) | Robert C. Martin, SOLID / Clean Architecture |
| Day | **Right-Sizing** / task decomposition | Agile story slicing, Goldilocks principle |

The contribution of this methodology is **not** inventing these principles — it's recognizing that they are **the same principles at every level**, and providing a single, automatable checklist that applies fractally from feature down to function.

### 8.5 Tooling Implication

A single tool can enforce all levels:

```
sw check --level=feature  docs/features/user_auth.md          # spec-level
sw check --level=module   docs/specs/flow_loader.md            # spec-level
sw check --level=module   src/specweaver/engine/                # code-level (directory)
sw check --level=class    src/specweaver/engine/core.py         # code-level (file)
sw check --level=function src/specweaver/engine/core.py::execute_step  # code-level (symbol)
```

The `--level` parameter selects the threshold set. The input type (`.md` vs `.py`) selects the parser. The tests themselves are unchanged.

---

## 9. Open Questions (For Further Discussion)

> [!NOTE]
> The following questions were identified during the initial discussion and require further refinement.

1. **Feature Spec ownership**: Who creates the Feature Spec — the PO, the architect, or the HITL during an agent-assisted session? What approval gates apply?

2. **Versioning**: When a component's Contract changes (e.g., new field), how do we propagate that change to all Feature Specs that reference it? Manual cross-reference, or automated dependency tracking?

3. **Legacy spec migration**: How do we migrate the existing 10 specs (~350KB) into this model? Big-bang rewrite, or incremental extraction as we implement each roadmap step?

4. **Spec-to-code traceability**: Should each component spec link directly to the source files that implement it? If so, how do we keep these links accurate as code evolves?

5. **The "too small" problem**: Can a spec be over-decomposed? At what point does splitting create more overhead (many tiny specs with heavy cross-referencing) than the monolith it replaced? What's the lower bound?

6. **Integration Specs**: When the Integration Seams between components are complex (e.g., the handoff between Flow Executor and State Store), does the interaction deserve its own spec? Or does it always live in the Feature Spec?

7. **Spec review sizing**: The `spec_review_pipeline.md` failed on 01_08 (107KB). What is the maximum spec size that can be reliably reviewed in one agent session? Is it defined by token limits, by conceptual complexity, or both?
