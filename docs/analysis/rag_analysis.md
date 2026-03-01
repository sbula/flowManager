# Analysis of RAG Architecture for Flow Manager

## Executive Summary
This document synthesizes key architectural strategies, ideas, and tools extracted from prior technical discussions regarding Retrieval-Augmented Generation (RAG). As Flow Manager evolves into a "High-Assurance Orchestrator", adopting these advanced, compartmentalized RAG mechanisms is critical for scaling a safe, multi-agent system.

---

## 1. RAG Architecture & Ingestion Optimizations

### 1.1 State-Boundary Hunking
*   **Concept**: Standard RAG relies on arbitrary "Sliding Windows" (e.g., 500 tokens). Flow Manager should implement **State-Boundary Hunking**.
*   **Application**: Tie "chunk" creation to logical triggers or state regimes (e.g., Tree-sitter function boundaries, module definitions, or market regime scopes). This maps the vector database to logical structural boundaries rather than temporal text blocks.

### 1.2 Multi-Vector Hunks (Dual-Track Search)
*   **Concept**: Store multiple embeddings per chunk.
*   **Application**: A single semantic vector (for NLP-based Agent querying) and a structural vector (for mathematical/code-signature matching). This allows Flow Manager to dual-track searches: finding code blocks that *mean* the same thing semantically and *look* similar structurally.

### 1.3 Asynchronous Hunk-Packing (LSM Buffering)
*   **Concept**: Pressure-release buffering for continuous indexing.
*   **Application**: Temporarily hold small data updates in a fast local memory buffer (LSM tree style) and batch-quantize them to the main Vector DB (e.g., Qdrant). This reduces DB I/O overhead and aligns with asynchronous agent processes.

### 1.4 Hunk-Chain Metadata (Sequence Indexing)
*   **Concept**: Preserving contextual adjacency.
*   **Application**: Inject `parent_hunk_id` and `sequence_index` into vector metadata. When an Agent makes a query and retrieves chunk `N`, Flow Manager can instantly surface chunks `N-1` and `N+1` without an additional vector lookup, resolving the fragmented context issue.

---

## 2. In-Depth Comparison: Chunking Strategies

A solid RAG retrieval pipeline relies entirely on how effectively documents and code are split before embedding. To understand why Flow Manager should use the advanced hunking strategies mentioned above, it is important to evaluate them against standard techniques.

### 2.1 Fixed-Size Chunking (Sliding Windows)
*   **Description**: Splitting documents by a fixed number of tokens or characters linearly (e.g., 500 tokens with a 50-token overlap).
*   **Pros**: Extremely fast indexing, easy to implement, language-agnostic, predictable memory usage.
*   **Cons**: Destroys semantic meaning by slicing through functions or paragraphs arbitrarily. Often retrieves "orphaned" code snippets without their class or variable declarations.
*   **Techniques**: `RecursiveCharacterTextSplitter`.

### 2.2 Content-Aware (Structural) Chunking
*   **Description**: Splitting based on document structure, such as Markdown headers (H1, H2) or HTML tags.
*   **Pros**: Preserves readable textual context by keeping logically related paragraphs together. Variable chunk sizes respect the author's intent.
*   **Cons**: Unreliable for raw code files or poorly formatted text. Degrades to basic splitting if headers are missing.
*   **Techniques**: `MarkdownHeaderTextSplitter`, `HTMLHeaderTextSplitter`.

### 2.3 AST-Based Chunking (Tree-Sitter)
*   **Description**: Using an Abstract Syntax Tree (AST) parser (e.g., Tree-sitter) to chunk code explicitly by Class, Function, or Method definitions.
*   **Pros**: Perfectly preserves code integrity. An agent always receives a full functional block, never a half-broken method. Great for tracking which code matches which semantic vector. Improves code generation by feeding structurally complete contexts.
*   **Cons**: Requires maintaining syntax parsers for every supported language.
*   **Best Practices for Flow Manager**: 
    1. **Non-Whitespace Character Counting**: Measure chunk thresholds using non-whitespace character counts rather than raw line counts to maintain consistency across verbose vs. dense coding styles.
    2. **Recursive Decomposition for God-Classes**: When an AST node (like a massive class) exceeds the context limit, employ a recursive divide-and-combine algorithm to traverse the AST downwards, attempting to merge adjacent sibling nodes (e.g., small helper methods) to maximize information density without breaking syntax.

### 2.4 State-Boundary Hunking
*   **Description**: The strategy specifically identified for Flow Manager. Closing a chunk not by size, but when a logical "Regime" or "State" changes (e.g., a regime escape triggered by the Regime Module for data streams).
*   **Pros**: Perfectly aligns the Vector DB with the system's operational states rather than arbitrary file structures. It creates a map of "States" allowing agents to get logic for an exact state reliably.
*   **Cons**: High complexity to implement and requires tight integration with system event streams.

### 2.5 Multi-Vector / Summary-Based Chunking (Parent Document Retriever)
*   **Description**: Implements a decoupling of the retrieval payload from the synthesis payload. For every large chunk (e.g., an AST function), smaller sub-chunks, summaries, or hypothetical questions are generated and vectorized.
*   **Pros**: Drastically improves search accuracy. By splitting the retrieval references (summaries/questions) from the synthesis references (the raw, original code), agents match on pure semantic intent ("Handles OAuth login") but are fed the exact structural code to prevent hallucination and logic gaps.
*   **Cons**: Computationally expensive and slow during the indexing phase (requires making LLM calls per code chunk). Increases vector store complexity.
*   **Techniques**: Parent-Document Retriever (search on child chunks, return the parent chunk), Multi-Vector Retriever.

### 2.6 Conclusion & Strategy Recommendation
Relying on out-of-the-box **Fixed-Size Chunking** is considered a liability for a complex 15-microservice trading architecture involving autonomous agents.

**Flow Manager should adopt a hybrid chunking strategy:**
1.  **For Code Repositories**: Use **AST-Based Chunking** (Tree-sitter) enhanced with **Multi-Vector Hunks** (Dual-Track Search). Parse functions fully, generate a concise semantic summary to act as the primary vector for NLP search, and return the AST block payload to the agent upon match.
2.  **For Active Logic/Data Streams**: Adopt **State-Boundary Hunking**, ensuring that market regimes or temporal logic states are distinctly delineated.

---

## 3. RAG Compartmentalization & Zero Trust

### 3.1 Multi-Tenant / Zero Trust RAG
*   **Concept**: Prevent "God-Object" agents that hallucinate capabilities based on global knowledge they shouldn't possess.
*   **Application**: Implement Logical Partitioning using Metadata Filtering. Agents querying the Flow Manager RAG must pass criteria.
    *   *Service A Dev*: Can see internals for Service A + Public Interfaces for all.
    *   *System Auditor*: Can see only Public Interfaces.
*   **Benefit**: Enforces Contract-Driven Development. Agents are forced to build and test based entirely on public interfaces rather than relying on internal service implementations they peeked at.

### 3.2 Schema-to-Semantic Pipeline
*   **Concept**: Exclude raw, messy implementation details from the global RAG.
*   **Application**: 
    1. Extract interfaces using Tree-sitter.
    2. Pass to a localized "Doc Agent" LLM to summarize semantic intent and side effects.
    3. Vectorize this summarization. 

### 3.3 Semantic Drift and Vectors as Build Artifacts
*   **Concept**: If documentation semantics shift slightly, deterministic tests fail.
*   **Application**: Tag every RAG vector with a `commit_hash`. When an Agent runs a scenario or evaluates a trajectory, the exact RAG state can be linked to the codebase point-in-time.

---

## 4. RAG Synchronization (The "Check-and-Sync" Manifest)

### 4.1 Resolving the "Granularity" and "Rename" Hallucinations
*   **Concept**: A naive git-hook script leads to duplicate/zombie vectors on renames.
*   **Application**: Evolve the existing `.flow/rag_manifest.json` into a deterministic SQLite/JSON state tracker.
    *   **Function-Level Identification**: Parse code with Tree-sitter. Vector Point IDs should inherently be derived from `FilePath + FunctionName`.
    *   **Content-Addressable Hashing**: If a file moves but hash matches, perform a MOVE (metadata update), not a re-embed.
    *   **Explicit Deletion**: Unmatched entities in the manifest must be explicitly deleted from the Vector DB (Qdrant) to prevent zombie functions from guiding agents.

---

## 5. RAG Evaluation Metrics

A RAG architecture must be continuously measured against objective metrics, ensuring that indexing strategies (like AST and multi-vector) actually improve outcomes.

### 5.1 Key Retrieval Metrics
*   **Context Precision**: Measures the signal-to-noise ratio of retrieved chunks. If the agent retrieves 5 chunks but only 1 is useful, precision is low. High precision prevents context window flooding.
*   **Context Recall**: Measures if the retrieval system found *all* the necessary information to solve the query. Low recall forces the agent to hallucinate missing steps.
*   **Answer Faithfulness**: Evaluates whether the agent's generated action or response is strictly derived from the retrieved context (checking for zero-trust adherence).

---

## 6. Recommended Technology Stack Alignments
*   **Vector Database**: **Qdrant**. Native to Rust (aligns with Phase 2 V-Next runtime migration strategy), highly optimized for memory footprint, and excels at the complex metadata filtering required for the Zero-Trust Multi-Tenant RAG architecture.
*   **Embedding Strategy**: Utilize Matryoshka models (e.g., `text-embedding-3`). Truncating high-dimension vectors locally for lower-latency preliminary matching reduces compute waste before refining.

---

## 7. Hierarchical Hashing (L1/L2/L3 Drift Detection)

> **Status**: PROPOSED — See [01_11_validation_gate_spec.md](../specs/01_11_validation_gate_spec.md).

### 7.1 The Problem with Flat File Hashing
The current `rag_manifest.json` uses a single `SHA256(file_content)` hash per file. This means:
*   A **private variable rename** inside a function body triggers a full re-embed of that file's chunks — even though no public API changed.
*   A **signature change** (parameter added) and a **whitespace formatting change** are treated identically.

### 7.2 Three-Level Hash Strategy
To distinguish the *type* of change, each symbol in the index should carry three hashes:

| Level | What's Hashed | Content | RAG Impact on Change |
|:---|:---|:---|:---|
| **L1: Implementation** | Method/function body | Local variables, control flow, string literals | None — no RAG update, but may trigger test re-run |
| **L2: Signature** | Normalized signature | Name + parameter names/types + return type + visibility | RAG entry invalidated; consumers alerted |
| **L3: Contract** | Public interface surface | Proto files, OpenAPI spec, exported class interfaces | Breaking change notification; full downstream audit |

### 7.3 Benefits
1.  **Prevents Over-Indexing**: Only L2/L3 changes trigger re-embedding, reducing RAG update volume by an estimated 60-80%.
2.  **Enables Precise Drift Detection**: The Validation Gate (01_11) can distinguish "this is a harmless refactoring" from "this breaks the API contract."
3.  **Supports Git-Committed Index**: Since L2/L3 hashes change infrequently, the `.machine-doc/` directory generates minimal diffs on most commits.

### 7.4 Implementation Notes
*   **Normalization**: Before hashing, signatures must be normalized (stripped of comments, whitespace, and formatting) to produce stable hashes across style changes.
*   **Language-Specific**: The hash extraction logic is language-dependent. Python uses `ast.parse()` (Phase 1) or Tree-sitter (Phase 3). Other languages deferred.

---

## 8. Cross-Service Symbol Linking

### 8.1 The Multi-Service Problem
When Flow Manager orchestrates agents across a polyglot microservice landscape, the RAG must understand inter-service relationships. An agent working on Service A must know that `OrderService.place()` is a gRPC call to Service B, not a local function.

### 8.2 Global Symbol Registry
Each microservice maintains its own `.machine-doc/` directory with local symbols. A **Global Registry** aggregates these into a unified cross-service index.

```
.flow/
  global_registry/
    service_a.symbols.json
    service_b.symbols.json
    cross_service_edges.json    # gRPC, Kafka, REST links
```

### 8.3 Relation Types for Cross-Service Edges

| Relation | Transport | Example |
|:---|:---|:---|
| `calls_grpc` | gRPC | ServiceA → `OrderService.place` (ServiceB) |
| `publishes_kafka` | Kafka | ServiceA → `order.created` topic |
| `subscribes_kafka` | Kafka | ServiceC ← `order.created` topic |
| `calls_rest` | HTTP | ServiceA → `GET /api/users` (ServiceB) |
| `implements_proto` | Proto | ServiceB.OrderService implements `order.proto` |

### 8.4 Ghost Signatures
When a public symbol is deleted from a service, it should be kept as a **Ghost** entry in the registry for a configurable retention period (default: 30 days or 10 commits). This allows:
*   Agents to discover: "This method was deleted in commit `abc123`; the recommended replacement is `newMethod()`."
*   Downstream consumer alerts without silent failures.

---

## 9. Integration with Validation Gate (01_11)

### 9.1 Shared Infrastructure
The RAG system and the Validation Gate share the **Symbol Index** (`.machine-doc/`). They differ in purpose:
*   **RAG**: Uses the index for *retrieval* — finding relevant code to inject into agent context.
*   **Gate**: Uses the index for *validation* — checking that agent output references real, accessible symbols.

### 9.2 Write-Then-Index Loop
```
Agent generates code
  → Validation Gate checks code against index → PASS/FAIL
  → If PASS: LoomAtom writes the file
  → SymbolExtractor re-parses the written file
  → IndexManager updates .machine-doc/ atomically
  → RAG re-embeds only if L2/L3 hashes changed
```

### 9.3 Cold Start Protocol
If `.machine-doc/` does not exist (fresh project, first clone):
1.  `flow index --full` scans the entire codebase using Tree-sitter.
2.  Generates the complete symbol index.
3.  The Validation Gate enters `warn` mode (logs violations but does not reject) until the index stabilizes.
4.  After first full index, subsequent updates are incremental.

---

## 10. Enhanced Synchronization Strategy

### 10.1 Content-Addressable Identity for Renames
The current `rag_manifest.json` keyed by `file_path` breaks on renames — the old path gets orphaned, the new path gets re-embedded, creating duplicates.

**Solution**: Use a content-addressable identity derived from the AST:
*   **Symbol ID**: `hash(fully_qualified_name + normalized_signature)`
*   On rename: if the symbol ID matches, update the `file_path` metadata without re-embedding.
*   Only if the symbol's *content* changes should it be re-embedded.

### 10.2 Manifest Schema Versioning
To prevent silent corruption when upgrading the manifest format:
```json
{
  "schema_version": "0.2",
  "generated_at": "2026-03-01T12:00:00Z",
  "files": { ... }
}
```
If `schema_version` does not match the expected version, `flow index` should prompt for a full rebuild rather than attempting to incrementally update an incompatible manifest.

### 10.3 Branch-Aware Indexing
When switching git branches, the delta between the current index and the branch target should be computed via `git diff`:
1.  `git diff --name-status main..feature-branch` → list of changed files.
2.  Only re-parse and re-embed changed files.
3.  Delete index entries for removed files.

---

## 11. Context Budget Management

### 11.1 The Token Explosion Problem
In large codebases with many relevant symbols, RAG retrieval can overwhelm the agent's context window, reducing reasoning quality.

### 11.2 Retrieval Budget Configuration
```json
{
  "knowledge": {
    "max_retrieval_chunks": 10,
    "max_retrieval_tokens": 4096,
    "max_symbols_per_request": 20,
    "retrieval_radius": "module"
  }
}
```

### 11.3 Budget Enforcement Strategies
*   **Top-K Hard Cap**: Never return more than `max_retrieval_chunks` results regardless of relevance.
*   **Retrieval Radius**: Limit search to the current module (`module`), package (`package`), or entire project (`project`).
*   **Summary Fallback**: If the raw code exceeds `max_retrieval_tokens`, replace with the L2 (signature) summary instead of the full L1 (implementation) body.

---

## 12. Deterministic Feature Vectors (No-LLM Option)

### 12.1 Concept
For environments where LLM-based embedding is too slow, expensive, or non-deterministic, Flow Manager should support a **deterministic feature vector** mode:

*   **Fixed 256-dimension vector** derived purely from structural AST properties.
*   No LLM calls required.
*   Same code always produces the same vector.

### 12.2 Vector Composition

| Segment | Dims | Content |
|:---|:---|:---|
| Symmetry Bits | 32 | One-hot encoding: language, visibility, side_effects, transport, is_async |
| Identity Hash | 64 | Reduced hash of fully qualified name |
| Structural Fingerprint | 160 | Hashed parameter types, return types, exception types, decorator presence |

### 12.3 Trade-offs
*   **Pro**: Deterministic, fast, no API cost, reproducible across environments.
*   **Con**: No semantic understanding — cannot find "similar intent" functions, only structurally similar ones.
*   **Recommendation**: Use as a **secondary** vector alongside LLM-generated semantic vectors. Enable "Dual-Track" search: semantic for intent matching, deterministic for structural matching.

---

## 13. Tiered RAG Access Rights

### 13.1 Problem: "God-Object" Agents
When an agent has full access to every service's internals, it writes code that bypasses API contracts and reaches directly into implementation details of other services. This creates tight coupling and violates microservice boundaries.

### 13.2 Access Tier Model
Every RAG query must include an `agent_scope` parameter. The `KnowledgeService` filters results based on the agent's tier:

| Tier | Scope | Sees | Does NOT See |
|:---|:---|:---|:---|
| **Internal** | Own microservice (local) | Full AST: public, protected, private symbols + DB schema + call graph | — |
| **Contract** | Other microservice (remote) | Public API only: `.proto`, OpenAPI, Kafka schemas, external entrypoints | Private methods, internal classes, DB schema, implementation logic |
| **Architectural** | System-wide consulting | Service topology, event schemas, data flow direction | Any code, any implementation details |

### 13.3 Implementation
*   All symbols in `.machine-doc/symbols.json` carry a `visibility` field and a `namespace` (owning service).
*   All RAG retrieval calls include `agent_scope: { service: "order-engine", tier: "internal" }`.
*   The `KnowledgeService` applies metadata filters before returning results.
*   Cross-service edges (gRPC, Kafka, REST) are always visible regardless of tier — they represent the *contract*, not the implementation.

### 13.4 Benefits
*   Enforces contract-driven development at the agent level.
*   Reduces context window usage by filtering irrelevant symbols.
*   Prevents agents from creating "distributed monolith" patterns where services leak internal details.

---

## 14. Symbol Contract Versioning (SemVer-Like)

### 14.1 Problem: Change Impact Ambiguity
When a symbol changes, the current L1/L2/L3 hash system (§7) detects *that* something changed, but not *how significant* the change is for downstream consumers.

### 14.2 Automatic Version Increment
Add a `symbol_version` field to the symbol schema. It auto-increments based on hash level:

| Hash Level Changed | Version Bump | Example |
|:---|:---|:---|
| L1 (Implementation only) | Patch (`x.x.+1`) | `1.0.2` → `1.0.3` |
| L2 (Signature change) | Minor (`x.+1.0`) | `1.0.3` → `1.1.0` |
| L3 (Contract/Interface) | Major (`+1.0.0`) | `1.1.0` → `2.0.0` |

### 14.3 Side-by-Side Versioning
When a symbol's major version changes, the old version is retained as a **ghost entry** (see §8.4) alongside the new version:

```json
{
  "symbol_id": "OrderService.place_v2",
  "version": "2.0.0",
  "status": "active",
  "replaces": "OrderService.place_v1",
  "consumers_on_old_version": ["RiskService", "Logger"]
}
```

### 14.4 Agent Behavior
*   When an agent queries the RAG, it receives only `"active"` versions by default.
*   If legacy code still references the old version, the Validation Gate flags a "Deprecated Symbol" warning.

---

## 15. Shadow Indexer (Drift Detection for Manual Edits)

### 15.1 Problem: Code Modified Outside Tool Pipeline
If a developer modifies code without using FM's file tools (e.g., direct IDE editing), the `.machine-doc/` index silently diverges from reality. This causes the Validation Gate to validate against stale symbol data — the worst kind of false sense of security.

### 15.2 `flow index --verify` Command
A lightweight command that:
1. Computes current file hashes for all tracked files.
2. Compares against `file_hashes.json` in `.machine-doc/`.
3. Reports files that have drifted without triggering a full re-index.

```
$ flow index --verify
⚠️  3 files have changed outside the tool pipeline:
  - src/flow/domain/parser.py (L2 hash mismatch — signature changed)
  - src/flow/engine/core.py (L1 hash mismatch — implementation only)
  - src/flow/tools/file_tool.py (L1 hash mismatch — implementation only)

Run `flow index --update` to reconcile.
```

### 15.3 Integration Points
*   **Git pre-commit hook**: Run `flow index --verify` before every commit. Warn (or block) if drift is detected.
*   **CI/CD gate**: Reject PRs where the committed `.machine-doc/` doesn't match the code.
*   **Periodic background**: In daemon mode (Phase 3+), run every N minutes.

### 15.4 Non-Goal
The shadow indexer does NOT re-index automatically. It only *detects* drift. The developer or agent must explicitly run `flow index --update` to reconcile. This prevents unexpected index changes during active agent work.

