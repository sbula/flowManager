# Part 2: Agent Isolation Architecture Using Google ADK

## Critical Clarifications

**Scope**: Flow Manager's internal expert orchestration for analysis/research/review/testing workflows  
**Technology**: Google Agent Development Kit (ADK) - Part of Vertex AI Agent Builder  
**Key Principle**: **Configurable, Domain-Specific Expert Sets with Stage-Specific Criteria**  
**NOT**: Quantivista product analysis

---

## 1. The Expert Isolation Problem

### 1.1 Current State

From `planning_expert_council.json` and `expert_sequencer.py`:

```
Research Phase (Multiple Experts)
→ Individual expert outputs collected
→ Synthesis Phase (Single Author)
→ Review Phase (Multiple Experts)
→ Approval Gate
```

**Problems**:

1. All experts share same conversation context ("groupthink")
2. **Expert sets are hardcoded** - same experts for every task
3. No domain-specific expert selection (UI task gets DB experts?)
4. Generic prompts without role personas
5. **Success criteria are generic** (not stage/domain-specific)

### 1.2 Required Capabilities

1. **Domain-Aware Expert Selection**: UI tasks ≠ DB tasks ≠ Trading Strategy tasks
2. **Configurable Expert Sets**: Per-task, per-domain expert composition
3. **Stage-Agnostic Personas**: Expert identity (WHO), not task (WHAT)
4. **Stage-Specific Success Criteria**: Concrete deliverables per stage+domain
5. **Branch-Based Isolation**: Experts execute independently (no context sharing)

---

## 2. Google ADK Isolation Primitives

### 2.1 Core ADK Agents

From [ADK documentation](https://google.github.io/adk-docs/agents/multi-agents/):

| Agent Type        | Purpose                                  | Isolation Mechanism                           |
| ----------------- | ---------------------------------------- | --------------------------------------------- |
| `ParallelAgent`   | Concurrent expert execution              | Each sub-agent gets unique `branch_id`        |
| `SequentialAgent` | Ordered execution (reviews)              | Shared state, sequential context              |
| `LlmAgent`        | Individual expert/synthesizer            | Role-specific prompts                         |
| `TriageAgent`     | Semantic routing & complexity estimation | Analyzes request intent to select Expert Set  |
| `SynthesisAgent`  | Conflict resolution & consolidation      | Merges isolated outputs into unified artifact |

### 2.2 Isolation Mechanism

**Branch Separation**:

```
research_parallel.research_quant_dev
research_parallel.research_sre
research_parallel.research_ui_ux
```

**State-Based Communication**:

```python
session.state = {
    "research.quant_dev.analysis": "...",
    "research.sre.analysis": "...",
    "research.ui_ux.analysis": "..."
}
```

**Guarantees**:

- Expert A cannot see Expert B's prompt
- No shared conversation history
- Parallel execution prevents sequential bias

### 2.3 Execution Topology: The "Iterative Round Table"

To balance isolation (avoiding groupthink) with cross-pollination (refining solutions), we employ a multi-phase topology:

1.  **Triage Phase**: `TriageAgent` analyzes request -> Selects `ExpertSet` + `ComplexityTier`.
2.  **Round 1 (Blind)**: Experts execute in `ParallelAgent` (STRICT Isolation). They cannot see each other.
3.  **Round 2 (Review)**: (Optional, High Complexity) Experts review anonymous summaries of peers' findings.
4.  **Synthesis Phase**: `SynthesisAgent` applies `synthesis_strategy` (e.g., Weighted Voting) to produce final JSO

---

## 3. Configurable Expert Registry

### 3.1 Expert Role Catalog (By Domain)

#### **Trading & Quant Domain**

- `quant_developer`: Statistical analysis, backtesting, risk metrics
- `quant_researcher`: Strategy validation, market microstructure
- `risk_manager`: Portfolio risk, VaR, stress testing
- `day_trader_expert`: Intraday patterns, execution speed, slippage
- `long_term_investor`: Fundamental analysis, macro trends
- `market_microstructure_expert`: Order flow, liquidity, market impact

#### **Infrastructure & SRE Domain**

- `sre_lead`: Reliability, observability, incident response
- `performance_engineer`: Latency optimization, throughput, profiling
- `security_architect`: Threat modeling, auth/authz, compliance
- `devops_engineer`: CI/CD, deployment, infrastructure-as-code
- `data_engineer`: Pipelines, ETL, data quality

#### **Database & Storage Domain**

- `db_architect`: Schema design, normalization, indexing
- `db_performance_expert`: Query optimization, sharding, replication
- `data_modeling_expert`: Entity relationships, migrations
- `timeseries_expert`: TSDB-specific optimization (InfluxDB, TimescaleDB)

#### **UI/UX Domain**

- `ui_ux_designer`: Ergonomics, workflows, accessibility
- `frontend_architect`: Component design, state management, performance
- `trader_user_rep`: Real trader workflows, pain points, requirements
- `accessibility_expert`: WCAG compliance, screen readers, keyboard nav

#### **API & Integration Domain**

- `api_architect`: REST/GraphQL/gRPC design, versioning
- `integration_engineer`: External system integration, adapters
- `backend_developer`: Business logic, service boundaries
- `backend_architect`: Service decomposition, domain-driven design, microservices
- `protocol_expert`: Protocol design, serialization, compatibility

#### **Implementation & Code Domain**

- `framework_selection_expert`: Framework/library evaluation, pros/cons analysis
- `algorithm_researcher`: Algorithm selection, complexity analysis, tradeoffs
- `codebase_migration_expert`: Legacy code analysis, migration strategies, technical debt
- `tdd_coach`: Test-driven development, test design, RED-GREEN-REFACTOR cycle
- `senior_implementation_lead`: Implementation strategy, design patterns, code quality
- `refactoring_expert`: Code smells, refactoring patterns, technical debt reduction

#### **Testing & QA Domain**

- `qa_lead`: Test strategy, coverage, automation
- `security_tester`: Penetration testing, vulnerability scanning
- `performance_tester`: Load testing, stress testing, benchmarking
- `integration_tester`: End-to-end workflows, contract testing

#### **Review & Governance Domain**

- `senior_architect`: Architecture review, technical debt, scalability
- `compliance_officer`: Regulatory requirements, audit trails
- `tech_lead`: Code quality, best practices, team standards
- `product_owner`: Business value, user stories, prioritization

---

## 3.2 CORRECTED: Expert Persona Structure (Stage-Agnostic)

**CRITICAL**: Personas define WHO the expert is, NOT what specific task they're doing.

### ❌ WRONG: Stage-Specific Persona with Generic Criteria

```yaml
# DO NOT DO THIS
role_id: quant_developer
persona: |
  You are reviewing a trading strategy plan...  # ← TOO SPECIFIC
success_criteria: |
  Validate statistical assumptions...  # ← TOO GENERIC
```

### ✅ CORRECT: Stage-Agnostic Persona

```yaml
# workflow_core/config/experts/quant_developer.yaml
role_id: quant_developer
display_name: "Quantitative Developer"
domains: [trading, research, backtesting, implementation, review]

# WHO they are (works for ALL stages)
persona: |
  You are a **Senior Quantitative Developer** with 8+ years in algorithmic trading.
  You've built and validated 50+ strategies across equities, futures, and crypto.

  Your expertise: Statistical analysis, backtesting, risk management, market microstructure.
  Your mindset: SKEPTICAL. If it looks too good to be true, it probably is.
  Your strength: Spotting statistical flaws and edge cases that blow up in production.

# Expertise areas (NOT tasks)
focus_areas:
  - Statistical rigor
  - Backtesting methodology
  - Risk management
  - Market regime changes
  - Overfitting detection

# NO success criteria here - those are stage-specific!
```

**Same expert, different stages:**

```yaml
# workflow_core/config/experts/tdd_coach.yaml
role_id: tdd_coach
display_name: "TDD Coach"
domains: [implementation, testing, tdd, review]

persona: |
  You are a **TDD Coach** with 10+ years teaching RED-GREEN-REFACTOR discipline.
  You've seen the pain of tests-after-code (always incomplete) and the elegance 
  of test-first design.

  Your philosophy: "The test is the first client of your API. If it's hard to 
  test, it's poorly designed."

  Your style: STRICT. No implementation code before a failing test exists.

focus_areas:
  - Test-first design
  - RED-GREEN-REFACTOR discipline
  - Test readability (arrange-act-assert)
  - Edge case identification
  - Refactoring safety
```

---

## 3.3 CORRECTED: Stage+Domain-Specific Success Criteria (In Expert Sets)

**Success criteria belong in EXPERT SET configurations**, not expert personas.

### Example: Trading Strategy Research (Stage: Research)

```yaml
# workflow_core/config/expert_sets/trading_strategy_research.yaml
set_id: trading_strategy_research
description: "Trading strategy development and validation"
stage: research
isolation_level: STRICT

# NEW: Complexity Tiers (Resource & Cost Control)
tiers:
  low: # Simple parameter tweak
    experts: [quant_developer]
    synthesis_strategy: simple_merge
    high: # New Strategy
      experts: [quant_developer, risk_manager, market_microstructure_expert]
      synthesis_strategy: debate_and_resolve

# Structured Output Requirement (Machine Verifiable)
common_output_schema:
  type: object
  properties:
    risks: { type: array, items: { type: string } }
    approval_status: { enum: [APPROVE, REJECT, NEEDS_DATA] }
    required_backtests: { type: array, items: { type: string } }

# STAGE+DOMAIN-SPECIFIC success criteria follows...

experts:
  - quant_developer
  - risk_manager
  - day_trader_expert

# STAGE+DOMAIN-SPECIFIC success criteria
expert_success_criteria:
  quant_developer: |
    You MUST deliver for THIS RESEARCH task:
    - 5+ statistical concerns with severity (CRITICAL/HIGH/MEDIUM)
    - 3+ edge cases with SPECIFIC market scenarios (flash crash, low liquidity, etc.)
    - 2+ overfitting detection methods to apply
    - Exact backtesting requirements:
      * Timeframe (min 3 years including crisis periods)
      * Instruments (specific contracts/tickers)
      * Metrics to track (Sharpe, max DD, win rate, etc.)

    You FAILED if you don't find at least 5 critical statistical flaws.

  risk_manager: |
    You MUST deliver for THIS RESEARCH task:
    - 3+ risk scenarios that could blow up the strategy
    - Specific position sizing formula with JUSTIFICATION
    - Stop-loss/take-profit thresholds with RATIONALE
    - Maximum drawdown tolerance with recovery analysis
    - Risk metrics to monitor live (VaR, Expected Shortfall, etc.)

    You FAILED if you approve a strategy without quantified risk limits.

  day_trader_expert: |
    You MUST deliver for THIS RESEARCH task:
    - 3+ intraday regime changes that could affect strategy
    - Execution speed requirements (max latency tolerance)
    - Slippage estimates for different market conditions
    - Market microstructure concerns (bid-ask spread impact, etc.)

    You FAILED if you don't identify intraday execution risks.

applicable_to:
  task_patterns: ["*Strategy*", "*Trading*", "*Backtest*"]
  task_types: [strategy_planning, algorithm_design]
```

### Example: Same Expert, Different Stage (Implementation Review)

```yaml
# workflow_core/config/expert_sets/strategy_implementation_review.yaml
set_id: strategy_implementation_review
description: "Review strategy implementation code"
stage: review
isolation_level: SHARED # Can see code being reviewed

experts:
  - quant_developer
  - senior_implementation_lead

# DIFFERENT success criteria for REVIEW stage
expert_success_criteria:
  quant_developer: |
    You MUST find in THIS CODE REVIEW:
    - 5+ implementation bugs or numerical accuracy issues
    - 3+ missing edge case handlers (data gaps, NaN values, etc.)
    - 2+ performance bottlenecks (unnecessary loops, memory leaks)
    - Missing test cases for critical market scenarios
    - Incorrect statistical calculations or off-by-one errors

    You FAILED if code passes review without finding these minimums.

  senior_implementation_lead: |
    You MUST find in THIS CODE REVIEW:
    - 3+ design pattern violations or code smells
    - 2+ maintainability issues (hardcoded values, poor naming)
    - Missing error handling paths
    - Insufficient logging/observability hooks

    You FAILED if you approve code that will be hard to debug in production.

applicable_to:
  task_patterns: ["*Implementation*", "*Code Review*"]
  task_types: [implementation_review, code_review]
```

### Example: TDD Implementation (Different Stage Again)

```yaml
# workflow_core/config/expert_sets/tdd_implementation.yaml
set_id: tdd_implementation
description: "TDD workflow guidance"
stage: implementation
isolation_level: SHARED

experts:
  - tdd_coach
  - qa_lead

expert_success_criteria:
  tdd_coach: |
    You MUST guide through TDD cycle:

    RED Phase:
    - Write 1+ failing test FIRST that describes expected behavior
    - Test must be specific (not generic "test_it_works")
    - Test must fail for the RIGHT reason (not syntax error)

    GREEN Phase:
    - Write MINIMAL code to make test pass (no gold-plating)
    - Verify test now passes

    REFACTOR Phase:
    - Identify code smells introduced in GREEN phase
    - Suggest refactorings WITH test safety net

    You FAILED if you allow implementation before failing test exists.

  qa_lead: |
    You MUST ensure for THIS IMPLEMENTATION:
    - Test coverage of edge cases (boundary values, nulls, etc.)
    - Test readability (clear arrange-act-assert structure)
    - Test independence (no test interdependencies)
    - Integration test identification (what needs E2E testing)

    You FAILED if tests are brittle or unclear.

applicable_to:
  task_patterns: ["*Implementation*", "*Feature*", "*TDD*"]
  task_types: [feature_implementation, bug_fix, refactoring]
```

---

## 3.4 Domain-Specific Expert Set Examples

```yaml
# workflow_core/config/expert_sets/ui_workflow_planning.yaml
set_id: ui_workflow_planning
stage: research
isolation_level: STRICT

experts:
  - ui_ux_designer
  - trader_user_rep
  - accessibility_expert

expert_success_criteria:
  ui_ux_designer: |
    For THIS UI PLANNING task, deliver:
    - 3+ usability concerns with trader workflows
    - 2+ ergonomic improvements for high-frequency operations
    - Accessibility requirements (keyboard shortcuts, screen reader support)
    - Wireframe or user flow diagram

    You FAILED if you don't identify workflow inefficiencies.

  trader_user_rep: |
    As a REAL TRADER, identify:
    - 5+ pain points in current UI tools
    - 3+ critical workflows that MUST be fast (< 2 seconds)
    - 2+ errors that could cost money if UI is confusing
    - Features competitors have that we need

    You FAILED if analysis is generic (not from trader's perspective).

  accessibility_expert: |
    For THIS UI, ensure:
    - WCAG 2.1 AA compliance requirements
    - Keyboard navigation for all critical actions
    - Screen reader compatibility for alerts/notifications
    - Color contrast for traders with color blindness

    You FAILED if accessibility is an afterthought.

applicable_to:
  task_patterns: ["*UI*", "*Dashboard*", "*Workflow*"]
  task_types: [feature_planning, user_story_analysis]
```

```yaml
# workflow_core/config/expert_sets/framework_selection.yaml
set_id: framework_selection
stage: research
isolation_level: STRICT

experts:
  - framework_selection_expert
  - backend_architect
  - performance_engineer
  - sre_lead

expert_success_criteria:
  framework_selection_expert: |
    For EACH framework option, provide:
    - 3+ SPECIFIC pros (not "it's popular")
    - 3+ SPECIFIC cons or gotchas (license issues, breaking changes, etc.)
    - Performance benchmarks IF performance-critical
    - Migration effort FROM current stack (hours/days estimate)
    - Learning curve for team
    - Long-term maintenance risk (abandoned projects, bus factor)

    Final recommendation with CLEAR reasoning.

    You FAILED if you don't identify deal-breaking cons.

  backend_architect: |
    Evaluate framework fit with:
    - Current architecture patterns (compatibility)
    - Service boundaries (does it force coupling?)
    - Scalability implications
    - Testability (mocking, integration testing)

    You FAILED if you ignore architectural constraints.

  performance_engineer: |
    Benchmark framework for:
    - Throughput (requests/sec)
    - Latency (p50, p95, p99)
    - Memory footprint
    - GC pressure (for JVM/Go)

    Provide NUMBERS, not opinions.

    You FAILED if you approve without performance data.

  sre_lead: |
    Assess operational impact:
    - Deployment complexity
    - Monitoring/observability hooks
    - Error debugging difficulty
    - Configuration management

    You FAILED if operational concerns are ignored.

applicable_to:
  task_patterns: ["*Framework*", "*Library*", "*Tool Selection*"]
  task_types: [architecture_planning, technical_research]
```

## 3.5 Operational Hardening: Tooling & FileSystem Scoping

To bridge the gap between "Thinking" and "Doing", experts are granted **Tool Bindings**. To ensure safety, these
tools are strictly **Scoped**.
expert_config:
ui_ux_designer:
tools: - name: read_file
config:
Allow reading docs and source, but NOT config/secrets
allowed_paths: - "./src/frontend" - "./docs" - "./status.md"

         - name: write_file
          config:

STRICTLY limited to frontend source. CANNOT wipe DB.
allowed_paths: - "./src/frontend"
blocked_patterns: - "\*.env" # Never write env files - "package.json" # Don't touch dependencies

**Security Mechanism**:
The Tool Wrapper resolves absolute paths and validates against `allowed_paths` BEFORE execution. Attempts to access outside scope raise `SecurityError`.

---

## 4. Configuration Structure Summary

### Expert Persona (Stage-Agnostic)

**Location**: `workflow_core/config/experts/{role_id}.yaml`

```yaml
role_id: { expert_role }
display_name: "Human Readable Name"
domains: [domain1, domain2, ...]

persona: |
  WHO you are:
  - Background & experience
  - Expertise areas
  - Mindset & personality
  - Strengths & superpowers

  NOT what specific task you're doing.

focus_areas:
  - Expertise area 1
  - Expertise area 2
  - ...

# NO success_criteria here!
# NO output_format here (unless truly generic)!
```

### Expert Set (Stage+Domain-Specific)

**Location**: `workflow_core/config/expert_sets/{set_id}.yaml`

```yaml
set_id: { expert_set_name }
description: "What this expert set does"
routing_intent: "Semantic description for Triage Agent"
stage: research | implementation | review | testing
isolation_level: STRICT | SHARED

# Complexity Tiers
tiers:
  low: { experts: [...], synthesis: ... }
  high: { experts: [...], synthesis: ... }

# Synthesis Configuration
synthesis_config:
  strategy: weighted_voting | veto_power | llm_arbitrator
  arbiter_role: senior_architect # Optional

# Structured Output (JSON Schema)
output_schema:
  type: object
  properties: ...

# Tool Bindings (Optional override per set)
tool_bindings:
  expert_role_1: [read_codebase, run_test]

experts:
  - expert_role_1
  - expert_role_2
  - ...

# STAGE+DOMAIN-SPECIFIC success criteria
expert_success_criteria:
  expert_role_1: |
    You MUST deliver for THIS {stage} task:
    - Concrete deliverable 1 with metric (5+ items)
    - Concrete deliverable 2 with specificity
    - ...

    You FAILED if you don't meet these minimums.

  expert_role_2: |
    You MUST deliver for THIS {stage} task:
    - ...

# Output format can be stage-specific too
expert_output_formats:
  expert_role_1: |
    ## Section 1
    [Specific to this stage/domain]

    ## Section 2
    ...

applicable_to:
  task_patterns: [...]
  task_types: [...]
```

---

## 5. Prompt Template Rendering

### Template Structure

```jinja2
{# prompts/experts/quant_developer.j2 #}

{{ expert_persona }}

## Your Task: {{ stage | upper }}
{{ task_description }}

## Success Criteria for This {{ stage | capitalize }}
{{ success_criteria }}

## Your Expertise Focus
{% for area in focus_areas %}
- {{ area }}
{% endfor %}

## Expected Output
{{ output_format }}

## Isolation Notice
- Branch: {{ branch_id }}
- You do NOT see other experts' outputs
- Provide independent analysis

---
Begin your {{ stage }} work:
```

### Rendering Flow

1. **Load Expert Persona**: Read `experts/{role}.yaml` → get `persona`, `focus_areas`
2. **Load Expert Set**: Read `expert_sets/{set_id}.yaml` → get `success_criteria[role]`, `output_format[role]`
3. **Render Template**: Inject persona + stage-specific criteria
4. **Execute ADK Agent**: Create `LlmAgent` with rendered prompt

---

## 6. Expert Set Examples by Stage

### Research Stage

| Set ID                      | Experts                                                                       | Domain         |
| --------------------------- | ----------------------------------------------------------------------------- | -------------- |
| `trading_strategy_research` | quant_developer, risk_manager, day_trader_expert                              | Trading        |
| `ui_workflow_planning`      | ui_ux_designer, trader_user_rep, accessibility_expert                         | UI/UX          |
| `db_schema_design`          | db_architect, db_performance_expert, timeseries_expert                        | Database       |
| `framework_selection`       | framework_selection_expert, backend_architect, performance_engineer, sre_lead | Implementation |
| `algorithm_design`          | algorithm_researcher, performance_engineer, quant_developer                   | Implementation |

### Implementation Stage

| Set ID               | Experts                                                          | Use Case     |
| -------------------- | ---------------------------------------------------------------- | ------------ |
| `tdd_implementation` | tdd_coach, senior_implementation_lead, qa_lead                   | TDD workflow |
| `codebase_migration` | codebase_migration_expert, backend_architect, refactoring_expert | Migration    |

### Review Stage

| Set ID                           | Experts                                        | Use Case      |
| -------------------------------- | ---------------------------------------------- | ------------- |
| `architecture_review`            | senior_architect, sre_lead, security_architect | Architecture  |
| `strategy_implementation_review` | quant_developer, senior_implementation_lead    | Strategy code |
| `code_quality_review`            | tech_lead, senior_developer, security_tester   | Code quality  |

### Testing Stage

| Set ID                | Experts                                         | Use Case    |
| --------------------- | ----------------------------------------------- | ----------- |
| `integration_testing` | qa_lead, integration_tester, performance_tester | E2E testing |
| `security_testing`    | security_tester, penetration_tester             | Security    |

---

## 7. Migration Roadmap

### Phase 1: Expert Personas & Tooling (Sprint 1)

- [ ] Create 20 stage-agnostic expert personas
- [ ] Implement `FileSystemScopedTool` wrapper with whitelist logic
- [ ] Define `output_schema` definitions for Research/Review stages

### Phase 2: Expert Sets & Routing (Sprint 2)

- [ ] Implement `TriageAgent` for intent-based routing
- [ ] Define 10 expert sets with `routing_intent` and `tiers`
- [ ] Create success criteria templates with JSON validation

### Phase 3: Integration & Synthesis (Sprint 3)

- [ ] Implement `SynthesisAgent` with conflict resolution strategies
- [ ] Build expert set matcher
- [ ] Implement prompt template rendering

### Phase 4: Validation (Sprint 4)

- [ ] Validate expert isolation via logs
- [ ] Measure output quality improvements
- [ ] Tune success criteria based on results

### Phase 5: Hardening (Sprint 5)

- [ ] Integrate Adversarial Review Phase (§8)
- [ ] Implement Rubric Scoring Engine (§9)
- [ ] Add per-role model parameter overrides (§10)
- [ ] Add citation/evidence requirements to output schemas (§11)
- [ ] Integration with Validation Gate ([01_11](../specs/01_11_validation_gate_spec.md))

---

## 8. Adversarial Review Phase

### 8.1 Problem: Mode Collapse in Expert Reviews
LLMs have a well-documented tendency toward sycophancy — agreeing with the presented work rather than critically evaluating it. In multi-agent review workflows, this manifests as:
*   All experts "approving" with minor suggestions
*   Convergence on generic positive feedback
*   Failure to identify structural or logical issues

### 8.2 The Adversarial Phase Pattern
After the standard synthesis phase (§2.3 Phase 3), add a dedicated adversarial step:

```yaml
# workflow_core/config/expert_sets/adversarial_review.yaml
set_id: adversarial_review
description: "Mandatory adversarial critique of synthesized output"
stage: adversarial
isolation_level: SHARED  # Can see the synthesis output

constraints:
  no_approvals: true        # "APPROVE" is NOT a valid output status
  min_issues_required: 3    # MUST find at least 3 issues
  require_evidence: true    # Every claim must cite a specific line/section

experts:
  - devil_advocate

expert_success_criteria:
  devil_advocate: |
    You are a CRITIC. You are STRUCTURALLY FORBIDDEN from approving.
    Your job is to ATTACK the synthesis output.

    You MUST deliver:
    - 3+ structural issues with SPECIFIC references
    - 2+ logical flaws or unstated assumptions
    - 1+ risk scenario the authors did not consider
    - A severity rating for EACH issue (CRITICAL/HIGH/MEDIUM/LOW)

    Output format: JSON with issues_found array. No prose.

    You FAILED if you deliver fewer than 3 issues.
    You FAILED if any issue lacks a specific file/line reference.
```

### 8.3 Anti-Sycophancy Techniques
The adversarial phase combines multiple techniques to ensure genuine criticism:

1. **Clean Slate Protocol**: The critic agent is spawned in a fresh context (new `branch_id`) with NO history of the previous collaborative discussion. It receives only the final artifact.
2. **Structural Prohibition**: The output schema literally does not include an "APPROVE" option. The agent's only valid outputs are structured issue lists.
3. **Minimum Issue Threshold**: The agent must find a configurable minimum number of issues. If it cannot, the system flags the review as "Insufficient Criticism" and loops.
4. **Chain-of-Thought Scratchpad**: Before producing the final structured output, the critic must produce a scratchpad section showing its reasoning. This forces deliberate analysis rather than reflexive approval.

### 8.4 When to Apply
| Task Complexity | Adversarial Phase |
|:---|:---|
| Low (simple fix) | Skipped |
| Medium (feature) | Optional (based on confidence score) |
| High (architecture) | Mandatory |
| Critical (security) | Mandatory + elevated `min_issues_required` |

---

## 9. Rubric-Based Scoring

### 9.1 Problem: Qualitative vs Quantitative Output
Current `expert_success_criteria` (§3.3) are qualitative ("You FAILED if…"). While effective for guiding behavior, they are:
*   Not machine-verifiable (requires human to judge compliance)
*   Binary (pass/fail, no gradient)
*   Cannot drive automated looping decisions

### 9.2 Structured Rubric Schema
Each expert set should define a rubric with numeric scoring:

```yaml
# Added to expert_set configuration
rubric:
  dimensions:
    - name: "completeness"
      description: "Are all requested deliverables present?"
      weight: 0.3
      min_threshold: 3  # On a 1-5 scale

    - name: "specificity"
      description: "Are findings specific with file/line references?"
      weight: 0.3
      min_threshold: 4

    - name: "actionability"
      description: "Can the team act on findings without clarification?"
      weight: 0.2
      min_threshold: 3

    - name: "risk_identification"
      description: "Are non-obvious risks identified?"
      weight: 0.2
      min_threshold: 3

  overall_min_threshold: 3.5  # Weighted average must exceed this
  auto_loop_on_fail: true     # If below threshold, loop back
  max_loops: 2                # After 2 loops, escalate to human
```

### 9.3 Expert Output with Scores
Experts include self-assessment scores in their structured output:
```json
{
  "findings": [ ... ],
  "self_scores": {
    "completeness": 4,
    "specificity": 5,
    "actionability": 3,
    "risk_identification": 4
  },
  "weighted_average": 4.1,
  "confidence": 0.85
}
```

### 9.4 Automated Score Validation
The Synthesis Agent can validate self-scores against the rubric:
*   If any dimension is below its `min_threshold` → reject and loop
*   If `weighted_average` < `overall_min_threshold` → reject and loop
*   After `max_loops` exhausted → escalate to Human-in-the-Loop (HITL)

---

## 10. LLM Model Parameter Overrides

### 10.1 Motivation
Different expert roles benefit from different model parameters:
*   **Analytical roles** (Architect, SRE, QA) should use low temperature for logical rigor
*   **Creative roles** (UI Designer, Product Owner) can use moderate temperature
*   **Adversarial roles** (Critic, Devil's Advocate) should use low temperature to prevent "creative" dismissals

### 10.2 Schema Extension
Add to the expert persona definition:

```yaml
# workflow_core/config/experts/quant_developer.yaml
role_id: quant_developer
display_name: "Quantitative Developer"
domains: [trading, research, backtesting, implementation, review]

persona: |
  You are a **Senior Quantitative Developer** ...

focus_areas:
  - Statistical rigor
  - Backtesting methodology

# NEW: Model parameter overrides
model_params:
  temperature: 0.1  # Very low for analytical work
  top_p: 0.9
  top_k: 40
```

### 10.3 Parameter Guidelines

| Role Category | Temperature | Rationale |
|:---|:---|:---|
| Analytical (QA, SRE, Quant) | 0.0 – 0.2 | Minimize creativity, maximize precision |
| Structural (Architect, Backend) | 0.2 – 0.4 | Balance between thoroughness and exploration |
| Creative (UI/UX, Product) | 0.4 – 0.7 | Allow exploratory suggestions |
| Adversarial (Critic, Devil's Advocate) | 0.0 – 0.2 | Rigorous, evidence-based criticism |

### 10.4 Override Precedence
```
Default (flow_config.json) → Persona (experts/role.yaml) → Expert Set (expert_sets/set.yaml)
```
Expert Set overrides take highest precedence (a specific review task may need different params than the persona's default).

---

## 11. Evidence-Grounded Output (Citation Requirements)

### 11.1 Problem: Ungrounded Claims
Agents often make claims like "This function is inefficient" without citing specific code. This makes verification impossible and enables hallucination.

### 11.2 Citation Schema
Expert output must include evidence for every finding:

```json
{
  "findings": [
    {
      "claim": "The retry logic has an off-by-one error",
      "evidence": {
        "type": "code_reference",
        "file": "src/flow/engine/core.py",
        "line_start": 142,
        "line_end": 145,
        "snippet": "for i in range(0, retry_count):"
      },
      "severity": "HIGH",
      "suggested_fix": "Change to range(0, retry_count + 1)"
    }
  ]
}
```

### 11.3 Validation Rules
*   Every finding with severity >= `MEDIUM` MUST include at least one evidence reference.
*   Evidence `file` must exist in the project (validated via `SafePath`).
*   Evidence `line_start`/`line_end` must be within the file's actual line count.
*   Evidence `snippet` must match the actual content at those lines (validated by the engine).

### 11.4 Ungrounded Claim Penalty
If an expert produces findings without evidence:
*   The finding is downgraded in the rubric scoring (§9) dimension for "specificity"
*   The synthesis agent flags it as "UNGROUNDED" and may discard it

---

## 12. Generalized Scratchpad Enforcement

### 12.1 Problem: Shallow or Reflexive Expert Output
The Chain-of-Thought Scratchpad is currently specified only for the adversarial critic (§8.3). However, the same problem — reflexive, shallow output without genuine deliberation — applies to *all* analytical expert roles (Architect, SRE, QA, Quant).

### 12.2 Configurable `require_scratchpad` Flag
Add to `expert_set` configuration:

```yaml
# workflow_core/config/expert_sets/trading_strategy_research.yaml
constraints:
  require_scratchpad: true   # NEW: mandatory for analytical roles
```

When enabled, the expert's prompt template must include:
```jinja2
## Scratchpad (MANDATORY — show your work before final output)
Before producing your final structured output, you MUST reason through:
1. 5 potential failure modes of the system under review
2. 3 missing requirements or unstated assumptions
3. Counter-arguments to your own initial observations

Only AFTER completing this section may you produce your final findings.
```

### 12.3 Guidelines
| Role Category | `require_scratchpad` |
|:---|:---|
| Analytical (QA, SRE, Quant, Architect) | `true` (mandatory) |
| Creative (UI/UX, Product) | `false` (optional) |
| Adversarial (Critic) | `true` (already required §8.3) |
| Implementation (TDD Coach) | `false` |

---

## 13. Mock-First Protocol (Interface Before Implementation)

### 13.1 Problem: Agent Writes Code Before Contract Exists
When an agent jumps straight to implementation, the Validation Gate has nothing to validate against. The symbol index doesn't know what the *expected* interface should be — it only knows what *currently* exists.

### 13.2 The Protocol
Before an agent writes any implementation code, it must first:
1. Define the interface/contract (e.g., class signatures, function stubs, proto definitions).
2. Commit this to the symbol index (via `flow index --update`).
3. Only then proceed to implementation.

### 13.3 Enforcement via Validation Gate
The gate can be extended to enforce this:
*   If an implementation flow is active and the target symbols don't yet exist in the index → reject the implementation and prompt the agent to define the interface first.
*   The spec's `must_call` constraints (from the structured task spec) must map to *existing* symbols before implementation begins.

### 13.4 Benefits
*   The Validation Gate has a target to validate against *during* implementation (not just after).
*   Multiple agents can work in parallel — one defines the interface, others can immediately start implementing against it.
*   Contract-first development naturally prevents tight coupling.

---

**Status**: ✅ **CORRECTED** - Stage-agnostic personas + stage-specific criteria
**Key Fix**: Success criteria moved from expert personas to expert set configs
**Additions (2026-03-01)**: Adversarial Review Phase, Rubric Scoring, Model Parameter Overrides, Evidence-Grounded Output, Generalized Scratchpad Enforcement, Mock-First Protocol
**Next**: Implement template rendering system + Validation Gate integration

