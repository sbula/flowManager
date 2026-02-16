import pytest
import os
from src.flow.tools.file import FileTool
from src.flow.tools.base import ToolContext, ToolResult

@pytest.fixture
def file_tool():
    return FileTool()

@pytest.fixture
def context(tmp_path):
    return ToolContext(
        service_root=str(tmp_path),
        isolation_level="STRICT",
        allowed_commands=[],
        access_token="",
        volume_id="vol-test",
        role="dev"
    )

def test_read_file_success(file_tool, context, tmp_path):
    """T1.02: Verify reading a valid file within scope."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world", encoding="utf-8")
    
    result = file_tool.run({
        "operation": "read_file",
        "path": "test.txt"
    }, context)
    
    assert result.status == "success"
    assert result.data["content"] == "hello world"

def test_read_file_path_traversal(file_tool, context):
    """T1.01: Verify path traversal is blocked."""
    result = file_tool.run({
        "operation": "read_file",
        "path": "../../../etc/passwd"
    }, context)
    
    assert result.status == "error"
    assert "Path traversal detected" in result.error["message"]

def test_write_file_atomic(file_tool, context, tmp_path):
    """T6.18 & T6.23: Verify atomic write."""
    target_file = tmp_path / "atomic.txt"
    
    result = file_tool.run({
        "operation": "write_file",
        "path": "atomic.txt",
        "content": "atomic content"
    }, context)
    
    assert result.status == "success"
    assert target_file.read_text(encoding="utf-8") == "atomic content"
    assert not (tmp_path / "atomic.txt.tmp").exists()

def test_write_file_blocked_pattern(file_tool, context):
    """T1.03: Verify blocked patterns (.env)."""
    result = file_tool.run({
        "operation": "write_file",
        "path": ".env",
        "content": "SECRET=123"
    }, context)
    
    assert result.status == "error"
    assert "Blocked file pattern" in result.error["message"]

def test_list_files(file_tool, context, tmp_path):
    """T3.11: Verify list_files."""
    (tmp_path / "a.txt").touch()
    (tmp_path / "b.py").touch()
    
    result = file_tool.run({
        "operation": "list_files",
        "path": "."
    }, context)
    
    assert result.status == "success"
    assert "b.py" in result.data["files"]

def test_read_ads_blocked_windows(file_tool, context, tmp_path):
    """T1.15: Verify Alternate Data Streams are blocked."""
    if os.name != 'nt':
        return

    # Create a file
    normal_file = tmp_path / "normal.txt"
    normal_file.write_text("content", encoding="utf-8")
    
    # Attempt to access ADS
    result = file_tool.run({
        "operation": "read_file",
        "path": "normal.txt:secret"
    }, context)
    
    # Should fail. Either Validation (invalid path chars) or Security.
    # On Windows, path:stream IS valid path syntax for open(), 
    # but pathlib might interpret it.
    # We want to ensure it's NOT allowed.
    assert result.status == "error"
    # We don't have explicit ADS check yet, so this might fail if code doesn't block it.
    # If it fails, we update FileTool to block ':'.
    assert "Invalid path" in result.error["message"] or "Security" in result.error["code"]
