# Methodology — Open Research Items

> **Status**: DRAFT — First pass on remaining open questions. Each section requires deeper investigation and discussion.
> **Date**: 2026-03-08
> **Related**:
> - [Methodology Index](../architecture/methodology_index.md) — consolidated overview
> - [Spec Methodology](../architecture/spec_methodology.md) — the framework these items extend
> - [DMZ Repository](https://github.com/TheMorpheus407/the-dmz) — reference implementation

---

## 1. Automated Decomposition

> Can an agent decompose a Feature Spec into Component Specs automatically?

### Current State
The [DMZ repository](https://github.com/TheMorpheus407/the-dmz) proves this works at the **issue level**: `auto-create-issues.sh` reads all documentation and creates GitHub issues with acceptance criteria. This is effectively "automated decomposition from docs → tasks."

SpecWeaver's framework defines the decomposition structure (Feature Spec → Component Specs) and the quality gate (10-test battery). What's missing is the **automation bridge**: can an agent read a Feature Spec and propose the decomposition?

### Hypothesis
Yes, but with constraints:
1. The agent needs the **Component Hierarchy Map** (which components exist, dependency levels) as input
2. The agent proposes, the HITL decides — agent should never auto-decompose without review
3. The decomposition must pass Structure Tests 1-5 for each resulting component change
4. The agent should check for completeness: "does the decomposition cover 100% of the Feature Spec's Change Map?"

### Research Needed
- Can the 10-test battery be run on the agent's *proposed* decomposition before it's written into specs?
- What's the failure mode? (Agent misidentifies component boundaries → wrong decomposition → wasted work)
- How does DMZ's `auto-create-issues.sh` handle deduplication against existing work?

### DMZ Pattern to Study
```
auto-create-issues.sh:
1. Reads ALL docs (SOUL.md, MEMORY.md, AGENTS.md, MILESTONES.md, BRD, DDs)
2. Reads ALL existing issues (open + closed for milestone)
3. Creates ONE issue with: title, summary, requirements, acceptance criteria, dependencies
4. Deduplication: checks both open (global) and closed (per milestone) issues
5. Loop until agent outputs DONE 3 consecutive times
```
Source: [github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz)

---

## 2. Threshold Calibration

> Are the current thresholds (5 H2 sections, 3 test environments, 25KB budget, etc.) correct?

### Current State
All thresholds in the methodology are initial estimates based on reasoning and the SpecWeaver experience (01_08 = too big, 01_02 = right-sized). They have NOT been empirically validated.

### Calibration Plan
1. Run the 10-test static battery against all 10 existing specs
2. For each spec, record:
   - Test results (pass/borderline/fail for each of the 10 tests)
   - Known implementation outcome (implemented successfully? failed? never attempted?)
3. Compare: Do the tests correctly predict implementation success/failure?
4. Adjust thresholds to minimize false positives (flagging good specs) and false negatives (passing bad specs)

### Expected Calibration Data

| Spec | Size | Known Outcome | Expected Static Result |
|------|------|--------------|----------------------|
| 01_02 (7KB) | Small | ✅ Implemented well | All PASS |
| 01_03 (12KB) | Medium | ⚠️ Exists but unproven | Some BORDERLINE |
| 01_05 (33KB) | Large | ⚠️ Implemented but broad | Size BORDERLINE, setup BORDERLINE |
| 01_06 (51KB) | Very large | ✅ Clean despite size | Size FAIL — needs calibration |
| 01_08 (107KB) | Monster | ❌ Never implemented | All FAIL |

### Key Calibration Question
The 01_06 case (51KB but well-implemented) suggests file size alone is insufficient. The composite score formula needs weighting that accounts for **focused detail** (many concrete examples, one concern) vs. **scattered breadth** (many concerns, few examples).

---

## 3. The "Too Small" Problem

> Can a spec be over-decomposed? What's the lower bound?

### Hypothesis
Yes. Over-decomposition creates overhead:
- Many tiny specs with heavy cross-referencing (the anti-signal from §4 of the methodology)
- Each spec requires its own review cycle — 20 tiny specs = 20 reviews
- Integration between tiny specs becomes the dominant complexity (instead of within-spec complexity)

### Proposed Lower Bound Signals

| Signal | Problem |
|--------|---------|
| The spec describes < 1 hour of work | Too small — combine with a neighbor |
| The spec's Boundaries section (§5) is longer than its Protocol section (§3) | More time spent defining what it DOESN'T do than what it does — probably part of a larger unit |
| The spec references > 3 other specs for its contract dependencies | It's not self-contained at this size — it should be part of a bigger unit |
| The spec produces a class with < 3 public methods | Consider whether this class is really a helper within another class |

### The Balancing Rule
> **Split until each piece passes the 10-test battery, but DO NOT split past the point where the anti-signal fires** (sub-specs constantly cross-reference each other).

### Research Needed
- Empirical evidence from existing projects: what's the smallest useful spec? 2KB? 5KB?
- Does the number of integration seams grow faster than the number of specs? (If splitting N specs into 2N specs creates 4N integration seams, the cure is worse than the disease.)

---

## 4. Spec-to-Code Traceability

> How to link specs to source files and keep links accurate?

### Problem
When a spec says "the FlowLoader must validate JSON Schema" and the code implements this in `src/specweaver/loader/validator.py`, there's no formal link between them. Over time, drift occurs: specs describe behavior the code no longer follows, or code implements features no spec describes.

### Proposed Approach: Bidirectional Links

**Spec → Code** (in the spec):
```markdown
## Implementation References
- `src/specweaver/loader/validator.py` — JSON Schema validation
- `tests/test_loader_validation.py` — test coverage for this spec
```

**Code → Spec** (in the code):
```python
"""Flow Loader — JSON Schema Validation.

Spec: docs/specs/flow_loader.md §2 (Contract)
"""
```

### Automation Opportunities
- **Link rot detection**: Static scan that checks all spec→code and code→spec links still resolve. Runnable as a pre-commit hook.
- **Coverage gap detection**: Scan spec Contract sections for public interfaces. Scan codebase for matching implementations. Flag gaps.
- **Drift detection**: Compare spec's Contract (interface definition) against code's actual interface (via AST parsing). Flag mismatches.

### Research Needed
- Is bidirectional linking worth the maintenance cost?
- Can link maintenance be automated? (Agent updates links when modifying code.)
- Does any existing tool do this well? (Doxygen has some linking, but it's C-centric.)

---

## 5. Completeness vs. Over-Specification

> Is there a "too detailed" failure mode?

### Hypothesis
Yes. Over-specification constrains the implementer unnecessarily:
- Prescribing internal variable names → agent can't refactor
- Prescribing algorithm choice → agent can't optimize
- Specifying private method signatures → spec breaks when implementation evolves

### Proposed Rule
> **Specify WHAT (Contract) and WHAT HAPPENS (Protocol). Do NOT specify HOW internally.**

| Appropriate Detail | Over-Specification |
|--------------------|--------------------|
| "Returns a sorted list of unique tokens" | "Use `sorted(set(tokens))` to return unique tokens" |
| "Handles missing keys by raising UnresolvedVariableError" | "At line 42, check `if key not in context:` and raise" |
| "Persists state as JSON to `.flow_state/`" | "Use `json.dump()` with `indent=2` and `sort_keys=True`" |

### The Guideline
- **Contract section**: Specify precisely (this IS the interface)
- **Protocol section**: Specify behavior and state transitions, NOT implementation
- **Policy section**: Specify configurable parameters, NOT how they're implemented
- **NEVER specify**: Private method names, internal variable names, specific library calls (unless the library IS the contract, like JSON Schema Draft 7)

### Measuring Over-Specification
Possible static signal: count references to specific code constructs (`use X`, `call Y`, `import Z`) in a spec. If count > 0 outside the Contract section, it may be over-specified. ~70% accuracy.

---

## 6. Cross-Domain Calibration

> Are the thresholds truly universal, or do they need per-domain tuning?

### Hypothesis
The thresholds are **mostly universal** for "spec documents intended for agent implementation," but at least two adjustments may be needed:

### Known Domain Variations

**RFC-style specs (networking, protocols)**:
- The word "should" has a specific meaning per RFC 2119 (SHOULD = recommended but optional, distinct from MUST). The ambiguity scanner (Test 8) must be calibrated to NOT flag RFC-compliant use of "should."
- Proposed fix: A domain flag `--rfc-mode` that adjusts the weasel word list.

**Regulated industries (healthcare, finance)**:
- Completeness requirements are higher — error paths must cover regulatory edge cases
- Test 9 (Error Path) threshold should be stricter: ≥ 3 error paths per interface instead of ≥ 1
- Done Definition (Test 10) must reference compliance requirements, not just test passing

**Embedded / safety-critical systems**:
- Day Test (Test 5) thresholds are different — a safety-critical module may legitimately take longer to implement and review
- Ambiguity tolerance (Test 8) is zero at ALL levels, not just L3-L4

**Data science / ML pipelines**:
- Protocol sections may be inherently stochastic (model training has non-deterministic outputs)
- Concrete Example Test (Test 6) needs adaptation: examples may show ranges rather than exact values
- Done Definition may include statistical criteria ("accuracy ≥ 0.95 on test set") rather than binary pass/fail

### Proposed Approach
- Define a **domain profile** (a set of threshold overrides) for each major domain
- The default profile is the universal one defined in `spec_methodology.md`
- Projects override specific thresholds in their Constitution (`CONSTITUTION.md § calibration`)
- SpecWeaver's `sw check` command accepts `--profile=domain` to apply overrides

### Research Needed
- How many domain profiles are actually needed? (Hypothesis: 3-5 cover 90% of projects.)
- Can domain detection be automated from the project's tech stack? (Python + pytest = standard profile; Python + FDA-compliance = regulated profile)
- Is there a meta-test: "are these thresholds working for THIS project?" — run after N specs and N implementations, compare predicted vs. actual implementability.
