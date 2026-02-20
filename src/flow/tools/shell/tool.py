import subprocess
from typing import Any, Dict, List
from src.flow.tools.base import Tool, ToolContext, ToolResult, ToolError


class ShellTool(Tool):
    name = "shell_tool"
    description = "Safe shell operations (git, dependencies)."
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "install_dependencies", "git_checkout", "git_push",
                    "git_status", "git_diff", "git_add", "git_commit",
                    "run_test", "run_lint"
                ]
            },
            "manager": {"type": "string"},
            "branch": {"type": "string"},
            "create_if_missing": {"type": "boolean"},
            "remote": {"type": "string"},
            "message": {"type": "string"},
            "files": {"type": "array"},
            "target": {"type": "string"},
            "truncation_strategy": {"type": "string"}
        },
        "required": ["operation"]
    }

    MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB Limit

    def run(self, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        operation = args.get("operation")

        try:
            if operation == "install_dependencies":
                return self._install_dependencies(args.get("manager"), context)
            elif operation == "git_checkout":
                return self._git_checkout(
                    args.get("branch"),
                    args.get("create_if_missing", False),
                    context
                )
            elif operation == "git_push":
                return self._git_push(
                    args.get("remote", "origin"),
                    args.get("branch"),
                    context
                )
            elif operation == "git_status":
                return self._run_git(["status"], context)
            elif operation == "git_diff":
                cmd = ["diff"]
                if args.get("staged"):
                    cmd.append("--staged")
                return self._run_git(cmd, context)
            elif operation == "git_add":
                files = args.get("files", [])
                if not files:
                    return ToolResult(status="error", error={
                        "code": "ValidationError",
                        "message": "No files specified"
                    })
                return self._run_git(["add"] + files, context)
            elif operation == "git_commit":
                msg = args.get("message")
                if not msg:
                    return ToolResult(status="error", error={
                        "code": "ValidationError",
                        "message": "Commit message required"
                    })
                return self._run_git(["commit", "-m", msg], context)
            elif operation == "run_test":
                return self._run_test(
                    args.get("target"),
                    args.get("truncation_strategy"),
                    context
                )
            elif operation == "run_lint":
                return self._run_lint(args.get("target"), context)
            else:
                return ToolResult(status="error", error={
                    "code": "UnknownOperation",
                    "message": f"Unknown operation: {operation}"
                })

        except ToolError as e:
            return ToolResult(status="error", error={
                "code": e.code,
                "message": str(e)
            })
        except Exception as e:
            return ToolResult(status="error", error={
                "code": "InternalError",
                "message": str(e)
            })

    def _install_dependencies(self, manager: str,
                              context: ToolContext) -> ToolResult:
        if manager == "npm":
            cmd = ["npm", "ci"]
        elif manager == "poetry":
            cmd = ["poetry", "install"]
        elif manager == "cargo":
            cmd = ["cargo", "build"] # Install dependencies via build
        elif manager == "pip":
            # Block raw pip to force lockfile usage via poetry
            raise ToolError(
                "Must use poetry or pipenv for python dependencies",
                code="PolicyViolation"
            )
        else:
            raise ToolError(f"Unsupported package manager: {manager}",
                            code="ValidationError")

        return self._run_command(cmd, context)

    def _git_checkout(self, branch: str, create: bool,
                      context: ToolContext) -> ToolResult:
        if not branch:
            raise ToolError("Branch name required", code="ValidationError")

        cmd = ["git", "checkout"]
        if create:
            cmd.append("-b")
        cmd.append(branch)

        return self._run_command(cmd, context)

    def _git_push(self, remote: str, branch: str,
                  context: ToolContext) -> ToolResult:
        # RBAC Check
        if context.role != "release_manager":
            raise ToolError("git_push requires 'release_manager' role",
                            code="PermissionDenied")

        cmd = ["git", "push", remote]
        if branch:
            cmd.append(branch)

        return self._run_command(cmd, context)

    def _run_git(self, args: List[str], context: ToolContext) -> ToolResult:
        return self._run_command(["git"] + args, context)

    def _run_test(self, target: str, truncation_strategy: str,
                  context: ToolContext) -> ToolResult:
        # Default to pytest
        cmd = ["pytest"]
        if target:
            # Validate target is within scope? 
            # Pytest handles paths, but checking basic validity is good.
            if target.startswith("/"): # Abs path - ensure scope
                 if not target.startswith(context.service_root):
                     raise ToolError("Test target outside service scope", code="SecurityError")
            cmd.append(target)
        
        # Add flags for CI/Tooling friendly output if needed
        # cmd.extend(["-v"]) 

        return self._run_command(cmd, context)

    def _run_lint(self, target: str, context: ToolContext) -> ToolResult:
        # Default to a script or standard tool. Assuming flake8/mypy or a 'lint' script
        # If 'run_lint' is generic, maybe we check for a 'lint' script in package.json or Makefile?
        # For now, let's assume 'pylint' or check if 'npm run lint' is better?
        # Specification says "Runs linters for the current service".
        # Safe bet: try standard python tools if python, or npm if node. 
        # But to keep it simple and safe: assume 'poe lint' or similar if using poetry,
        # or just fail if not configured. 
        # Let's fallback to 'flake8' for python as a safe default for now.
        
        cmd = ["flake8"]
        if target:
             if target.startswith("/") and not target.startswith(context.service_root):
                 raise ToolError("Lint target outside service scope", code="SecurityError")
             cmd.append(target)
        else:
             cmd.append(".")

        return self._run_command(cmd, context)

    def _run_command(self, cmd: List[str], context: ToolContext) -> ToolResult:
        # Advanced subprocess wrapper with Job Object and Stream Buffering
        import os
        import threading
        
        job = None
        if os.name == 'nt':
            try:
                from .win32_job import WindowsJobObject
                job = WindowsJobObject()
            except (ImportError, Exception):
                pass

        process = None
        stdout_buffer = []
        stderr_buffer = []
        current_out_size = 0
        current_err_size = 0
        
        limit_exceeded = False

        def read_stream(stream, buffer, is_stdout):
            nonlocal current_out_size, current_err_size, limit_exceeded
            try:
                while True:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    
                    chunk_len = len(chunk)
                    
                    if is_stdout:
                        if current_out_size + chunk_len > self.MAX_BUFFER_SIZE:
                            limit_exceeded = True
                            # Truncate and stop
                            remaining = self.MAX_BUFFER_SIZE - current_out_size
                            if remaining > 0:
                                buffer.append(chunk[:remaining])
                            buffer.append("\n[TRUNCATED: Output Limit Exceeded]")
                            # We can't easily kill from thread, so we accept the flag 
                            # and let the main waiter handle it? 
                            # Or just close stream?
                            break
                        current_out_size += chunk_len
                    else:
                        if current_err_size + chunk_len > self.MAX_BUFFER_SIZE:
                             # Stderr buffer limit (separate or shared? Spec implies total?)
                             # Let's apply same limit to stderr for safety
                             remaining = self.MAX_BUFFER_SIZE - current_err_size
                             if remaining > 0:
                                 buffer.append(chunk[:remaining])
                             buffer.append("\n[TRUNCATED]")
                             break
                        current_err_size += chunk_len

                    buffer.append(chunk)
            except Exception:
                pass

        try:
            cwd = context.service_root
            
            # Start process
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8', 
                errors='replace' # Prevent decoding crashes
            )

            # Assign to Job Object immediately
            if job:
                job.assign_process(int(process._handle))

            # Start Reader Threads
            t_out = threading.Thread(target=read_stream, args=(process.stdout, stdout_buffer, True))
            t_err = threading.Thread(target=read_stream, args=(process.stderr, stderr_buffer, False))
            t_out.start()
            t_err.start()

            start_time = os.time.time() if hasattr(os, 'time') else __import__('time').time()
            timeout = 300 
            
            while t_out.is_alive() or t_err.is_alive():
                if limit_exceeded:
                    process.kill()
                    break
                
                if __import__('time').time() - start_time > timeout:
                    process.kill()
                    raise subprocess.TimeoutExpired(cmd, timeout)
                    
                __import__('time').sleep(0.1)
                if process.poll() is not None:
                    # Process finished, wait for threads to drain buffers
                    t_out.join(timeout=1)
                    t_err.join(timeout=1)
                    break

            # Ensure threads join
            t_out.join(timeout=1)
            t_err.join(timeout=1)

            stdout_str = "".join(stdout_buffer)
            stderr_str = "".join(stderr_buffer)

            if limit_exceeded:
                 return ToolResult(status="error", error={
                    "code": "OutputLimitExceeded",
                    "message": f"Output exceeded {self.MAX_BUFFER_SIZE} bytes. Process terminated.",
                    "details": {"stdout": stdout_str, "stderr": stderr_str}
                })

            if process.returncode != 0:
                 return ToolResult(status="error", error={
                    "code": "CommandFailed",
                    "message": f"Command failed: {process.returncode}",
                    "details": {"stdout": stdout_str, "stderr": stderr_str}
                })

            return ToolResult(status="success", data={
                "stdout": stdout_str,
                "stderr": stderr_str
            })

        except subprocess.TimeoutExpired as e:
            return ToolResult(status="error", error={
                "code": "Timeout",
                "message": f"Command timed out after {e.timeout}s",
                 # Grab whatever we have so far
                "details": {"cmd": e.cmd, "stdout": "".join(stdout_buffer)}
            })
        except Exception as e:
             return ToolResult(status="error", error={
                "code": "InternalError",
                "message": f"Execution failed: {str(e)}"
            })
        finally:
            if job:
                job.close()
            if process and process.poll() is None:
                # Ensure cleanup if we exited via exception
                process.kill()
