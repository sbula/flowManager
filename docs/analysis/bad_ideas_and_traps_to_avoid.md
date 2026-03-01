# Bad Ideas, Traps, and Strategic Risks to Avoid

This document distills the critical "what NOT to do" insights and strategic risks identified during the architectural synthesis phase of Flow Manager's design.

## 1. Bad Ideas & Distractions (To Avoid)

- **🚨 Co-Locating Flow Manager With the Target Project**: In production, Flow Manager **MUST NOT** live inside the project directory it orchestrates. If it does, the agents FM controls could modify FM's own Validation Gate, SafePath, Symbol Index, or engine code — completely destroying the trust boundary. FM must be installed in a **separate, protected location**. Agents may only read/write files in the target project; they have zero access to FM's own source, config, or engine. See [00_MASTER_OVERVIEW.md](../00_MASTER_OVERVIEW.md) — Deployment Isolation.
- **Shared Chat Contexts During Reviews**: Allowing reviewers (like the SRE persona) to read the context or logic of a previous reviewer (like the Architect) inevitably leads to mode collapse and "lazy simulation." They must run on isolated file states using the Parallel Blind Review (Dispatcher) pattern.
- **Synchronous CLI Execution Bounds**: Running Flow Manager as a standard foreground Python script. If the terminal closes, the agents die mid-write. Flow Manager must act as a background daemon where the CLI and Web interfaces act as thin clients.
- **Over-Engineering the Semantic Mirror Early**: Trying to parse side-effects, purity, deep type inference (for Python/JS), and full cross-module data flow in v0.1. The mirror should start brutally small (Symbol ID, Signature, Visibility, Call Graph).
- **Naive Text Splitting**: Simply chopping code up and feeding it to an embedding model (the "dumb RAG" trap). This destroys architectural invariants. AST parsing (Tree-sitter) is mandatory.
- **Infinite Regeneration Loops**: Rejecting an agent's code without providing structural error context, causing the agent to blindly retry and burn quota. The Validation Gate *must* return structured JSON to fix the error.
- **"The Tree-Sitter Trap" in Ancient Java**: Assuming AST parsers will easily catch all logic in a 30-year-old monolith that relies heavily on XML config, AspectJ, or deep reflection. COB (Controlled Operational Boundary) and DB schema extraction are critical fallbacks.
- **Committing a Vector DB to Git**: Ensure only the deterministic JSON (`symbols.json`, `edges.json`) is committed as the `.machine-doc/`. Committing binary databases (like ChromaDB) causes merge conflicts and brittleness.
- **Agent-Authored Specs**: Agents should assist humans in writing specs, but humans must finalize them. If an agent writes a hallucinated spec, the Validation Gate will perfectly enforce a broken architecture.
- **"Polyglot Hallucination"**: An agent working across languages may write Kotlin-style logic in a Rust service (forgetting borrow checking) or Python idioms in Java. The deterministic feature vector (see `rag_analysis.md` §12) must include language idioms so the agent stays in the correct "mindset." RAG retrieval should always filter by the target language.
- **"Graph Explosion" in Legacy**: In a 30-year-old monolith, everything calls everything. If the retrieval radius is not hard-capped (`radius=1 or 2`, `max_symbols=20`), the agent's context will drown in irrelevant call chains. This is distinct from general "context explosion" — it specifically occurs when attempting to index *legacy* systems with deep, tangled call graphs.
- **"RAG Index Locking" in Multi-Agent Scenarios**: In multi-service environments, two agents updating the same symbol index simultaneously can create race conditions. Each microservice must *own* its own `.machine-doc/` subdirectory. Cross-service edges should be stored separately in a `cross_service_edges.json` file.
- **"Version Ghost" Trap**: If agent code is based on an old version of the RAG index (e.g., the index was updated by another agent or a manual commit), the agent's code silently references stale contracts. Mitigation: include `index_version` or `git_sha` in the validation context. If the agent's context is older than the index, force a re-query before proceeding.
- **"Hidden Dependency" Across Services**: Service A calls Service B via a public API. Service B changes its *internal logic* but not its *signature*. The agent in Service A may make assumptions about B's behavior based on old behavior. Mitigation: contract tests should be triggered across service boundaries when internal changes are detected (Phase 3+).

## 2. Strategic Risks

- **Spec Degradation**: If the specifications (the input to the MVP loop) degrade into fuzzy prose rather than structured constraints (e.g., JSON/YAML with `must_call` or `must_not_modify`), the Validation Gate loses its leverage. 
  - *Mitigation*: Enforce strict, machine-readable schemas for tasks/specs.
- **Context Explosion**: Feeding the agent the entire dependency graph of a symbol. 
  - *Mitigation*: Strictly enforce a `radius=1` or `max_symbols=20` limit during RAG retrieval.
- **Silent Drift**: "Agent code applied but semantic mirror not updated." 
  - *Mitigation*: Make the file-write tool and the `.machine-doc/` update a single atomic transaction.
- **Schema Creep**: Every new feature adds new fields to the symbol schema. After several iterations, the schema becomes bloated, migrations are painful, and determinism becomes fragile.
  - *Mitigation*: Bump `schema_version` on every structural change. Write migration scripts. Never silently evolve the schema.
- **Index Staleness from Manual Edits**: Developers modifying code outside the FM tool pipeline causes the `.machine-doc/` index to silently diverge from reality.
  - *Mitigation*: Implement `flow index --verify` as a lightweight hash-diff command. Can run as a git pre-commit hook.

## 3. AI Conversation Quality Warnings

> **Source**: Identified during cross-referencing of external AI conversations against Flow Manager documentation (March 2026).

- **Fabricated IDE Features**: Several AI conversations **hallucinated Antigravity IDE features** — claiming existence of an "Agent Manager sidebar," a `google.adk` Python library, and a `ParallelAgent` class within the IDE. The *architectural patterns* these conversations described (parallel isolation, file-based I/O, clean-slate contexts) are sound and already documented in our specs. However, the specific tooling claims are false. Flow Manager must implement these patterns in its own engine.
- **Quantivista Bleed-Through**: When discussing Flow Manager architecture, AI conversations frequently confused Flow Manager (the builder tool) with Quantivista (the trading platform being built). Any ideas about regime modules, VWAP calculations, candle data, or market microstructure belong to Quantivista documentation, not Flow Manager.
- **Speculative Success Probabilities**: AI conversations assigned specific percentage success rates (e.g., "65% success probability"). These numbers are fabricated — there is no empirical basis for them. Disregard all numeric probability claims from AI conversations.
