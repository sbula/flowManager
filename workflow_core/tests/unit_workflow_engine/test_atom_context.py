import pytest
from pathlib import Path
from workflow_core.engine.atoms import context

@pytest.fixture
def mock_workspace(tmp_path):
    # Create a structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("main", encoding="utf-8")
    (tmp_path / "src" / "utils.py").write_text("utils", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text("readme", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cache.pyc").write_text("binary", encoding="utf-8")
    return tmp_path

def test_slice_include_only(mock_workspace):
    """Test including specific patterns."""
    result = context.gather(root=mock_workspace, includes=["src/*.py"])
    assert "src/main.py" in result
    assert "src/utils.py" in result
    assert "docs/readme.md" not in result

def test_slice_exclude(mock_workspace):
    """Test excluding patterns."""
    result = context.gather(root=mock_workspace, includes=["**/*"], excludes=["__pycache__/*"])
    # The result keys are relative paths usually
    keys = result.keys()
    assert any("main.py" in k for k in keys)
    assert not any("cache.pyc" in k for k in keys)

def test_slice_content_read(mock_workspace):
    """Test content reading."""
    result = context.gather(root=mock_workspace, includes=["docs/readme.md"])
    # Adjust key expectation based on implementation (relative path usually best)
    # Let's assume keys are relative paths to root string
    assert result.get("docs/readme.md") == "readme"
