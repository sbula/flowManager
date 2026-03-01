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

    def _get_command(self) -> str | None:
        import sys
        from typing import cast

        config = cast(ScriptAtomConfig, self.config)
        script = getattr(config, "script", None)
        if config.command:
            return config.command
        if script:
            return f'python -c "{script}"'
        return None

    def run(self, context: Dict[str, Any]) -> AtomResult:
        import sys

        config = self.config

        command_to_execute = self._get_command()
        if not command_to_execute:
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
                    command_to_execute,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                )

                if sys.platform == "win32":
                    import ctypes

                    try:
                        proc_handle = int(process._handle)  # type: ignore
                        if job:
                            job.assign_process(proc_handle)
                    except Exception as e:
                        process.kill()
                        return AtomResult(
                            AtomStatus.FAILED,
                            f"Failed to attach process to Windows Job Object: {e}",
                        )

                # Read streams with limits (T7.09 Firehose Defense)
                MAX_STREAM_SIZE = 10 * 1024 * 1024  # 10 MB
                import select
                import time

                start_time = time.time()
                totals = [0, 0]  # total_out, total_err

                # Manual poll loop since select.select doesn't work well on Windows pipes
                import threading

                t_out = threading.Thread(
                    target=self._read_stream,
                    args=(
                        process.stdout,
                        f_out,
                        False,
                        process,
                        totals,
                        MAX_STREAM_SIZE,
                    ),
                )
                t_out.daemon = True
                t_err = threading.Thread(
                    target=self._read_stream,
                    args=(
                        process.stderr,
                        f_err,
                        True,
                        process,
                        totals,
                        MAX_STREAM_SIZE,
                    ),
                )
                t_err.daemon = True
                t_out.start()
                t_err.start()

                try:
                    process.wait(timeout=config.timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return AtomResult(
                        status=AtomStatus.FAILED,
                        message=f"Script execution timed out after {config.timeout}s",
                    )

                t_out.join(timeout=1.0)
                t_err.join(timeout=1.0)

                if totals[0] > MAX_STREAM_SIZE or totals[1] > MAX_STREAM_SIZE:
                    return AtomResult(
                        AtomStatus.FAILED, "Stream exceeded limit, process SIGKILLed"
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

    def _read_stream(self, stream, outfile, is_err, process, totals, max_size):
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                idx = 1 if is_err else 0
                totals[idx] += len(chunk)
                if totals[idx] > max_size:
                    process.kill()
                    return
                outfile.write(chunk)
        except Exception:
            pass
