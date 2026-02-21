# Flow Manager: RAG & Knowledge System Architecture

## 1. Executive Summary

The **Knowledge System** is a semantic intelligence layer designed to decouple the "Memory" of the codebase from the "Reasoning" of the Agent. It provides **Retrieval-Augmented Generation (RAG)** to safely and efficiently give the agent deep context about the system without context-window stuffing. It relies on a fully local-first stack where possible, but is built agnostically.

**Key Design Principles (Aligned with 01_06 Spec):**
1.  **Structure-Aware Ingestion**: Instead of naive text splitting, we use tools like **Tree-sitter** to parse code into semantic chunks (Classes, Functions, Modules).
2.  **Evolution Tracking**: We use a **Manifest-based Hashing Strategy** (`rag_manifest.json`) to track file changes incrementally and prevent redundant re-indexing.
3.  **Model Agnostic**: Zero lock-in. Uses an **LLM Gateway / Profile Router** to support Gemini, Ollama, OpenAI, or Anthropic depending on the cognitive task.
4.  **Local First**: All vector data is stored locally using **ChromaDB** (or LanceDB) for privacy and speed.

## 2. System Architecture

```mermaid
graph TD
    subgraph "Flow Manager"
        A[Agent/Atom] -->|Query| B[KnowledgeService]
    end

    subgraph "Knowledge Core"
        B -->|Retrieve| C[VectorStore (ChromaDB)]
        B -->|Synthesize| D[LLM Gateway / Router]
        
        D -->|Route| E{Task Profile}
        E -->|Coding| F[Claude / DeepSeek]
        E -->|Reasoning| G[Thinking Model]
        E -->|Fast Chat| H[Gemini Flash / Llama 3]
    end

    subgraph "Ingestion Pipeline"
        L[IngestionEngine] -->|Scan| M[Manifest Manager]
        M -->|Changed?| N{Hash Diff}
        N -->|Yes| O[Semantic Parse (Tree-sitter)]
        O -->|Chunk| P[Embed & Upsert]
        N -->|No| Q[Skip]
    end

    subgraph "Events"
        Z[Git Hooks / Cron] -->|Trigger| L
    end
```

## 3. The Ingestion Strategy

### 3.1 What to Index
| Content Type | Granularity | Metadata |
|--------------|-------------|----------|
| **Code** | Function/class level (Tree-sitter) | Language, file path, imports |
| **Documentation** | Section level (Markdown headers) | Type (API/guide/spec) |
| **Tests** | Test case | Target function, assertions |
| **Decisions (ADRs)** | Document level | Linked issue/feature |

### 3.2 Manifest Manager (`rag_manifest.json`)
To avoid "wasting reading and relinking unchanged code," an incremental State Manifest is used.
*   **Location**: `.flow/rag_manifest.json`
*   **Trigger**: On ingestion trigger (e.g., git `post-commit` hook), the engine computes the SHA256 hash of targets.
    *   `New/Changed Hash`: Parse, Embed, Upsert. Update Manifest.
    *   `Deleted`: Remove from Chroma. Update Manifest.
    *   `Unchanged`: Skip. Zero API calls, zero processing.

### 3.3 Semantic Chunking Implementation Strategy
We avoid naive splitting. Code must be extracted using ASTs:
```python
# Extract functions/classes as atomic chunks
def extract_code_chunks(file_path, language):
    parser = get_tree_sitter_parser(language)
    tree = parser.parse(file_path.read_bytes())
    
    chunks = []
    for node in tree.root_node.children:
        if node.type in ['function_definition', 'class_definition']:
            chunks.append({
                'content': node.text.decode('utf-8'),
                'type': node.type,
                'name': extract_name(node),
                'file': str(file_path)
            })
    return chunks
```

### 3.4 Cold Start Mitigation
To ensure fast boot times, base Docker images or environments can ship with **Pre-Computed Indexes** for standard libraries or stable core modules. The system only indexes the "delta" missing from the manifest on startup.

## 4. Retrieval & Query Patterns

### 4.1 Query Processing
The `KnowledgeService` supports querying across code, documentation, and historical decisions through multiple techniques:
1.  **Semantic Search**: Querying ChromaDB with an LLM-generated embedding.
2.  **Structural Search**: Using tools like `ast-grep` to find exact functional patterns (e.g., `ast.grep("async def $FUNC($ARGS)")`).
3.  **Hybrid Search**: Combining embedding similarity with strict metadata filtering.

```python
# Semantic + metadata filters Example
results = rag.query(
    query="database connection pooling",
    where={
        "language": "rust",
        "service": "portfolio-service"
    }
)
```

### 4.2 Expert Profiles & LLM Routing
The system uses **Expert Profiles** in `flow_config.json` to route tasks to the best-suited model. The Knowledge System acts as a Gateway.

```json
"knowledge": {
  "embedding_provider": "local/ollama",
  "embedding_model": "nomic-embed-text",
  "profiles": {
    "default": { "provider": "gemini", "model": "gemini-1.5-flash" },
    "coding": { "provider": "anthropic", "model": "claude-3-5-sonnet" },
    "reasoning": { "provider": "ollama", "model": "deepseek-r1:7b", "api_base": "http://localhost:11434" }
  }
}
```

### 4.3 Flow Manager Integration
Retrieval is integrated directly into the Flow Engine via Atoms like `RAG_Context_Gather`. The context is injected into the prompt payload before the LLM generates a response.

## 5. Technology Stack Selection

| Component | Choice | Rationale |
| :--- | :--- | :--- |
| **Orchestration** | **Custom Python Wrapper** | Explicit control over context and routing. |
| **Vector DB** | **ChromaDB** | Local, fast, Python-native. (LanceDB as backup if scale > 500k LOC). |
| **Parsing** | **Tree-sitter** | Industry standard for robust code parsing over multi-language bases. |
| **Embeddings** | **Ollama** | Local, zero API costs, full privacy. |
| **Providers** | **LLM Gateway** | Best-of-breed selection (Claude for Code, Local for Privacy). |
