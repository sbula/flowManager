from unittest.mock import MagicMock, patch

import pytest

from src.flow.tools.base import ToolContext, ToolResult
from src.flow.tools.shell import ShellTool


@pytest.fixture
def shell_tool():
    with patch("src.flow.tools.shell.win32_job.WindowsJobObject"):
        yield ShellTool()


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


def mock_process_factory(stdout="", stderr="", returncode=0):
    process = MagicMock()
    # read() needs to return data once, then empty string (EOF) repeatedly
    process.stdout.read.side_effect = [stdout, ""]
    process.stderr.read.side_effect = [stderr, ""]
    process.poll.return_value = returncode
    process.returncode = returncode
    process._handle = 123
    return process


def test_git_status(shell_tool, context):
    """Verify git_status command."""
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = mock_process_factory(stdout="M file.txt")

        result = shell_tool.run({"operation": "git_status"}, context)

        assert result.status == "success"
        assert "M file.txt" in result.data["stdout"]

        args = mock_popen.call_args[0][0]
        assert "git" in args
        assert "status" in args


def test_git_diff(shell_tool, context):
    """Verify git_diff command."""
    with patch("subprocess.Popen") as mock_popen:
        # Use side_effect to return a NEW process for each call
        # because the read() iterator gets exhausted after one use.
        mock_popen.side_effect = lambda *args, **kwargs: mock_process_factory(
            stdout="diff content"
        )

        # Test unstaged
        shell_tool.run({"operation": "git_diff", "staged": False}, context)
        args_unstaged = mock_popen.call_args[0][0]
        assert "git" in args_unstaged
        assert "diff" in args_unstaged
        assert "--staged" not in args_unstaged

        # Test staged
        shell_tool.run({"operation": "git_diff", "staged": True}, context)
        args_staged = mock_popen.call_args[0][0]
        assert "--staged" in args_staged


def test_git_add(shell_tool, context):
    """Verify git_add command."""
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = mock_process_factory()

        result = shell_tool.run(
            {"operation": "git_add", "files": ["a.txt", "b.txt"]}, context
        )

        assert result.status == "success"

        args = mock_popen.call_args[0][0]
        assert "add" in args
        assert "a.txt" in args
        assert "b.txt" in args


def test_git_commit(shell_tool, context):
    """Verify git_commit command."""
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = mock_process_factory()

        result = shell_tool.run(
            {"operation": "git_commit", "message": "fix: bug"}, context
        )

        assert result.status == "success"

        args = mock_popen.call_args[0][0]
        assert "commit" in args
        assert "-m" in args
        assert "fix: bug" in args
