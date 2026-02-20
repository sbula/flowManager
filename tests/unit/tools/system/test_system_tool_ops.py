import pytest
from unittest.mock import patch
from src.flow.tools.system import SystemTool
from src.flow.tools.base import ToolContext

@pytest.fixture
def system_tool():
    return SystemTool()

@pytest.fixture
def sre_context():
    return ToolContext(
        service_root="/app",
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="vol-test",
        role="sre"
    )

def test_verify_binary_success(system_tool, sre_context):
    """Verify verify_binary checks PATH."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/python"
        
        result = system_tool.run({
            "operation": "verify_binary",
            "binary_name": "python"
        }, sre_context)
        
        assert result.status == "success"
        assert result.data["exists"] is True
        assert result.data["path"] == "/usr/bin/python"

def test_verify_binary_missing(system_tool, sre_context):
    """Verify verify_binary handles missing binaries."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        
        result = system_tool.run({
            "operation": "verify_binary",
            "binary_name": "unknown_tool"
        }, sre_context)
        
        assert result.status == "success" # It's a check, not an error
        assert result.data["exists"] is False

def test_migrate_config(system_tool, sre_context):
    """Verify migrate_config runs refactor script."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "done"

        result = system_tool.run({
            "operation": "migrate_config",
            "target_version": "2.0"
        }, sre_context)
        
        assert result.status == "success"
        args = mock_run.call_args[0][0]
        assert "python" in args
        assert "scripts/refactor_git.py" in str(args) # naive check
