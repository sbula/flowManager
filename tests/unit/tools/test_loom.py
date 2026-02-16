import pytest
from src.flow.tools.file_tool import FileTool
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

def test_edit_file_replace_exact(file_tool, context, tmp_path):
    """T2.01: Simple replacement with count=1."""
    target = tmp_path / "code.py"
    target.write_text("a = 1\nb = 2\nc = 3", encoding="utf-8")
    
    result = file_tool.run({
        "operation": "edit_file",
        "path": "code.py",
        "edits": [
            {
                "operation": "replace",
                "match_mode": "exact",
                "spec": "b = 2",
                "content": "b = 20",
                "count": 1
            }
        ]
    }, context)
    
    assert result.status == "success"
    assert target.read_text(encoding="utf-8") == "a = 1\nb = 20\nc = 3"

def test_edit_file_count_mismatch(file_tool, context, tmp_path):
    """T2.02: Count mismatch error."""
    target = tmp_path / "code.py"
    target.write_text("x = 1\nx = 1", encoding="utf-8")
    
    result = file_tool.run({
        "operation": "edit_file",
        "path": "code.py",
        "edits": [
            {
                "operation": "replace",
                "spec": "x = 1",
                "content": "y = 2",
                "count": 1 # Expected 1, found 2
            }
        ]
    }, context)
    
    assert result.status == "error"
    assert "StartLine mismatch" in result.error["message"] or "Match count mismatch" in result.error["message"]
    # Verify file is unchanged
    assert target.read_text(encoding="utf-8") == "x = 1\nx = 1"

def test_edit_file_idempotency(file_tool, context, tmp_path):
    """T2.08: Idempotency (Already applied)."""
    target = tmp_path / "code.py"
    target.write_text("new_code", encoding="utf-8")
    
    result = file_tool.run({
        "operation": "edit_file",
        "path": "code.py",
        "edits": [
            {
                "operation": "replace",
                "spec": "old_code",
                "content": "new_code"
            }
        ]
    }, context)
    
    # Use allow info if supported, or error if strict. Spec says T2.08: Success (Idempotent No-Op)
    # But ONLY if "new_code" is found? Or simply if "old_code" is not found?
    # Idempotency check: "old_code" not found, but "new_code" is present.
    # Should succeed with no changes.
    
    result = file_tool.run({
        "operation": "edit_file",
        "path": "code.py",
        "edits": [
            {
                "operation": "replace",
                "spec": "old_code",
                "content": "new_code"
            }
        ]
    }, context)
    
    assert result.status == "success"
    assert "No changes made" in result.data["message"]
    assert target.read_text(encoding="utf-8") == "new_code" 
