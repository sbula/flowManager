# Service Checklist: Rust/Actix (High Performance)

## 1. Project Initialization
- [ ] Initialize Cargo Project:
    ```bash
    cargo new service-name
    ```
- [ ] Configure `Cargo.toml`:
    - [ ] Dependencies: `actix-web`, `tokio`, `rdkafka`, `serde`.
    - [ ] Dev Dependencies: `wiremock` (for testing).

## 2. Infrastructure (Containerization)
- [ ] Create `Dockerfile`:
    - [ ] Builder Stage: Match `infrastructure/project-config/tech_stacks.json` (Build static assets).
    - [ ] Run Stage: `gcr.io/distroless/cc-debian12`.
    - [ ] Optimization: Release Profile (LTO, strip).
- [ ] Update `podman-compose.yaml`.

## 3. Quality Gates (Bindings)
- [ ] Verify `status.md` bindings:
    - [ ] `lint_check_cmd`: `cargo clippy -- -D warnings`
    - [ ] `unit_test_cmd`: `cargo test --lib`
    - [ ] `integration_test_cmd`: `cargo test --test integration`
- [ ] Run `bash workflow_core/validate.sh . --check quality` to verify.
