import subprocess
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.flow.tools.base import ToolContext
from src.flow.tools.shell import ShellTool


@pytest.fixture
def mock_job_object():
    with patch("src.flow.tools.shell.win32_job.WindowsJobObject") as mock:
        yield mock


@pytest.fixture
def shell_tool(mock_job_object):
    # Reduce buffer size for testing to avoid allocating 10MB in tests
    tool = ShellTool()
    tool.MAX_BUFFER_SIZE = 1024  # 1KB limit for testing
    return tool


@pytest.fixture
def context(tmp_path):
    return ToolContext(
        service_root=str(tmp_path),
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="vol-test",
        role="dev",
    )


def test_streaming_output_limit_exceeded(shell_tool, context):
    """T7.19: Verify process is killed when output exceeds buffer."""

    # Mock subprocess.Popen
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process._handle = 123
        mock_process.returncode = None
        mock_process.poll.return_value = None  # Running initially

        # Simulate infinite stream
        def infinite_stream(size):
            yield "a" * size
            yield "b" * size

        # Configure the mock to return data when read
        # We need a way to simulate threaded reading from the mock
        # Real file objects block or return empty bytes.
        # Using a real subprocess might be safer for integration tests,
        # but for unit tests we can use a custom simpler mock for read.

        # A simple fake stream
        class FakeStream:
            def __init__(self):
                self.data = "x" * 2000  # 2KB > 1KB limit
                self.cursor = 0

            def read(self, size):
                if self.cursor >= len(self.data):
                    return ""
                chunk = self.data[self.cursor : self.cursor + size]
                self.cursor += len(chunk)
                return chunk

        mock_process.stdout = FakeStream()
        mock_process.stderr = FakeStream()

        mock_popen.return_value = mock_process

        # We also need to loop mock_process.poll() to eventually return returncode
        # The ShellTool loop checks poll()
        # We can make poll() return None a few times then 0?
        # BUT, we expect the tool to CALL kill() because limit exceeded.

        mock_process.kill.side_effect = lambda: setattr(mock_process, "returncode", -9)

        result = shell_tool.run(
            {"operation": "install_dependencies", "manager": "npm"},  # Any valid op
            context,
        )

        assert result.status == "error"
        assert result.error["code"] == "OutputLimitExceeded"
        assert "Process terminated" in result.error["message"]
        assert mock_process.kill.called


def test_run_test_command_structure(shell_tool, context):
    """Verify run_test constructs correct command."""
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout.read.return_value = ""  # EOF
        mock_process.stderr.read.return_value = ""
        mock_process.poll.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        shell_tool.run(
            {"operation": "run_test", "target": "tests/unit/test_foo.py"}, context
        )

        args = mock_popen.call_args[0][0]
        assert args[0] == "pytest"
        assert args[1] == "tests/unit/test_foo.py"


def test_run_lint_command_structure(shell_tool, context):
    """Verify run_lint constructs correct command."""
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout.read.return_value = ""
        mock_process.stderr.read.return_value = ""
        mock_process.poll.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        shell_tool.run({"operation": "run_lint", "target": "."}, context)

        args = mock_popen.call_args[0][0]
        assert args[0] == "flake8"
        assert args[1] == "."


def test_output_capture_success(shell_tool, context):
    """Verify normal output capture."""
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()

        # Fake streams
        class FiniteStream:
            def __init__(self, content):
                self.content = content
                self.read_done = False

            def read(self, size):
                if self.read_done:
                    return ""
                self.read_done = True
                return self.content

        mock_process.stdout = FiniteStream("hello stdout")
        mock_process.stderr = FiniteStream("hello stderr")
        mock_process.poll.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        result = shell_tool.run({"operation": "git_status"}, context)

        assert result.status == "success"
        assert result.data["stdout"] == "hello stdout"
        assert result.data["stderr"] == "hello stderr"
