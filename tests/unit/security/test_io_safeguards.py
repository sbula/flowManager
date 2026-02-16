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

def test_read_binary_file_fails(file_tool, context, tmp_path):
    """T7.03: Verify binary file reading is rejected."""
    bin_file = tmp_path / "binary.dat"
    bin_file.write_bytes(b"\x00\xFF\x00\xFF")
    
    result = file_tool.run({
        "operation": "read_file",
        "path": "binary.dat"
    }, context)
    
    assert result.status == "error"
    assert result.error["code"] == "BinaryFile"

def test_read_large_file_fails(file_tool, context, tmp_path):
    """T7.02: Verify file size limits are enforced."""
    large_file = tmp_path / "large.txt"
    # Write 1KB
    large_file.write_text("a" * 1024, encoding="utf-8")
    
    # Limit to 500 bytes
    result = file_tool.run({
        "operation": "read_file",
        "path": "large.txt",
        "max_bytes": 500
    }, context)
    
    assert result.status == "error"
    assert result.error["code"] == "FileTooLarge"

def test_read_utf8_valid(file_tool, context, tmp_path):
    """Verify valid UTF-8 works."""
    valid_file = tmp_path / "utf8.txt"
    valid_file.write_text("Hello World 🌍", encoding="utf-8")
    
    result = file_tool.run({
        "operation": "read_file",
        "path": "utf8.txt"
    }, context)
    
    assert result.status == "success"
    assert result.data["content"] == "Hello World 🌍"

def test_recursive_expansion_dos(file_tool, context, tmp_path):
    """
    T7.13: Verify protection against 'Zip Bomb' like text patterns.
    Actually, FileTool just reads. If the file is 100MB of 'a', it reads it if limit allows.
    The safeguard is 'max_bytes'.
    Let's verify strict default limit if not provided.
    Implementation default is 100KB?
    """
    huge_file = tmp_path / "huge.txt"
    # Create file slightly larger than default 100KB
    size = 100 * 1024 + 1
    with open(huge_file, "wb") as f:
        f.seek(size - 1)
        f.write(b"\0")
        
    result = file_tool.run({
        "operation": "read_file",
        "path": "huge.txt"
        # No max_bytes provided, use default
    }, context)
    
    assert result.status == "error"
    assert result.error["code"] == "FileTooLarge"
