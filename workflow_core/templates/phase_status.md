# Phase [N]: [Phase Name]

## 1. Setup & Context
- [ ] 1.1. `Init.Env`: Environment Check (Tools, Secrets, VPN).
- [ ] 1.2. `Plan.Goal`: Context (Draft `context_brief.md`).
- [ ] 1.3. `Plan.Arch`: Skeleton (Append Service Headers).
- [ ] 1.3. `Plan.Arch`: Data Flow (Draft `data_flow_map.md`).
- [ ] 1.4. `Plan.Strategy`: Serialized Planning (Refine Service Implementation Plans).

## 2. Infrastructure: [Topic]
- [ ] 2.1. `Git.Branch`: Initialize `feature/infra-[topic]`.
- [ ] 2.2. `Plan.Detail`: Context & Implementation Design.
- [ ] 2.3. `Impl.Feature`: Define Infrastructure (Docker/Compose/Helm).
- [ ] 2.4. `Valid.Unit`: Static Validation (Syntax Check).
- [ ] 2.5. `Valid.Integration`: Health Check (Spin Up, Verify Ports).
- [ ] 2.6. `Review.Architecture`: Gap Analysis.
- [ ] 2.7. `Git.Merge`: Merge to Master.

## 3. Implementation: [Epic / Functional Area]
- [ ] 3.1. **[Service Name]: Skeleton**
    - [ ] 3.1.1. `Git.Branch`: Initialize `feature/[service]-skeleton`.
    - [ ] 3.1.2. `Plan.Detail`: Context & Implementation Design.
    - [ ] 3.1.3. `Init.Service`: Initialize Project (Use Golden Template: [Link]).
    - [ ] 3.1.4. `Valid.Quality`: Pre-Merge Gate.
    - [ ] 3.1.5. `Review.Code`: Human Gate.
    - [ ] 3.1.6. `Git.Merge`: Merge to Master.

- [ ] 3.2. **[Service Name]: [Feature A]**
    - [ ] 3.2.1. `Git.Branch`: Initialize `feature/[service]-[feature]`.
    - [ ] 3.2.2. `Plan.Detail`: Context & Implementation Design.
    - [ ] 3.2.3. `Impl.Feature`: Implement Logic.
    - [ ] 3.2.4. `Valid.Unit`: Verify Logic.
    - [ ] 3.2.5. `Valid.Quality`: Pre-Merge Gate.
    - [ ] 3.2.6. `Review.Code`: Human Gate.
    - [ ] 3.2.7. `Git.Merge`: Merge to Master.

## 4. Verification & Finalization
- [ ] 4.1. **End-to-End Verification**
    - [ ] 4.1.1. `Git.Branch`: Initialize `feature/phase-[n]-verification`.
    - [ ] 4.1.2. `Plan.Detail`: Context & Implementation Design.
    - [ ] 4.1.3. `Valid.E2E`: Execute Golden Path (Happy Flow).
    - [ ] 4.1.4. `Valid.E2E`: Execute Edge Cases (Chaos/Security).
    - [ ] 4.1.5. `Valid.Performance`: Latency/Throughput Benchmark.
    - [ ] 4.1.6. `Git.Merge`: Merge to Master.

- [ ] 4.2. **Phase Sign-Off**
    - [ ] 4.2.1. `Review.Architecture`: Final Post-Mortem.
    - [ ] 4.2.2. `Impl.Refactor`: Finalize Documentation (`README.md`, `Architecture.md`).
    - [ ] 4.2.3. `Plan.SignOff`: Phase Completion.

## 5. Bugs/Impediments/Improvements/Issues
- [ ] 5.1. `Impl.Fix`: [Description]

## 6. Continuous Improvements & Recurring Tasks
- [ ] 6.1. `Refactor.Technical`: [Description]
