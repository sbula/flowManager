# Legacy Extraction — Valuable Information From Deprecated Files

> **Date**: 2026-03-08
> **Purpose**: Preserved knowledge from `docs/archive/` (11 files) and `workflow_core/` before deletion.
> **Rule**: Only non-redundant information is included here. Content already covered in `spec_methodology.md`, `completeness_tests.md`, `lifecycle_layers.md`, or `fractal_patterns.md` is omitted.

---

## 1. Incident Report: Agent Bypass Prevention

**Source**: `workflow_core/audit/incident_2025_12_30_validate_bypass.md`

On 2025-12-30, the agent bypassed the Flow Manager protocol and executed `validate.sh` directly. This caused:
1. **Context loss**: The script had no knowledge of task ID, phase, or blocking requirements
2. **State corruption**: Artifacts produced outside the flow were untracked
3. **Habit formation**: Eroded the "single point of entry" discipline

**Lesson preserved**: *"The Flow Manager is the Operating System. The Scripts are the Kernel. User code (Agent) calls the OS, never the Kernel directly."*

**Relevance**: This directly supports the Constitution Template's §6 (Prohibited Actions) — agents must not bypass the orchestrator. It's also an argument for the read-only reviewer pattern (agents shouldn't have escape hatches).

---

## 2. Triage Agent Design (Dynamic Expert Routing)

**Source**: `docs/archive/part9_synthesis_and_optimizations.md`

The V2 design included a **Triage Agent** — an LLM that dynamically assigns work to experts based on task complexity, rather than using hardcoded expert lists.

**Input**: Task name + context + available expert capabilities
**Output**: JSON with complexity rating, recommended model, execution strategy (parallel/sequential), and selected experts with per-expert focus directives.

```json
{
  "complexity": "HIGH",
  "recommended_model": "gemini-1.5-pro",
  "execution_strategy": "parallel_blind",
  "selected_experts": [
    {
      "role_id": "quant_dev",
      "reason": "MACD requires statistical validation",
      "focus_directives": ["Check for look-ahead bias"]
    }
  ]
}
```

**Key insight**: The triage output becomes the **configuration input** for the next workflow step. This is "configuration-as-data-flow" — the agent's decision literally configures what runs next.

**Relevance**: Directly applicable to SpecWeaver's L2 (Architecture) layer — an agent could triage which experts review a Feature Spec, based on the domain and complexity.

---

## 3. YAML Frontmatter Plan Format

**Source**: `docs/archive/part4_development_plan_format.md`

Proposed a hybrid YAML+Markdown format for development plans:

```yaml
---
plan_metadata:
  task_id: "4.3.2"
  planning_level: 4
  parent_plan: "file://./parent.md"
  status: "DRAFT"  # DRAFT | READY_FOR_REVIEW | APPROVED | REJECTED

context:
  phase: "Phase 5"
  service: "Market Intelligence"
  expert_set: "AlphaSquad"

tracking:
  created: "2026-01-23T14:00:00Z"
  agents:
    - role: "Analyst"
      completed: true
    - role: "Planner"
      completed: false

validation:
  schema_version: "2.0"
  required_sections: ["Analysis", "Proposed Changes", "Verification Plan"]
---
# Implementation Plan: MACD Strategy Bundle
[Markdown body here]
```

**Why this matters**:
- **Machine-parseable**: YAML frontmatter is structured data that `sw check` can read
- **Agent tracking**: The `tracking` section records which agents contributed — useful for audit
- **State machine**: `status` field enables automated workflow (DRAFT→REVIEW→APPROVED→REJECTED)
- **Parent linking**: Explicit `parent_plan` enables fractal hierarchy traversal

**Relevance**: This format should inform how SpecWeaver's Component Specs are structured. The 5-section template (Purpose/Contract/Protocol/Policy/Boundaries) could use YAML frontmatter for machine-readable metadata while keeping the body in Markdown.

---

## 4. Business → Technical Analysis Framework (DDD-Based)

**Source**: `docs/archive/part6_analysis_process_framework.md`

A 4-phase framework for transforming business requirements into technical specs, using Domain-Driven Design (DDD) concepts:

### Phase 1: Domain Discovery
- Structured questionnaire (`domain_discovery.yaml`)
- Questions: "What problem?", "Who are users?", "What are key entities?", "What actions?"
- Output: `discovery_notes.md`

### Phase 2: Context Mapping (DDD Bounded Contexts)
```yaml
contexts:
  - name: Signal Generation
    responsibility: Create and validate trading signals
    entities: [Signal, Indicator, Strategy]
    interfaces: [POST /signals]
    dependencies: [Market Data Context]
```

### Phase 3: Technical Design (Service Decomposition)
Decision matrix for monolith vs. microservices:

| Factor | Monolith | Microservices |
|--------|----------|---------------|
| Team size | < 5 | > 5 |
| Domain complexity | Low-Medium | High |
| Deployment frequency | Weekly | Daily |
| Scalability needs | Vertical | Horizontal |

### Phase 4: Implementation Specification
- API contracts (OpenAPI)
- Database schemas
- L4/L5 task breakdown

**Quality checklist per phase**:
- Discovery: All entities identified? Workflows documented? Business rules captured?
- Domain Model: Relationships clear? State machines defined? Ubiquitous language established?
- Context Map: Bounded contexts identified? Integration points defined?
- Technical Design: Single responsibilities? Tech stack justified? API contracts defined?

**Relevance**: This is the **L1 Business Engineering** layer that our `lifecycle_layers.md` describes abstractly. This framework provides concrete templates and questionnaires for that layer. The phase quality checklists are early versions of our completeness tests applied at L1.

---

## 5. Language Evaluation Decision

**Source**: `docs/archive/part7_implementation_language.md`

**Decision**: Keep Python for V2. The evaluation criteria were:

| Criterion | Weight | Winner |
|-----------|--------|--------|
| Configuration Flexibility | 30% | Python |
| Agent Integration | 25% | Python |
| Ecosystem | 20% | Python |
| Performance | 15% | Rust |
| Safety | 10% | Rust |

**Hybrid architecture option**: Python core + Rust extensions (via PyO3) for performance-critical atoms (file parsing, regex matching, parallel execution).

**When to reconsider Python**: Workflow execution > 5 seconds/task, managing > 10K tasks simultaneously, memory > 1GB/process.

**Relevance**: This decision should be captured in the project's Constitution (§2 Tech Stack). The evaluation criteria and thresholds for language migration are useful for any future revisit.

---

## 6. V2 RAG Architecture Decisions

**Source**: `docs/archive/knowledge_system_v1.md`, `knowledge_system_v2.md`

**Key architectural decisions**:
1. **Local-first**: All vector data stored locally (ChromaDB). No code leaves the machine.
2. **Expert Model Routing**: Different LLM models for different tasks (coding → Claude, reasoning → DeepSeek-R1, chat → Gemini Flash)
3. **Structure-aware indexing**: Tree-sitter for semantic code chunking (classes, functions, modules) — not naive text splitting
4. **Manifest-based hashing**: SHA256 content hashes per file. On ingestion, compare hashes: new/changed → re-embed, unchanged → skip. Zero API calls for unchanged files.
5. **HyDE optimization**: Hypothetical Document Embeddings — generate a hypothetical answer, then search for real code similar to that hypothesis. Improves retrieval quality.

**Relevance**: These decisions are captured at a higher level in `01_09_rag_spec.md` and `rag_architecture.md`. The manifest-based hashing pattern is reusable for SpecWeaver's own file change detection (e.g., re-running `sw check` only on changed specs).

---

## 7. Engine V1 Patterns Worth Preserving

**Source**: `docs/archive/02_Flow_Engine.md`, `03_Cognitive_Layer.md`, `04_Tooling_System.md`, `05_Lifecycle_Management.md`

### Crash Recovery Semantics
- State persisted to disk after every step (`.flow_state/<task_id>.json`)
- On hard crash: resume restarts the interrupted step from the beginning ("at-least-once" delivery)
- On logical stuck: `reset <task_id>` deletes state, next `start` treats it as fresh (but files on disk remain as "Draft")

### Context Pollution Prevention
Data must be **explicitly exported** from steps to be available downstream. No implicit global state.
```json
{
  "id": "analyze_repo",
  "export": { "summary": "repo_analysis_summary" }
}
```
Only `repo_analysis_summary` is available to subsequent steps. Everything else is ephemeral.

### Just-In-Time Context Loading
Instead of dumping the whole repo into LLM context, use FileSystem atoms to read specific files into variables immediately before the prompt step. Variables are "ephemeral" — used for one prompt and discarded unless exported.

### Git as Transaction Log
After every significant step, auto-commit with standardized message format: `[FlowManager] Step {step_id}: {description}`. Enables per-step rollback if an agent corrupts files.

**Relevance**: These patterns (explicit export, JIT loading, git-as-transaction-log) are implementation patterns for the L4 Implementation layer. They should be referenced when building SpecWeaver's own flow execution engine.

---

## 8. Expert Council System (V1 Implementation)

**Source**: `docs/archive/part1_current_state_assessment.md`

### Expert Sets (from `core_teams.json`)
| Team | Members |
|------|---------|
| ProductCouncil | PO, Principal Architect, Compliance |
| PlatformGrid | Backend Dev, DBA, SRE, Security |
| AlphaSquad | Quant Dev, ML Engineer, Performance Eng |
| ExecutionCore | Backend Dev, QA, Test Automation |
| QualityAssurance | QA, Test Automation, Performance |

### Fractal Templates
Same templates used at ALL levels (L1-L5): `research.j2`, `synthesis.j2`, `review.j2`. The template doesn't change — the context it receives determines the depth.

### Known Limitations (Identified by the Team)
1. **Agent Context Leakage**: Single agent sees all contexts → confirmation bias, rubber-stamp reviews
2. **Workflow Duplication**: Same patterns repeated, no inheritance/composition
3. **Document Format Rigidity**: Markdown hard for machines to parse
4. **No Agent Communication Protocol**: Context only through shared document access, no isolation

**Relevance**: Limitations 1 and 4 are directly solved by the Constitution Template (agent isolation, read-only reviewer) and the Lifecycle Layers (separate personas per layer). Limitation 2 is solved by the fractal model. Limitation 3 is solved by the YAML frontmatter format (§3 above).

---

## What Was Intentionally Omitted

The following content from the deprecated files is NOT preserved because it's already covered or superseded:

| Content | Why Omitted |
|---------|-------------|
| Fractal L1-L5 hierarchy definitions | Covered in `spec_methodology.md` §8 and `fractal_patterns.md` |
| Workflow JSON step definitions | Implementation-specific to V1, superseded by spec-driven approach |
| Python code for atoms/executor | Deprecated implementation code, not design knowledge |
| Detailed Jinja2 template system | V1-specific, SpecWeaver will define its own template system |
| Status.md parsing logic | V1-specific state management, superseded |
| Pydantic/JSON Schema config examples | Standard patterns, not project-specific knowledge |
| 114 workflow_core source files | Deprecated implementation — the ARCHITECTURE.md captured the design |
