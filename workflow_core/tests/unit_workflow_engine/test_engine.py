# Copyright 2026 Steve Bula @ pitBula
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import json
from pathlib import Path
from workflow_core.engine.core.engine import WorkflowEngine
from workflow_core.engine.schemas.models import StateStatus

# Mock setup
@pytest.fixture
def mock_env(tmp_path):
    config_root = tmp_path / "config"
    state_root = tmp_path / "root"
    config_root.mkdir()
    state_root.mkdir()
    
    # 1. Atoms Registry
    (config_root / "atoms.json").write_text(json.dumps({
        "Atoms": {
            "Render_Template": {"python_module": "workflow_core.engine.atoms.dummy"}
        }
    }))
    
    # 2. Workflow
    workflows_dir = config_root / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "test_flow.json").write_text(json.dumps({
        "name": "TestFlow",
        "steps": [
            {
                "id": "step1",
                "type": "atom",
                "ref": "Render_Template",
                "args": {"foo": "bar"}
            }
        ]
    }))
    
    return config_root, state_root

def test_engine_initialization(mock_env):
    config, state = mock_env
    engine = WorkflowEngine(config, state_root=state)
    assert engine.atoms_registry["Atoms"]["Render_Template"] is not None

def test_run_workflow_execution(mock_env):
    """Test full execution of a Mock Workflow."""
    config, state = mock_env
    engine = WorkflowEngine(config, state_root=state)
    
    # Run
    # AtomExecutor will fall back to "MOCKED" status if module not found 
    # (as implemented in executor.py fallback logic)
    # OR raise ImportError if we didn't implement fallback.
    # In my executor.py I implemented: "if not module_name: return MOCKED"
    # But here I defined "python_module": "..." so it tries to import.
    # I need to create the dummy module or mock the executor.
    # For now, let's create a dummy atom file.
    
    dummy_atom = config.parent / "workflow_core" / "engine" / "atoms"
    dummy_atom.mkdir(parents=True, exist_ok=True)
    (dummy_atom / "dummy.py").write_text("def run(args, context): return {'status': 'DONE', 'message': 'Hello'}")
    
    # We need PYTHONPATH to include tmp_path so importlib finds 'workflow_core'
    # This is hard in a subprocess test.
    # Better to Mock the AtomExecutor.execute_step method.
    
    # MOCKING EXECUTION
    def mock_exec(step, context):
        return {"status": "DONE", "message": "Mock Success"}
        
    engine.executor.execute_step = mock_exec
    
    state_obj = engine.run_workflow("task_mock", "TestFlow")
    
    assert state_obj.task_id == "task_mock"
    assert state_obj.current_step_index == 1
    assert state_obj.steps_history["step1"].status == StateStatus.COMPLETED
