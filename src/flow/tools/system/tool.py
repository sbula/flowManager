import shutil
import subprocess
from typing import Any, Dict, List, Optional

from flow.tools.base import Tool, ToolContext, ToolError, ToolResult


class SystemTool(Tool):
    name = "system_tool"
    description = "SRE-only system management tools."
    required_role = "sre"
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "install_package",
                    "system_ctl",
                    "verify_binary",
                    "migrate_config",
                ],
            },
            "manager": {"type": "string", "enum": ["apt", "cargo", "npm-g"]},
            "package": {"type": "string"},
            "version": {"type": "string"},
            "service": {"type": "string"},
            "action": {
                "type": "string",
                "enum": ["start", "stop", "restart", "status"],
            },
            "binary_name": {"type": "string"},
        },
        "required": ["operation"],
    }

    def run(self, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        # Double-check role enforcement (Defense in Depth)
        if context.role != self.required_role:
            return ToolResult(
                status="error",
                error={
                    "code": "PermissionDenied",
                    "message": f"Role '{context.role}' cannot access SystemTool",
                },
            )

        operation = args.get("operation")

        try:
            if operation == "install_package":
                return self._install_package(
                    args.get("manager"),
                    args.get("package"),
                    args.get("version"),
                    context,
                )
            elif operation == "system_ctl":
                return self._system_ctl(
                    args.get("service"), args.get("action"), context
                )
            elif operation == "verify_binary":
                return self._verify_binary(args.get("binary_name"))
            elif operation == "migrate_config":
                return self._migrate_config(args.get("target_version"), context)
            else:
                return ToolResult(
                    status="error",
                    error={
                        "code": "UnknownOperation",
                        "message": f"Unknown operation: {operation}",
                    },
                )

        except ToolError as e:
            return ToolResult(status="error", error={"code": e.code, "message": str(e)})
        except Exception as e:
            return ToolResult(
                status="error", error={"code": "InternalError", "message": str(e)}
            )

    def _install_package(
        self,
        manager: Optional[str],
        package: Optional[str],
        version: Optional[str],
        context: ToolContext,
    ) -> ToolResult:
        if not package:
            raise ToolError("Package name required", code="ValidationError")

        if manager == "apt":
            # apt-get install -y package=version
            cmd = ["apt-get", "install", "-y"]
            if version:
                cmd.append(f"{package}={version}")
            else:
                cmd.append(package)
        elif manager == "cargo":
            cmd = ["cargo", "install", package]
            if version:
                cmd.extend(["--version", version])
        elif manager == "npm-g":
            cmd = ["npm", "install", "-g", package]
            if version:
                cmd[-1] = f"{package}@{version}"
        else:
            raise ToolError(f"Unsupported manager: {manager}", code="ValidationError")

        return self._run_command(cmd, context)

    def _system_ctl(
        self, service: Optional[str], action: Optional[str], context: ToolContext
    ) -> ToolResult:
        if not service or not action:
            raise ToolError("Service and action required", code="ValidationError")

        # Whitelist actions
        if action not in ["start", "stop", "restart", "status"]:
            raise ToolError("Invalid action", code="ValidationError")

        cmd = ["sudo", "systemctl", action, service]
        return self._run_command(cmd, context)

    def _verify_binary(self, binary_name: Optional[str] = None) -> ToolResult:
        if not binary_name:
            raise ToolError("Binary name required", code="ValidationError")
        path = shutil.which(binary_name)
        return ToolResult(
            status="success", data={"exists": bool(path), "path": path or ""}
        )

    def _migrate_config(
        self, target_version: Optional[str], context: ToolContext
    ) -> ToolResult:
        if not target_version:
            raise ToolError("Target version required", code="ValidationError")

        # Locate the refactor script
        # Assuming scripts/refactor_git.py exists in project root or similar.
        # We need to construct the absolute path or run via python -m

        script_path = "scripts/refactor_git.py"  # Relative to service root?
        # Test expects: python scripts/refactor_git.py

        cmd = ["python", script_path, "--target", target_version]
        return self._run_command(cmd, context)

    def _run_command(self, cmd: List[str], context: ToolContext) -> ToolResult:
        try:
            # SRE tools run from root or service root?
            # We stick to service_root for consistency unless overridden.
            result = subprocess.run(
                cmd,
                cwd=context.service_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=300,  # SRE tools (e.g. install) might take time
            )
            return ToolResult(status="success", data={"stdout": result.stdout})
        except subprocess.CalledProcessError as e:
            return ToolResult(
                status="error",
                error={
                    "code": "CommandFailed",
                    "message": f"Command failed: {e.returncode}",
                    "details": {"stderr": e.stderr},
                },
            )
        except subprocess.TimeoutExpired as e:
            return ToolResult(
                status="error",
                error={
                    "code": "Timeout",
                    "message": f"Command timed out after {e.timeout}s",
                    "details": {"cmd": e.cmd},
                },
            )
