import pytest
from unittest.mock import patch, MagicMock
from src.flow.tools.file_tool import FileTool
from src.flow.tools.base import ToolContext, ToolError

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

def test_edit_file_regex(file_tool, context, tmp_path):
    """T2.05 (Partial): Verify regex replacement."""
    target = tmp_path / "regex.txt"
    target.write_text("v1.0.0\nv2.1.3", encoding="utf-8")
    
    result = file_tool.run({
        "operation": "edit_file",
        "path": "regex.txt",
        "edits": [
            {
                "operation": "replace",
                "match_mode": "regex",
                "spec": r"v(\d+)\.(\d+)\.(\d+)",
                "content": r"Version \1-\2-\3",
                "count": 2
            }
        ]
    }, context)
    
    assert result.status == "success"
    # replacements: v1.0.0 -> Version 1-0-0
    content = target.read_text(encoding="utf-8")
    assert "Version 1-0-0" in content
    assert "Version 2-1-3" in content

def test_lock_manager_pid_check(tmp_path):
    """T2.03: Verify stale lock recovery via PID check."""
    from src.flow.tools.loom.lock_manager import LockManager
    from unittest.mock import patch
    
    manager = LockManager(timeout_seconds=30)
    target = tmp_path / "target.txt"
    target.touch()
    
    # Create a "stale" lock file with a non-existent PID
    # .lock.target.txt.99999
    lock_file = tmp_path / f".lock.target.txt.99999"
    lock_file.touch()
    
    # Mock _process_exists to return False (Dead PID)
    with patch.object(LockManager, "_process_exists", return_value=False) as mock_pid_check:
        with manager.acquire(target):
            # Should succeed by breaking the lock
            assert lock_file.exists() == False # Old lock gone
            # New lock should exist (with MY pid)
            # checking wildcard
            assert len(list(tmp_path.glob(".lock.target.txt.*"))) == 1
    
    mock_pid_check.assert_called_with(99999)

def test_lock_manager_pid_alive_contention(tmp_path):
    """T2.04: Verify active lock contention (PID Alive)."""
    from src.flow.tools.loom.lock_manager import LockManager
    from unittest.mock import patch
    from src.flow.tools.base import ToolError

    manager = LockManager(timeout_seconds=30)
    target = tmp_path / "target.txt"
    target.touch()
    
    # Lock with "Alive" PID
    lock_file = tmp_path / f".lock.target.txt.88888"
    lock_file.touch()
    
    # Mock _process_exists to return True (Alive)
    with patch.object(LockManager, "_process_exists", return_value=True):
        with pytest.raises(ToolError) as exc:
            with manager.acquire(target):
                pass
        
        assert exc.value.code == "ResourceBusy"
        assert lock_file.exists()
