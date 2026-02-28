import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from flow.tools.base import Tool, ToolContext, ToolError, ToolResult

logger = logging.getLogger(__name__)


class FileTool(Tool):
    name = "file_tool"
    description = "Safe filesystem interactions (read, write, list)."
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "read_file",
                    "write_file",
                    "list_files",
                    "delete_file",
                    "create_directory",
                    "edit_file",
                    "search_file",
                    "count_matches",
                ],
            },
            "path": {"type": "string"},
            "content": {"type": "string"},
            "max_bytes": {"type": "integer"},
            "edits": {"type": "array"},
            "regex": {"type": "string"},
            "recursive": {"type": "boolean"},
        },
        "required": ["operation", "path"],
    }

    BLOCKED_PATTERNS = [".env", "secrets/", ".git/", "node_modules/"]

    def run(self, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        operation = args.get("operation")
        path_str = args.get("path")

        if not path_str:
            return ToolResult(
                status="error",
                error={"code": "ValidationError", "message": "Path cannot be empty"},
            )

        try:
            safe_path = self._validate_path(path_str, context)

            # recursive defaults to False for safety unless explicit
            recursive = args.get("recursive", False)

            if operation == "read_file":
                return self._read_file(safe_path, args.get("max_bytes", 100 * 1024))
            elif operation == "write_file":
                return self._write_file(safe_path, args.get("content", ""))
            elif operation == "list_files":
                return self._list_files(safe_path)
            elif operation == "delete_file":
                return self._delete_file(safe_path)
            elif operation == "create_directory":
                return self._create_directory(safe_path)
            elif operation == "edit_file":
                return self._edit_file(safe_path, args.get("edits", []))
            elif operation == "search_file":
                return self._search_file(safe_path, args.get("regex"), recursive)
            elif operation == "count_matches":
                return self._count_matches(safe_path, args.get("regex"), recursive)
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
        except OSError as e:
            # Handle Path Too Long specifically
            # Windows: 206 (Filename too long) or ?
            # Linux: 36 (ENAMETOOLONG)
            if e.errno in [36, 63, 206]:  # Common ENAMETOOLONG codes
                return ToolResult(
                    status="error",
                    error={
                        "code": "ValidationError",
                        "message": f"Path too long: {e.strerror}",
                    },
                )
            # Fallback for other IO Errors
            return ToolResult(
                status="error", error={"code": "IOError", "message": str(e)}
            )
        except Exception as e:
            return ToolResult(
                status="error", error={"code": "InternalError", "message": str(e)}
            )

    def _edit_file(self, path: Path, edits: List[Dict[str, Any]]) -> ToolResult:
        if not path.exists():
            return ToolResult(
                status="error",
                error={"code": "FileNotFound", "message": "File not found"},
            )

        # Advanced Loom Integration
        try:
            from .loom.lock_manager import LockManager
            from .loom.patch_applicator import PatchApplicator

            locker = LockManager()
            patcher = PatchApplicator()

            with locker.acquire(path):
                # 1. Read
                original_content = path.read_text(encoding="utf-8")

                # 2. Patch
                try:
                    new_content = patcher.apply(original_content, edits)
                except ToolError as e:
                    return ToolResult(
                        status="error", error={"code": e.code, "message": str(e)}
                    )

                # 3. Write (Atomic)
                if new_content != original_content:
                    self._write_file(path, new_content)
                    return ToolResult(
                        status="success", data={"message": "File edited successfully"}
                    )
                else:
                    return ToolResult(
                        status="success", data={"message": "No changes made"}
                    )

        except ToolError as e:
            return ToolResult(status="error", error={"code": e.code, "message": str(e)})
        except Exception as e:
            return ToolResult(
                status="error",
                error={"code": "InternalError", "message": f"Edit failed: {e}"},
            )

    def _validate_path(self, path_str: str, context: ToolContext) -> Path:
        # Resolve absolute path
        base_path = Path(context.service_root).resolve()
        try:
            # Construct target path
            # We must be careful about symlinks.
            target_path = (base_path / path_str).resolve()

            # Explicitly block operating ON a symlink (if it exists)
            # This prevents specific attack vectors where an agent
            # is tricked into overwriting a link.
            check_path = base_path / path_str
            if check_path.is_symlink():
                raise ToolError(
                    f"Symlinks are not allowed: {path_str}", code="SecurityError"
                )

            # Block Alternate Data Streams (ADS) on Windows
            # A valid absolute path on Windows has at most 1 colon (drive letter).
            # Any more implies a stream.
            if os.name == "nt" and str(target_path).count(":") > 1:
                raise ToolError(
                    f"Alternate Data Streams are not allowed: {path_str}",
                    code="SecurityError",
                )

        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"Invalid path: {e}", code="ValidationError")

        # 1. Scope Check
        # Check if target_path is within base_path
        # We assume context.service_root is the jail.
        if not str(target_path).startswith(str(base_path)):
            # Special case: Shared contracts might be allowed
            raise ToolError(
                f"Path traversal detected: {path_str} is outside service root",
                code="SecurityError",
            )

        # 2. Blocked Pattern Check
        # Check against BLOCKED_PATTERNS
        rel_path = str(target_path.relative_to(base_path)).replace("\\", "/")
        norm_path = rel_path.lower() if os.name == "nt" else rel_path

        for pattern in self.BLOCKED_PATTERNS:
            p = pattern.lower() if os.name == "nt" else pattern

            if p in norm_path or (p.endswith("/") and p[:-1] in norm_path.split("/")):
                raise ToolError(
                    f"Blocked file pattern: {path_str}", code="SecurityError"
                )

        return target_path

    def _read_file(self, path: Path, max_bytes: int) -> ToolResult:
        if not path.exists():
            return ToolResult(
                status="error",
                error={
                    "code": "FileNotFound",
                    "message": f"File not found: {path.name}",
                },
            )

        if path.stat().st_size > max_bytes:
            return ToolResult(
                status="error",
                error={
                    "code": "FileTooLarge",
                    "message": f"File exceeds max_bytes ({max_bytes})",
                },
            )

        try:
            content = path.read_text(encoding="utf-8")
            return ToolResult(status="success", data={"content": content})
        except UnicodeDecodeError:
            return ToolResult(
                status="error",
                error={"code": "BinaryFile", "message": "File is not valid UTF-8"},
            )

    def _write_file(self, path: Path, content: str) -> ToolResult:
        # Atomic Write Pattern
        tmp_path = path.with_suffix(f".tmp.{uuid.uuid4()}")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(content, encoding="utf-8")

            # fsync (simplistic version)

            # Atomic replacement
            os.replace(tmp_path, path)
            return ToolResult(
                status="success", data={"path": str(path), "size": len(content)}
            )
        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise ToolError(f"Write failed: {e}", code="IOError")

    def _list_files(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult(
                status="error",
                error={"code": "FileNotFound", "message": "Directory not found"},
            )

        if not path.is_dir():
            return ToolResult(
                status="error",
                error={"code": "NotADirectory", "message": "Path is not a directory"},
            )

        files = [p.name for p in path.iterdir()]
        return ToolResult(status="success", data={"files": files})

    def _delete_file(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult(
                status="error",
                error={"code": "FileNotFound", "message": "File not found"},
            )

        if path.is_dir():
            return ToolResult(
                status="error",
                error={
                    "code": "IsADirectory",
                    "message": "Use delete_directory for directories",
                },
            )

        path.unlink()
        return ToolResult(status="success", data={"message": "File deleted"})

    def _create_directory(self, path: Path) -> ToolResult:
        path.mkdir(parents=True, exist_ok=True)
        return ToolResult(status="success", data={"message": "Directory created"})

    def _search_file(
        self, path: Path, regex: Optional[str] = None, recursive: bool = False
    ) -> ToolResult:
        if not regex:
            raise ToolError("Regex required for search", code="ValidationError")

        try:
            import re

            pattern = re.compile(regex, re.MULTILINE)
        except re.error as e:
            raise ToolError(f"Invalid regex: {e}", code="ValidationError")

        matches = []
        files_to_search = []

        # Assuming file_path is already validated and converted to Path by the public method

        if path.is_file():
            files_to_search.append(path)
        elif path.is_dir():
            if recursive:
                files_to_search.extend([p for p in path.rglob("*") if p.is_file()])
            else:
                files_to_search.extend([p for p in path.iterdir() if p.is_file()])
        else:
            return ToolResult(
                status="error",
                error={"code": "FileNotFound", "message": "Path not found"},
            )

        for f in files_to_search:
            try:
                content = f.read_text(encoding="utf-8")
                # Find matches with line numbers
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern.search(line):
                        matches.append(
                            {"file": f.name, "line": i, "content": line.strip()}
                        )
            except (UnicodeDecodeError, OSError):
                continue  # Skip binary/unreadable

        return ToolResult(status="success", data={"matches": matches})

    def _count_matches(
        self, path: Path, regex: Optional[str] = None, recursive: bool = False
    ) -> ToolResult:
        if not regex:
            raise ToolError("Regex required for count", code="ValidationError")

        # Reuse search logic? Or optimized?
        # Search returns snippet list, which can be huge.
        # Count should just return number.

        try:
            import re

            pattern = re.compile(regex, re.MULTILINE)
        except re.error as e:
            raise ToolError(f"Invalid regex: {e}", code="ValidationError")

        count = 0
        files_to_search = []

        if path.is_file():
            files_to_search.append(path)
        elif path.is_dir():
            if recursive:
                files_to_search.extend([p for p in path.rglob("*") if p.is_file()])
            else:
                files_to_search.extend([p for p in path.iterdir() if p.is_file()])
        else:
            return ToolResult(
                status="error",
                error={"code": "FileNotFound", "message": "Path not found"},
            )

        for f in files_to_search:
            try:
                content = f.read_text(encoding="utf-8")
                count += len(pattern.findall(content))
            except (UnicodeDecodeError, OSError):
                continue

        return ToolResult(status="success", data={"count": count})
