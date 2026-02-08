# 01_04 Tooling & Security Specification (V1.3)

> **Status**: DRAFT (Implementation)
> **Version**: 1.3
> **Key Changes**: Green Field Strategy, SRE RBAC, Advanced Edit Operations, Incremental RAG.

## 1. Overview

The **Tooling System** provides the strictly governed "Hands" for Agents to interact with the environment.

### 1.1 Terminology: Atom vs. Tool
To avoid confusion in the fractal architecture:
*   **Atom**: The fundamental, indivisible unit of execution within the Flow Engine (e.g., `Manifest_Parse`, `Template_Render`). Flows are composed of Atoms and other Flows. Atoms are internal optimization primitives.
*   **Tool**: A secure, user-facing capability exposed to an Agent (e.g., `read_file`, `run_test`). Tools are standardized interfaces (MCP-compatible) that may wrap one or more Atoms but enforce **Security Policies** (Scope, Redaction, Rate Limiting).

### 1.2 Security Philosophy
We adhere to a **Paranoid Security Model**:
1.  **Deny by Default**: Agents start with zero permissions.
2.  **Service Isolation**: Agents are jailed to their specific Service Directory.
3.  **Input/Output Sanitization**: All streams are scanned for secrets.
4.  **No Implicit Trust**: Tools do not trust Agent arguments; they validate everything.
5.  **Role-Based Access Control (RBAC)**: SRE Agents have distinct privileges (System Tools) denied to standard Dev Agents.

---

## 2. Architecture: "The Toolbox"

We implement a **Native Python Library** (`src/flow/tools/`) exposing tools via the **MCP Interface**.

### 2.1 The Tool Interface
Every tool must implement:
```python
class Tool(ABC):
    name: str          # Unique ID (e.g., "file_read")
    description: str   # Instructions for the Agent
    input_schema: Dict # JSON Schema for arguments
    
    def call(self, args: Dict, context: ToolContext) -> ToolResult:
        ...
```

### 2.2 Standardized Result Schema (`ToolResult`)
To ensure Agents can recover from errors, all tools return a standard structure:

```json
{
  "status": "success" | "error",
  "data": { ... },           // Payload on success
  "error": {                 // Present on error
    "code": "FileNotFound",
    "message": "File src/main.py does not exist.",
    "suggestion": "Check the path or use list_files to see available files."
  },
  "metadata": {
    "duration_ms": 12,
    "security_checks": "passed"
  }
}
```

### 2.3 The Tool Context (`ToolContext`)
The `ToolContext` is injected by the Engine at runtime. It contains:
*   `service_root` (Path): The root directory of the **Active Service** (e.g., `services/trade-engine/`).
*   `isolation_level` (Enum): `STRICT` (default) or `SHARED`.
*   `allowed_commands` (List[str]): Whitelisted commands for this specific task.
*   `access_token` (str): Ephemeral token for RAG/API access.
*   `volume_id` (str): Unique ID of the ephemeral volume to ensure operations don't cross mount points.

### 2.4 Permissions & Roles Matrix (RBAC)
The system enforces strict role-based capability limits.

| Role ID | Description | Allowed Capabilities | Restricted Tools |
| :--- | :--- | :--- | :--- |
| **`dev`** | Standard Developer (Default) | Read/Write Source in Service, run tests. | `git_push`, `SystemTool` |
| **`sre`** | Site Reliability Engineer | Infrastructure management, System Tools. | None (Audited) |
| **`release_manager`** | Release Engineer | Merge/Push to protected branches. | None (Audited) |
| **`product_owner`** | Non-Technical | Read-Only access to docs/plans. | `write_file`, `git_commit` |

**Enforcement**:
*   The `ToolExecutor` checks `context.role` against the tool's `required_role` attribute.
*   If `required_role` is set and does not match, a `PermissionDenied` error is raised.
*   Critical actions by high-privilege roles (`sre`, `release_manager`) are always logged to the Security Audit Stream.

---

## 3. The File Toolset (`FileTool`)

A unified suite of functions for file system interaction.

### 3.1 Capabilities
| Tool Name | Arguments | Description | Security Check |
| :--- | :--- | :--- | :--- |
| `read_file` | `path`, `max_bytes` (default: 100KB) | Reads content as UTF-8. Fails on binary or >max_bytes. | **Service Scope Check** |
| `write_file` | `path`, `content` | Overwrites or creates a file. | **Service Scope Check** + **Secret Scan** |
| `edit_file` | `path`, `edits` | Surgically modifies a file (Loom). | **Service Scope Check** + **Secret Scan** |
| `search_file` | `path`, `regex`, `recursive` | Grep-like search. Returns snippets. | **Service Scope Check** |
| `count_matches` | `path`, `regex`, `recursive` | Returns count of pattern matches. **Crucial for verifying uniqueness before edit.** | **Service Scope Check** |
| `list_files` | `path`, `recursive` | Lists directory contents. | **Service Scope Check** |
| `delete_file` | `path` | Deletes a file. | **Strict Whitelist** (No `rm -rf`) |

### 3.2 Surgical Editing (`edit_file`)
Powered by the **Loom Engine**, this tool allows precise code modification using multiple strategies.

**Schema**:
```json
{
  "path": "src/main.py",
  "edits": [
    { 
      "operation": "replace",    // enum: ["replace", "append_after", "prepend_before", "delete"]
      "match_mode": "exact",     // enum: ["exact", "regex", "ast"]
      "spec": "old_var = 1",     // The string/pattern/AST-selector to find
      "content": "new_var = 2",  // The content to inject (ignored for delete)
      "count": 1                 // Expected matches. Default: 1. Fails if actual != count.
    }
  ]
}
```

#### Match Modes
1.  **Exact** (Default): String literal match. Whitespace sensitive.
2.  **Regex**: Python `re` syntax. Capture groups can be used in `content`? (TBD: Keep simple for V1).
3.  **AST** (Future): Uses `ast-grep` patterns like `function $NAME($ARGS) { $$$ }`.

#### Safety Pattern: "Atomic Uniqueness"
The `edit_file` tool **internally** counts matches *before* applying edits. If `match_count != count`, the entire operation aborts. This prevents "blind" editing.

### 3.2.1 Operational Semantics (Loom Logic)
*   **Concurrency**: Implements **Advisory File Locking**.
    *   *Rent*: Before reading/editing, Loom acquires an exclusive lock (`.lock.filename`) with a 5s timeout.
    *   *Return*: Lock is released immediately after write.
    *   *Failure*: If lock acquisition fails, the tool errors with `ResourceBusy`.
    *   *Stale Lock Policy*: If a lock file is older than 30 seconds (e.g., agent crashed), it is considered **Stale**. The next operation forces the lock (deletes old lock, logs warning, acquires new lock).
*   **Conflict Resolution**:
    *   *Overlap*: If multiple edits target overlapping line ranges, the operation is **rejected**.
    *   *Order*: Edits are applied transactionally. Either all succeed, or none.
*   **ReDoS Protection**:
    *   All regex operations run with a strict **100ms timeout** using `google-re2` (or similar non-backtracking engine).
    *   If a regex times out, the tool returns a `SecurityError`.

### 3.3 Security: The "Service Scope Guard"
*   **Allow Scope**: All paths must resolve to `${context.service_root}` or `${project.root}/shared_contracts/`.
*   **Mono-Repo Policy**:
    *   **Own Service**: `read/write` allowed in `${service_root}`.
    *   **Shared**: `read-only` allowed in `${project.root}/shared/` or `${project.root}/contracts/`.
    *   **Forbidden**: Access to sibling directories (e.g., `../other-service/`) is **STRICTLY FORBIDDEN**. The Agent is physically jailed to its own service folder.
*   **Blocked Zones (Deny List)**: Specific paths are blocked even within scope:
    *   `.env`, `.git/`, `secrets/`, `node_modules/`.
*   **Volume Guard**:
    *   Symlinks must resolve to a path within the Allowed Scope.
    *   Hard links and Mount points are detected via `os.stat().st_dev`. Operations crossing device boundaries are blocked.

---

## 4. The Shell Toolset (`ShellTool`)

Controlled execution of system commands. **Raw `run_command` is DEPRECATED.**

### 4.1 Capabilities (Intent-Based Tools)
| Tool Name | Arguments | Description | Security Check |
| :--- | :--- | :--- | :--- |
| `run_test` | `target`, `truncation_strategy` | Runs tests. `truncation_strategy` (e.g., "HEAD:5") limits output size to prevent context overflow. | **Test Scope Check** |
| `run_lint` | `target` | Runs linters for the current service. | **Test Scope Check** |
| `git_status` | None | Checks git status. | **Read-Only** |
| `git_diff` | `staged` (bool) | Shows diffs. | **Read-Only** |
| `git_add` | `files` (List) | Stages files. | **Service Scope Check** |
| `git_commit` | `message` | Commits changes. | **Message Validation** |
| `git_push` | `remote`, `branch` | Pushes to remote. **Requires 'release_manager' Role**. | **RBAC Check** |
| `git_checkout` | `branch`, `create_if_missing` | Switches branch. Creates if `create_if_missing=True`. | **Branch Name Policy** |
| `install_dependencies` | `manager` (npm, poetry, cargo) | Installs dependencies using lockfiles (`npm ci`, `poetry install`). | **RBAC Check** |

### 4.2 Dangerous Command Policy
*   **Dev Agents**:
    *   `npm install`: **BLOCKED**. Must use `npm ci`.
    *   `pip install`: **BLOCKED**. Must use `poetry install` (lockfile based).
*   **SRE Agents**:
    *   Allowed access to `SystemTool` (see Section 6) for **Infrastructure** setup, not Project dependencies.

### 4.3 Git Push Policy (RBAC)
*   **Default**: `git push` is **NOT** available.
*   **Role Constraint**: Only Agents with `context.role == "release_manager"` (RelEng) may access the `git_push` tool.
*   **Safety**: Defaults to `--dry-run` and requires explicit confirmation.

### 4.4 Legacy `run_command`
**Status**: REMOVED. This project is Green Field. All capabilities must be migrated to `ShellTool` or `SystemTool`.

---

## 5. The Knowledge Toolset (`KnowledgeTool`)

**Prefix**: `rag_*`
Integrates with the **Local RAG System** (Ollama + ChromaDB).

### 5.1 Capabilities
| Tool Name | Arguments | Description |
| :--- | :--- | :--- |
| `search_knowledge` | `query`, `limit` | Semantic search across the codebase and docs. |
| `find_usage` | `symbol` | Structural search (AST-based) to find usages. |
| `get_related_tests` | `file_path` | Retrieves tests linked to a specific source file. |
| `get_system_map` | `root_dir` (Optional) | Returns a dynamic high-level map of Services, Docs, and Infra (Ref: `generate_map.py`). |
| `get_task_context` | `task_id` | Parses `status.md` to return hierarchical context (Phase -> Service -> Feature -> Task). |

### 5.2 RAG Context
Example Query: *"How do I implement the Event Bus?"*
*   **Source**: Indexes `docs/specs`, `src/core`, and `tests/`.
*   **Privacy**: RAG queries are local; no data leaves the environment.

### 5.3 Incremental Indexing & Cold Start
1.  **Manifest**: System maintains `rag_manifest.json` mapping `file_path -> sha256_hash`.
2.  **Cold Start Mitigation**:
    *   Base Docker images ship with **Pre-Computed Indexes** for standard libraries and stable core modules.
    *   Only the *delta* (current project changes) needs to be indexed on startup.
3.  **Delta Indexing**: Only files with changed hashes are re-embedded and upserted to Vector DB.
4.  **Bootstrap**: If no manifest exists (fresh clone), a full background index is triggered. Agent is warned "Knowledge Base Building..." and may experience reduced recall for ~2 minutes.

---

## 6. The System Toolset (`SystemTool`) - SRE ONLY

**Role Requirement**: `context.role == "sre"`

Provides privileged access to system configuration and package management.

### 6.1 Capabilities
| Tool Name | Arguments | Description |
| :--- | :--- | :--- |
| `install_package` | `manager` (apt, cargo, npm-g), `package`, `version` | Installs system dependencies. |
| `verify_binary` | `binary_name` | Checks if a binary is in PATH and runnable. |
| `system_ctl` | `service`, `action` (status, restart) | Manages local services (e.g., Docker/Podman). |
| `migrate_config` | `target_version` | Upgrades configuration files to match new schema versions (Ref: `refactor_git.py`). |

### 6.2 Security Constraints
1.  **Audit Logging**: Every `SystemTool` call is logged with `Severity: CRITICAL`.
2.  **Dependency Boundary**:
    *   `SystemTool` is for **Infrastructure** (e.g. `pg_dump`, `curl`, `apt-get`).
    *   **Project Dependencies** (e.g. `pip install`, `npm install`) are **BLOCKED** here. They must be managed via `ShellTool` using lockfile-compliant commands (`npm ci`, `poetry install`).
3.  **No Interactive Mode**: All commands run with `-y` or equivalent non-interactive flags.
4.  **Sudo Policy**: If `sudo` is required, it must be configured passwordless for the Agent User on specific binaries only. Agent does NOT hold root password.

---

## 7. The Redactor (Stream Security)

**Requirement**: All output (Stdout, Stderr, File Reads) passes through a **Smart Redactor**.

### 7.1 Entropy & Secret Scanning
Regex is insufficient. The Redactor must:
1.  **Pattern Match**: Known formats (`sk-...`, `ghp-...`).
2.  **Entropy Scan**: Detect high-entropy strings (potential random keys).
3.  **Known Secret Filter**: actively block values present in `os.environ` (even if they don't look like keys).

*Note*: We acknowledge that a malicious Agent with code execution can bypass redaction (e.g. by splitting strings). This layer protects against *accidental* leakage in logs, not malicious exfiltration.

### 7.2 Security Audit Log & Active Defense
Any action denied by the **Service Scope Guard** or **Command Whitelist** must be logged to a secure audit stream (outside the Agent's context).
*   **Log Event**: `{ timestamp, agent_id, violation_type, target_path, command_args }`
*   **Kill Switch**: High-frequency violations (e.g., >5 in 1 min) trigger an **Alert Mode** (V1). The incident is flagged for Human Review. (Future: Automatic Session Termination).

---

## 8. Security Configuration (`.flow/config.json`)

The central policy file for the project.

```json
{
  "scope": {
     "service_isolation": "STRICT",
     "shared_paths": ["shared_contracts/", "docs/policies/"],
     "block_patterns": [".env", "secrets/"]
  },
  "tools": {
     "allow_legacy_run_command": false,
     "whitelisted_binaries": ["pytest", "npm", "cargo"]
  },
  "secrets": {
     "redact_patterns": ["sk-...", "ghp-..."]
  }
}
```

## 9. Implementation Plan

1.  **Refactor**: Separate `Atom` (Internal) and `Tool` (External) classes.
2.  **Toolchain**: Implement `ToolchainConfig` loader for `test/lint` commands.
3.  **RAG**: Build `KnowledgeTool` connecting to the ChromaDB service.
4.  **Security**:
    *   Implement `EntropyRedactor`.
    *   Add `FileLock` to Loom.
    *   Block `npm install` in `ShellTool` (allow `npm ci`).
    *   Implement `ToolResult` schema.
