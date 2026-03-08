# SpecWeaver MVP — Feature Definition

> **Status**: PROPOSAL — Requires HITL approval before implementation.
> **Date**: 2026-03-08
> **Decisions**: Python for generated code ✅, L2 skipped ✅, Deployment isolation ✅, Per-layer rule config ✅, Typer CLI ✅, Gemini API ✅
> **Related**:
> - [Methodology Index](../architecture/methodology_index.md) — methodology framework
> - [Lifecycle Layers](../architecture/lifecycle_layers.md) — L1-L6 layer definitions
> - [Spec Methodology](../architecture/spec_methodology.md) — 10-test battery, 5-section template
> - [Completeness Tests](../architecture/completeness_tests.md) — second axis (detail)
> - [DMZ Repository](https://github.com/TheMorpheus407/the-dmz) — reference implementation for L4-L5

---

## Deployment Isolation (Critical Constraint)

SpecWeaver is a **tool that operates ON projects**. It does NOT live inside the target project.

```
SpecWeaver (the tool)                     Target Project (the product)
──────────────────────────                ─────────────────────────────
c:\specweaver\                            c:\projects\my-app\
  src/specweaver/                           .specweaver/          ← SW metadata
    cli.py                                    config.yaml
    validation/                               reports/
    drafting/                               specs/                ← drafted here
    implementation/                           greet_service_spec.md
    review/                                 src/                  ← generated here
    llm/                                      greet_service.py
    config/                                 tests/                ← generated here
  tests/                                      test_greet_service.py
  pyproject.toml
```

- SpecWeaver knows the target via `--project <path>` flag or `SW_PROJECT` env var
- Target project has NO dependency on SpecWeaver (no imports, no runtime link)
- `.specweaver/` in the target is a metadata folder (reports, config) — like `.git/`
- SpecWeaver can also run from a Podman container, mounting the target project as a volume

---

## The Core Loop

```
  F2: Draft ──→ F3: Validate Spec ──→ F4: Review Spec ──→ F5: Implement
                     │                      │                    │
                  (rules)              (LLM semantic)        (LLM codegen)
                     │                      │                    │
                     ▼                      ▼                    ▼
              PASS → proceed         ACCEPTED → proceed    F6: Validate Code
              FAIL → fix & retry     DENIED → back to F2        │
                                                            F7: Review Code
                                                                 │
                                                            ACCEPTED → done
```

**Validation vs Review** (both for specs and code):
- **Validation** = automated rules, free, instant, runs FIRST
- **Review** = semantic LLM judgment, token cost, runs AFTER validation passes

---

## Features

### F1: CLI Entry Point (`sw`)

| Command | Purpose | Phase |
|---------|---------|-------|
| `sw init --project <path>` | Set up target project | Setup |
| `sw draft <name>` | Start collaborative spec writing | Drafting |
| `sw validate spec <spec.md>` | Run spec validation rules | Spec QA |
| `sw review spec <spec.md>` | Run spec review (LLM) | Spec QA |
| `sw implement <spec.md>` | Generate code + tests | Implementation |
| `sw validate code <file>` | Run code validation rules | Code QA |
| `sw review code <file>` | Run code review (LLM) | Code QA |

### F2: Spec Drafting (`sw draft`)

Interactive session. Agent and HITL co-author a Component Spec.
- **Asks questions** based on the 5-section template (Purpose, Contract, Protocol, Policy, Boundaries)
- **Makes suggestions** — proposes content for each section
- HITL accepts, modifies, or rejects suggestions
- Agent flags completeness gaps
- Output: `<name>_spec.md` — DRAFT, not yet validated/reviewed
- LLM required (via adapter interface)

### F3: Spec Validation (`sw validate spec`)

Automated rules against a spec file. Uniform rule interface — all rules run, results collected, caller decides next action.

| ID | Rule | Method | Draft Implementation |
|----|------|--------|---------------------|
| S01 | One-Sentence | Static | Conjunction count in Purpose |
| S02 | Single Test Setup | Static | H2/H3 section count |
| S03 | Stranger | LLM | Summarization from Purpose alone |
| S04 | Dependency Direction | Static | Cross-ref direction scan |
| S05 | Day Test | Static | Word/section count heuristic |
| S06 | Concrete Example | Static | Code block presence in Contract |
| S07 | Test-First | LLM | Test generation from Contract alone |
| S08 | Ambiguity | Static | Weasel word scan |
| S09 | Error Path | Static | Error/failure keyword search |
| S10 | Done Definition | Static | Verification section check |

All rules are DRAFT implementations with `# DRAFT` markers. Uniform interface ensures independent upgrades.

### F4: Spec Review (`sw review spec`)

LLM semantic evaluation of a spec that passed validation. Assesses meaning, not structure. Output: ACCEPTED or DENIED with findings. Same review module as F7, different prompts.

### F5: Implementation (`sw implement`)

Reads validated+reviewed spec, generates code + tests:
- From Contract: signatures, types, docstrings
- From Protocol: method bodies
- From Policy: configurable parameters
- From examples: test cases
- Output: `<name>.py` + `test_<name>.py` in the target project
- LLM required

### F6: Code Validation (`sw validate code`)

Same rule interface as F3, different rules:

| ID | Rule | Method | Draft Implementation |
|----|------|--------|---------------------|
| C01 | Syntax Valid | Static | Import check |
| C02 | Tests Exist | Static | Test file presence |
| C03 | Tests Pass | Static | Pytest execution |
| C04 | Coverage | Static | Coverage ≥ 70% |
| C05 | Import Direction | Static | Upward import scan |
| C06 | No Bare Except | Static | AST scan |
| C07 | No Orphan TODO | Static | TODO/FIXME grep |
| C08 | Type Hints | Static | AST annotation check |

### F7: Code Review (`sw review code`)

LLM semantic evaluation of code against its source spec. Reviewer is read-only. Output: ACCEPTED or DENIED with findings. Same approach as F4.

---

## Module Map — SpecWeaver (the tool)

```
src/specweaver/
│
├── __init__.py                          # Package root, version
├── cli.py                               # F1: CLI dispatcher
│
├── config/
│   ├── __init__.py
│   ├── settings.py                      # Project paths, env vars, SW_PROJECT
│   ├── layers.py                        # Per-layer config: which rules, thresholds, template, generator
│   └── templates/
│       └── component_spec.md            # 5-section template (MVP; feature_spec.md added for L2)
│
├── llm/
│   ├── __init__.py
│   ├── adapter.py                       # LLMAdapter interface (abstract)
│   └── gemini_adapter.py               # MVP: one concrete adapter
│
├── context/
│   ├── __init__.py
│   ├── provider.py                      # ContextProvider interface (abstract)
│   └── hitl_provider.py                 # MVP: interactive HITL questions
│                                        # Later: file_search, rag, web_search providers
│
├── drafting/
│   ├── __init__.py
│   └── drafter.py                       # F2: Interactive spec drafting (uses ContextProviders)
│
├── validation/
│   ├── __init__.py
│   ├── models.py                        # Rule, RuleResult, Finding interfaces
│   ├── runner.py                        # Runs all rules, collects results
│   └── rules/
│       ├── __init__.py
│       ├── spec/                        # F3: 10 spec rules (s01-s10)
│       │   ├── __init__.py
│       │   ├── s01_one_sentence.py
│       │   ├── s02_single_setup.py
│       │   ├── s03_stranger.py          # LLM
│       │   ├── s04_dependency_dir.py
│       │   ├── s05_day_test.py
│       │   ├── s06_concrete_example.py
│       │   ├── s07_test_first.py        # LLM
│       │   ├── s08_ambiguity.py
│       │   ├── s09_error_path.py
│       │   └── s10_done_definition.py
│       └── code/                        # F6: 8 code rules (c01-c08)
│           ├── __init__.py
│           ├── c01_syntax_valid.py
│           ├── c02_tests_exist.py
│           ├── c03_tests_pass.py
│           ├── c04_coverage.py
│           ├── c05_import_direction.py
│           ├── c06_no_bare_except.py
│           ├── c07_no_orphan_todo.py
│           └── c08_type_hints.py
│
├── review/
│   ├── __init__.py
│   ├── reviewer.py                      # F4 + F7: Unified reviewer
│   └── prompts/
│       ├── spec_review.md               # LLM prompt for spec review
│       └── code_review.md              # LLM prompt for code review
│
├── implementation/
│   ├── __init__.py
│   ├── generator.py                     # F5: Code generation
│   └── test_generator.py               # F5: Test generation
│
└── project/
    ├── __init__.py
    ├── discovery.py                     # Find/validate target project path
    └── scaffold.py                      # Initialize .specweaver/, specs/
```

**Estimated size**: ~25 Python files, ~2500-4000 LOC (excluding tests).

---

## Module Map — Target Project (what SpecWeaver creates)

When `sw init --project <path>` runs on a new project:

```
target-project/
│
├── .specweaver/                         # SpecWeaver metadata (like .git/)
│   ├── config.yaml                      # Project-specific settings
│   └── reports/                         # Validation/review reports (JSON)
│
├── specs/                               # Spec files (drafted by F2)
│   └── greet_service_spec.md
│
├── src/                                 # Generated code (by F5)
│   └── greet_service.py
│
└── tests/                               # Generated tests (by F5)
    └── test_greet_service.py
```

Standard Python project. No SpecWeaver dependency.

---

## Module Responsibilities

| Module | Feature | Input | Output | LLM? |
|--------|---------|-------|--------|------|
| `cli.py` | F1 | CLI args | Dispatches to handlers | No |
| `config/settings.py` | — | Env/flags | Project paths, config | No |
| `config/layers.py` | — | config.yaml | Per-layer rules, thresholds, templates | No |
| `context/provider.py` | — | — | ContextProvider interface | — |
| `context/hitl_provider.py` | F2 | HITL input | Context from user | No |
| `llm/adapter.py` | — | — | Abstract interface | — |
| `llm/gemini_adapter.py` | — | Prompt | LLM response | Yes |
| `drafting/drafter.py` | F2 | HITL interaction | `*_spec.md` (DRAFT) | Yes |
| `validation/runner.py` | F3/F6 | File path | `[RuleResult]` | No |
| `validation/rules/spec/*` | F3 | Spec content | Per-rule result | Mostly no |
| `validation/rules/code/*` | F6 | Code content | Per-rule result | No |
| `review/reviewer.py` | F4/F7 | File + spec | ACCEPTED/DENIED | Yes |
| `implementation/generator.py` | F5 | Spec content | `.py` source | Yes |
| `implementation/test_generator.py` | F5 | Spec content | `test_*.py` | Yes |
| `project/discovery.py` | — | Path/env | Validated project root | No |
| `project/scaffold.py` | — | Project root | `.specweaver/`, dirs | No |

---

## Architecture Constraints

### Spec Type Parameter (Fractal Readiness)
All commands accept a `--type` parameter that selects the spec template and layer config:
```
sw draft greet_service --type component    ← MVP (only option)
sw draft user_auth     --type feature      ← post-MVP (L2)
```
The drafter, validator, reviewer, and generator are **spec-type-agnostic**. They receive their behavior from the layer config. Adding a new layer = adding a config block + optional layer-specific rules. Zero engine changes.

### Per-Layer Rule Configuration
Each layer has its own set of rules, thresholds, templates, and review prompts:
```yaml
# .specweaver/config.yaml
layers:
  component:                       # MVP layer
    template: component_spec.md
    validation_rules: [s01, s02, ..., s10]
    thresholds:
      s01_max_conjunctions: 1      # strict at component level
      s05_max_word_count: 3000
    review_prompt: component_review.md
    generates: code                # output type

  code:                            # MVP layer
    validation_rules: [c01, c02, ..., c08]
    thresholds:
      c04_min_coverage: 70
    review_prompt: code_review.md

  # Post-MVP — just add a block:
  feature:                         # L1 layer
    template: feature_spec.md
    validation_rules: [s01, s05, s08, f01_blast_radius, f02_seam_def]
    thresholds:
      s01_max_conjunctions: 3      # looser at feature level
    review_prompt: feature_review.md
    generates: component_specs     # output = N component specs
```
The validation runner reads `layers.<type>.validation_rules` and `layers.<type>.thresholds`. It does not know which layer it's running — it just applies rules and thresholds.

### LLM Adapter Pattern
```
LLMAdapter (interface)
  ├── generate(prompt, config) → response
  └── supports(capability) → bool

MVP: ONE concrete adapter (Gemini).
Later: Multiple adapters, model routing per task type.
```
Adapter interface defined and used everywhere. Swapping backends = no caller changes.

### Context Provider Interface
```
ContextProvider (interface)
  ├── name: str
  ├── gather(query, project_path) → Context
  └── available() → bool

MVP: HITLProvider (interactive questions).
Later: FileSearchProvider, RAGProvider, WebSearchProvider.
```
The drafter, reviewer, and generator accept a list of context providers. MVP ships with `HITLProvider`. Adding RAG or web search = implement the interface + register in config. Zero changes to existing modules.

### Uniform Rule Interface
```
Rule (interface)
  ├── id: str
  ├── name: str
  ├── run(target_path, content) → RuleResult
  └── category: "spec" | "code"

RuleResult
  ├── rule_id: str
  ├── status: PASS | FAIL | WARN
  ├── findings: list[Finding]
  └── details: str
```
All rules implement this interface. Validation runners collect all results. Users can add custom rules by implementing the interface and registering in the layer config.

---

## Tests (for SpecWeaver itself)

```
tests/
├── unit/
│   ├── test_cli.py                      # CLI dispatch
│   ├── test_settings.py                 # Config loading
│   ├── test_rule_models.py              # Interface compliance
│   ├── test_runner.py                   # Result collection
│   ├── test_spec_rules/                 # Per-rule tests (s01-s10)
│   ├── test_code_rules/                 # Per-rule tests (c01-c08)
│   ├── test_reviewer.py                 # Prompt construction
│   └── test_project.py                 # Discovery, scaffold
│
├── integration/
│   ├── test_draft_flow.py               # F2: drafting → spec
│   ├── test_validate_spec.py            # F3: good/bad specs
│   ├── test_implement_flow.py           # F5: spec → code
│   └── test_full_loop.py               # Full loop: F2→F3→F4→F5→F6→F7
│
└── fixtures/
    ├── good_spec.md                     # Known-good spec
    ├── bad_spec_ambiguous.md            # S08 fails
    ├── bad_spec_no_examples.md          # S06 fails
    └── bad_spec_too_big.md              # S05 fails
```

---

## What's IN / OUT

**IN**: F1-F7, deployment isolation, Python code generation, single-component specs, uniform rule interface, LLM adapter pattern, context provider interface, per-layer rule config, spec type parameter, `sw init`.

**OUT**: L2 decomposition, multi-language, deploy, RAG, git automation, multi-reviewer, Constitution enforcement, Podman containerization. All of these are designed as extensions to the existing interfaces — no restructuring needed.

---

## Resolved Decisions

1. **LLM provider**: Google Gemini API (user has subscription). Use latest available model (gemini-3.1 or current top tier).
2. **CLI library**: **Typer** — modern, type-hint-based, built on Click, most community momentum ("FastAPI of CLIs"). Single external dependency, used by 38%+ of new CLI projects.
3. **Spec template**: Ships with SpecWeaver (in `config/templates/`). Copied to target project on `sw init` for customization.
4. **New repository**: SpecWeaver will be built in a fresh repo. Original project: [github.com/sbula/flowManager](https://github.com/sbula/flowManager). See `docs/ORIGINS.md` for full attribution.
