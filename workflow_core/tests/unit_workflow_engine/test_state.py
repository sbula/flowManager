import pytest
from pathlib import Path
from workflow_core.engine.core.state import PersistenceManager
from workflow_core.engine.schemas.models import WorkflowState

@pytest.fixture
def temp_state_dir(tmp_path):
    return tmp_path

def test_save_and_load(temp_state_dir):
    """Test saving state and loading it back."""
    pm = PersistenceManager(temp_state_dir)
    
    state = WorkflowState(
        task_id="1.2.3",
        workflow_ref="TestFlow",
        current_step_index=5
    )
    
    pm.save_state(state)
    
    loaded = pm.load_state("1.2.3")
    assert loaded is not None
    assert loaded.task_id == "1.2.3"
    assert loaded.current_step_index == 5
    assert loaded.workflow_ref == "TestFlow"

def test_load_non_existent(temp_state_dir):
    """Test loading missing state returns None."""
    pm = PersistenceManager(temp_state_dir)
    loaded = pm.load_state("9.9.9")
    assert loaded is None

def test_corrupt_state_raises(temp_state_dir):
    """Test that corrupt JSON raises ValueError."""
    pm = PersistenceManager(temp_state_dir)
    
    # Manually write bad JSON
    bad_file = temp_state_dir / ".flow_state" / "bad.state.json"
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text("{ NOT JSON }")
    
    with pytest.raises(ValueError):
        pm.load_state("bad")
