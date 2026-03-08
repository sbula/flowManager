# Completeness Tests — Spec Implementability Methodology

> **Status**: DRAFT
> **Date**: 2026-03-08
> **Scope**: Universal. Applies to any project at any decomposition level.
> **Related**:
> - [Spec Methodology](../architecture/spec_methodology.md) — defines Structure Tests (the other axis)
> - [Static Spec Readiness Analysis](static_spec_readiness_analysis.md) — static automation for Structure Tests
> - [Fractal Readiness Walkthrough](fractal_readiness_walkthrough.md) — worked examples of Structure Tests

---

## 1. The Two-Axis Model

A spec can fail in two orthogonal ways:

```
                    TOO VAGUE
                   (aspirational prose)
                        ▲
                        │
                        │    Completeness
                        │    Tests catch this
                        │
TOO BIG ◄───────────────┼───────────────► RIGHT SIZE
(monolith)              │                 (focused)
     Structure          │
     Tests catch this   │
                        │
                        ▼
                    IMPLEMENTABLE
                   (concrete blueprint)
```

| Quadrant | Structure | Completeness | Example | Outcome |
|----------|-----------|-------------|---------|---------|
| Top-Left | ❌ Too big | ❌ Too vague | 01_08 flows spec (107KB of mixed concerns, many TBDs) | Worst case: un-reviewable AND un-buildable |
| Top-Right | ✅ Right size | ❌ Too vague | "Solve the energy-pollution problem" | Passes structure tests, fails implementation |
| Bottom-Left | ❌ Too big | ✅ Detailed | 01_06 LLM Binding (51KB, but actually very precise) | Implementable in theory, hard to review and test |
| **Bottom-Right** | **✅ Right size** | **✅ Detailed** | A focused spec with concrete examples and tests | **Ready to implement** |

**Both axes must pass.** Structure Tests (1-5) ensure the spec is small and focused enough to work with. Completeness Tests (6-10) ensure it contains enough information to actually build from.

The axes are **independent**: fixing structure doesn't fix completeness, and vice versa. Splitting a vague spec into 4 smaller vague specs produces 4 specs that are still un-implementable. Adding detail to a monolithic spec makes it bigger without making it more focused.

---

## 2. The Five Completeness Tests

### Test 6: The Concrete Example Test

> **Does the spec include at least one concrete input → output example with real values — not abstract descriptions?**

**Why it matters**: Concrete examples force precision. Writing `f("hello ${name}", {name: "Alice"}) → "hello Alice"` exposes edge cases (what about nested keys? missing keys? type mismatches?) that prose hides. If the author can't produce one worked example, they don't understand the problem well enough to specify it.

**Pass**:
```
Input:  template = "Hello ${user.name}", context = {"user": {"name": "Alice"}}
Output: "Hello Alice"
```

**Fail**:
```
"The function resolves variables from the context dictionary."
```

The second form is a wish. It doesn't tell the implementer what the delimiter syntax is (`${}` vs `{{}}` vs `%s`), whether nesting works, or what happens with missing keys.

### Test 7: The Test-First Test

> **Can you write a failing test FROM the spec BEFORE writing any implementation code?**

**Why it matters**: This is the strongest single signal of completeness. If the spec gives you enough information to write a test, it has defined the interface, the behavior, and the expected output — which is everything you need to implement. If you can't write a test, the spec is missing one of those three.

**Pass**: Reading the spec, you can immediately write:
```python
def test_resolve_simple():
    assert resolve("${x}", {"x": 42}) == "42"

def test_resolve_missing_key():
    with pytest.raises(UnresolvedVariableError):
        resolve("${missing}", {})
```

**Fail**: Reading the spec, you stare at it and think: "but what's the function signature? What does it return on error? A string? None? An exception?" If you're guessing, it's not a spec — it's a suggestion.

### Test 8: The Ambiguity Test

> **Does the spec contain weasel words that leave decisions unmade?**

**Why it matters**: Every ambiguous word is a decision deferred to the implementer. Two different agents (or developers) will resolve the ambiguity differently, producing inconsistent code. Weasel words are the #1 source of "it works but not how I expected."

**Weasel word taxonomy**:

| Category | Words | Problem |
|----------|-------|---------|
| **Vague obligation** | should, might, could, may | "Should" means "optional" to an LLM |
| **Deferred decisions** | TBD, TODO, to be determined, later | Decision not made = implementation will invent one |
| **Subjective judgment** | as appropriate, as needed, reasonable, sufficient | What's "reasonable"? Depends who's asking |
| **Hand-waving** | properly, correctly, efficiently, seamlessly | Means nothing without a metric |
| **Hidden options** | optionally, possibly, alternatively, consider | Is it in scope or not? |

**Pass**: `"The function MUST return an empty string if the key is not found."`

**Fail**: `"The function should handle missing keys appropriately."`

### Test 9: The Error Path Test

> **Does the spec define what happens when the operation fails — not just the happy path?**

**Why it matters**: Most agent-generated code fails on error paths. If the spec says "resolve variables from context" but never mentions missing keys, type mismatches, circular references, or malformed templates, the agent will either ignore errors (silent bugs) or invent error handling (hallucinated behavior). Both are wrong.

**Minimum error coverage per level**:

| Level | Minimum Error Paths Required |
|-------|------------------------------|
| L1 Feature | What the user sees when the feature fails (error page, retry prompt, notification) |
| L2 Module | What exceptions/errors the module can produce, and what each means |
| L3 Class | What each public method raises, under what conditions |
| L4 Function | What the function returns or raises for each category of invalid input |

**Pass**:
```
Errors:
- UnresolvedVariableError: raised when a ${key} references a context key that doesn't exist
- CircularReferenceError: raised when ${a} references ${b} which references ${a}  
- InvalidTemplateError: raised when the template contains malformed ${...} syntax
```

**Fail**: No mention of any error case. The spec only describes success.

### Test 10: The Done Definition Test

> **Does the spec state an unambiguous condition under which the work is COMPLETE?**

**Why it matters**: Without a done definition, work expands forever. An agent (or developer) will gold-plate, add features, or iterate endlessly because there's no stop signal. Conversely, they might stop too early because "it works for my one test case."

**What a done definition must include**:
1. An observable outcome (not a process — "all tests pass", not "thorough testing was performed")
2. A finite, enumerable condition (not "comprehensive coverage" — that's infinite)
3. Something the implementer can check without asking anyone (self-verifiable)

**Pass**: *"Done when: `test_resolver.py` passes (11 cases covering happy path, missing keys, nested keys, circular refs, and type coercion). Coverage ≥ 70% for `resolver.py`."*

**Fail**: *"Done when the variable resolution system is complete and robust."* — What is "complete"? What is "robust"? Unmeasurable.

---

## 3. Fractal Application — Equalities and Differences

### 3.1 What Stays the Same (Equalities)

The **test questions** are identical at every level:

| Test | Universal Question |
|------|--------------------|
| 6. Concrete Example | Does it show at least one real input → output? |
| 7. Test-First | Can you write a test before code? |
| 8. Ambiguity | Are all decisions explicitly made? |
| 9. Error Path | Is failure defined? |
| 10. Done Definition | Is completion unambiguous and verifiable? |

The **failure response** is also identical: if a completeness test fails, **add the missing information** — don't restructure (that's the structure tests' job), don't split, just fill in the blanks.

The **principle** is also identical at every level: a spec is a **contract between author and implementer**. If the implementer (human or agent) must guess, the contract is incomplete.

### 3.2 What Changes (Differences)

#### Thresholds by Level

| Test | L1: Feature | L2: Module | L3: Class | L4: Function |
|------|------------|-----------|-----------|-------------|
| **6. Concrete Example** | ≥ 1 user scenario with named actors and observable outcomes | ≥ 1 input→output per public interface | ≥ 1 example per public method | ≥ 1 `assert f(x) == y` |
| **7. Test-First** | Can write an acceptance test (E2E) | Can write an integration test (module-level) | Can write a unit test (class in isolation) | Can write a single assertion |
| **8. Ambiguity** (max weasel words) | ≤ 3 | ≤ 1 | 0 | 0 |
| **9. Error Path** (min failure modes) | ≥ 2 user-facing errors | ≥ 1 per public method | ≥ 1 per public method | ≥ 1 (invalid input behavior) |
| **10. Done Definition** | Acceptance criteria observable by user/PO | All public methods pass test suite | All defined examples + error cases pass | Single assertion + edge cases pass |

> [!NOTE]
> **Ambiguity tolerance decreases sharply**. A feature spec can say "the exact retry delay strategy will be defined in the module spec" (ambiguity deferred to a lower level). A function spec cannot defer anything — it's the leaf of the fractal.

#### Nature of Evidence Changes

| Level | Concrete Example looks like | Test-First looks like | Done Definition looks like |
|-------|----------------------------|----------------------|---------------------------|
| **L1 Feature** | User story with named user, actions, and outcome | Acceptance test scenario (Given/When/Then) | User-observable behavior checklist |
| **L2 Module** | API call with request body and response body | `test_module_integration.py` with mocked dependencies | "All tests in `tests/test_module.py` pass" |
| **L3 Class** | Constructor call + method call + assertion | `test_class.py` with one test per public method | "All public methods tested with examples + errors" |
| **L4 Function** | `f(input) == output` | One or more assertions | "The function passes all listed assertions" |

#### Who Provides the Missing Information

| Level | When Test Fails, Who Fills the Gap? |
|-------|-------------------------------------|
| **L1 Feature** | PO / Architect — they own the business intent |
| **L2 Module** | Senior Developer / Architect — they own the technical decomposition |
| **L3 Class** | Developer — they're implementing it |
| **L4 Function** | Developer — can often fill the gap themselves during implementation |

At L3-L4, the implementer and the spec author are often the same person. At L1-L2, they're usually different people — which makes completeness testing MORE important (the gap between "what the author meant" and "what the implementer understood" is wider).

---

## 4. Static Analysis for Completeness Tests

### 4.1 Per-Test Automation Feasibility

| Test | Static Accuracy | Method | LLM Needed? |
|------|----------------|--------|-------------|
| **6. Concrete Example** | ~75% | Scan for code blocks, `→` / `=>` patterns, `Input:`/`Output:` markers, `assert` statements | For borderline: is the "example" actually concrete? |
| **7. Test-First** | ~50% | Check for presence of test reference in done criteria, or test-like code blocks | Hard to judge statically if there's ENOUGH for a test |
| **8. Ambiguity** | **~95%** | Regex scan for weasel words — trivial and highly reliable | No — this is the most automatable test of all 10 |
| **9. Error Path** | ~70% | Scan for "Error", "Raise", "Exception", "Fail", "Invalid", "Reject" + count distinct error cases | For borderline: are the error cases actually defined or just mentioned? |
| **10. Done Definition** | ~80% | Check for sections named "Done", "Completion", "Acceptance Criteria", "Definition of Done". Scan for measurable verbs ("passes", "returns", "count ≥") vs. vague verbs ("is complete", "works") | For borderline: is the done definition actually verifiable? |

### 4.2 Implementation Sketches

#### Test 8 — Ambiguity (highest accuracy, cheapest to implement)

```python
WEASEL_WORDS = {
    "vague_obligation": ["should", "might", "could", "may"],
    "deferred":         ["tbd", "todo", "to be determined", "to be decided", "later"],
    "subjective":       ["as appropriate", "as needed", "reasonable", "sufficient",
                         "adequate", "properly", "correctly"],
    "handwaving":       ["efficiently", "seamlessly", "robustly", "gracefully", "cleanly"],
    "hidden_option":    ["optionally", "possibly", "alternatively", "consider"],
}

def test_ambiguity(text: str, level: str) -> TestResult:
    max_allowed = {"feature": 3, "module": 1, "class": 0, "function": 0}
    findings = []
    for category, words in WEASEL_WORDS.items():
        for word in words:
            matches = re.findall(rf'\b{word}\b', text, re.IGNORECASE)
            if matches:
                findings.append((category, word, len(matches)))
    
    total = sum(count for _, _, count in findings)
    threshold = max_allowed[level]
    
    if total > threshold * 2:
        return FAIL(f"Weasel words: {total} (max: {threshold})", findings)
    if total > threshold:
        return BORDERLINE(f"Weasel words: {total} (max: {threshold})", findings)
    return PASS()
```

#### Test 6 — Concrete Example

```python
EXAMPLE_SIGNALS = [
    r'```',                          # code blocks
    r'Input\s*:',                    # "Input:" markers
    r'Output\s*:',                   # "Output:" markers  
    r'(?:→|=>|returns?)',            # result indicators
    r'assert\s+',                    # assertions
    r'Given\s.*?When\s.*?Then\s',    # Gherkin scenarios
    r'"[^"]+"\s*,\s*\{',             # function call with args
    r'\|\s*Input\s*\|.*\|\s*Output', # table with Input/Output columns
]

def test_concrete_example(text: str, level: str) -> TestResult:
    min_required = {"feature": 1, "module": 1, "class": 1, "function": 1}
    signals_found = sum(1 for pattern in EXAMPLE_SIGNALS
                        if re.search(pattern, text, re.IGNORECASE))
    
    if signals_found == 0:
        return FAIL("No concrete examples found")
    if signals_found < min_required[level]:
        return BORDERLINE(f"Example signals: {signals_found} (min: {min_required[level]})")
    return PASS()
```

#### Test 9 — Error Path

```python
ERROR_SIGNALS = [
    r'Error\b',  r'Exception\b',  r'Raise[sd]?\b',
    r'Fail[sed]*\b',  r'Invalid\b',  r'Reject[sed]*\b',
    r'Timeout\b',  r'Missing\b',  r'Not found\b',
    r'Malformed\b',  r'Corrupt\b',
]

def test_error_path(text: str, level: str) -> TestResult:
    min_error_types = {"feature": 2, "module": 1, "class": 1, "function": 1}
    unique_errors = set()
    for pattern in ERROR_SIGNALS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        unique_errors.update(m.lower() for m in matches)
    
    threshold = min_error_types[level]
    if len(unique_errors) == 0:
        return FAIL("No error cases defined")
    if len(unique_errors) < threshold:
        return BORDERLINE(f"Error types: {len(unique_errors)} (min: {threshold})")
    return PASS()
```

#### Test 10 — Done Definition

```python
DONE_SECTION_NAMES = [
    r'##\s*(?:Done|Completion|Acceptance|Definition of Done|Success Criteria|Deliverable)',
]
MEASURABLE_VERBS = ["passes", "returns", "equals", "contains", "count", "≥", "≤", "=="]
VAGUE_DONE = ["is complete", "works correctly", "is robust", "is ready", "is finished"]

def test_done_definition(text: str, level: str) -> TestResult:
    has_done_section = any(re.search(p, text, re.IGNORECASE) for p in DONE_SECTION_NAMES)
    measurable = sum(1 for v in MEASURABLE_VERBS if v in text.lower())
    vague = sum(1 for v in VAGUE_DONE if v in text.lower())
    
    if not has_done_section:
        return FAIL("No 'Done' or 'Acceptance Criteria' section found")
    if vague > measurable:
        return BORDERLINE("Done definition uses more vague verbs than measurable ones")
    return PASS()
```

### 4.3 Combined Gate Model (Both Axes)

```
Document saved/committed
         │
         ▼
  ┌──────────────────────┐
  │  Structure Tests 1-5  │    ← Static (free)
  │  (from readiness      │
  │   analysis doc)       │
  └──────────┬────────────┘
             │
         ALL PASS?
          │     │
         YES    NO → Author fixes structure first
          │
          ▼
  ┌──────────────────────┐
  │ Completeness Tests    │    ← Static (free)
  │ 6-10                  │
  └──────────┬────────────┘
             │
         ALL PASS?
          │     │
         YES    NO → Author adds missing detail
          │
          ▼
    Both axes pass
    → Proceed to LLM review
      (semantic quality, not structure or completeness)
```

**Why structure first**: A bloated spec will produce false positives on completeness tests — it may contain examples buried in 107KB that the static scanner can't contextualize. Fix structure, THEN check completeness.

**Token flow**: Static tests (Tests 1-10) cost 0 tokens. Only when ALL 10 pass does the spec proceed to LLM-based semantic review. Estimated total savings: ~85% vs. running everything through an LLM.

---

## 5. Comparison: Structure vs. Completeness

| Dimension | Structure Tests (1-5) | Completeness Tests (6-10) |
|-----------|----------------------|---------------------------|
| **Axis** | Size / coupling / cohesion | Detail / precision / implementability |
| **What they prevent** | Monolithic, entangled specs | Vague, aspirational specs |
| **Failure mode** | "I can't review this" | "I can't build from this" |
| **Fix action** | Split / decompose | Add detail / make decisions |
| **Who benefits most** | Reviewer / architect | Implementer / agent |
| **Sensitivity to level** | Thresholds loosen at higher levels | Ambiguity tolerance loosens at higher levels |
| **Direction of tightening** | L1 most lenient → L4 strictest | L1 most lenient → L4 strictest |
| **Can fix one break the other?** | Splitting can create vague sub-specs (completeness regression) | Adding detail can bloat the spec (structure regression) |
| **Static automation** | 60-90% accuracy | 50-95% accuracy |
| **Most automatable test** | Test 4: Dependency Direction (~90%) | Test 8: Ambiguity (~95%) |
| **Least automatable test** | Test 3: Stranger (~60%) | Test 7: Test-First (~50%) |
| **Classical analogy** | SOLID principles, Clean Architecture | TDD, BDD, Design by Contract |

### The Interaction Between Axes

> [!WARNING]
> **Fixing one axis can break the other.** Splitting a spec (to fix structure) can produce sub-specs that are too vague because the context is now scattered. Adding examples (to fix completeness) can push a spec past its size budget.

The correct workflow handles this iteratively:

```
        ┌──── Fix structure ────┐
        │                       │
        ▼                       │
  Structure Tests ──FAIL──→ Split/decompose ──→ re-check structure
        │                                             │
       PASS                                    may break completeness
        │                                             │
        ▼                                             ▼
  Completeness Tests ──FAIL──→ Add detail ──→ re-check completeness
        │                                             │
       PASS                                    may break structure
        │                                             │
        ▼                                             ▼
      READY                                    loop back to top
```

In practice, this converges within 2-3 iterations because:
- Structure splits produce smaller specs that need less detail each
- Completeness additions are targeted (one example, one error case) — they don't double the spec size

---

## 6. The Full 10-Test Battery

For reference, the complete set of tests across both axes:

| # | Test | Axis | Question | Static Accuracy |
|---|------|------|----------|----------------|
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

**A spec is ready to implement ONLY when all 10 pass.**

---

## 7. Open Questions

1. **Completeness vs. over-specification**: At what point does adding detail become prescriptive to the point of constraining the implementer unnecessarily? Is there a "too complete" failure mode?

2. **Example count scaling**: Should the number of required concrete examples scale with complexity (e.g., 1 example for simple functions, 3+ for functions with branching logic)?

3. **Error path discovery**: The spec author may not know all failure modes upfront. Should completeness tests account for "known unknowns" by requiring at least a "known risks" section?

4. **Cross-domain calibration**: Are the weasel word lists universal? Different domains may use "should" normatively (as in RFCs: "SHOULD" has a specific meaning in RFC 2119). The ambiguity scanner needs domain-aware calibration.

5. **Code-level completeness**: For L3-L4 (class/function), completeness is usually expressed as docstrings, type hints, and test coverage rather than separate spec documents. Should SpecWeaver check code-level completeness using the same tests applied to docstrings + type signatures?
