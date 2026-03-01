# 01_11 Validation Gate Specification

> **Status**: DRAFT
> **Owner**: Architecture Team
> **Context**: The "Anti-Hallucination Firewall" — semantic validation of agent-generated code.

> [!IMPORTANT]
> This is the **highest-leverage component** for making autonomous agent-driven code generation reliable. While RAG improves context, the Validation Gate prevents invalid output from ever reaching the codebase.

## 1. Overview

The **Validation Gate** is a deterministic, write-time semantic validator. It intercepts all agent-generated code modifications (via `LoomAtom`, `FileTool`, or any write path) and cross-checks the proposed changes against the **Symbol Index** — a structured, machine-readable map of the codebase's public interfaces, signatures, and architectural boundaries.

**Key Capabilities:**
1. **Symbol Reference Validation**: Every symbol reference in agent-generated code is verified against the index.
2. **Signature Matching**: Parameter types, counts, and return types are checked for compatibility.
3. **Visibility Enforcement**: Agents cannot access private/protected symbols outside their scope.
4. **Architectural Boundary Enforcement**: Cross-module, cross-service, and layer violations are rejected.
5. **Contract Drift Detection**: Stale references to changed/deleted symbols are caught.

**Design Principle**: The gate does NOT judge code quality. It validates **structural correctness** — ensuring the agent's output references real, accessible, compatible symbols.

---

## 2. Architecture

```
Agent Code Output
       ↓
  AST Parser (Tree-sitter)
       ↓
  Symbol Extraction
       ↓
  Cross-Reference Engine ←── Symbol Index (.machine-doc/)
       ↓
  Violation Report
       ↓
  [PASS] → Apply via LoomAtom/FileTool
  [FAIL] → Structured Error → Agent Retry
```

### 2.1 Integration Points
- **LoomAtom**: Gate is invoked BEFORE any write operation. Loom's existing `SafePath` handles filesystem security; the gate handles semantic security.
- **FileTool**: All `write_file` and `edit_file` operations pass through the gate.
- **Atom Result Validation**: Gate can optionally validate `AtomResult.exports` for schema compliance.

### 2.2 Symbol Index (`.machine-doc/`)
The gate reads from a deterministic, git-committed symbol index:
```
.machine-doc/
  schema_version.json    # Index format version
  symbols.json           # Flat list of all symbols
  edges.json             # Call graph, inheritance, implements
  file_hashes.json       # Per-file hash for incremental updates
```

---

## 3. Validation Rules

### 3.1 Symbol Existence Check
```
RULE: Every symbol referenced in new/modified code MUST exist in the Symbol Index.
FAIL: "Symbol 'UserService.createUser' not found in index."
```

### 3.2 Signature Compatibility
```
RULE: Call sites must match the symbol's declared parameter types and count.
FAIL: "UserService.createUser expects (email: str, password: str) but called with (email: str)."
```

### 3.3 Visibility Enforcement
```
RULE: Agents can only access symbols with visibility >= their access tier.
FAIL: "Symbol 'UserRepo._internal_save' is private. Agent scope: 'external'."
```

### 3.4 Architectural Boundary
```
RULE: Modifications to protected modules require explicit spec authorization.
FAIL: "Module 'flow.engine.core' is protected. Spec REQ-XYZ does not authorize modification."
```

### 3.5 Import Validation
```
RULE: Imports in generated code must resolve to real, indexable modules.
FAIL: "Import 'from utils.magic import do_thing' — module 'utils.magic' not in index."
```

### 3.6 Deletion Impact Check
```
RULE: Deleting a public symbol triggers a downstream consumer scan.
WARN: "Symbol 'OrderService.place' is consumed by 3 other modules."
```

---

## 4. Symbol Index Schema

### 4.1 Symbol Entry
```json
{
  "symbol_id": "hash(fq_name + normalized_signature)",
  "kind": "method|class|function|interface|struct",
  "fq_name": "flow.domain.parser.StatusParser.load",
  "file_path": "src/flow/domain/parser.py",
  "namespace": "flow-engine",
  "visibility": "public|protected|private",
  "parameters": [
    {"name": "path", "type": "Path", "nullable": false}
  ],
  "return_type": "StatusTree",
  "throws": ["StatusParsingError", "IntegrityError"],
  "calls": ["_parse_content", "_validate_cycles"],
  "called_by": ["Engine.load_status"],
  "is_async": false,
  "is_static": false,
  "signature_hash": "sha256(normalized_signature)",
  "implementation_hash": "sha256(method_body)",
  "symbol_version": "1.0.0",
  "schema_version": "0.2"
}
```

**New fields (v0.2):**
*   `namespace`: Owning microservice or module. Used by RAG for tiered access filtering (see [01_09 §10](01_09_rag_spec.md)).
*   `symbol_version`: SemVer-like version auto-incremented based on hash level changes. L1 change → patch, L2 → minor, L3 → major. See [RAG Analysis §14](../analysis/rag_analysis.md) for full design.

### 4.2 Hierarchical Hashing
Three hash levels prevent over-indexing:

| Level | What's Hashed | RAG Impact on Change |
|:---|:---|:---|
| **L1: Implementation** | Method body, local variables | No RAG update needed; may trigger test re-run |
| **L2: Signature** | Method name, params, return type, visibility | RAG entry invalidated; consumers alerted |
| **L3: Contract/Interface** | OpenAPI spec, Proto file, public class interface | Breaking change workflow triggered |

### 4.3 Edge Schema
```json
{
  "source": "symbol_id_A",
  "target": "symbol_id_B",
  "relation": "calls|implements|inherits|reads|writes|publishes|subscribes"
}
```

### 4.4 Spec-to-Symbol Traceability
To ensure agents don't just write valid code, but code that fulfills the requirement:
```json
{
  "requirement_id": "REQ-USER-REG-01",
  "implemented_by": [
    "UserService.createUser",
    "UserRepository.save"
  ],
  "validated_by": [
    "UserServiceTest.shouldCreateUser",
    "ScenarioTest.userRegistrationFlow"
  ]
}
```
**Goal**: The Validation Gate checks that modifications map to the active `requirement_id` in the spec.

### 4.5 SQL Contract Extraction ("The Beast" Strategy)
For large, data-heavy legacy systems, hallucinations often occur at the DB layer.
*   **Concept**: Treat DB schemas (Tables, Columns, Foreign Keys, Stored Procedures) as "Symbols" in the index.
*   **Gate Rule**: Reject any SQL string or ORM call referencing non-existent columns or tables.
*   **Implementation**: A minimal SQL parser or schema export script feeds DB symbols into `symbols.json`.

---

## 5. Error Feedback Protocol

When validation fails, the gate returns a **structured error** (not prose) to the agent:

```json
{
  "gate_status": "REJECTED",
  "violations": [
    {
      "rule": "SYMBOL_NOT_FOUND",
      "symbol": "UserService.deleteAccount",
      "suggestion": "Did you mean 'UserService.deactivateAccount'?",
      "nearest_matches": ["UserService.deactivateAccount", "AccountService.remove"]
    },
    {
      "rule": "VISIBILITY_VIOLATION",
      "symbol": "UserRepo._internal_save",
      "current_scope": "external",
      "required_scope": "internal"
    }
  ],
  "index_version": "abc123",
  "index_timestamp": "2026-03-01T12:00:00Z"
}
```

This structured feedback enables the agent to make targeted corrections rather than blind retries.

---

## 6. Incremental Index Updates

The symbol index is updated **transactionally** alongside every file write:

1. Agent proposes code change
2. Gate validates against current index
3. If PASS: apply change AND update index atomically
4. If FAIL: reject, return structured error

**Critical invariant**: There must never be a state where "agent code applied but index not updated." This would create drift, which is a hallucination amplifier.

---

## 7. Interfaces

### 7.1 `ValidationGate`
```python
class ValidationGate:
    def validate(self, proposed_code: str, file_path: Path, agent_scope: str) -> ValidationResult:
        """
        Validates proposed code against the symbol index.
        Returns PASS with empty violations, or FAIL with structured violations.
        """

    def update_index(self, file_path: Path) -> None:
        """
        Re-parses the given file and updates the symbol index atomically.
        Called after successful file writes.
        """
```

### 7.2 `SymbolExtractor`
```python
class SymbolExtractor:
    def extract(self, file_path: Path, language: str) -> List[Symbol]:
        """
        Uses Tree-sitter to extract all symbols from a file.
        Returns normalized Symbol objects.
        """
```

### 7.3 `IndexManager`
```python
class IndexManager:
    def load(self) -> SymbolIndex:
        """Loads the symbol index from .machine-doc/"""

    def save(self, index: SymbolIndex) -> None:
        """Persists the symbol index deterministically (sorted, canonical)."""

    def diff(self, old: SymbolIndex, new: SymbolIndex) -> IndexDelta:
        """Returns added, removed, and modified symbols."""
```

---

## 8. Configuration

```json
{
  "validation_gate": {
    "enabled": true,
    "strictness": "warn|reject",
    "index_path": ".machine-doc/",
    "supported_languages": ["python"],
    "max_violations_before_halt": 5,
    "protected_modules": [],
    "schema_version": "0.1"
  }
}
```

---

## 9. Scope & Limitations (V1)

### In Scope
- Python (via `ast` module and/or Tree-sitter)
- Public/protected method signatures
- Import validation
- Call graph (static calls, no reflection)
- Single-repo validation

### Out of Scope (Deferred)
- Multi-language (Kotlin, Rust, etc.) — Phase 2
- Deep static analysis (data flow, side effects, purity)
- Cross-repo / cross-service validation — Phase 3
- Runtime type inference for dynamic languages
- Macro/generic expansion

## 10. Controlled Operational Boundary (COB)

For huge brownfield projects (e.g., a 30-year-old monolith), indexing or retrieving the entire call graph will cause context/token explosion.

*   **Concept**: Define an `"active_scope": ["com.company.billing.*"]` during a task.
*   **Retrieval**: The agent receives the structural graph *only* for symbols within the active scope.
*   **Validation**: Everything outside the active scope is treated as a read-only black box. The gate strictly rejects modifications outside the COB unless explicitly authorized.

---

## 10. Test Inventory

### T11.01-03: Symbol Extraction
- Extract functions, classes, methods from Python file
- Handle decorators, async, static methods
- Handle nested classes and inner functions

### T11.04-06: Validation Rules
- Reject code referencing non-existent symbol
- Reject code violating visibility
- Reject code with wrong parameter count

### T11.07-09: Index Management
- Incremental update on file change
- Deterministic output (same file → same index)
- Handle file deletion (remove symbols from index)

### T11.10-12: Integration
- Gate integrates with LoomAtom write path
- Structured error feedback returned to agent
- Atomic index update after successful write

### T11.13-15: Edge Cases
- Handle empty files
- Handle syntax errors in proposed code
- Handle missing index (cold start → full index)
