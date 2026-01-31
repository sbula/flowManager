# Review Report: {REVIEW_TYPE}
**Task:** `{TASK_ID}`
**Service:** `{SERVICE_PATH}`
**Date:** `{DATE}`
**Experts:** `{EXPERTS}`

## 1. Compliance Checklist
> [!IMPORTANT]
> All items must be verified before approval.

- [ ] **Protocol**: `status.md` was updated *before* code changes.
- [ ] **Context**: `context_brief.md` (or `implementation_plan.md`) is up-to-date.
- [ ] **Standards**: Toolchain versions match `infrastructure/project-config/tech_stacks.json`.
- [ ] **Secrets**: No secrets committed (checked `.env` exclusion).
- [ ] **Cleanliness**: No debug prints, TODOs, or commented-out blocks.

## 2. Automated Metrics
### Linting Issues
<!-- {LINT_METRICS} -->
*(Run `validate.sh {service} --check lint` to populate)*

### Complexity / Test Coverage
<!-- {COMPLEXITY_METRICS} -->
*(Run `validate.sh {service} --check complexity` or `unit` to populate)*

## 3. Human Analysis
### Key Findings
*   [Find 1]
*   [Find 2]

### Security & Performance
*   **Security Review**: [Pass/Fail/Notes]
*   **Performance Impact**: [Pass/Fail/Notes]

## 4. Review Matrix
> **Requirement**: Each review must explicitly state the **Aspect** reviewed, a **Status**, a **Comment**, and a **Proposal** (if findings exist, or "N/A" if solid).

| **Role** | **Aspect** | **Status** | **Comment** | **Proposal** |
| :--- | :--- | :--- | :--- | :--- |
| **SRE** | Infra/Scale | [ ] Pending | | |
| **Architect** | Design/Patterns | [ ] Pending | | |
| **Product Owner** | Value/Scope | [ ] Pending | | |
| **QA Engineer** | Quality/Test | [ ] Pending | | |
| **Security** | SecOps/Audit | [ ] Pending | | |

## 5. Decision Record
| Decision | Sign-Off | Date |
| :--- | :--- | :--- |
| **{DECISION}** | {USER} | {DATE} |
