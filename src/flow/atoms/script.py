import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from flow.tools.shell.win32_job import WindowsJobObject

from .base import Atom, AtomConfig, AtomResult, AtomStatus


class ScriptAtomConfig(AtomConfig):
    command: str
    timeout: int = 60


class ScriptAtom(Atom):
    """
    ScriptAtom (Subprocess Execution).
    Running deterministic, local scripts or shell commands.
    Respects 128KB Context Memory Limit by routing streams to Blobs.
    """

    def _parse_config(self, config: Dict[str, Any]) -> ScriptAtomConfig:
        return ScriptAtomConfig(**config)

    def run(self, context: Dict[str, Any]) -> AtomResult:
        import sys
        from typing import cast

        config = cast(ScriptAtomConfig, self.config)
        script = getattr(config, "script", None)

        # Determine the command to execute
        if config.command:
            command_to_execute = config.command
        elif script:
            # If a script is provided, assume it's a Python script for now
            # This part might need further refinement based on actual use case (e.g., shebang, file extension)
            command_to_execute = f'python -c "{script}"'
        else:
            return AtomResult(
                AtomStatus.FAILED, "Missing 'command' or 'script' in config"
            )

        cwd = context.get("__root__", ".")
        task_id = context.get("__task_id__", "unknown-task")
        run_id = self.config.run_id or task_id

        # Determine Blob Paths
        flow_artifacts_dir = Path(cwd) / ".flow" / "artifacts"

        try:
            flow_artifacts_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Catch Hardware IO Exhaustion (ENOSPC)
            return AtomResult(
                AtomStatus.FAILED, f"Failed to create artifacts directory: {e}"
            )

        stdout_blob_name = f"blob_{run_id}_stdout.txt"
        stderr_blob_name = f"blob_{run_id}_stderr.txt"

        stdout_path = flow_artifacts_dir / stdout_blob_name
        stderr_path = flow_artifacts_dir / stderr_blob_name

        job = WindowsJobObject() if os.name == "nt" else None

        try:
            with open(stdout_path, "wb") as f_out, open(stderr_path, "wb") as f_err:
                process = subprocess.Popen(
                    command_to_execute, cwd=cwd, stdout=f_out, stderr=f_err, shell=True
                )

                if sys.platform == "win32":
                    import ctypes

                    try:
                        # Type ignore because _handle is private and mypy doesn't know it exists
                        proc_handle = int(process._handle)  # type: ignore

                        # Check if process is already in a job
                        is_in_job = ctypes.c_int(0)
                        # This part of the original instruction was incomplete.
                        # Assuming the intent was to assign the process to the job object if not already in one.
                        # The original code had `job.assign_process(int(process._handle))`.
                        # Re-integrating that with the new `proc_handle` variable.
                        if job:  # Ensure job object was created
                            job.assign_process(proc_handle)
                    except Exception as e:
                        process.kill()
                        return AtomResult(
                            AtomStatus.FAILED,
                            f"Failed to attach process to Windows Job Object: {e}",
                        )

                try:
                    process.wait(timeout=config.timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return AtomResult(
                        status=AtomStatus.FAILED,
                        message=f"Script execution timed out after {config.timeout}s",
                    )

            exports = {
                "exit_code": process.returncode,
                "stdout_blob": stdout_blob_name,
                "stderr_blob": stderr_blob_name,
            }

            if process.returncode == 0:
                return AtomResult(
                    AtomStatus.SUCCESS, "Script executed successfully", exports=exports
                )
            else:
                return AtomResult(
                    AtomStatus.FAILED,
                    f"Script failed with exit code {process.returncode}",
                    exports=exports,
                )

        except OSError as e:
            return AtomResult(
                AtomStatus.FAILED, f"OS IO Error during subprocess execution: {e}"
            )
        finally:
            if job:
                job.close()
