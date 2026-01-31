import pytest
from pathlib import Path
from workflow_core.engine.core.loader import WorkflowLoader

# Point to real config root
CONFIG_ROOT = Path("c:/development/pitbula/quantivista/workflow_core/config")

def test_load_planning_workflow():
    """Verify loading the Planning_Standard workflow."""
    loader = WorkflowLoader(CONFIG_ROOT)
    wf = loader.load_workflow("Planning_Standard")
    assert wf.name == "Planning_Standard"
    assert len(wf.steps) >= 2
    assert wf.steps[0].ref == "Render_Template"

def test_load_feature_impl_workflow():
    """Verify loading the Impl.Feature workflow (aliased)."""
    loader = WorkflowLoader(CONFIG_ROOT)
    wf = loader.load_workflow("Impl.Feature")
    assert wf.name == "Impl.Feature"
    assert len(wf.steps) >= 4
    # Check recursionRef exist
    assert wf.steps[0].type.value == "workflow"
    assert wf.steps[0].ref == "Planning_Standard"

def test_load_non_existent():
    """Verify error for missing workflow."""
    loader = WorkflowLoader(CONFIG_ROOT)
    with pytest.raises(FileNotFoundError):
        loader.load_workflow("Ghost_Flow")
