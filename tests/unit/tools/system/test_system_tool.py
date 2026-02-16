import pytest
import subprocess
from unittest.mock import patch
from src.flow.tools.system_tool import SystemTool
from src.flow.tools.base import ToolContext, ToolResult

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

@pytest.fixture
def dev_context():
    return ToolContext(
        service_root="/app",
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="vol-test",
        role="dev"
    )

def test_system_tool_access_denied_dev(system_tool, dev_context):
    """T1.06: Dev cannot access SystemTool."""
    # The ToolExecutor usually checks this, but the tool itself should also enforce or check metadata
    # The spec says "ToolExecutor checks context.role against tool.required_role"
    # So we should verify the tool has the attribute.
    assert system_tool.required_role == "sre"
    
    # If the tool logic itself re-checks (defensive), we test that too
    result = system_tool.run({"operation": "install_package", "package": "curl"}, dev_context)
    assert result.status == "error"
    assert "PermissionDenied" in result.error["code"]

def test_install_package_success(system_tool, sre_context):
    """T1.13: SRE can install packages."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = system_tool.run({
            "operation": "install_package",
            "manager": "apt",
            "package": "curl"
        }, sre_context)
        
        assert result.status == "success"
        args = mock_run.call_args[0][0]
        assert "apt-get" in args
        assert "curl" in args

def test_system_ctl(system_tool, sre_context):
    """T6.07: Verify system_ctl logic."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = system_tool.run({
            "operation": "system_ctl",
            "service": "docker",
            "action": "status"
        }, sre_context)
        
        assert result.status == "success"
        args = mock_run.call_args[0][0]
        assert "systemctl" in args

def test_system_tool_timeout(system_tool, sre_context):
    """T7.14: Verify system tool timeout."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="apt-get", timeout=1)
        result = system_tool.run({
            "operation": "install_package",
            "manager": "apt", 
            "package": "heavy-pkg"
        }, sre_context)
        
        assert result.status == "error"
        assert result.error["code"] == "Timeout"

