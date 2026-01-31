import pytest
from workflow_core.engine.core.engine import WorkflowEngine
from workflow_core.engine.schemas.models import WorkflowState, WorkflowStep, StepType
from typing import Dict, Any

class MockExecutor:
    """Mock Atom Executor to capture calls"""
    def __init__(self, registry):
        self.registry = registry
        self.last_call = None

    def execute_step(self, step_def: WorkflowStep, context: Dict[str, Any]):
        self.last_call = {
            "step_def": step_def,
            "context": context
        }
        return {"status": "DONE"}

@pytest.fixture
def mock_engine_with_executor(tmp_path):
    """Factory for Engine with mocked executor"""
    # Create valid config root
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "atoms.json").write_text("{}")
    
    engine = WorkflowEngine(config_root)
    engine.executor = MockExecutor({})
    return engine

def test_resolve_instructions_success(mock_engine_with_executor):
    """Test successful resolution of variables in instructions"""
    engine = mock_engine_with_executor
    context = {"feature_name": "Market Price", "file_path": "src/market.py"}
    
    # Raw Instructions with placeholders
    raw_instructions = "Mission: Implement ${feature_name} in ${file_path}."
    
    step_def = WorkflowStep(
        id="test_step",
        ref="Test_Atom",
        type=StepType.ATOM,
        instructions=raw_instructions
    )
    
    # We need to expose the internal _resolve_instructions or verify via execution side-effect
    # For unit testing, let's assume we can call the helper directly if explicit, 
    # OR we verify what gets passed to the executor if we decide executor handles it.
    # Architecture Decision: Engine resolves BEFORE calling executor so the Atom sees clean text.
    
    # Let's test the helper method directly if we make it public-ish or accessible
    resolved = engine._resolve_instructions(step_def.instructions, context)
    
    assert resolved == "Mission: Implement Market Price in src/market.py."

def test_resolve_instructions_missing_var(mock_engine_with_executor):
    """Test handling of missing variables (Should keep original placeholder or warn)"""
    engine = mock_engine_with_executor
    context = {"feature_name": "Market Price"}
    
    raw_instructions = "Mission: Implement ${feature_name} in ${missing_var}."
    
    resolved = engine._resolve_instructions(raw_instructions, context)
    
    # Expectation: Keep ${missing_var} or replace with None/Empty?
    # Logic: Keep placeholder to signal error/missing config to user is usually safer than silent failure.
    assert resolved == "Mission: Implement Market Price in ${missing_var}."

def test_resolve_instructions_no_placeholders(mock_engine_with_executor):
    """Test instructions without placeholders remain unchanged"""
    engine = mock_engine_with_executor
    context = {"foo": "bar"}
    
    raw = "Just do it."
    resolved = engine._resolve_instructions(raw, context)
    
    assert resolved == "Just do it."

def test_resolve_instructions_none(mock_engine_with_executor):
    """Test handling of None instructions"""
    engine = mock_engine_with_executor
    assert engine._resolve_instructions(None, {}) is None
