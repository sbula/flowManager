# Flow Synthesis: Secure Agent-Driven Development Workflows

> **Research Date:** 2026-03-08  
> **Purpose:** Analyze how engineers, companies, and open-source projects design workflows for writing **secure** code (not vibe coding) using AI agents. Focus on requirement decomposition, spec granularity, and code review/acceptance gates.

---

## 1. The Problem: Why "Vibe Coding" Fails

"Vibe coding" — accepting AI-generated code without critical review, planning, or testing — produces:
- **Bloated codebases** with duplicated logic
- **Security vulnerabilities** (OWASP Top 10 violations baked in silently)
- **Architectural drift** that compounds over time
- **Untestable code** due to missing contracts and unclear boundaries
- **Technical debt** that costs 10x more to fix later

Every serious agent-driven workflow is fundamentally a response to this problem. The common insight: **AI agents are powerful junior developers who need structured constraints, clear specs, and mandatory review gates.**

---

## 2. Researched Approaches

### 2.1 TheMorpheus407 — `the-dmz` Repository (Complete Agent Ecosystem)

**Source:** [github.com/TheMorpheus407/the-dmz](https://github.com/TheMorpheus407/the-dmz)

What initially looked like a single script (`auto-develop.sh`) is actually a **complete, production-grade agent ecosystem** for building a real product (a cybersecurity training game). Deep-diving the full repository reveals a layered architecture of governance, memory, specialization, and automation that is the most comprehensive working example found.

#### The Full Stack (not just the script)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Layer 1: GOVERNANCE (immutable, human-authored)                      │
│   SOUL.md        — project constitution (identity, tech, standards)  │
│   AGENTS.md      — master agent instructions + prohibited actions    │
│   CONTRIBUTING.md — human contribution rules, CI pipeline, hooks     │
├──────────────────────────────────────────────────────────────────────┤
│ Layer 2: DOCUMENTATION (~47K lines, human-authored, agent-consumed) │
│   docs/BRD.md        — 1,363 lines business requirements            │
│   docs/DD/           — 14 Design Documents (~24,500 lines)          │
│   docs/BRD/          — 14 BRD research files (~22,200 lines)        │
│   docs/MILESTONES.md — M0–M16 development roadmap                   │
│   docs/story.md      — game premise (context for agents)            │
│   docs/adr/          — architecture decision records                 │
├──────────────────────────────────────────────────────────────────────┤
│ Layer 3: LIVING MEMORY (agent-updated)                               │
│   MEMORY.md — project state, tech decisions, completed work,         │
│               known blockers, update instructions                    │
├──────────────────────────────────────────────────────────────────────┤
│ Layer 4: SUB-AGENT SPECIALIZATION (.claude/agents/)                  │
│   backend.md  — Fastify, game engine, event sourcing                 │
│   frontend.md — SvelteKit, Svelte 5, PixiJS, terminal aesthetic     │
│   database.md — Drizzle, migrations, PostgreSQL RLS                  │
│   testing.md  — Vitest, Playwright, property-based tests             │
│   devops.md   — Docker, CI/CD, Dockerfiles                           │
│   reviewer.md — 15-point review checklist, OWASP, ACCEPTED/DENIED   │
├──────────────────────────────────────────────────────────────────────┤
│ Layer 5: AUTOMATION (bash orchestration)                             │
│   auto-create-issues.sh — docs → GitHub issues pipeline              │
│   auto-develop.sh       — issue → code → review → merge pipeline     │
└──────────────────────────────────────────────────────────────────────┘
```

---

#### Layer 1: SOUL.md — The Project Constitution

`SOUL.md` is a read-only file that **agents must not modify**. It defines:

| Section | Purpose |
|---------|---------|
| **Identity** | Project name, premise, market positioning |
| **Tech Stack** | Complete technology table (frontend, backend, DB, ORM, testing, CI/CD, infra) |
| **Architecture Principles** | 7 non-negotiable rules (e.g., "Event sourcing from day one", "tenant_id on every table from day one", "Modular monolith first") |
| **Coding Standards** | TypeScript strict mode, Svelte 5 runes only, named exports, server-authoritative state, Zod validation, Pino structured logging, error codes registry |
| **Security Principles** | OWASP Top 10, no secrets in code, CSP headers, Trusted Types, input validation at every boundary, rate limiting, AI content safety rules |
| **Key Documents** | Index of all design documents with line counts |

**Key Insight:** Every agent — whether research, implement, review, or specialized sub-agent — is instructed to read `SOUL.md` first. This ensures all agents share the same non-negotiable constraints regardless of their role.

---

#### Layer 2: AGENTS.md — Master Agent Instructions

`AGENTS.md` defines the behavioral contract for all agents:

**8-Step Workflow:**
1. Work is driven by GitHub Issues
2. Read the issue, all comments, and relevant Design Documents before starting
3. Research before implementing — check `docs/DD/` for the relevant system specification
4. Implement in small, testable increments
5. Write or update tests for every change
6. Run tests before considering work complete
7. Never commit without passing tests
8. Update `MEMORY.md` when completing milestones or making significant decisions

**Prohibited Actions (4 categories):**

| Category | Examples |
|----------|----------|
| **Filesystem** | No reading/writing outside project root. No deleting top-level dirs. No modifying governance files (`SOUL.md`, `AGENTS.md`, `auto-develop.sh`) without explicit user instruction. No writing secrets to tracked files. |
| **Git** | No `git push --force` to master. No `git reset --hard` without user instruction. No amending pushed commits. No skipping hooks (`--no-verify`). |
| **System** | No installing system packages. No exploit tools. No persistent background services. No shell profiles. No downloading remote binaries. |
| **Content** | No real company/person names or URLs in game content. No copyrighted content without attribution. No offensive content. |

**Critical Design Decision:** Governance files are explicitly protected. Agents cannot modify their own constraints — a direct analog to a legal constitution that requires a special process to amend.

---

#### Layer 3: MEMORY.md — Living Project Memory

A Cline-style memory bank, but simpler and more focused:

| Section | Content |
|---------|---------|
| **Current State** | Active phase, active milestone, known blockers |
| **Completed Work** | Checklist of finished deliverables with file paths |
| **Tech Decisions Log** | Table: Decision, Choice, Rationale, Date |
| **Architecture Notes** | Key structural decisions (monorepo layout, event sourcing, route groups) |
| **Update Instructions** | 5-step procedure for agents to update memory |

**Key Insight:** The update instructions are themselves part of the file — teaching agents HOW to maintain the memory, not just what's in it. This is meta-cognition for agents.

---

#### Layer 4: Specialized Sub-Agents (`.claude/agents/`)

Each sub-agent file has:
- **YAML frontmatter**: name, description, tool permissions
- **Mandatory reading list**: Always starts with `SOUL.md` + `MEMORY.md` + relevant DDs
- **Domain-specific rules**: Detailed constraints for their area

**Tool Permissions by Role:**

| Agent | Read | Edit | Write | Glob | Grep | Bash |
|-------|------|------|-------|------|------|------|
| **backend** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **frontend** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **database** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **testing** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **devops** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **reviewer** | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |

**The reviewer agent is explicitly read-only for code** (no Edit, no Write) — it can only read code and run tests via Bash. This prevents the reviewer from "fixing" code and bypassing the implement→review separation.

**Reviewer's 15-Point Checklist (from `reviewer.md`):**
1. Issue fit
2. Correctness
3. Security (OWASP Top 10) — with specific details: `sanitizeInputHook`, CSP headers, rate limiting with Redis, `pnpm audit` in CI, secret detection
4. Error handling — standard envelope format with error codes registry
5. Tenant isolation — `tenant_id NOT NULL` on every scoped table, RLS policies
6. Event sourcing — immutable events, deterministic replay, `DomainEvent<T>` interface
7. TypeScript & Svelte — strict mode, no untyped `any`, Zod schemas compiled to JSON Schema
8. Module boundaries — imports only from `index.ts`, no cross-module internals
9. Accessibility — WCAG 2.1 AA, keyboard, screen reader, axe-core
10. Tests — run `pnpm test`, check coverage, verify colocated test files
11. Performance — no N+1 queries, unbounded loops, memory leaks
12. Standards — named exports, colocated tests, error codes, Pino logging, conventional commits, DRY
13. Database — migrations in correct path, append-only, TIMESTAMPTZ UTC, Drizzle DSL
14. Environment config — Zod-validated env vars, `.env.example` synced, no `.env` committed
15. Prohibited actions — cross-reference against `AGENTS.md` prohibited list

---

#### Layer 5a: `auto-create-issues.sh` — Documentation → Issues Pipeline

A separate automation that **creates GitHub issues from documentation**, filling the gap between specs and implementation:

```
MILESTONES.md + DDs + BRD → AI Agent → GitHub Issues (one at a time)
```

**How it works:**
1. Agent reads ALL docs (SOUL.md, MEMORY.md, AGENTS.md, MILESTONES.md, BRD.md, story.md, all DDs)
2. Agent reads ALL existing GitHub issues (open + closed for the milestone)
3. Agent creates exactly ONE new issue with:
   - Title format: `M{milestone}-{X}: {concise title}`
   - Structured body: Summary, Requirements, Acceptance Criteria checklist, Dependencies
   - Style modeled after previously solved issues
4. Deduplication: checks both open issues (globally) and closed issues (per milestone)
5. Loop continues until agent outputs `DONE` 3 consecutive times (3-strike termination)
6. Special mode: `--milestone 1337` = bug-fix discovery mode (finds real bugs in the codebase and creates issues for them)

**Key Insight:** Issues are not written manually. They're generated from the documentation by an AI agent, which ensures they inherit the right level of detail from the design documents. This is the missing "spec → tasks" bridge that GitHub Spec Kit describes.

---

#### Layer 5b: `auto-develop.sh` — Issue → Code → Review → Merge Pipeline

*(as previously documented)* Research → Implement → Dual Review → Finalize, with the DENIED feedback loop.

---

#### Layer 5c: CI Pipeline and Git Hooks (from `CONTRIBUTING.md`)

Even with agent automation, the project has traditional CI gates:

| Gate | Mechanism | When |
|------|-----------|------|
| **Secret Detection** | `secretlint` in pre-commit hook | Before every commit |
| **Lint on staged files** | `lint-staged` in pre-commit hook | Before every commit |
| **Commit message format** | `commitlint` in commit-msg hook | On every commit |
| **TypeScript strict check** | `pnpm typecheck` in pre-push hook | Before every push |
| **Full lint + typecheck + format** | CI job 1 | On every PR |
| **Unit tests with coverage** | CI job 2 (Vitest) | On every PR |
| **E2E tests** | CI job 3 (Playwright + Postgres + Redis) | On every PR |
| **Production build** | CI job 4 | On every PR |
| **DB migration smoke test** | CI job 5 (integration) | On every PR |

---

#### Full Workflow: Documentation to Deployed Code

```
[Human writes]     [Agent creates]      [Agent implements]     [Agents review]     [Agent finalizes]
     │                    │                     │                     │                     │
  SOUL.md ─────────► auto-create ────────► auto-develop ────────► Reviewer A ────────► Commit
  BRD.md              -issues.sh             Research              Reviewer B             Push
  DDs (14)               │                   Implement                │                  Close
  MILESTONES.md     GitHub Issues             Tests              ACCEPTED/DENIED          │
     │                    │                     │                     │                     │
     └────── feeds ──────┘└───── feeds ────────┘└────── gates ──────┘└───── gates ────────┘
                                                                          │
                                                                     CI Pipeline
                                                                  (lint, type, test,
                                                                   e2e, build, audit)
```

#### Updated Strengths (with full ecosystem context)
- **Layered governance:** Constitution (SOUL.md) → Instructions (AGENTS.md) → Sub-agent specialization → Automation
- **Documentation-first:** ~47K lines of specs BEFORE any code. Issues are generated from docs, not written ad-hoc
- **6 specialized sub-agents** with domain-specific mandatory reading lists and review criteria
- **Reviewer is read-only** — cannot modify code, only read and run tests
- **Triple safety net:** Agent review → CI hooks (secretlint, commitlint, typecheck) → CI pipeline (5 jobs)
- **Living memory** that agents maintain as they work
- **Prohibited actions** explicitly constrain agent capabilities (filesystem, git, system, content)
- **Traceability:** `logs/issues/{N}/` with research, implementation, and review artifacts

#### Remaining Gaps
- No explicit SAST scanning (Semgrep/CodeQL) — relies on OWASP awareness in reviewer prompt + `pnpm audit`
- No test coverage threshold enforcement (CI "enforces" thresholds but not clearly defined)
- The implement-review loop in `auto-develop.sh` can still theoretically cycle forever
- No sandboxing of agent execution (agents run with full developer permissions via `--dangerously-skip-permissions` / `--yolo`)
- Bug-fix discovery mode (`milestone 1337`) is creative but unvalidated — the agent might create phantom bugs

---

### 2.2 GitHub Spec Kit — Spec-Driven Development (SDD)

**Source:** GitHub Blog, Martin Fowler, multiple blog posts

GitHub's official framework for structured AI-assisted development. Formalizes the idea that **specs are the source of truth, not prompts**.

#### 5-Phase Workflow

```
Specify → Plan → Tasks → Implement → Validate
```

| Phase | Input | Output | Key Principle |
|-------|-------|--------|---------------|
| **Specify** | High-level description of *what* and *why* | `spec.md` — user journeys, success criteria, constraints, non-functional requirements | Human defines intent. AI structures it. |
| **Plan** | `spec.md` + existing codebase context | `plan.md` — technical architecture, tech stack, constraints, component interfaces | AI proposes architecture. Human validates. |
| **Tasks** | `plan.md` | `tasks.md` — granular, independent, testable units with acceptance criteria | Each task is a self-contained unit an agent can implement in one session. |
| **Implement** | Individual task from `tasks.md` + codebase context | Code changes + tests | Agent executes one task at a time. |
| **Validate** | Implemented code vs. `spec.md` | Test results, coverage report, manual review | Continuous validation against original spec. |

#### The `constitution.md` Concept

A project-level file establishing **non-negotiable principles** that all AI agents must follow. Think of it as a bill of rights for your codebase:

```markdown
# Constitution
1. All public functions must have JSDoc/docstring with parameter types
2. No direct database access outside the repository layer
3. All error handling must use the Result<T, E> pattern
4. Input validation happens at system boundaries only
5. Tests must cover happy path, sad path, and edge cases
```

#### Right-Sizing Tasks: The Goldilocks Principle

The critical challenge is task granularity. Too fine-grained = massive overhead, context loss. Too coarse = agent produces garbage.

**Practical heuristics observed across multiple sources:**

| ❌ Too Small | ✅ Right Size | ❌ Too Large |
|-------------|-------------|-------------|
| "Add a null check on line 42" | "Implement the UserRepository with CRUD operations, including input validation and error handling" | "Build the entire user management system" |
| "Rename variable x to userId" | "Create the authentication middleware that validates JWT tokens and attaches user context" | "Implement the backend API" |
| "Import the logging library" | "Add structured logging to the payment processing pipeline with correlation IDs" | "Add observability to the system" |

**Rule of thumb emerging from practice:**
- A task should be completable in **one agent session** (roughly 30-100 files of context)
- A task should produce **one testable behavior change**
- A task should touch **one logical component** (single responsibility)
- A task should have **clear acceptance criteria** (machine-verifiable when possible)

---

### 2.3 Cline — Memory Bank + Plan/Act Dual-Mode

**Source:** Cline documentation, community guides

Cline's approach addresses a different problem: **how does an agent maintain context across sessions and stay focused during long tasks?**

#### Memory Bank Architecture

A structured markdown-based documentation set persisted in `/memory-bank/`:

| File | Purpose |
|------|---------|
| `projectbrief.md` | Overall project scope and goals |
| `productContext.md` | Target users, UX goals, problems being solved |
| `systemPatterns.md` | Architecture, design patterns, key decisions |
| `techContext.md` | Tech stack, dependencies, constraints |
| `activeContext.md` | Current task, working notes, immediate context |
| `progress.md` | Status of completed and pending tasks |

This is essentially an **externalized working memory** that survives context window resets.

#### Plan/Act Mode Separation

1. **Plan Mode (read-only):** Agent analyzes codebase, reads files, asks clarifying questions, formulates implementation plan. **Cannot modify any files.** This is the "think before you act" gate.

2. **Act Mode (read/write):** After plan approval, agent implements the planned solution.

#### Deep Planning + Focus Chain

- **Deep Planning:** Two-agent workflow. Agent 1 investigates and produces a plan. A **fresh** Agent 2 executes the plan — preventing context contamination from exploration.
- **Focus Chain:** A persistent to-do list re-injected into context at regular intervals to prevent agent drift.

#### Key Insight
The separation of investigation context from implementation context prevents the agent from being biased by the paths it explored during research. This is similar to how human code reviewers should ideally not be the same person who wrote the code.

---

### 2.4 Plan-Act-Reflect Framework

**Source:** Academic papers, InfoQ, multiple engineering blogs

An iterative cycle drawn from PDCA (Plan-Do-Check-Act) adapted for AI agents:

```
┌──────────────────────────────────────────────┐
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │   PLAN   │──│   ACT    │──│  REFLECT  │──┤
│  └──────────┘  └──────────┘  └───────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

| Phase | Agent Activity | Human Activity |
|-------|---------------|----------------|
| **Plan** | Analyze requirements, propose approach, identify risks | Review plan, approve/reject, add constraints |
| **Act** | Generate code, write tests, run tools | Monitor progress, approve file modifications |
| **Reflect** | Summarize outcomes, identify what worked/didn't, propose improvements | Evaluate quality, decide next iteration |

#### Why This Matters for Security
The "Reflect" phase is where security review naturally fits. Without it, the cycle is just "generate and ship" — which is vibe coding.

---

### 2.5 Cursor Rules / Agent Configuration Files

**Source:** Cursor documentation, community `.cursorrules` examples

A complementary approach focused on **behavioral guardrails** rather than workflow structure.

#### Three-Tier Rule System

1. **Global Rules** — Core principles for all interactions ("prefer functional programming", "handle errors with Result types")
2. **Project Rules** — `.cursorrules` in project root ("use PostgreSQL, not MongoDB", "follow our API naming conventions")
3. **Pattern-Specific Rules** — `.cursor/rules/*.mdc` targeting specific file patterns ("React components must use hooks", "API handlers must validate input")

#### Practical Example Structure

```
.cursor/rules/
  security.mdc      # "Never use eval(). Always sanitize HTML. Use parameterized queries."
  testing.mdc       # "Every public function needs unit test. Mock external deps. Min 80% coverage."
  architecture.mdc  # "No circular deps. Services talk through interfaces. No direct DB in handlers."
  naming.mdc        # "camelCase for JS, snake_case for Python, PascalCase for classes."
```

#### How This Relates to Constitution.md

Cursor rules are a tool-specific implementation of the same principle as GitHub Spec Kit's `constitution.md`: **codified behavioral constraints that the agent must follow**. The key difference is that Cursor rules are automatically applied based on file patterns, while `constitution.md` must be explicitly referenced.

---

### 2.6 Multi-Agent Code Review with Security Gates

**Source:** Semgrep blog, OWASP guidelines, Claude Code documentation

The trend in 2025-2026 is towards **automated security review as a mandatory pipeline stage**, not optional.

#### Layered Security Review

```
Agent Code → SAST (Semgrep/Snyk) → AI Reviewer (correctness) → AI Reviewer (security) → Human Review → Merge
```

| Gate | Tool/Agent | Checks |
|------|-----------|--------|
| **Static Analysis** | Semgrep, Snyk Code, CodeQL | Known vulnerability patterns, dependency CVEs, secret detection |
| **AI Correctness Review** | Claude/GPT as code reviewer | Logic errors, edge cases, regression risk, test coverage |
| **AI Security Review** | Specialized security prompt | OWASP Top 10, input validation, auth/authz correctness, injection vectors |
| **Human Review** | Senior engineer | Architectural fit, business logic correctness, strategic decisions |

#### OWASP Top 10 for Agentic Applications (2025/2026)

A new OWASP list specifically for risks introduced by AI agents:
1. Excessive Agency / Privilege Escalation
2. Prompt Injection / Manipulation
3. Insecure Output Handling
4. Insufficient Access Control on Tools
5. Supply Chain Vulnerabilities (agent dependencies)

This means **the agent itself is an attack surface** and must be constrained.

---

## 3. Synthesized Workflow Pattern

Combining the strongest elements from all researched approaches:

```
┌─────────────────────────────────────────────────────────────────────┐
│                  SECURE AGENT-DRIVEN DEV WORKFLOW                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Phase 0: FOUNDATION (one-time)                                     │
│  ┌───────────────────────────────────────────────┐                  │
│  │ constitution.md  — non-negotiable principles  │                  │
│  │ agent_rules/     — behavioral constraints     │                  │
│  │ security_policy  — OWASP checklist            │                  │
│  │ memory_bank/     — persistent project context │                  │
│  └───────────────────────────────────────────────┘                  │
│                                                                     │
│  Phase 1: SPECIFY (Human-driven, AI-assisted)                      │
│  ┌───────────────────────────────────────────────┐                  │
│  │ Input:  High-level requirement / issue        │                  │
│  │ Output: spec.md (what, why, success criteria) │                  │
│  │ Gate:   Human approves spec before proceeding │                  │
│  └───────────────────────────────────────────────┘                  │
│                         │                                           │
│  Phase 2: RESEARCH (Agent-driven)                                   │
│  ┌───────────────────────────────────────────────┐                  │
│  │ Input:  spec.md + codebase                    │                  │
│  │ Output: research.md (impact analysis, risks,  │                  │
│  │         approach options, test strategy)       │                  │
│  │ Gate:   Human reviews research for blind spots│                  │
│  └───────────────────────────────────────────────┘                  │
│                         │                                           │
│  Phase 3: PLAN (Agent proposes, Human validates)                    │
│  ┌───────────────────────────────────────────────┐                  │
│  │ Input:  spec.md + research.md + constitution  │                  │
│  │ Output: plan.md (architecture, interfaces,    │                  │
│  │         component boundaries)                 │                  │
│  │ Gate:   Human approves architecture           │                  │
│  └───────────────────────────────────────────────┘                  │
│                         │                                           │
│  Phase 4: DECOMPOSE (Agent-driven, Human-reviewed)                  │
│  ┌───────────────────────────────────────────────┐                  │
│  │ Input:  plan.md                               │                  │
│  │ Output: tasks.md (ordered, atomic, testable)  │                  │
│  │ Gate:   Human validates task granularity       │                  │
│  └───────────────────────────────────────────────┘                  │
│                         │                                           │
│  Phase 5: IMPLEMENT (Agent-driven, per task)                        │
│  ┌───────────────────────────────────────────────┐                  │
│  │ For each task:                                │                  │
│  │   1. Fresh agent context (no leakage)         │                  │
│  │   2. Load: task + plan + constitution         │                  │
│  │   3. Implement + write tests                  │                  │
│  │   4. Agent does NOT commit                    │                  │
│  └───────────────────────────────────────────────┘                  │
│                         │                                           │
│  Phase 6: REVIEW (Multi-agent + automated gates)                    │
│  ┌───────────────────────────────────────────────┐                  │
│  │ Gate A: SAST scan (Semgrep/Snyk/CodeQL)       │                  │
│  │ Gate B: Lint + Type check                     │                  │
│  │ Gate C: AI Review — Correctness               │                  │
│  │ Gate D: AI Review — Security (OWASP)          │                  │
│  │ Gate E: AI Review — Spec compliance           │                  │
│  │ Gate F: Human review (Senior Engineer)        │                  │
│  │                                               │                  │
│  │ ANY gate fails → feedback to Phase 5          │                  │
│  │ ALL gates pass → proceed to Phase 7           │                  │
│  └───────────────────────────────────────────────┘                  │
│                         │                                           │
│  Phase 7: FINALIZE (Automated)                                      │
│  ┌───────────────────────────────────────────────┐                  │
│  │ 1. Commit with conventional message           │                  │
│  │ 2. Push to branch                             │                  │
│  │ 3. Create / update PR                         │                  │
│  │ 4. Update memory bank / progress tracking     │                  │
│  └───────────────────────────────────────────────┘                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Task Decomposition: Practical Sizing Guidelines

This is the hardest part to get right. Here's what the research converges on:

### The "One Behavior, One Boundary" Rule

A well-sized task should:

| Criterion | Test |
|-----------|------|
| **Single behavioral change** | Can you describe what changes in one sentence? |
| **Single component boundary** | Does it touch only one module/service/layer? |
| **Testable in isolation** | Can you write a test that proves it works without deploying everything? |
| **Context-window friendly** | Does the agent need to understand ≤50-100 files to do this? |
| **Reviewable in one sitting** | Can a reviewer understand the diff in <15 minutes? |
| **Acceptance criteria are machine-verifiable** | Can a test or linter confirm the criteria are met? |

### Task Template (from synthesized best practices)

```markdown
## Task: [descriptive name]

### Context
- Parent spec: [link to spec.md section]
- Depends on: [list completed tasks this builds on]

### Objective
[One sentence: what changes in the system after this task is done]

### Acceptance Criteria
- [ ] [Specific, testable criterion 1]
- [ ] [Specific, testable criterion 2]
- [ ] [Specific, testable criterion 3]

### Constraints
- Must follow: [link to constitution.md relevant sections]
- Must not: [explicit anti-patterns to avoid]
- File scope: [list of files/directories the agent may touch]

### Test Requirements
- Unit tests for: [list]
- Integration test for: [describe scenario]
- Coverage: must maintain ≥ [X]% on modified files

### Security Checklist
- [ ] Input validation at boundary
- [ ] No secrets in code
- [ ] No SQL/command injection vectors
- [ ] Error messages don't leak internals
```

---

## 5. Spec Granularity for Agent Implementation

### What Level of Detail Does an Agent Need?

From examining real-world successes and failures:

| Spec Element | Too Vague (Agent Fails) | Right Detail Level | Over-Specified (Human Waste) |
|-------------|------------------------|-------------------|------------------------------|
| **Behavior** | "Handle errors" | "On validation failure, return `Result.err(ValidationError)` with field-level messages. Never throw exceptions past service boundary." | "On line 42 of user_service.py, add a try-catch..." |
| **Interface** | "Create an API" | "POST `/api/v1/users` accepts `{name: string, email: string}`, returns `201 {id, name, email}` or `422 {errors: [{field, message}]}`. Rate-limited to 10 req/min per IP." | "Create UserController with method createUser that calls UserService.create which calls UserRepository.insert..." |
| **Data** | "Store user data" | "User entity: `{id: UUID, name: string(1-100), email: string(unique, RFC5322), created_at: ISO8601}`" | (actual SQL DDL in the spec) |

### The "Why, What, Constraints" Pattern

Every spec section should answer:
1. **Why** does this exist? (business context — helps agent make judgment calls)
2. **What** is the expected behavior? (contracts, inputs, outputs, state changes)
3. **What constraints apply?** (security requirements, performance bounds, compatibility)

### What to **NOT** put in a spec for agents:
- Implementation details (which classes, which patterns — unless mandated by constitution)
- Line-by-line instructions (defeats the purpose of having an agent)
- Ambiguous language ("should be fast", "handle edge cases", "be secure")

---

## 6. Review & Evaluation: Before Commit/Accept

### The Multi-Gate Review Model

Research converges on a **defense in depth** approach — no single gate is sufficient:

#### Gate 1: Automated Static Checks (instant, no agent needed)
- Lint (ESLint, ruff, clippy)
- Type check (TypeScript, mypy)
- Formatting (Prettier, Black)
- **Hard gate:** Any failure = automatic rejection

#### Gate 2: Security Scanning (automated, no agent needed)
- SAST tools (Semgrep, Snyk Code, CodeQL)
- Secret detection (TruffleHog, detect-secrets)
- Dependency vulnerability check (npm audit, pip audit)
- **Hard gate:** Critical/High findings = automatic rejection

#### Gate 3: AI Correctness Review (agent, different from implementer)
Focus areas:
- Logic errors and off-by-one bugs
- Missing edge case handling
- Regression risk analysis
- Test quality and coverage assessment
- DRY violations and code duplication
- Naming and readability
- **Output:** `ACCEPTED` or `DENIED` with specific feedback

#### Gate 4: AI Spec Compliance Review (agent, different from implementer)
Focus areas:
- Do the changes actually implement what the spec says?
- Are all acceptance criteria met?
- Are there unintended side effects on other spec sections?
- **Output:** `ACCEPTED` or `DENIED` with specific feedback

#### Gate 5: AI Security Review (agent with security prompt)
Focus areas:
- OWASP Top 10 checklist against the diff
- Input validation completeness
- Authentication/authorization correctness
- Injection vector analysis
- Error handling doesn't leak sensitive information
- **Output:** `ACCEPTED` or `DENIED` with specific feedback

#### Gate 6: Human Review (senior engineer)
Focus areas:
- Architectural fit (does this belong here?)
- Business logic correctness (does this solve the actual problem?)
- Strategic decisions (is this the right approach long-term?)
- Performance implications
- **Final authority:** Human can override all AI verdicts

### The Feedback Loop

```
DENIED at any gate
       │
       ▼
┌─────────────────────────────────┐
│ Denial feedback is appended to  │
│ agent context as CRITICAL input │
│ "Fix ALL issues raised. Do not  │
│  repeat the same mistakes."     │
└─────────────────────────────────┘
       │
       ▼
  Re-implement (fresh or incremental)
       │
       ▼
  Re-review from Gate 1
```

### Critical: Prevent Infinite Loops

The `auto-develop.sh` script lacks this, but production workflows need:
- **Max retry count** (e.g., 3 attempts per gate)
- **Escalation to human** after max retries
- **Circuit breaker** — if the agent consistently fails a gate, the task may need re-decomposition

---

## 7. Key Principles Distilled

### From All Sources Combined

1. **Spec before code.** No exceptions. The spec is the contract.

2. **Separate concerns across agents.** The agent that writes code should never be the one that reviews it. Different agents, different prompts, different biases.

3. **Fresh context per phase.** Cline's Deep Planning insight: investigation context contaminates implementation. Start clean.

4. **Defense in depth.** No single automated check is sufficient. Layer static analysis, AI review (multiple perspectives), and human review.

5. **Tasks must be atomic and testable.** One behavior, one boundary, one session.

6. **Constitution over convention.** Codify your non-negotiable rules. Agents follow explicit rules better than implicit conventions.

7. **Feedback loops with bounds.** Allow retry but prevent infinite loops. Escalate to humans when automation fails.

8. **Traceability.** Every artifact (research, plan, implementation, review) is persisted and linked. You must be able to trace any line of code back to a requirement.

9. **Agents are untrusted.** Apply least privilege. Sandbox execution. Audit everything.

10. **The human is the architect, not a rubber stamp.** Humans own architecture, strategy, and final approval. Agents own execution and grunt work.

---

## 8. Comparison Matrix

| Aspect | the-dmz ecosystem | GitHub Spec Kit | Cline | Cursor Rules | Multi-Agent Review |
|--------|-------------------|----------------|-------|-------------|-------------------|
| **Spec Phase** | ✅ (47K lines docs + auto-create-issues) | ✅ (5-phase SDD) | ⚠️ (memory bank) | ⚠️ (rules only) | ❌ (review only) |
| **Research Phase** | ✅ (dedicated agent) | ❌ (implicit) | ✅ (Plan mode) | ❌ | ❌ |
| **Task Decomposition** | ✅ (auto-create-issues.sh from DDs) | ✅ (explicit phase) | ⚠️ (Focus Chain) | ❌ | ❌ |
| **Fresh Context** | ✅ (separate agent calls) | ⚠️ (not enforced) | ✅ (Deep Planning) | N/A | ✅ |
| **Dual Review** | ✅ (A + B) | ❌ | ❌ | ❌ | ✅ |
| **Security Scanning** | ✅ (OWASP reviewer + secretlint + audit) | ❌ | ❌ | ⚠️ (rules) | ✅ (SAST + OWASP) |
| **Human Gate** | ❌ (fully auto) | ✅ (per phase) | ✅ (approve mode) | ✅ (per action) | ✅ |
| **Feedback Loop** | ✅ (retry on DENIED) | ⚠️ (manual) | ⚠️ (manual) | N/A | ✅ |
| **Loop Bounds** | ❌ (infinite possible) | N/A | N/A | N/A | Varies |
| **Traceability** | ✅ (artifact files + MEMORY.md) | ✅ (spec docs) | ✅ (memory bank) | ❌ | ⚠️ |
| **Constitution/Rules** | ✅ (SOUL.md + AGENTS.md + prohibited actions) | ✅ | ⚠️ (custom rules) | ✅ | ❌ |
| **Sub-agent Specialization** | ✅ (6 agents, role-specific tools) | ❌ | ❌ | ❌ | ⚠️ |
| **Living Memory** | ✅ (MEMORY.md with update instructions) | ❌ | ✅ (memory bank) | ❌ | ❌ |
| **Agent Constraints** | ✅ (4 prohibited action categories) | ⚠️ (constitution) | ⚠️ (per action) | ✅ (rules files) | ❌ |

---

## 9. Recommendations for FlowManager

Based on this research, the following elements should be incorporated into our own development workflow:

### Must Have (from Day 1)
1. **Spec before implementation** — Use the Specify → Plan → Tasks → Implement → Validate pipeline
2. **Constitution file** — Codify architectural principles from our existing specs (fractal patterns, engine core rules, etc.)
3. **Fresh agent sessions** — Never let investigation context leak into implementation
4. **Multi-gate review** — At minimum: lint + typecheck + AI correctness review + human review
5. **Task template with acceptance criteria** — Use the template from §4
6. **Retry budget with escalation** — Max 3 agent retries, then escalate to human

### Should Have (early maturity)
7. **Dedicated security review gate** — AI reviewer with OWASP-focused prompt
8. **SAST integration** — Automated vulnerability scanning before any review
9. **Memory bank for project context** — Persist architectural decisions, patterns, traps
10. **Dual AI review** (correctness + spec compliance) — Different prompts, different focus

### Nice to Have (at scale)
11. **Full automation à la auto-develop.sh** — Issue-to-merge without human intervention for low-risk changes
12. **Metrics collection** — Track review pass rates, common denial reasons, agent performance
13. **Dynamic task sizing** — Auto-decompose tasks that fail review > N times

---

## 10. Sources

| Source | Type | Key Insight |
|--------|------|-------------|
| [auto-develop.sh](https://github.com/TheMorpheus407/the-dmz/blob/master/auto-develop.sh) | Open Source | Working multi-agent pipeline with dual review gates |
| GitHub Spec Kit / Blog | Framework | 5-phase SDD: Specify → Plan → Tasks → Implement → Validate |
| Martin Fowler / martinfowler.com | Thought Leadership | Spec-first as single source of truth |
| Cline Documentation | Tool | Memory Bank + Plan/Act separation + Deep Planning |
| Cursor Rules Guide | Tool | Three-tier behavioral constraints for AI agents |
| OWASP Top 10 for Agentic Apps | Security Standard | Agent-specific security risks (2025/2026) |
| Semgrep Blog | Security Tooling | Multi-agent collaborative security review |
| Augment Code Blog | Industry | AI agent integration in enterprise CI/CD |
| Multiple Medium/Dev.to posts | Community | Plan-Act-Reflect framework, anti-vibe-coding patterns |
