# Test Inventory: Tooling & Security (Task 1.4)

This file tracks **ALL** identified test cases for the V1.3 "Paranoid Hardened" Tooling System.
Consolidated Structure: 8 Chapters (Security, Loom, Shell, Knowledge, System, Reliability, IO, Platform).

## 1. Security, Access Control & Sandbox
*   **T1.01 Service Scope Isolation**:
    *   Input: Agent in `services/trade-engine` tries `read_file("../portfolio-service/secrets.py")`.
    *   Expect: `SecurityError` (Scope Violation). Path must allow-list `${service_root}`.
*   **T1.02 Shared Contract Access**:
    *   Input: Agent in `services/trade-engine` tries `read_file("shared_contracts/api.proto")`.
    *   Expect: **Success** (Shared Scope Allowed).
*   **T1.03 Blocked File Pattern**:
    *   Input: `read_file(".env")` or `write_file("config/secrets.yaml")`.
    *   Expect: `SecurityError` (Blocked Pattern).
*   **T1.04 RBAC Denial (Dev -> Prod)**:
    *   Input: Agent with role `dev` tries `git_push`.
    *   Expect: `PermissionDenied` (Requires `release_manager`).
*   **T1.05 RBAC Success (RelEng -> Prod)**:
    *   Input: Agent with role `release_manager` tries `git_push`.
    *   Expect: **Success** (Command Executed).
*   **T1.06 SystemTool Denial (Dev)**:
    *   Input: Agent with role `dev` tries `system_ctl`.
    *   Expect: `PermissionDenied` (Requires `sre`).
*   **T1.07 Volume Escape (Symlink)**:
    *   Input: `read_file("logs/link_to_root")` where link points to `/`.
    *   Expect: `SecurityError` (Symlink traversal outside scope).
*   **T1.08 Direct Import Block**:
    *   Input: Agent tries to execute python code `import os; os.system('calc')` via a "Run Python" tool (if available).
    *   Expect: `SecurityError`. usage of `os`, `sys`, `subprocess` is blocked by AST sanitizer or restricted globals.
*   **T1.09 Shell Bypass**:
    *   Input: `run_command("python -c 'import urllib; ...'")`.
    *   Expect:
        *   If `python` is allowed: Command runs.
        *   **Requirement**: Network Access must be blocked by Container/Firewall rules if not explicitly whitelisted. Test `curl google.com`.
*   **T1.10 Tool Exclusivity (The Loophole)**:
    *   Input: Agent tries to use standard library `open()` instead of `read_file()` tool within a code-execution block.
    *   Expect: The Execution Environment (Docker/Wasm/RestrictedPython) denies access to the host filesystem. Filesystem access is ONLY possible via the injected `read_file` function.
*   **T1.11 Active Defense (Alert Mode)**:
    *   Input: Trigger 10 Security Violations in 1 minute.
    *   Expect: `Alert[CRITICAL]` logged. Agent is **NOT** killed (V1 Policy).
*   **T1.12 Sensitive Redaction**:
    *   Input: specific environment variable key present in output.
    *   Expect: Output contains `[REDACTED]`.
*   **T1.13 Install Package (SRE Only)**:
    *   Input: `install_package(manager="apt", package="curl")`. Role=`sre`.
    *   Expect: Success.
*   **T1.14 Install Package (Dev Denial)**:
    *   Input: Same command. Role=`dev`.
    *   Expect: `PermissionDenied`.
*   **T1.15 NTFS Alternate Data Streams (Windows)**:
    *   Input: `read_file("sensitive.txt:hidden_stream")`.
    *   Expect: `SecurityError` (Colon detected in filename, blocking ADS access).
*   **T1.16 UNC Path Injection (Windows)**:
    *   Input: `write_file("\\\\evil-server\\share\\exploit.exe")`.
    *   Expect: `SecurityError` (UNC paths blocked to prevent SMB hash leakage).
*   **T1.17 Reserved Device Names (Windows)**:
    *   Input: `write_file("COM1")`, `read_file("PRN")`, `AUX`, `NUL`, `CON`.
    *   Expect: `SecurityError` (Reserved device names blocked).
*   **T1.18 Named Pipe Masquerade (Windows)**:
    *   Input: Tool attempts to open `\\.\pipe\docker_engine` or other IPC pipes.
    *   Expect: `SecurityError`. Access restricted to regular files unless explicitly whitelisted.
*   **T1.19 Windows 8.3 Shortnames**:
    *   Input: `read_file("SECRE~1.TXT")` (where `secrets.txt` exists and is blocked).
    *   Expect: `SecurityError`. Tool resolves canonical path (`secrets.txt`) before checking deny-list.

## 2. The Loom (Surgical Editing)
*   **T2.01 Atomic Uniqueness Check (Success)**:
    *   Input: `edit_file` with `count=1`. Target has exactly 1 match.
    *   Expect: Edit applied.
*   **T2.02 Atomic Uniqueness Check (Fail)**:
    *   Input: `edit_file` with `count=1`. Target has 2 matches.
    *   Expect: `Error("Match count mismatch: Expected 1, Found 2")`. No changes made.
*   **T2.03 Stale Lock Recovery**:
    *   Input: `.lock` file exists, timestamp is 45s ago (Timeout=30s).
    *   Expect: Structure claims lock (breaks stale one), warns, and proceeds.
*   **T2.04 Active Lock Contention**:
    *   Input: `.lock` file exists, timestamp is 2s ago.
    *   Expect: `ResourceBusyError`.
*   **T2.05 Regex Timeout (ReDoS)**:
    *   Input: `edit_file` with evil regex `(a+)+`.
    *   Expect: `SecurityError` (Timeout > 100ms).
*   **T2.06 Overlapping Edits**:
    *   Input: Two edits in same request targeting lines 10-15 and 12-20.
    *   Expect: `ValidationError` (Overlap rejected).
*   **T2.07 Ambiguity (Multiple Matches)**:
    *   Input: `edit_file` targeting "return True". Content appears 3 times. `count=1` (Default).
    *   Expect: `Error("Match count mismatch: Expected 1, Found 3")`.
*   **T2.08 Zero Match (Idempotency)**:
    *   Input: `edit_file` targeting "old_code". "old_code" not found, but "new_code" IS found.
    *   Expect: **Success** (Idempotent No-Op).
*   **T2.09 Attributes Preservation**:
    *   Input: `edit_file` on 0600 file.
    *   Expect: Post-edit file is 0600 (not 0644). Owner/Group preserved.
*   **T2.10 BOM Preservation**:
    *   Input: `edit_file` on UTF-8-SIG file.
    *   Expect: BOM preserved in output.
*   **T2.11 ACL/Read-Only Context**:
    *   Input: `edit_file` where read is allowed but directory is read-only (cannot create temp file).
    *   Expect: Clean Fail (`PermissionDenied`), no zombie `.tmp` files left behind.

## 3. ShellTool (Dependencies & Git)
*   **T3.01 Install Dependencies (NPM CI)**:
    *   Input: `install_dependencies(manager="npm")`.
    *   Expect: Runs `npm ci` (clean install). Access Allowed (RBAC check passed if role allows).
*   **T3.02 Install Dependencies (Block Generic)**:
    *   Input: `install_dependencies(manager="pip")`.
    *   Expect: `ValidationError` (Must use `poetry` or `pipenv` per policy, plain `pip` blocked).
*   **T3.03 Git Checkout (Switch)**:
    *   Input: `git_checkout(branch="feature/x")`. Branch exists.
    *   Expect: HEAD points to `feature/x`.
*   **T3.04 Git Checkout (Create)**:
    *   Input: `git_checkout(branch="feature/new", create_if_missing=True)`.
    *   Expect: New branch created and checked out.
*   **T3.05 Git Checkout (Name Policy)**:
    *   Input: `git_checkout(branch="Master")`.
    *   Expect: `ValidationError` (Must use `master` or policy valid names).
*   **T3.06 Git Push (Dry Run Default)**:
    *   Input: `git_push(remote="origin", branch="feature/x")`.
    *   Expect: Runs with `--dry-run` unless `force=True` (if supported) or config override.

## 4. KnowledgeTool (Context & RAG)
*   **T4.01 System Map Generation**:
    *   Input: `get_system_map()`.
    *   Expect: Returns JSON with Service/Infra/Test breakdown (Dynamic discovery).
*   **T4.02 RAG Health Status**:
    *   Input: `check_status()`.
    *   Expect: Returns `{"status": "ready"}` or `{"status": "indexing", "progress": "45%"}`. Essential for proactive monitoring.
*   **T4.03 RAG Search (Scope)**:
    *   Input: `search_knowledge("Event Bus")`.
    *   Expect: Results from `docs/` and `src/core` only (Privacy scope).


## 5. System & Configuration
*   **T5.01 Migrate Config**:
    *   Input: `migrate_config(target_version="v2")`.
    *   Expect: Updates `workflow_registry.json` schema. (Legacy Gem verification).
*   **T5.02 Context Immutability**:
    *   Input: Tool code attempts `context.allowed_commands.append("curl")`.
    *   Expect: `AttributeError` or change is ignored. Context is frozen/tuple.
*   **T5.03 Tool Composition Context**:
    *   Input: `SystemTool` (Outer) calls `ShellTool` (Inner).
    *   Expect: Inner tool receives the *original* `ToolContext` (volume_id, role), ensuring scope enforcement even in nested calls.

## 6. Reliability, Lifecycle & Concurrency
*   **T6.01 Graceful Teardown (SIGTERM)**:
    *   Input: Send SIGTERM during `edit_file` (while lock active).
    *   Expect: Process catches signal, releases `.lock`, cleans up `.tmp` files, and exits Cleanly.
*   **T6.02 Child Process Cleanup**:
    *   Input: Engine crashes while `npm ci` is running.
    *   Expect: Child process is terminated (not orphaned) via OS group kill or parent-death signal.
*   **T6.03 Grandchild Process Cleanup (Job Object)**:
    *   Input: Tool spawns `node process` -> spawns `gcc`. Engine crashes (SIGKILL).
    *   Expect: All descendants (`node`, `gcc`) are terminated via Job Object / Process Group fate-sharing. Verified via OS process tree check.
*   **T6.04 SIGKILL Escalation (Zombie Killer)**:
    *   Input: Tool spawns a process that traps/ignores SIGTERM. Engine shuts down.
    *   Expect: Supervisor sends SIGTERM, waits 5s, detects process running, then sends SIGKILL. Process dies.
*   **T6.05 Interrupt during I/O Wait**:
    *   Input: User cancels (SIGINT/SIGTERM) while tool is in `time.sleep(100)` or `socket.recv()`.
    *   Expect: Clean exit, no zombie process, `SystemExit` caught and logged.
*   **T6.06 Disk Full (ENOSPC) [MOCK]**:
    *   Input: `write_file` when disk is full (Mocked `OSError(28)` via `os.write` patch).
    *   Expect: `SystemError`. Target file remains unchanged (Atomic Write protection).
*   **T6.07 Windows Job Object Cleanup (Verify)**:
    *   Input: Engine Crash (SIGKILL) while `npm ci` is running on Windows.
    *   Expect: OS View shows `npm` process terminated by Nested Job Object.
*   **T6.08 Permission Flapping**:
    *   Input: File permissions change to 000 mid-operation.
    *   Expect: `PermissionDenied`. No partial write.
*   **T6.09 Broken Pipe Resilience**:
    *   Input: Tool writes to stdout, Engine closes pipe (crash/restart).
    *   Expect: Tool receives `SIGPIPE` (Linux) or `EPIPE` (Windows) and exits gracefully. Does not hang writing to void.
*   **T6.10 Environment Wipe**:
    *   Input: Run tool with `env={}`.
    *   Expect: Tool Wrapper supplies safe defaults (`PATH`, `TEMP`, `SystemRoot` on Windows) to prevent immediate crash of child process.
*   **T6.11 CWD Deletion Recovery**:
    *   Input: External process does `rm -rf <cwd>` while Tool is running.
    *   Expect: Tool/Engine recovers gracefully on exit (does not crash with `FileNotFoundError` when trying to cleanup).
*   **T6.12 Parallel Edit Race**:
    *   Input: 50 threads execute `edit_file("shared.txt")` simultaneously.
    *   Expect: 1 Success, 49 `ResourceBusy` or Queued. File content valid (no corruption).
*   **T6.13 Deadlock Detection**:
    *   Input: Agent A holds Lock 1, wants Lock 2. Agent B holds Lock 2, wants Lock 1.
    *   Expect: Watchdog kills one transaction after timeout (5s).
*   **T6.14 Tool-Level Semantic Locking**:
    *   Input: `install_dependencies` (npm ci) called twice in parallel by different agents/threads.
    *   Expect: Second call fails immediately with `ResourceBusy` (Semantic Lock). It must NOT run concurrent installs in the same dir.
*   **T6.15 TOCTOU Mitigation (Symlink Switch)**:
    *   Input: Tool checks `path` (file exists). Attacker swaps `path` to Symlink -> `/etc/passwd`. Tool opens `path`.
    *   Expect: Tool uses file descriptor pinning or atomic open-with-check to fail if file type changed.
*   **T6.16 Handle Exhaustion (Chaos)**:
    *   Input: Spawn 1000 processes/threads via Tools.
    *   Expect: `ResourceExhausted` handled gracefully. Engine does not crash.
*   **T6.17 Zombie Lock (Chaos)**:
    *   Input: Process A takes lock, is `kill -9`ed. Process B tries to take lock immediately.
    *   Expect: Immediate recovery (T2.03) via PID liveness check.
*   **T6.18 Interrupted Write (Atomic)**:
    *   Input: Simulate power loss during `write_file` syscall.
    *   Expect: Target file remains 100% unchanged (Atomic `os.replace` guarantee). No partial/corrupt files on disk. (Verify via Crash-Mid-Write mock).
*   **T6.19 Re-run Install**:
    *   Input: `install_dependencies` interrupted. Run again.
    *   Expect: Package Manager (`npm/pip`) handles resume or cleans up lockfile. Tool Wrapper does not block "re-run".
*   **T6.20 Orphaned Lock Claim (Lock Stealing)**:
    *   Input: `pid_123.lock` exists. PID 123 is demonstrably dead. Tool invoked.
    *   Expect: Tool detects stale PID, breaks lock, and proceeds. Does not block indefinitely.
*   **T6.21 Idempotent Append (Dup Prevention)**:
    *   Input: `edit_file(op="append", content="config_line=1")`. File already has line.
    *   Expect: No change (Idempotency). Tool checks existence before appending.
*   **T6.22 Resume Install (Clean Recovery)**:
    *   Input: `npm ci` interrupted at 50% (dirty `node_modules`). Run again.
    *   Expect: Tool detects dirty state and recovers (wipes or resumes). Must not fail with "Directory not empty".
*   **T6.23 Crash-Mid-Write (Atomic)**:
    *   Input: `write_file` operation interrupted by `SIGKILL` during the physical write.
    *   Expect: Target file remains 100% unchanged (Atomic `os.replace` guarantee). No partial/corrupt files on disk.
*   **T6.24 Clock Skew Recovery**:
    *   Input: System time jumps backwards 1 hour while Lock is held.
    *   Expect: Lock expiration logic uses `time.monotonic()` (or equivalent), NOT wall clock. Lock must not become "instantly stale" or "infinitely valid".
*   **T6.25 Job Object Containment (Windows)**:
    *   Input: Tool spawns `node server.js` which spawns `mongo`. Tool exits.
    *   Expect: `Windows Job Object` kills the entire process tree. No orphaned `mongo.exe` allowed.
*   **T6.26 Job Object Verification (Windows)**:
    *   Input: Spawn processes, kill Engine immediately.
    *   Expect: Use `ctypes` to query `IsProcessInJob`. Verify child processes are explicitly assigned to a Job Object on creation. Verify `JOBOBJECT_LIMIT_KILL_ON_JOB_CLOSE` flag is set.
*   **T6.27 Job Object Escape Attempt (Windows)**:
    *   Input: Tool spawns `start /B pythonw.exe detached_script.py` (Windows Detached Process). Engine exits.
    *   Expect: OS View confirms `pythonw.exe` is killed. Job Object must contain even "detached" children.
*   **T6.28 Stale Lock PID Reuse**:
    *   Input: Create lockfile with PID=X. Kill process X. Spawn new process Y until PID=X is reused (hard to deterministic, but simulate via mock PID provider).
    *   Expect: Lock checking logic must validate start-time or UUID, not just PID, to prevent false-positive ownership.

## 7. Input/Output Safety & Limits
*   **T7.01 Negative Max Bytes**:
    *   Input: `read_file("valid.txt", max_bytes=-1)`.
    *   Expect: `ValidationError` (Must be > 0).
*   **T7.02 Huge Binary Payload**:
    *   Input: `write_file("data.bin", content="<10MB_binary_data>")`.
    *   Expect: `ValidationError` (Exceeds payload limit or binary check if content detection active).
*   **T7.03 Null Byte Injection**:
    *   Input: `read_file("src/main.py\0.exe")`.
    *   Expect: `SecurityError` (Null byte detected).
*   **T7.04 Empty Path/Content Validation**:
    *   Input: `write_file(path="", content="")` or `read_file(path="  ")`.
    *   Expect: `ValidationError` (Path cannot be empty or whitespace only).
*   **T7.05 Gibberish Sanitization**:
    *   Input: Tool returns 1MB of binary garbage (non-ALPHANUM, non-UTF8).
    *   Expect: Output is sanitized to `"<Binary Data Redacted>"` or similar safe token. It MUST NOT crash the JSON serializer or the LLM tokenizer.
*   **T7.06 Recursive/XML Expansion**:
    *   Input: Tool returns valid XML/JSON that expands to 100x size when parsed.
    *   Expect: Tool Wrapper treats output as Opaque String, does not attempt to parse/expand recursively.
*   **T7.07 Token Economy (Head/Tail)**:
    *   Input: Tool returns 10MB text log.
    *   Expect: Wrapper truncates to "First 50 lines ... [Truncated 9MB] ... Last 50 lines".
*   **T7.08 Monolithic Line Flood (Buffering Attack)**:
    *   Input: Tool emits 1GB string without newlines.
    *   Expect: Wrapper stream-reads in fixed-size chunks (e.g., 4KB). Detects size limit violation *before* loading full line into RAM. Kills process.

*   **T7.10 Schema Interoperability**:
    *   Input: Generate Tool Definition (JSON Schema).
    *   Verify: Schema passes validation for:
        *   OpenAI Functions (strict subset).
        *   Anthropic Tools (input_schema).
        *   Gemini Function Declarations.
    *   Expect: No "OneOf" or generic types that break specific providers.
*   **T7.11 Token Economy (Smart Summary)**:
    *   Input: `read_file` of a 50MB log file.
    *   Expect: Tool returns a "Smart Summary" (e.g., First 2KB + Last 2KB + Line Count). It MUST NOT return 50MB.
*   **T7.12 Generic Error Stability**:
    *   Input: Missing required argument (LLM hallucination).
    *   Expect: Tool returns a friendly string `Error: Missing 'path' argument`, NOT a Python traceback / HTTP 500.
*   **T7.13 Infinite Output Stream**:
    *   Input: `run_command(cmd="yes")`.
    *   Expect: Tool returns `error="OutputLimitExceeded"` or `data="y\ny\n...[TRUNCATED]"` after 1MB. Process Killed.
*   **T7.14 Tool Timeout**:
    *   Input: `run_command(cmd="sleep 100")` with `timeout=1s`.
    *   Expect: Tool returns `error="Timeout"` after 1.1s. Process Killed.
*   **T7.15 Rapid Fire (DoS Protection)**:
    *   Input: 50 calls to `search_knowledge` in 1s.
    *   Expect: First N succeed, rest fail with `RateLimitExceeded`.
*   **T7.16 Environment Sanitization**:
    *   Input: `run_test` with `env={"PATH": "/malicious"}`.
    *   Expect: Tool overrides/ignores unsafe ENV vars.
*   **T7.17 Rate Limit Persistence**:
    *   Input: Consume 100% quota -> Restart Engine -> Attempt Action.
    *   Expect: `RateLimitExceeded`. Quota usage MUST persist across restarts (Redis/Disk).
*   **T7.18 Stdin Starvation**:
    *   Input: Tool attempts `input()` or `sys.stdin.read()`.
    *   Expect: Immediate `EOF` or `OSError`. Tool must NEVER hang waiting for user input.
*   **T7.19 Streaming Memory Leak (Infinite Drip)**:
    *   Input: Tool outputs 1GB of data at 10KB/s. Engine `max_buffer=1MB`.
    *   Expect: `OutputLimitExceeded` error raised *before* OOM. Memory usage remains constant/bounded.

*   **T7.21 Environment Poisoning**:
    *   Input: Tool execution with `LD_PRELOAD=/tmp/evil.so` or `PYTHONPATH=/tmp/hack`.
    *   Expect: Sanitizer strips dangerous variables before `subprocess.popen`.
*   **T7.22 Recursive Symlink Loop**:
    *   Input: `list_files` on directory where `a/b -> a` (Infinite loop).
    *   Expect: Engine detects cycle or depth limit, logs warning, and returns valid file list without hanging.
*   **T7.23 File Descriptor Exhaustion**:
    *   Input: Tool attempts to open 10,000 files/sockets.
    *   Expect: `ResourceExhausted` (EMFILE). Engine supervisor remains stable; Tool fails gracefully without crashing the parent process.
*   **T7.24 Proxy Injection**:
    *   Input: Tool execution with `env={"HTTP_PROXY": "http://evil.com"}`.
    *   Expect: Tool Executor sanitizes environment. Proxy settings are ignored or strictly whitelisted.
*   **T7.25 Budget Inheritance (Tool-in-Tool)**:
    *   Input: Tool A (Timeout=10s) calls Tool B (Default Timeout=30s).
    *   Expect: Tool B must expire at T+10s (Inherited Budget), not T+30s. Prevent "Time Extension" attacks.
*   **T7.26 Tool Output Deserialization Attack**:
    *   Input: Tool returns valid JSON that deserializes into a Python Object (pickle-style exploit) or uses `__proto__` pollution.
    *   Expect: Strict JSON loader (e.g., `orjson`) that produces pure dicts, never objects.

## 8. Platform & Filesystem Reality
*   **T8.01 Max Path Length (Windows)**:
    *   Input: `write_file` to path > 260 chars.
    *   Expect: Tool uses `\\?\` prefix or Extended Path handling. If not supported, fails gracefully with `PathTooLongError`, not a crash.
*   **T8.02 Case Sensitivity Conflict**:
    *   Input: `read_file("Makefile")` when disk has `makefile`.
    *   Expect:
        *   Linux: `FileNotFoundError` (Case Sensitive) or `Success` (if file exists exactly).
        *   Windows: Returns content (Case Insensitive).
        *   **Requirement**: Tooling must warn if multiple files match case-insensitively (ambiguity check).
        *   **Verified in**: `tests/unit/tools/file/test_file_tool_platform_constraints.py`
*   **T8.03 Locked File Editing**:
    *   Input: `edit_file` on a file locked by Excel/Word/Notepad.
    *   Expect: `ResourceBusyError`. Content is untouched.
*   **T8.04 Unicode Path Handling**:
    *   Input: `write_file("🔥.txt")` and `read_file("data/銘.json")`.
    *   Expect: Success on both Windows (NTFS UTF-16) and Linux (EXT4 UTF-8). Tool handles encoding correctly without crashing.
*   **T8.05 Executable Extension Spying (Windows)**:
    *   Input: `run_command("test.txt")` where `.txt` is associated with `cmd.exe`.
    *   Expect: Tool Wrapper forces strict executable check or uses `CreateProcess` with `NoShell` to prevent implicit association execution.
*   **T8.06 Windows CRLF Preservation**:
    *   Input: `edit_file` on a file with CRLF line endings, using LF content in the spec.
    *   Expect: Resulting file MIGHTY strictly preserve CRLF. It must NOT mix line endings (e.g., LF in modified lines, CRLF elsewhere).

## 9. File System Tools (Moved from Ch 3)
*   **T9.01 Path Traversal via Content**:
    *   *(Moved from T3.07)*
    *   Input: `write_file("src/main.py", content="import ../../../secret")`.
    *   Expect: `SecurityError` (Content Scanner detects traversal pattern).
*   **T9.02 Binary File Protection**:
    *   *(Moved from T3.08)*
    *   Input: `read_file("assets/image.png")`.
    *   Expect: `Error` (Binary detected). User must use `read_binary` (if avail) or simply list it.
*   **T9.03 Create Directory (Recursive)**:
    *   *(Moved from T3.09)*
    *   Input: `create_directory("src/new/deep/path", exist_ok=True)`.
    *   Expect: Directory structure created. Success.
*   **T9.04 Delete File (Whitelist)**:
    *   *(Moved from T3.10)*
    *   Input: `delete_file("src/temp.py")`.
    *   Expect: Success.
    *   Input: `delete_file("/")`.
    *   Expect: `SecurityError` (Root deletion blocked).
*   **T9.05 File Read (Random Access)**:
    *   *(Moved from T3.11)*
    *   Input: `read_file("large.log", offset=1000, limit=100)`.
    *   Expect: Returns exactly 100 bytes starting at byte 1000. Essential for efficient log analysis without OOM.

