# Lifecycle Layers — Implementation Guides

> **Status**: DRAFT — First draft, requires discussion and refinement.
> **Date**: 2026-03-08
> **Scope**: Universal. Describes what happens at each layer of the software development lifecycle when using SpecWeaver.
> **Related**:
> - [Methodology Index](methodology_index.md) — consolidated overview
> - [Spec Methodology](spec_methodology.md) — the 10-test battery that gates every layer transition
> - [DMZ Repository](https://github.com/TheMorpheus407/the-dmz) — reference implementation for L4-L5 (Code + Review)

---

## Overview

SpecWeaver spans the entire software development lifecycle, from business idea to deployed software. Each layer receives input from the layer above, applies the 10-test battery at the appropriate fractal level, and produces output for the layer below.

```
L1: Business Engineering   → Feature Spec
L2: Architecture/Design    → Component Decomposition
L3: Specification          → Component Specs (implementable)
L4: Implementation         → Code + Tests
L5: Review/Verification    → Reviewed, validated code
L6: Integration/Deploy     → Released software
```

**Key principle**: Every layer transition is gated by the 10-test battery. A Feature Spec must pass structure + completeness tests before it flows to L2. A Component Spec must pass before it flows to L4. Code must pass before it flows to L5.

---

## L1: Business Engineering

> *"We need feature X"* → Feature Spec

### Actors
- **Primary**: Product Owner (PO), Business Analyst, Customer
- **Agent role**: Assistive — helps structure requirements, asks clarifying questions, identifies ambiguities. Does NOT invent requirements.
- **HITL gate**: PO approves the Feature Spec before it flows to L2.

### Input
- Customer request, user story, market need, bug report
- Existing project documentation (SOUL.md / Constitution equivalent)

### Process
1. HITL describes the feature in natural language
2. Agent structures it into Feature Spec format (Intent, Blast Radius, Change Map, Integration Seams, Sequence)
3. Agent runs Completeness Tests 6-10 on the draft:
   - T6: "You haven't included a concrete user scenario — what does Alice see when she uses this?"
   - T8: "Your description says 'should handle errors appropriately' — what specifically happens on error?"
4. HITL and agent iterate until the Feature Spec passes all completeness tests
5. Agent runs Structure Tests 1-5 to verify the feature isn't too broad
6. HITL approves

### Quality Gate (Feature Spec level)
- Structure Tests 1-5 at L1 thresholds (allow ≤2 conjunctions, ≤3 test setups)
- Completeness Tests 6-10 at L1 thresholds (allow ≤3 weasel words, need ≥1 user scenario)

### Output
- Feature Spec (≤10KB) with: Intent, Blast Radius, Change Map, Integration Seams, Sequence
- Approved by HITL

### Open Questions
- How much can an agent help with requirement discovery? (Without hallucinating requirements that the PO didn't ask for)
- Template for Feature Spec — should it be standardized or flexible per project?

---

## L2: Architecture / Design

> Feature Spec → Component Decomposition

### Actors
- **Primary**: Senior Developer / Architect
- **Agent role**: Propositive — suggests decomposition based on component boundaries, identifies integration seams. HITL decides.
- **HITL gate**: Architect approves the decomposition before component specs are written.

### Input
- Approved Feature Spec from L1
- Existing Component Specs (to identify which components are affected)
- Component Hierarchy Map (for dependency direction analysis)

### Process
1. Agent reads the Feature Spec and identifies affected components (Change Map section)
2. Agent proposes a decomposition: "component A gets change X, component B gets change Y"
3. For each proposed component change, agent runs readiness tests:
   - "Is this change one responsibility?" (T1)
   - "Can it be tested in one setup?" (T2)
   - "Does it depend only downward?" (T4)
4. If any test fails, agent proposes further splitting
5. Architect reviews and approves the decomposition

### Quality Gate
- Each component change passes Structure Tests 1-5 at L2 thresholds
- The decomposition covers 100% of the Feature Spec's Change Map (no gaps)
- Integration Seams are explicitly defined (no implicit coupling)

### Output
- Updated Component Spec list: which specs to create or modify
- Integration Seam definitions (shared contracts between components)
- Build sequence (what depends on what)

### Reference Implementation
The DMZ repository's `auto-create-issues.sh` ([source](https://github.com/TheMorpheus407/the-dmz)) implements a version of this: an agent reads all documentation and creates GitHub issues from it. Key patterns to adopt:
- Agent reads ALL project context before proposing decomposition
- One issue (component change) at a time — not batch
- Deduplication against existing work
- Acceptance criteria checklist per issue

### Open Questions
- How to handle decomposition disagreements between agent and architect?
- Can decomposition be validated automatically? (Compare blast radius of decomposition against Feature Spec's Change Map — any uncovered areas?)

---

## L3: Specification

> Component Decomposition → Implementable Component Specs

### Actors
- **Primary**: Developer (or senior developer for complex components)
- **Agent role**: Co-author — agent drafts spec sections, developer reviews and refines. Both iterate.
- **HITL gate**: Developer signs off that the spec is implementable.

### Input
- Component changes from L2 decomposition
- Existing Component Spec (if updating)
- 5-Section Template (Purpose / Contract / Protocol / Policy / Boundaries)

### Process
1. Agent creates or updates the Component Spec using the 5-section template
2. Agent fills in each section based on the Feature Spec's requirements for this component
3. Full 10-test battery runs on the spec:
   - Structure Tests 1-5 at L2 thresholds
   - Completeness Tests 6-10 at L2 thresholds
4. Any failures → agent and developer iterate:
   - Structure failure → split or restructure
   - Completeness failure → add missing detail (examples, error paths, done definition)
5. Static analysis gate (free, instant) catches obvious problems
6. LLM Spec Review Pipeline (PO → Architect → Junior Dev) runs on specs that pass static gate

### Quality Gate
- All 10 tests pass at L2 (module) thresholds
- Spec is within 25KB budget
- Every public interface has ≥1 concrete example
- Every error path is defined
- Done Definition references specific, runnable tests

### Output
- Component Spec (≤25KB) following the 5-section template
- Approved by developer

### Tools
- `sw check --level=module spec.md` — static 10-test battery
- Spec Review Pipeline (`spec_review_pipeline.md`) — LLM semantic review

---

## L4: Implementation

> Component Spec → Code + Tests

### Actors
- **Primary**: Developer or Implementation Agent
- **Agent role**: Primary implementer — agent writes code from the spec. Developer reviews.
- **HITL gate**: Code review before merge.

### Input
- Approved Component Spec from L3
- Existing codebase

### Process
1. Agent reads the entire Component Spec
2. Agent researches existing codebase (imports, interfaces, patterns)
3. Agent implements in small, testable increments
4. For each increment: write code → write test → run test → commit
5. Agent runs readiness tests on resulting code:
   - T1 (One-Sentence): Does each class/function do one thing?
   - T2 (Single Test Setup): Does each test file use one fixture?
   - T4 (Dependency Direction): Do imports flow downward?

### Quality Gate
- All tests pass
- Code coverage ≥ 70% (per user rule)
- Readiness tests at L3 (class) and L4 (function) thresholds pass
- No weasel patterns in code (TODO without issue link, bare except, etc.)

### Output
- Implementation (source files + tests)
- Ready for review

### Reference Implementation: DMZ `auto-develop.sh`
The DMZ repository ([github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz)) provides a production-proven implementation of this layer:

**DMZ's 4-Phase Implementation Loop:**
```
Research → Implement → Review A → Review B → Finalize
    │          │           │            │          │
 Read docs   Write code   Agent 1     Agent 2    Commit
 Read issues  Run tests   checks      checks     Push
 Read memory              15-point    15-point   Close issue
                          checklist   checklist
                              │
                          DENIED → loop back to Implement
```

**Key patterns to adopt:**
1. **Research before implementing**: Agent reads ALL relevant docs (SOUL.md, MEMORY.md, Design Docs) before writing code. Prevents hallucinated architecture.
2. **Small, testable increments**: AGENTS.md mandates "implement in small, testable increments."
3. **Tests before commit**: "Never commit without passing tests."
4. **MEMORY.md updates**: Agent updates living memory after significant work — maintains project state awareness across sessions.
5. **Log artifacts**: All research, implementation, and review artifacts saved to `logs/issues/{N}/` for traceability.

**DMZ patterns NOT to adopt:**
- `--dangerously-skip-permissions` / `--yolo` — agents run with full dev permissions. SpecWeaver must maintain deployment isolation.
- Infinite retry loop — DMZ's implement→review loop can theoretically cycle forever. SpecWeaver needs a max-iteration bound.

---

## L5: Review / Verification

> Code → Reviewed, validated code

### Actors
- **Primary**: Reviewer Agent (read-only) + HITL final approval
- **Agent role**: Adversarial critic — searches for bugs, spec violations, security issues. **Cannot edit code.**
- **HITL gate**: Human approves merge after agent review.

### Input
- Implementation from L4
- Component Spec the code was built from
- Project-specific Review Checklist (see [Review Checklists](review_checklists.md))

### Process
1. Reviewer agent reads the code changes
2. Reviewer agent reads the corresponding Component Spec
3. Reviewer agent runs the project-specific review checklist (item by item)
4. Reviewer agent runs tests (`pytest`, or project-equivalent)
5. Reviewer agent produces a structured verdict: ACCEPTED or DENIED with specific findings
6. If DENIED → loops back to L4 (Implementation) with specific, actionable feedback
7. If ACCEPTED → HITL reviews the agent's assessment, approves or requests changes

### Quality Gate
- All review checklist items pass
- All tests pass
- Code matches spec (every Contract item implemented, every Protocol followed, every Policy configurable)
- No new warnings or regressions

### Output
- Review verdict (ACCEPTED/DENIED with findings)
- Approved code ready for integration

### Reference Implementation: DMZ `reviewer.md`
The DMZ repository's reviewer agent ([github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz)) provides a proven pattern:

**Key patterns to adopt:**
1. **Read-only permissions**: Reviewer cannot edit or write code — only read and run tests. Enforces separation of implement vs. review.
2. **15-point domain-specific checklist**: Issue fit, correctness, security (OWASP), error handling, module boundaries, tests, performance, standards, etc.
3. **Binary verdict**: ACCEPTED or DENIED — no "maybe" or "looks okay I guess." Forces a decision.
4. **Dual review**: Two reviewer agents independently, then merge. Reduces single-reviewer blind spots.

---

## L6: Integration / Deployment

> Reviewed code → Released software

### Actors
- **Primary**: DevOps / CI pipeline
- **Agent role**: Minimal — agents configure pipelines, don't run them in production.
- **HITL gate**: Deploy approval for production.

### Input
- Reviewed and approved code from L5
- CI/CD configuration

### Process
1. Automated CI pipeline runs on merge/PR:
   - Lint + format check
   - Type check (if applicable)
   - Unit tests + coverage threshold
   - Integration tests
   - Security scan (SAST, dependency audit)
   - Build verification
2. Staging deployment (if applicable)
3. HITL approve for production deployment

### Quality Gate
- All CI jobs pass
- No security findings above threshold
- Coverage ≥ 70%
- Build succeeds

### Output
- Deployed software
- Release notes

### Reference Implementation: DMZ CI Pipeline
The DMZ repository's CI configuration ([github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz)):

| Gate | Mechanism | When |
|------|-----------|------|
| Secret detection | `secretlint` pre-commit hook | Every commit |
| Lint on staged files | `lint-staged` pre-commit hook | Every commit |
| Commit message format | `commitlint` commit-msg hook | Every commit |
| TypeScript strict check | `pnpm typecheck` pre-push hook | Every push |
| Full lint + typecheck | CI job 1 | Every PR |
| Unit tests with coverage | CI job 2 (Vitest) | Every PR |
| E2E tests | CI job 3 (Playwright) | Every PR |
| Production build | CI job 4 | Every PR |
| DB migration smoke test | CI job 5 | Every PR |

---

## Layer Interaction Summary

```
L1 Business    ──Feature Spec──►  L2 Architecture  ──Decomposition──►  L3 Specification
                                                                            │
                                                                    Component Specs
                                                                            │
L6 Deploy  ◄──Released──  L5 Review  ◄──Code──  L4 Implementation  ◄────────┘
```

Each arrow is gated by the 10-test battery at the appropriate fractal level.
