# SpecWeaver Methodology — Consolidated Index

> **Status**: DRAFT — All linked documents are drafts requiring further discussion.
> **Date**: 2026-03-08
> **Purpose**: Single entry point to all methodology documents produced in this session. Start here.

---

## The Problem

SpecWeaver's original specs (~350KB across 10 files) failed because they lacked an organizing principle. Specs grew into monoliths mixing data definitions, runtime behavior, policies, and future ideas. The 01_08 flows spec (107KB) was the worst case — 7 concerns in one document, un-reviewable and un-implementable.

This session produced a universal methodology for writing, sizing, and validating specifications that applies at every level of software architecture and across any project domain.

---

## What We Produced

### Framework Documents (the "how to think" layer)

| Document | Type | What It Defines |
|----------|------|----------------|
| [Spec Methodology](architecture/spec_methodology.md) | Architecture | The core framework: two-level spec model (Feature Spec → Component Spec), 5-section template (Purpose/Contract/Protocol/Policy/Boundaries), 5 structure tests, fractal levels, size budgets, concern routing rules |
| [Completeness Tests](architecture/completeness_tests.md) | Architecture | The second axis: 5 completeness tests (Concrete Example, Test-First, Ambiguity, Error Path, Done Definition), two-axis model (structure × completeness), fractal comparison, static analysis sketches |
| [Lifecycle Layers](architecture/lifecycle_layers.md) | Architecture | **DRAFT** — Layer-specific implementation guides (L1 Business → L6 Deploy). DMZ patterns adopted for L4-L5. |
| [Constitution Template](architecture/constitution_template.md) | Architecture | **DRAFT** — Universal template for project constitutions. References DMZ's SOUL.md. |
| [Review Checklists](architecture/review_checklists.md) | Architecture | **DRAFT** — Project-specific review checklist template. Maps DMZ's 15-point checklist to universal categories. |

### Analysis Documents (the "proof it works" layer)

| Document | Type | What It Proves |
|----------|------|---------------|
| [Static Spec Readiness Analysis](analysis/static_spec_readiness_analysis.md) | Analysis | Per-test static automation feasibility. Tests 2 and 4 are ~85-90% automatable with zero LLM tokens. Gate model: static bouncer → LLM judge. ~80% token savings. |
| [Fractal Readiness Walkthrough](analysis/fractal_readiness_walkthrough.md) | Analysis | Concrete application of all 5 structure tests at all 4 levels (L1 Feature, L2 Module, L3 Class, L4 Function) using real SpecWeaver examples. Shows pass/fail with reasoning. |
| [Open Research Items](analysis/methodology_open_research.md) | Analysis | **DRAFT** — First pass on 6 remaining research questions: automated decomposition, threshold calibration, too-small problem, traceability, over-specification, cross-domain calibration. |

### Context Documents (produced earlier, still relevant)

| Document | Type | Relevance |
|----------|------|-----------|
| [FlowManager Re-Evaluation](analysis/flowmanager_reevaluation.md) | Analysis | Project assessment that identified the vision-implementation gap and spec bloat. Root cause analysis for the methodology work. |
| [SpecWeaver Roadmap](proposals/specweaver_roadmap.md) | Proposal | Step-by-step plan from current state to functional product. Steps 1-5 are concrete; 6-12 are blurry. Step 10 now references this methodology. |
| [Flow Synthesis](analysis/flow_synthesis.md) | Analysis | Industry research: DMZ ecosystem, GitHub Spec Kit, Cline Memory Bank, PAR pattern. Contains the DMZ 5-layer analysis. |
| [Spec Review Pipeline](architecture/spec_review_pipeline.md) | Architecture | Multi-stage LLM review process (PO → Architect → Junior Dev). Complementary to the static analysis gate — this is the LLM layer that runs AFTER static tests pass. |

---

## The Big Picture

```
                          A spec is ready when BOTH axes pass
                          
                              TOO VAGUE
                             (no examples,
                              weasel words,
                              no error paths)
                                  ▲
                                  │
                     Completeness Tests 6-10
                                  │
  TOO BIG ◄── Structure Tests 1-5 ┼ ──────────► RIGHT SIZE
  (monolith,                      │              (focused,
   tangled,                       │               decoupled,
   coupled)                       │               one-day scope)
                                  │
                     Completeness Tests 6-10
                                  │
                                  ▼
                            IMPLEMENTABLE
                           (concrete examples,
                            testable, unambiguous,
                            failure defined)
```

### The 10-Test Battery (Universal, Fractal)

| # | Test | Axis | Universal Question | Static? |
|---|------|------|--------------------|---------|
| 1 | One-Sentence | Structure | Is it one responsibility? | ~70% |
| 2 | Single Test Setup | Structure | Is it cohesive? | ~85% |
| 3 | Stranger | Structure | Is it self-contained? | ~60% |
| 4 | Dependency Direction | Structure | Is it decoupled? | ~90% |
| 5 | Day Test | Structure | Is it right-sized? | ~65% |
| 6 | Concrete Example | Completeness | Does it show real I/O? | ~75% |
| 7 | Test-First | Completeness | Can you write a test? | ~50% |
| 8 | Ambiguity | Completeness | Are all decisions made? | ~95% |
| 9 | Error Path | Completeness | Is failure defined? | ~70% |
| 10 | Done Definition | Completeness | Is completion verifiable? | ~80% |

These tests apply at **every fractal level** (Feature → Module → Class → Function) with thresholds that tighten as you go deeper.

### Lifecycle Integration

```
Author writes spec
      │
      ▼
Static Tests 1-10 (free, instant)  ← catches ~80% of problems
      │
  ┌───┼───┐
  │   │   │
PASS BORDER FAIL
  │   │     │
  │   │     └→ Author fixes before proceeding
  │   │
  │   └→ LLM judges borderline cases (minimal tokens)
  │
  ▼
LLM Spec Review Pipeline (2-3 stages)  ← semantic quality review
      │
      ▼
Feature Spec → Component Specs (decomposition)
      │
      ▼
Implementation (can borrow DMZ patterns here)
```

---

## What's Decided

1. **Two-level spec model**: Feature Spec (what goes where) → Component Spec (how it works)
2. **5-section template**: Purpose / Contract / Protocol / Policy / Boundaries
3. **10-test battery**: 5 structure + 5 completeness, applied fractally
4. **Static-first gate**: Run cheap checks before LLM. ~80% token savings.
5. **Fractal application**: Same tests at L1 (Feature) through L4 (Function)
6. **Structure and completeness are orthogonal**: Fixing one doesn't fix the other

## What's Still Open (First Drafts Created — Discussion Required)

All 9 items now have first drafts. They are marked DRAFT and require discussion.

| # | Item | First Draft Location | Status |
|---|------|---------------------|--------|
| 1 | Layer-specific implementation guides (L1-L6) | [lifecycle_layers.md](architecture/lifecycle_layers.md) | DRAFT — needs discussion, especially L1-L3 |
| 2 | Constitution layer | [constitution_template.md](architecture/constitution_template.md) | DRAFT — template ready, needs SpecWeaver-specific instance |
| 3 | Automated decomposition | [methodology_open_research.md §1](analysis/methodology_open_research.md) | DRAFT — hypothesis + DMZ pattern documented |
| 4 | Project-specific review checklists | [review_checklists.md](architecture/review_checklists.md) | DRAFT — template + DMZ mapping done |
| 5 | Threshold calibration | [methodology_open_research.md §2](analysis/methodology_open_research.md) | DRAFT — calibration plan defined, execution pending |
| 6 | The "too small" problem | [methodology_open_research.md §3](analysis/methodology_open_research.md) | DRAFT — lower bound signals proposed |
| 7 | Spec-to-code traceability | [methodology_open_research.md §4](analysis/methodology_open_research.md) | DRAFT — bidirectional linking approach proposed |
| 8 | Completeness vs over-specification | [methodology_open_research.md §5](analysis/methodology_open_research.md) | DRAFT — what/how boundary rule proposed |
| 9 | Cross-domain calibration | [methodology_open_research.md §6](analysis/methodology_open_research.md) | DRAFT — domain profiles approach proposed |

### External References

- **DMZ Repository**: [github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz) — production reference for L4-L5 patterns (auto-develop.sh, reviewer.md, SOUL.md, AGENTS.md, MEMORY.md). Analyzed in [flow_synthesis.md](analysis/flow_synthesis.md) §2.1.
