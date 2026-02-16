# Knowledge System Design (V2.3)

> **Status**: APPROVED
> **Objective**: Define the architecture for a rigorous, local-first RAG system to track codebase evolution, documentation, and decision-making.

## 1. Executive Summary

The **Knowledge System V2** is a semantic intelligence layer designed to decouple the "Memory" of the codebase from the "Reasoning" of the Agent. It addresses the limitations of context-window stuffing by providing **Retrieval-Augmented Generation (RAG)**.

**Key Design Principles:**
1.  **Model Agnostic**: Zero lock-in to Gemini. The system uses an **LLM Gateway** pattern to support Gemini (current), Ollama (local target), and major providers (OpenAI, Anthropic, DeepSeek).
2.  **Expert Model Routing**: Configure distinct models for different cognitive tasks (e.g., *DeepSeek-R1* for Reasoning/Decisions, *Claude 3.5 Sonnet* for Coding).
3.  **Structure-Aware Indexing**: Instead of naive text splitting, we use **Tree-sitter** to parse code into semantic chunks (Classes, Functions, Modules).
4.  **Efficiency First**: We implement a **Manifest-based Hashing Strategy** to track file changes (SHA256) and prevent redundant re-indexing/re-embedding.
5.  **Local Supremacy**: All vector data is stored locally (ChromaDB).

---

## 2. System Architecture

```mermaid
graph TD
    subgraph "Flow Manager"
        A[Agent/Atom] -->|Query| B[KnowledgeService]
    end

    subgraph "Knowledge Core"
        B -->|Retrieve| C[VectorStore (ChromaDB)]
        B -->|Synthesize| D[LLM Gateway]
        
        D -->|Route| E{Task Type}
        E -->|Coding| F[Coding Model (Claude/DeepSeek)]
        E -->|Reasoning| G[Thinking Model (o1/R1)]
        E -->|Chat| H[Fast Model (Gemini Flash)]
    end

    subgraph "Ingestion Pipeline"
        L[IngestionEngine] -->|Scan| M[Manifest Manager]
        M -->|Changed?| N{Hash Diff}
        N -->|Yes| O[Tree-sitter Parse]
        O -->|Chunk| P[Embed & Upsert]
        N -->|No| Q[Skip]
    end
```

### 2.1 Components

1.  **`KnowledgeService`**: The internal API.
    *   `ask(question, task_type='general')`: Routes to the appropriate model based on task.
2.  **`LLM Gateway`**: Handles the routing logic.
3.  **`VectorStore`**: `ChromaDB` (Local).
4.  **`IngestionEngine`**: Optimized background worker.

---

## 3. Configuration & Routing

We introduce **Expert Profiles** in `flow_config.json`. This allows precise control over which model handles which domain.

```json
{
  "knowledge": {
    "embedding_provider": "ollama",
    "embedding_model": "nomic-embed-text",
    
    "profiles": {
      "default": {
        "provider": "gemini",
        "model": "gemini-1.5-flash"
      },
      "coding": {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20240620",
        "temperature": 0.1
      },
      "reasoning": {
        "provider": "ollama",
        "model": "deepseek-r1:7b",
        "api_base": "http://localhost:11434"
      },
      "decisions": {
        "provider": "openai",
        "model": "o1-mini",
        "description": "Used for analyzing ADRs and architectural consistency"
      }
    }
  }
}
```

---

## 4. Optimization: Manifest & Hashing

To avoid "wasting reading and relinking unchanged code," we use a **State Manifest**.

### 4.1 `rag_manifest.json`
Located in `.flow/rag_manifest.json`. It maps file paths to their SHA256 content hash.

```json
{
  "src/app.py": "a1b2c3d4...",
  "docs/design/knowledge_system_v2.md": "e5f6g7h8..."
}
```

### 4.2 Ingestion Logic
On every run (or triggered event):
1.  **Scan**: Walk the target directories (`src/`, `docs/`).
2.  **Hash**: Compute `SHA256` for each file.
3.  **Compare**:
    *   **New/Changed**: Trigger `Tree-sitter` parsing -> Embedding -> Upsert to Chroma. Update Manifest.
    *   **Deleted**: Remove from Chroma. Update Manifest.
    *   **Unchanged**: **SKIP**. Zero API calls, zero processing.

---

## 5. LLM Abstraction (The "Universal Adapter")

```python
class LLMGateway:
    def __init__(self, config):
        self.providers = self._init_providers(config)

    def generate(self, prompt: str, profile: str = 'default') -> str:
        provider_config = self.config['profiles'].get(profile, self.config['profiles']['default'])
        adapter = self.providers[provider_config['provider']]
        return adapter.generate(prompt, model=provider_config['model'])
```

---

## 6. Data Schema & Strategy

### 6.1 The "Knowledge Artifact"
1.  **Code**: Source files (`.py`, `.rs`, `.ts`).
2.  **Documentation**: Specs, ADRs, Plans (`.md`).
3.  **Decisions**: Structured logs of "Why" (linked via Metadata).

### 6.2 Feature Flag: Decision Context
To support "Reviewing Agents":

```python
def ask(self, query: str, profile: str = 'default', include_decisions: bool = True):
    # Routing + Context Filter
    ...
```

### 6.3 Metadata Schema (ChromaDB)

```json
{
  "id": "src/app.py:MyClass.run:hash",
  "document_id": "src/app.py",
  "type": "code_function",
  "language": "python",
  "decision_ref": "ADR-004-Local-RAG"
}
```

---

## 7. Implementation Roadmap

### Phase 1: Foundation (The "Skeleton")
*   [ ] Define `LLMProvider` interface and `LLMGateway`.
*   [ ] Implement Adapters: `GeminiProviders` (google-generativeai), `OpenAIProvider`, `AnthropicProvider`, `OllamaProvider`.
*   [ ] Implement `ChromaVectorStore` (basic add/query).
*   [ ] Create `KnowledgeService` singleton.

### Phase 2: Refined Ingestion (The "Brain")
*   [ ] Integrate `tree-sitter` bindings for Python.
*   [ ] Implement `CodeSplitter` logic (Semantic Chunking).
*   [ ] Create `IngestionEngine` with **Manifest & Hashing**.

### Phase 3: Workflow Integration (The "Hands")
*   [ ] Create `RagRetrievalAtom` with `profile` and `include_decisions` arguments.
*   [ ] Build "Ask Codebase" workflow.
*   [ ] Index existing `docs/` and `src/`.

---

## 8. Technology Stack Selection

| Component | Choice | Rationale |
| :--- | :--- | :--- |
| **Orchestration** | **Custom Wrapper** | Explicit control over context and routing. |
| **Vector DB** | **ChromaDB** | Local, fast, python-native. |
| **Parsing** | **Tree-sitter** | Industry standard for robust code parsing. |
| **Providers** | **Expert Router** | Best-of-breed selection (Claude for Code, o1 for Logic). |
