# Service Checklist: Kotlin/Quarkus

## 1. Project Initialization
- [ ] Initialize Quarkus Project:
    ```bash
    quarkus create app com.quantivista:service-name \
        --extension="kotlin,resteasy-reactive-jackson,smallrye-reactive-messaging-kafka,hibernate-reactive-panache" \
        --maven
    ```
- [ ] Configure `pom.xml`:
    - [ ] Add `maven-surefire-plugin` (Tests).
    - [ ] Add `maven-failsafe-plugin` (Integration).
    - [ ] Add `jacoco-maven-plugin` (Coverage).

## 2. Infrastructure (Containerization)
- [ ] Create `Dockerfile` (Non-Root User):
    - [ ] Base Image: Match `infrastructure/project-config/tech_stacks.json` (or similar).
    - [ ] Build Stage: Gradle Build (Cache dependencies).
    - [ ] Run Stage: Distroless/Minimal + Java App.
    - [ ] Security: `USER 1001`.
- [ ] Update `podman-compose.yaml`:
    - [ ] Define Service.
    - [ ] Map Ports (gRPC/REST).
    - [ ] Link Networks (Kafka/DB/Loki).

## 3. Database Management
- [ ] Install Flyway.
- [ ] Create `src/main/resources/db/migration/V1__init_schema.sql`.
- [ ] Verify `podman-compose` runs DB migration on startup.

## 4. Quality Gates (Bindings)
- [ ] Verify `status.md` bindings:
    - [ ] `lint_check_cmd`: `mvn verify`
    - [ ] `unit_test_cmd`: `mvn test`
    - [ ] `integration_test_cmd`: `mvn failsafe:integration-test`
- [ ] Run `bash workflow_core/validate.sh . --check quality` to verify.
