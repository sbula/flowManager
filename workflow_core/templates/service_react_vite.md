# Service Checklist: React/Vite (Web UI)

## 1. Project Initialization
- [ ] Initialize Vite Project:
    ```bash
    npm create vite@latest ui-dashboard -- --template react-ts
    ```
- [ ] Configure `package.json`:
    - [ ] Dependencies: `react`, `react-dom`, `recharts` (for charts).
    - [ ] Dev Dependencies: `typescript`, `eslint`, `prettier`, `vitest`.

## 1.5. Standard Interface
- [ ] Create `test.sh` (Wrapper):
    ```bash
    #!/bin/bash
    TYPE=$1
    case $TYPE in
      lint) npm run lint ;;
      unit) npm run test ;;
      e2e) npm run e2e ;;
      *) echo "Usage: $0 {lint|unit|e2e}"; exit 1 ;;
    esac
    ```
    - [ ] `chmod +x test.sh`

## 2. Infrastructure (Containerization)
- [ ] Create `Dockerfile`:
    - [ ] Builder Stage: Match `infrastructure/project-config/tech_stacks.json` (Build static assets).
    - [ ] Run Stage: `nginx:alpine` (Serve static files).
    - [ ] Nginx Config: SPA fallback (`try_files $uri /index.html`).
- [ ] Update `podman-compose.yaml`:
    - [ ] Define Service (Port 80/8080).

## 3. Quality Gates (Bindings)
- [ ] Verify `status.md` bindings:
    - [ ] `lint_check_cmd`: `npm run lint`
    - [ ] `unit_test_cmd`: `npm run test`
    - [ ] `integration_test_cmd`: `npm run e2e` (Cypress/Playwright).
- [ ] Run `bash workflow_core/validate.sh . --check quality` to verify.
