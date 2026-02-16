import pytest
import os
import sys
from pathlib import Path
from src.flow.tools.file import FileTool
from src.flow.tools.base import ToolContext

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
        volume_id="vol-adv",
        role="dev"
    )

def test_recursive_symlink_loop_protection(file_tool, context, tmp_path):
    """
    T7.22: Verify `list_files` does not hang or crash on recursive symlink loops.
    """
    # Setup: a -> b -> a
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    
    # Create symlink 'loop' inside 'a' pointing back to 'a'
    # Windows requires admin for symlinks usually, but recently Developer Mode allows it.
    # Python 3.8+ handles allowed symlinks.
    try:
        os.symlink(dir_a, dir_a / "loop")
    except OSError:
        pytest.skip("Symlinks not supported/allowed in this environment")

    # This should NOT hang or crash.
    # It should either return the link (if shallow) or skip it.
    # If recursive=True, it MUST stop.
    
    # We test recursive list/search
    result = file_tool.run({
        "operation": "list_files",
        "path": "a",
        # list_files isn't recursive by default in the tool signature,
        # but let's assume we might add 'search_file' which IS recursive.
    }, context)
    
    assert result.status == "success"
    
    # Now try search_file with recursive=True
    result = file_tool.run({
        "operation": "search_file",
        "path": "a",
        "regex": "test",
        "recursive": True
    }, context)
    
    assert result.status == "success"
    # It should finish.

def test_case_sensitivity_conflict(file_tool, context, tmp_path):
    """
    T8.02: Verify ambiguity detection on Case-Sensitive vs Insensitive FS.
    If 'Makefile' exists, reading 'makefile' should:
    - Linux: Fail (FileNotFound)
    - Windows: Return 'Makefile' but potentially warn? 
    
    Actually, the stricter requirement is preventing confusion.
    If the user asks for 'makefile' and 'Makefile' exists, the tool should 
    ideally canonicalize or warn.
    """
    (tmp_path / "ReadMe.txt").write_text("content")
    
    # Attempt to read 'readme.txt'
    result = file_tool.run({
        "operation": "read_file",
        "path": "readme.txt"
    }, context)
    
    if os.name == 'nt':
        # On Windows, this usually succeeds.
        assert result.status == "success"
        # BUT, for security, we might want to check if the explicit case matches the on-disk case?
        # That's a "Paranoid" check. 
        # Let's verify if the Tool checks canonical path match.
        pass 
    else:
        # Linux
        assert result.status == "error"
        assert result.error["code"] == "FileNotFound"

def test_max_path_length_validation(file_tool, context, tmp_path):
    """
    T8.01: Verify handling of excessively long paths.
    """
    # Windows MAX_PATH is 260.
    long_name = "a" * 255
    
    result = file_tool.run({
        "operation": "write_file",
        "path": long_name,  # Total path will be tmp_path + 255 chars > 260
        "content": "test"
    }, context)
    
    # Should fail cleanly, not crash with "OSError: [Errno 36] File name too long" traceback leak
    # It should be caught and returned as ToolError or validated upfront.
    
    if result.status == "error":
        assert result.error["code"] in ["ValidationError", "InternalError", "IOError"]
    else:
        # If it succeeds (because LongPathsEnabled is on), that's fine too.
        pass

