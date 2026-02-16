import pytest
from src.flow.tools.file_tool import FileTool
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
        volume_id="vol-test",
        role="dev"
    )

def test_search_file_single(file_tool, context, tmp_path):
    """Verify search in single file."""
    f = tmp_path / "test.txt"
    f.write_text("hello world\npython code\nhello again", encoding="utf-8")
    
    result = file_tool.run({
        "operation": "search_file",
        "path": "test.txt",
        "regex": "hello"
    }, context)
    
    assert result.status == "success"
    matches = result.data["matches"]
    assert len(matches) == 2
    assert matches[0]["line"] == 1
    assert matches[1]["line"] == 3

def test_search_file_directory_recursive(file_tool, context, tmp_path):
    """Verify recursive search."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("def foo(): pass", encoding="utf-8")
    (tmp_path / "src/b.py").write_text("def bar(): pass", encoding="utf-8")
    
    result = file_tool.run({
        "operation": "search_file",
        "path": "src",
        "regex": "def",
        "recursive": True
    }, context)
    
    assert result.status == "success"
    matches = result.data["matches"]
    assert len(matches) == 2

def test_count_matches(file_tool, context, tmp_path):
    """Verify counting matches."""
    f = tmp_path / "count.txt"
    f.write_text("a\na\nb\na", encoding="utf-8")
    
    result = file_tool.run({
        "operation": "count_matches",
        "path": "count.txt",
        "regex": "a"
    }, context)
    
    assert result.status == "success"
    assert result.data["count"] == 3

def test_search_invalid_regex(file_tool, context, tmp_path):
    """Verify regex validation."""
    f = tmp_path / "test.txt"
    f.touch()
    
    result = file_tool.run({
        "operation": "search_file",
        "path": "test.txt",
        "regex": "[" # Invalid regex
    }, context)
    
    assert result.status == "error"
    assert "Invalid regex" in result.error["message"]
