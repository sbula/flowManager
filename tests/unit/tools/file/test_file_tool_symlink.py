import os
from pathlib import Path

import pytest

from src.flow.tools.base import ToolContext, ToolResult
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


def test_symlink_block_read(file_tool, context, tmp_path):
    """T1.07: Attempt to read a symlink should fail."""
    target_file = tmp_path / "target.txt"
    target_file.write_text("secret", encoding="utf-8")

    link_file = tmp_path / "link.txt"
    try:
        os.symlink(target_file, link_file)
    except OSError:
        # On Windows, symlinks check requires privileges or Dev Mode.
        # If we can't create symlink, skip test or assume environment supports it.
        # In modern Windows 10/11 with Dev Mode, it works.
        # If not, pytest.skip("Symlinks not supported")
        pytest.skip("Symlink creation failed")

    result = file_tool.run({"operation": "read_file", "path": "link.txt"}, context)

    assert result.status == "error"
    assert "Symlinks are not allowed" in result.error["message"]


def test_symlink_block_write(file_tool, context, tmp_path):
    """T1.07: Attempt to write to a symlink should fail."""
    target_file = tmp_path / "target.txt"
    target_file.write_text("original", encoding="utf-8")

    link_file = tmp_path / "link_write.txt"
    try:
        os.symlink(target_file, link_file)
    except OSError:
        pytest.skip("Symlink creation failed")

    result = file_tool.run(
        {"operation": "write_file", "path": "link_write.txt", "content": "hacked"},
        context,
    )

    assert result.status == "error"
    assert "Symlinks are not allowed" in result.error["message"]

    # Verify target was NOT modified
    assert target_file.read_text("utf-8") == "original"
