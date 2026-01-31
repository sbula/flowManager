# Service Checklist: Python Sidecar/Adapter

## 1. Project Initialization
- [ ] Initialize Poetry Project:
    ```bash
    poetry new service-name
    ```
- [ ] Configure `pyproject.toml`:
    - [ ] Dependencies: `pydantic`, `kafka-python`, `prometheus-client`.
    - [ ] Dev Dependencies: `pytest`, `black`, `isort`, `mypy`.
    - [ ] Tool Config: Enforce strict typing.

## 2. Infrastructure (Containerization)
- [ ] Create `Dockerfile`:
    - [ ] Base Image: Match `infrastructure/project-config/tech_stacks.json` (Builder).
    - [ ] Run Stage: `gcr.io/distroless/python3`.
    - [ ] Multi-Stage: Copy virtualenv.
    - [ ] Security: Non-root execution.
- [ ] Update `podman-compose.yaml`:
    - [ ] Define Service.
    - [ ] Environment Variables (Kafka Bootstrap, Topics).

## 3. Code Quality (Bindings)
- [ ] Verify `status.md` bindings:
    - [ ] `lint_check_cmd`: `flake8 . && black --check . && mypy .`
    - [ ] `unit_test_cmd`: `pytest tests/unit`
    - [ ] `integration_test_cmd`: `pytest tests/integration`
- [ ] Run `bash workflow_core/validate.sh . --check quality` to verify.
