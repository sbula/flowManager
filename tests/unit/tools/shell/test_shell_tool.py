import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.flow.tools.base import ToolContext, ToolResult
from src.flow.tools.shell import ShellTool


@pytest.fixture
def mock_job_object():
    with patch("src.flow.tools.shell.win32_job.WindowsJobObject") as mock:
        yield mock


@pytest.fixture
def shell_tool(mock_job_object):
    return ShellTool()


@pytest.fixture
def context():
    return ToolContext(
        service_root="/app/services/trade-engine",
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="vol-test",
        role="dev",
    )


@pytest.fixture
def release_manager_context():
    return ToolContext(
        service_root="/app",
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="vol-test",
        role="release_manager",
    )


class MockStream:
    def __init__(self, content=""):
        self.content = content
        self.read_done = False

    def read(self, size):
        if self.read_done:
            return ""
        self.read_done = True
        return self.content


def mock_process_factory(stdout="stdout", stderr="stderr", returncode=0):
    process = MagicMock()
    process.stdout = MockStream(stdout)
    process.stderr = MockStream(stderr)
    process.returncode = returncode
    process.poll.return_value = returncode
    process._handle = 123
    return process


def test_install_dependencies_npm_ci_allow(shell_tool, context):
    """T3.01: Allow npm ci."""
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = mock_process_factory()

        result = shell_tool.run(
            {"operation": "install_dependencies", "manager": "npm"}, context
        )

        assert result.status == "success"
        # Verify npm ci was called
        mock_popen.assert_called()
        args = mock_popen.call_args[0][0]
        assert "ci" in args
        assert "install" not in args


def test_install_dependencies_block_pip(shell_tool, context):
    """T3.02: Block generic pip."""
    result = shell_tool.run(
        {"operation": "install_dependencies", "manager": "pip"}, context
    )

    assert result.status == "error"
    assert "Must use poetry" in result.error["message"]


def test_git_checkout_new_branch(shell_tool, context):
    """T3.04: Git checkout with create."""
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = mock_process_factory()

        result = shell_tool.run(
            {
                "operation": "git_checkout",
                "branch": "feature/test",
                "create_if_missing": True,
            },
            context,
        )

        assert result.status == "success"
        args = mock_popen.call_args[0][0]
        assert "checkout" in args
        assert "-b" in args


def test_git_push_rbac_denial(shell_tool, context):
    """T1.04: Dev cannot push."""
    result = shell_tool.run(
        {"operation": "git_push", "remote": "origin", "branch": "master"}, context
    )

    assert result.status == "error"
    assert "PermissionDenied" in result.error["code"]


def test_git_push_rbac_allow(shell_tool, release_manager_context):
    """T1.05: Release Manager can push."""
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = mock_process_factory()

        result = shell_tool.run(
            {"operation": "git_push", "remote": "origin", "branch": "master"},
            release_manager_context,
        )

        assert result.status == "success"


def test_run_command_timeout(shell_tool, context):
    """T7.14: Verify command timeout."""
    # Retry with Thread Mocking approach which is cleaner for white-box testing the loop
    with patch("subprocess.Popen") as mock_popen, patch(
        "threading.Thread"
    ) as mock_thread_cls, patch("time.time") as mock_time, patch("time.sleep"):

        # Process setup
        process = MagicMock()
        process.poll.return_value = None
        process._handle = 123
        mock_popen.return_value = process

        # Thread setup
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread
        # Sequence: Loop runs while threads alive.
        # Check 1: Alive. Time = 0.
        # Check 2: Alive. Time = 301. -> Timeout!
        mock_thread.is_alive.return_value = True

        # Time setup: Start=100. Check1=101. Check2=500.
        mock_time.side_effect = [100.0, 101.0, 500.0]

        # Run
        # We assume cmd="sleep 100" or similar
        args = {
            "operation": "install_dependencies",  # uses run_command
            "manager": "npm",  # runs npm ci
        }

        # We expect it to catch TimeoutExpired and return ErrorResult
        result = shell_tool.run(args, context)

        assert result.status == "error"
        assert result.error["code"] == "Timeout"
        # Verify process killed
        process.kill.assert_called()
