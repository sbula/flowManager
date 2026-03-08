# Static Spec Readiness Analysis

> **Status**: DRAFT — Findings from architectural discussion. Implementation not started.
> **Date**: 2026-03-08
> **Related**:
> - [Spec Methodology](../architecture/spec_methodology.md) — defines the 5 readiness tests this document analyzes
> - [SpecWeaver Roadmap](../proposals/specweaver_roadmap.md) — this analysis feeds future automation (Step 10+)
> - [Spec Review Pipeline](../architecture/spec_review_pipeline.md) — the LLM-based review pipeline that this complements

---

## 1. Problem Statement

The [Spec Methodology](../architecture/spec_methodology.md) defines 5 readiness tests that determine whether a spec is small enough to implement or needs further decomposition. Running all 5 tests via an LLM is expensive (tokens) and unreliable (LLMs are bad at structural counting tasks).

**Question**: How much of the readiness testing can be done with static code analysis (zero LLM tokens) while maintaining useful accuracy?

**Answer**: 2 of 5 tests are fully automatable statically. 3 more can be proxied with structural metrics. Combined, static analysis can gate ~80% of problems before any LLM is involved.

---

## 2. Per-Test Analysis

### 2.1 Test 1: One-Sentence Test — Partially Static (~70% accuracy)

**Goal**: Detect specs with multiple responsibilities.

**Static Signals**:

| Signal | How to Measure | Threshold |
|--------|---------------|-----------|
| H2 section count | Count `## ` markers | > 5 sections → flag |
| Verb diversity in Purpose | Count unique action verbs in §1 Purpose | > 3 distinct verbs → flag |
| Conjunction density | Count "and also", "additionally", "furthermore", "as well as" in §1 | > 2 occurrences → flag |

**What it catches**: Specs with obviously multiple top-level responsibilities (like 01_08 with 10+ H2 sections).

**What it misses**: Specs where one section quietly does two jobs without structural markers. These require semantic understanding → LLM escalation.

**Implementation**:
```python
def test_one_sentence(spec_text: str, purpose_section: str) -> TestResult:
    h2_count = spec_text.count("\n## ")
    conjunctions = sum(purpose_section.lower().count(c)
                       for c in ["and also", "additionally", "furthermore", "as well as"])

    if h2_count > 5:
        return FAIL(f"H2 count: {h2_count} (max: 5)")
    if conjunctions > 2:
        return FAIL(f"Conjunction density: {conjunctions} in Purpose section")
    if h2_count > 3 or conjunctions > 0:
        return BORDERLINE(f"H2: {h2_count}, conjunctions: {conjunctions}")
    return PASS()
```

---

### 2.2 Test 2: Single Test Setup — Fully Static (~85% accuracy)

**Goal**: Detect specs that require multiple test environments.

**Static Signals**: Scan for keywords from distinct test environment categories:

| Category | Keywords |
|----------|----------|
| **fixture** | fixture, sample, example input, test data, mock data |
| **runtime** | running, execute, start the engine, invoke, dispatch, process |
| **crash_sim** | kill, crash, recover, resume, restart, interrupt, SIGKILL |
| **network** | mock server, API call, endpoint, HTTP, gRPC, webhook |
| **database** | database, SQL, SQLite, migration, schema, table, query |
| **filesystem** | file, directory, path, write to, read from, create directory |
| **concurrency** | parallel, thread, mutex, lock, race, fan-out, semaphore |

**Decision logic**:
```python
def test_single_setup(spec_text: str) -> TestResult:
    active = [cat for cat, keywords in ENV_CATEGORIES.items()
              if any(kw in spec_text.lower() for kw in keywords)]
    if len(active) > 3:
        return FAIL(f"Test environments: {len(active)} — {active}")
    if len(active) > 2:
        return BORDERLINE(f"Test environments: {len(active)} — {active}")
    return PASS()
```

**Why this works well**: The keyword categories are domain-stable. A spec mentioning "crash recovery" AND "parallel mutex" AND "API endpoints" is structurally doing too many things regardless of the project.

**Calibration data from existing specs**:
- `01_02` (Status Domain): fixture, filesystem → 2 categories → ✅ PASS
- `01_06` (LLM Binding): runtime, network → 2 categories → ✅ PASS
- `01_08` (Flows): fixture, runtime, crash_sim, concurrency, filesystem → 5 categories → ❌ FAIL

---

### 2.3 Test 3: Stranger Test — Mostly Static (~60% accuracy)

**Goal**: Detect specs that can't be understood without reading other documents.

**Static Signals**:

| Signal | How to Measure | Threshold |
|--------|---------------|-----------|
| Cross-references | Count markdown links to other `.md` files | > 5 → flag |
| "See" references | Count `see §`, `see section`, `see spec`, `as defined in` | > 3 → flag |
| Undefined terms | Terms in backticks used but never introduced/defined in this document | > 3 → flag |

**Implementation**:
```python
def test_stranger(spec_text: str) -> TestResult:
    md_links = len(re.findall(r'\[.*?\]\(.*?\.md.*?\)', spec_text))
    see_refs = len(re.findall(r'[Ss]ee\s+(?:§|section|spec)\s*\S+', spec_text))
    total = md_links + see_refs

    if total > 8:
        return FAIL(f"External references: {total} (links: {md_links}, see-refs: {see_refs})")
    if total > 5:
        return BORDERLINE(f"External references: {total}")
    return PASS()
```

**Limitation**: Cannot distinguish between *necessary* references (a spec SHOULD reference its interfaces) and *problematic* references (the spec can't stand alone). This is where the ~60% accuracy comes from. Borderline cases need LLM judgment: "are these references for context, or is the spec actually incomplete without them?"

---

### 2.4 Test 4: Dependency Direction — Fully Static (~90% accuracy)

**Goal**: Detect specs that depend on peer or higher-level components.

**Prerequisite**: A component hierarchy map (defined once per project, updated when architecture changes).

**Example hierarchy map** (for SpecWeaver):
```python
# Level 0 = foundation, higher = more abstract
HIERARCHY = {
    "filesystem":      0,
    "json_schema":     0,
    "status_parser":   1,
    "state_store":     1,
    "atom_contract":   1,
    "tool_interface":  1,
    "llm_provider":    1,
    "flow_loader":     2,
    "flow_executor":   2,
    "skill_system":    2,
    "agent_system":    3,
    "persona_system":  3,
    "validation_gate": 3,
}
```

**Implementation**:
```python
def test_dependency_direction(spec_text: str, this_component: str) -> TestResult:
    this_level = HIERARCHY[this_component]
    violations = []
    for component, level in HIERARCHY.items():
        if component == this_component:
            continue
        if component in spec_text and level >= this_level:
            violations.append(f"references peer/upward '{component}' (level {level})")
    if violations:
        return FAIL(f"Dependency violations: {violations}")
    return PASS()
```

**Why this is ~90%**: The hierarchy map is human-curated, so the classification of levels is reliable. The only inaccuracy source is string matching (a spec might mention "executor" in prose without actually depending on the executor module). More precise matching (component name in backticks, or in link targets) pushes accuracy higher.

**Key insight**: The hierarchy map itself is a valuable architectural artifact — it forces the team to explicitly state "what depends on what," which is often implicit knowledge.

---

### 2.5 Test 5: Day Test — Proxy via Composite Score (~65% accuracy)

**Goal**: Detect specs too large for one implementation session.

**Static Signals**:

| Signal | Weight | Rationale |
|--------|--------|-----------|
| File size (KB) | 0.30 | Strongest single correlator. 01_08 = 107KB → months; 01_02 = 7KB → days. |
| Section count (H2 + H3) | 0.20 | More sections = more distinct behaviors to implement. |
| Decision branches | 0.20 | Count of "if", "when", "unless", "except", "otherwise" — proxy for conditional logic. |
| State count | 0.15 | Count of `UPPERCASE_IDENTIFIERS` (e.g., `COMPLETED`, `FAILED`, `WAITING`) — proxy for state machine complexity. |
| Code block count | 0.15 | More code examples = more precise implementation demands. |

**Implementation**:
```python
def test_day(spec_text: str) -> TestResult:
    size_kb = len(spec_text) / 1024
    sections = spec_text.count("\n## ") + spec_text.count("\n### ")
    branches = sum(spec_text.lower().count(kw)
                   for kw in ["if ", "when ", "unless ", "except ", "otherwise"])
    states = len(set(re.findall(r'`[A-Z][A-Z_]+`', spec_text)))
    code_blocks = spec_text.count("```")

    score = (size_kb * 0.30 + sections * 0.20 + branches * 0.20
             + states * 0.15 + code_blocks * 0.15)

    if score > 40:
        return FAIL(f"Complexity score: {score:.1f} (threshold: 40)")
    if score > 25:
        return BORDERLINE(f"Complexity score: {score:.1f}")
    return PASS()
```

**Calibration needed**: The weights and thresholds above are initial estimates. After running against the 10 existing specs, calibrate empirically: which specs were actually implementable in ~1 day vs. which ones weren't? Adjust weights to match.

---

## 3. Combined Gate Model

The key design principle: **static checks are the bouncer; the LLM is the judge.**

```
Document saved/committed
         │
         ▼
  ┌──────────────────┐
  │  Static Analysis  │    ← FREE, instant, runs on every save
  │  (5 tests)        │
  └────────┬──────────┘
           │
     ┌─────┼─────────────────┐
     │     │                 │
     ▼     ▼                 ▼
   PASS  BORDERLINE         FAIL
     │     │                 │
     │     ▼                 ▼
     │   Author reviews    Author MUST fix
     │   flags manually    before proceeding
     │     │
     │     ├─ Fixes → Re-run static
     │     │
     │     └─ Disputes → LLM judges
     │                    (targeted, minimal tokens)
     │
     ▼
  Proceed to agent review
  (full spec review pipeline)
```

### Token Savings Estimate

| Scenario | Without Static Gate | With Static Gate |
|----------|-------------------|-----------------|
| Spec clearly too big (01_08-like) | Full LLM review → discovers structural problems → wasted tokens | Static catches it instantly → 0 LLM tokens |
| Spec borderline | Full LLM review | Static flags specific concerns → LLM judges only those → ~80% fewer tokens |
| Spec well-sized (01_02-like) | Full LLM review | Static passes → LLM review proceeds (no savings, but no overhead either) |

**Estimated overall token savings**: ~80% reduction in spec-validation token usage, because most structural problems (size, coupling, mixed concerns) are detectable without semantic understanding.

---

## 4. When to Run in the Document Lifecycle

| Lifecycle Stage | What Runs | Cost | Purpose |
|----------------|-----------|------|---------|
| **Author writing** (every save) | Size budget check only (< 1ms) | Free | Early warning: "you're at 80% of the 25KB budget" |
| **Pre-commit hook** | All 5 static tests (< 100ms) | Free | Gate: block commits that introduce FAIL-level specs |
| **Feature Spec created** | Static tests on the Feature Spec itself | Free | Catch over-scoped features before decomposition |
| **Component Spec first draft** | All 5 static tests + report | Free | Author sees issues before requesting review |
| **Before LLM review** | Static gate (pass/borderline/fail) | Free | Prevent wasting tokens on structurally broken specs |
| **Borderline dispute** | Targeted LLM judgment on specific flags | Minimal tokens | Only the flagged concern, not the whole spec |
| **Full review** | Spec Review Pipeline (LLM) | Full token cost | Semantic quality review — only after structural quality is confirmed |

**Key insight**: The static checks maximize their value when run **early and cheap** (pre-commit, first draft). Every structural problem caught before the LLM review is free money.

---

## 5. Implementation Sizing

**Estimated effort**: ~200-300 lines of Python, no external dependencies beyond `re`.

**File structure**:
```
src/specweaver/analysis/
    readiness.py         # The 5 tests + composite gate
    hierarchy.py         # Component hierarchy map (per-project config)
    __init__.py
```

**CLI integration**:
```
sw check docs/specs/flow_loader.md

Flow Loader Spec — Readiness Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ One-Sentence:     H2 count: 3, conjunctions: 0
✅ Test Setup:       1 environment (filesystem)
⚠️ Stranger:         6 cross-references (threshold: 5) — BORDERLINE
✅ Dependency:       2 downward (filesystem, json_schema)
✅ Complexity:       12.3 (threshold: 40)

Result: 4/5 PASS, 1 BORDERLINE
Action: Review cross-references manually or escalate to LLM
```

**When to build this**: After the Steel Thread (roadmap Step 2) proves the engine works. This becomes a natural candidate for roadmap Step 10 (Spec Slicing Automation) or could be a standalone tool built even earlier as a pre-commit hook.

---

## 6. Calibration: Running Against Existing Specs

Before trusting the thresholds, run the static tests against all 10 existing specs and compare with known outcomes:

| Spec | Known Outcome | Expected Static Result |
|------|--------------|----------------------|
| `01_02` (7KB) | ✅ Implemented successfully | All PASS |
| `01_05` (33KB) | ⚠️ Implemented but too broad | Size BORDERLINE, setup BORDERLINE |
| `01_06` (51KB) | ✅ Implementation is clean despite size | Size FAIL — needs calibration (the spec is detailed but well-focused) |
| `01_08` (107KB) | ❌ Never implemented, monster spec | All FAIL |

The 01_06 case is important: it's 51KB but the implementation is clean. This means file size alone isn't sufficient — the composite score (which accounts for section count, branch count, etc.) must compensate. If 01_06 has few decision branches and few test environments despite its size, the composite score should correctly classify it as BORDERLINE rather than FAIL.

**Action**: Run the static tests against all 10 specs, compare with implementation reality, and adjust weights/thresholds.

---

## 7. Open Questions

1. **Hierarchy map maintenance**: Who updates the component hierarchy map when architecture changes? Should it be derived from the codebase (import graph) or manually maintained?

2. **Project bootstrapping**: For a brand-new project with no hierarchy map, what are sensible defaults? Start with a flat hierarchy (all level 0) and promote components as structure emerges?

3. **Cross-project calibration**: Are the thresholds (5 H2 sections, 3 test environments, etc.) universal, or do they need per-project tuning? Initial hypothesis: they're universal for "spec documents intended for agent implementation," but this needs validation across multiple projects.

4. **False positive cost**: A false positive (flagging a good spec as "too big") costs author time investigating. A false negative (passing a bad spec) costs LLM tokens downstream. Which is more expensive? This determines whether thresholds should be aggressive (more false positives, fewer false negatives) or conservative.
