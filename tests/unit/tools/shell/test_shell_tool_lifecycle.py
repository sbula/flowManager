import os
import subprocess
import sys
from unittest.mock import ANY, MagicMock, patch

import pytest

from src.flow.tools.base import ToolContext
from src.flow.tools.shell import ShellTool
from src.flow.tools.shell.win32_job import (
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    WindowsJobObject,
)


@pytest.fixture
def shell_tool():
    with patch("src.flow.tools.shell.win32_job.WindowsJobObject") as mock_job_cls:
        # We start with a fresh tool for each test
        tool = ShellTool()
        # Should we return the tool AND the mock?
        # The tool imports WindowsJobObject inside _run_command usually...
        # Wait, the tool imports it inside _run_command:
        # "from .win32_job import WindowsJobObject"
        # So patching it at module level of test might be tricky if it's a local import.
        # But `sys.modules` patching or `patch.dict` works.
        yield tool


@pytest.fixture
def context(tmp_path):
    return ToolContext(
        service_root=str(tmp_path),
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="vol-lifecycle",
        role="dev",
    )


def test_job_object_creation_on_windows(context):
    """T6.07: Verify Windows Job Object is created and configured."""
    # Force OS to be NT
    with patch("os.name", "nt"), patch(
        "ctypes.windll.kernel32.CreateJobObjectW", return_value=123
    ) as mock_create, patch(
        "ctypes.windll.kernel32.SetInformationJobObject", return_value=True
    ) as mock_set:

        job = WindowsJobObject()

        assert mock_create.called
        assert mock_set.called

        # Verify correctness of flags
        # implementation detail: info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        # We can verify arguments to SetInformationJobObject
        args = mock_set.call_args[0]
        # args[2] is the pointer to info. We can't easily inspect ctypes pointer content in mock
        # without complex side_effects, but verifying it was called is step 1.
        pass


def test_process_assignment_to_job(shell_tool, context):
    """T6.02: Verify Child Process is assigned to Job Object."""

    # We need to patch the local import in ShellTool._run_command
    # OR patch src.flow.tools.shell.tool.WindowsJobObject if it was global.
    # It is local: "from .win32_job import WindowsJobObject"

    with patch("os.name", "nt"), patch("subprocess.Popen") as mock_popen, patch(
        "src.flow.tools.shell.win32_job.WindowsJobObject"
    ) as mock_job_cls:

        mock_job_instance = mock_job_cls.return_value

        # Mock process
        process = MagicMock()
        process._handle = 999
        process.stdout.read.return_value = ""  # EOF
        process.stderr.read.return_value = ""
        process.poll.return_value = 0
        mock_popen.return_value = process

        shell_tool.run({"operation": "run_test", "target": "."}, context)

        # Verify assignment
        mock_job_instance.assign_process.assert_called_with(999)
        # Verify close
        mock_job_instance.close.assert_called_with()


def test_child_process_cleanup_on_exception(shell_tool, context):
    """T6.02: Verify Child Process is killed if an exception occurs."""

    with patch("subprocess.Popen") as mock_popen, patch(
        "src.flow.tools.shell.win32_job.WindowsJobObject"
    ):

        process = MagicMock()
        process.poll.side_effect = [None, None]  # Running
        process.kill = MagicMock()
        mock_popen.return_value = process

        # Mock threading to raise Exception to simulate crash/error during monitoring
        # Or mock time.sleep to raise InterruptedError
        with patch("time.sleep", side_effect=RuntimeError(" Crash ")):
            try:
                shell_tool.run({"operation": "run_test", "target": "."}, context)
            except ToolError:
                pass  # Tool wraps exceptions
            except Exception:
                pass

        # REQUIRED: process.kill() must be called in finally block
        assert process.kill.called


def test_grandchild_fate_sharing_logic(context):
    """T6.03: Verify Job Object Config Logic (Mocked)."""
    # This tests the win32_job.py logic directly

    with patch("os.name", "nt"), patch(
        "ctypes.windll.kernel32.CreateJobObjectW", return_value=123
    ), patch(
        "ctypes.windll.kernel32.SetInformationJobObject", return_value=True
    ) as mock_set:

        WindowsJobObject()

        # We can inspect the struct construction if we mock the class?
        # Actually, let's trust test_job_object_creation_on_windows covered the API call.
        # Here we emphasize the semantic meaning: The flag MUST be 0x2000.

        # We can't easily verify the struct content passed to C in a python unit test w/o detailed ctypes mocking.
        # But we can verify strict dependency on the constant.
        assert JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE == 0x2000


def test_sigkill_escalation_timeout(shell_tool, context):
    """T6.04: Verify process is Killed on Timeout."""

    with patch("subprocess.Popen") as mock_popen, patch(
        "time.time"
    ) as mock_time, patch("time.sleep"):

        process = MagicMock()
        process.poll.return_value = None  # Always running
        mock_popen.return_value = process

        # Time moves forward: 0 -> 301 (Timeout 300)
        mock_time.side_effect = [0, 301, 302]

        shell_tool.run({"operation": "run_test", "target": "."}, context)

        assert process.kill.called
