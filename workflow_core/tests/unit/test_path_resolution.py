import pytest
from pathlib import Path
from unittest.mock import MagicMock
from workflow_core.core.context.context_manager import ContextManager
from workflow_core.core.context.models import Task, StatusFile
from workflow_core.infrastructure.config.loader import FlowConfig

@pytest.fixture
def mock_env(tmp_path):
    """
    Sets up a Phase 5 directory structure mock.
    """
    phase5 = tmp_path / "phase5"
    phase5.mkdir()
    
    # Status File
    status_file = phase5 / "status.md"
    status_file.touch()
    
    # Task Directories
    (phase5 / "3_Refactor_Market_Price_Service").mkdir()
    (phase5 / "4_Trading_Signal").mkdir()
    
    return {
        "root": tmp_path,
        "phase5": phase5,
        "status_file": status_file
    }

@pytest.fixture
def context_manager(mock_env):
    config = MagicMock(spec=FlowConfig)
    config.root = mock_env["root"]
    # We mock reader because ContextManager calls reader.parse() in get_current_context
    # But for _resolve_artifact_dir, we can just call it directly if it was public/isolated?
    # It is internal, but we can test it.
    reader = MagicMock()
    return ContextManager(config=config, reader=reader)

def test_resolve_root_match(context_manager, mock_env):
    """Test resolving a task that maps to a directory."""
    task = Task(id="3.1.2", name="Some Task", mark="/")
    
    resolved = context_manager._resolve_artifact_dir(mock_env["status_file"], task)
    
    expected = mock_env["phase5"] / "3_Refactor_Market_Price_Service"
    assert resolved == expected

def test_resolve_nested_match(context_manager, mock_env):
    """Test resolving a deeply nested task."""
    task = Task(id="3.5.1", name="Deep Task", mark="/")
    
    resolved = context_manager._resolve_artifact_dir(mock_env["status_file"], task)
    
    expected = mock_env["phase5"] / "3_Refactor_Market_Price_Service"
    assert resolved == expected

def test_resolve_fallback(context_manager, mock_env):
    """Test fallback when no directory matches."""
    task = Task(id="1.1", name="Ramp Up", mark="/")
    # No "1_..." directory created in fixture
    
    resolved = context_manager._resolve_artifact_dir(mock_env["status_file"], task)
    
    # Should fall back to phase5 root
    expected = mock_env["phase5"]
    assert resolved == expected

def test_resolve_exact_root_task(context_manager, mock_env):
    """Test resolving the root task itself (ID '4')."""
    task = Task(id="4", name="Trading Signal", mark="/")
    
    resolved = context_manager._resolve_artifact_dir(mock_env["status_file"], task)
    
    expected = mock_env["phase5"] / "4_Trading_Signal"
    assert resolved == expected

def test_resolve_invalid_id(context_manager, mock_env):
    """Test robustness against weird IDs."""
    task = Task(id="invalid", name="?", mark="/")
    # "invalid" split('.') -> ["invalid"]
    # No "invalid_*" dir -> Fallback
    
    resolved = context_manager._resolve_artifact_dir(mock_env["status_file"], task)
    assert resolved == mock_env["phase5"]
