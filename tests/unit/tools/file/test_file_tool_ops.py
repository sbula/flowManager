import pytest

from src.flow.tools.base import ToolContext
from src.flow.tools.file import FileTool


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
        role="dev",
    )


def test_create_directory_success(file_tool, context, tmp_path):
    """Verify creating a directory (nested)."""
    result = file_tool.run({"operation": "create_directory", "path": "a/b/c"}, context)

    assert result.status == "success"
    assert (tmp_path / "a/b/c").is_dir()
    assert "Directory created" in result.data["message"]


def test_create_directory_existing(file_tool, context, tmp_path):
    """Verify create_directory is idempotent (exist_ok=True)."""
    (tmp_path / "exist").mkdir()

    result = file_tool.run({"operation": "create_directory", "path": "exist"}, context)

    assert result.status == "success"
    assert (tmp_path / "exist").is_dir()


def test_delete_file_success(file_tool, context, tmp_path):
    """Verify deleting a file."""
    f = tmp_path / "del.txt"
    f.touch()

    result = file_tool.run({"operation": "delete_file", "path": "del.txt"}, context)

    assert result.status == "success"
    assert not f.exists()
    assert "File deleted" in result.data["message"]


def test_delete_file_not_found(file_tool, context):
    """Verify deleting non-existent file expected error."""
    result = file_tool.run({"operation": "delete_file", "path": "ghost.txt"}, context)

    assert result.status == "error"
    assert "FileNotFound" in result.error["code"]


def test_delete_file_is_directory_error(file_tool, context, tmp_path):
    """Verify delete_file cannot delete directories."""
    d = tmp_path / "dir"
    d.mkdir()

    result = file_tool.run({"operation": "delete_file", "path": "dir"}, context)

    assert result.status == "error"
    assert "IsADirectory" in result.error["code"]
    assert d.exists()
