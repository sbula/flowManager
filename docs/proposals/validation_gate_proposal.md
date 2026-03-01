# Proposal: Validation Gate (Semantic Anti-Hallucination Firewall)

> **Status**: PROPOSED
> **Spec**: [01_11_validation_gate_spec.md](../specs/01_11_validation_gate_spec.md)
> **Priority**: P0 — Highest-leverage feature for autonomous code generation reliability

## 1. Problem Statement

Flow Manager already prevents **filesystem-level** corruption (SafePath, LoomAtom, Loom Jail). However, it has **no mechanism** to validate the **semantic correctness** of agent-generated code:

- An agent can write a function call to `UserService.deleteAccount()` — a method that doesn't exist
- An agent can import `from utils.magic import do_thing` — a module that doesn't exist
- An agent working on Service A can call private methods of Service B
- An agent can call a method with wrong parameters and types

These are not malicious attacks — they are **hallucinations**. And they are the #1 cause of agent-generated code failures.

---

## 2. Proposed Solution: The Symbol Index + Validation Gate

### 2.1 The `.machine-doc/` Directory
A deterministic, git-committed directory containing the machine-readable representation of the codebase:

```
.machine-doc/
  schema_version.json       # "0.1" — index format version
  symbols.json              # Flat list of all extracted symbols
  edges.json                # Call graph, inheritance relationships
  file_hashes.json          # Per-file hash for incremental updates
```

**Key design decisions:**
1. **Committed to git** — not ephemeral. Every branch has its own symbol state.
2. **Deterministic output** — same code always produces same index (sorted, canonical JSON).
3. **Incremental** — only changed files are re-parsed via content hash comparison.
4. **Not an LLM artifact** — purely deterministic, Tree-sitter/AST-based extraction. No embeddings, no generation.

### 2.2 The Validation Gate
An engine-level component that intercepts all write operations:

```
Agent Output → [Validation Gate] → [LoomAtom / FileTool]
                     ↓ (if fail)
              Structured Error → Agent Retry
```

When validation fails, the agent receives a **structured JSON error** (not prose), enabling targeted correction.

---

## 3. Hierarchical Hashing Strategy

The critical innovation: **three levels of hashing** to distinguish types of change.

| Level | What's Hashed | Change Impact |
|:---|:---|:---|
| **L1: Implementation** | Method body | None (private refactoring) |
| **L2: Signature** | Method name + params + return type + visibility | Consumer alert, RAG update |
| **L3: Contract** | Public interface / proto / OpenAPI | Breaking change workflow |

**Why this matters**: If developer Alice refactors the internals of `process_order()` but doesn't change its signature, L1 changes but L2/L3 stay stable. No downstream alerts, no RAG re-embedding. This prevents the "re-index everything on every commit" problem.

---

## 4. Implementation Phases

### Phase 1: Python-Only Symbol Index (Target: 2 weeks)
- [ ] `SymbolExtractor` using Python `ast` module
- [ ] `IndexManager` with deterministic JSON serialization
- [ ] `file_hashes.json` manifest for incremental updates
- [ ] CLI: `flow index` command to build/rebuild the index
- [ ] Tests: T11.01-09

### Phase 2: Validation Gate Integration (Target: 2 weeks)
- [ ] `ValidationGate.validate()` — symbol existence, signature, visibility
- [ ] Integration with `LoomAtom` write path
- [ ] Structured error feedback protocol
- [ ] Atomic index update after successful writes
- [ ] Tests: T11.10-15

### Phase 3: Tree-sitter Migration (Target: 1 week)
- [ ] Replace Python `ast` with Tree-sitter for Python
- [ ] Add support for polyglot parsing (preparation)
- [ ] Validate equivalence: ast vs tree-sitter output for Python

### Phase 4: CI/CD Integration (Target: 1 week)
- [ ] Pre-commit hook: `flow validate`
- [ ] CI gate: reject PRs with index drift
- [ ] `flow index --check` for dry-run validation

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|:---|:---|:---|:---|
| Index drift from manual edits | High | Medium | File watcher + periodic reconciliation |
| Performance degradation on large repos | Medium | Medium | Incremental hashing, parallel parsing |
| False positives from dynamic Python | Medium | Low | `strictness: warn` mode for gradual adoption |
| Index merge conflicts in git | Low | Low | Deterministic output minimizes diff surface |

---

## 6. Success Criteria

1. Agent-generated code references only existing, accessible symbols
2. Zero false negatives (never passes invalid code)
3. < 5% false positive rate on real-world Python code
4. Index rebuild < 10 seconds for 50k LOC
5. Incremental update < 100ms per changed file
6. Index is deterministic: same code → same JSON, always

---

## 7. Relationship to Existing Components

| Component | Current Role | Gate Integration |
|:---|:---|:---|
| `SafePath` | Filesystem jail | Gate sits **above** SafePath in the write pipeline |
| `LoomAtom` | Surgical editing | Gate validates content **before** Loom applies it |
| RAG (`01_09`) | Context retrieval | Gate shares the Symbol Index with RAG for retrieval |
| Agent Isolation | Branch-based scope | Gate enforces visibility tier from isolation config |
| Registry | Atom whitelist | Gate validates atom references similarly to registry |
