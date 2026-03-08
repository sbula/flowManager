# Project-Specific Review Checklists

> **Status**: DRAFT — First draft, requires discussion and refinement.
> **Date**: 2026-03-08
> **Scope**: Universal pattern. Each project creates its own checklist from this guide.
> **Related**:
> - [Lifecycle Layers — L5 Review](lifecycle_layers.md) — where checklists are used
> - [Completeness Tests — T10 Done Definition](completeness_tests.md) — the generic completeness test that checklists extend
> - [DMZ Repository — reviewer.md](https://github.com/TheMorpheus407/the-dmz) — reference implementation (15-point checklist)

---

## Purpose

The 10-test battery (see [Spec Methodology](spec_methodology.md)) is **universal** — it works for any project. But every project also has **domain-specific** quality concerns that the universal tests don't cover.

A Review Checklist is a **project-specific extension** of Test 10 (Done Definition). It turns "is completion verifiable?" into "does this code meet OUR project's specific quality bar?"

---

## Anatomy of a Review Checklist

### Structure

A checklist is a numbered list of review items. Each item has:

| Field | Purpose | Example |
|-------|---------|---------|
| **Category** | Groups related items | "Security", "Testing", "Standards" |
| **Check** | What to verify (specific, binary — yes/no) | "All user input is validated with a schema before processing" |
| **How** | How to verify it (concrete action) | "Search for request handlers without schema validation" |
| **Severity** | What happens if this check fails | BLOCK (cannot merge) or WARN (note for author) |

### Required vs. Optional Items

- **BLOCK items**: Code CANNOT be merged if these fail. These are non-negotiable.
- **WARN items**: Code CAN be merged, but the finding is reported to the HITL for awareness.

---

## Template

```markdown
# [Project Name] — Review Checklist

> **Applies to**: All code changes reviewed by agent or human.
> **Verdict**: ACCEPTED (all BLOCK items pass) or DENIED (any BLOCK item fails).

## 1. Spec Compliance
- [ ] **[BLOCK]** Every public function/class maps to a requirement in the Component Spec
- [ ] **[BLOCK]** No functionality exists that isn't described in the spec (no gold-plating)
- [ ] **[WARN]** Spec was updated if implementation deviated from original design

## 2. Correctness
- [ ] **[BLOCK]** Happy path works as specified
- [ ] **[BLOCK]** All error paths from the spec are implemented
- [ ] **[WARN]** Edge cases beyond spec are handled or explicitly noted as out-of-scope

## 3. Testing
- [ ] **[BLOCK]** Tests exist for every public method
- [ ] **[BLOCK]** Tests pass (`pytest` / project equivalent)
- [ ] **[BLOCK]** Coverage ≥ [project threshold]%
- [ ] **[WARN]** Error path tests exist (not just happy path)

## 4. Security
- [ ] **[BLOCK]** No secrets in code (API keys, passwords, tokens)
- [ ] **[BLOCK]** All user/agent input validated before use
- [ ] **[BLOCK]** File operations use safe path validation
- [ ] **[WARN]** OWASP Top 10 considerations relevant to this change

## 5. Standards
- [ ] **[BLOCK]** Code follows project coding standards (naming, imports, error handling)
- [ ] **[BLOCK]** Type hints present on all public interfaces
- [ ] **[WARN]** Docstrings on public classes and functions
- [ ] **[WARN]** No TODO/FIXME without an issue reference

## 6. Architecture
- [ ] **[BLOCK]** No imports from peer or upper-level modules (dependency direction)
- [ ] **[BLOCK]** No violation of Constitution principles
- [ ] **[WARN]** Module boundaries respected (no reaching into another module's internals)

## 7. [Domain-Specific Category]
- [ ] **[BLOCK/WARN]** [Project-specific checks go here]
```

---

## Reference: DMZ's 15-Point Checklist

The DMZ repository ([github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz)) uses a 15-point reviewer checklist in `reviewer.md`. This is the most comprehensive working example found:

| # | DMZ Check | Universal Category | Our Equivalent |
|---|-----------|-------------------|---------------|
| 1 | Issue fit | Spec Compliance | §1 — maps to spec |
| 2 | Correctness | Correctness | §2 — happy + error paths |
| 3 | Security (OWASP) | Security | §4 — OWASP, secrets, input validation |
| 4 | Error handling | Correctness | §2 — error path coverage |
| 5 | Tenant isolation | Domain-Specific | §7 — project-specific (multi-tenancy) |
| 6 | Event sourcing | Domain-Specific | §7 — project-specific (CQRS/ES) |
| 7 | TypeScript & Svelte | Standards | §5 — coding standards |
| 8 | Module boundaries | Architecture | §6 — dependency direction |
| 9 | Accessibility | Domain-Specific | §7 — project-specific (WCAG) |
| 10 | Tests | Testing | §3 — tests exist, pass, coverage |
| 11 | Performance | Domain-Specific | §7 — N+1, unbounded loops, leaks |
| 12 | Standards | Standards | §5 — named exports, DRY, logging |
| 13 | Database | Domain-Specific | §7 — project-specific (migrations) |
| 14 | Environment config | Security | §4 — no .env committed, Zod validation |
| 15 | Prohibited actions | Architecture | §6 — cross-reference AGENTS.md prohibitions |

**Key insight**: Items 1-4, 7-8, 10-12, 14-15 are **universal** (every project needs them). Items 5-6, 9, 13 are **domain-specific** (only relevant to DMZ's cybersecurity game). This validates our template structure: universal categories (§1-§6) + a domain-specific extension slot (§7).

---

## Guidelines for Creating a Project Checklist

1. **Start with the template** (§1-§6). These categories work for any project.
2. **Add domain-specific items** in §7. Ask: "What quality concerns are specific to THIS project's domain?"
3. **Mark severity honestly**: BLOCK means "will cause bugs or security issues." WARN means "code quality concern."
4. **Keep it under 20 items total**. More than 20 and the reviewer (human or agent) starts skimming.
5. **Each check must be binary**: yes/no. Not "code quality is good" (subjective) but "all public methods have type hints" (binary).
6. **Update the checklist as the project evolves**: New security concern? Add an item. Obsolete framework concern? Remove it.

---

## Reviewer Agent Permissions

Following the DMZ pattern, the reviewer agent should be **read-only for code**:

| Permission | Reviewer Agent | Implementation Agent |
|------------|---------------|---------------------|
| Read code | ✅ | ✅ |
| Edit code | ❌ | ✅ |
| Write files | ❌ | ✅ |
| Run tests | ✅ (via shell) | ✅ |
| Search/grep | ✅ | ✅ |

**Rationale**: If the reviewer can fix code, it bypasses the implement → review separation. The reviewer's job is to find problems and report them — not to silently fix them and hide the fact that the implementation was wrong.
