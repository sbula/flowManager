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
