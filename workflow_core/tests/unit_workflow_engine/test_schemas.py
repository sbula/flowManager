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
from pydantic import ValidationError
from workflow_core.engine.schemas.models import WorkflowDefinition, WorkflowStep, StepType

def test_workflow_definition_valid():
    """Test creating a valid workflow definition."""
    data = {
        "name": "TestFlow",
        "steps": [
            {
                "id": "step1",
                "type": "atom",
                "ref": "Render_Template",
                "args": {"target": "foo.md"}
            }
        ]
    }
    wf = WorkflowDefinition(**data)
    assert wf.name == "TestFlow"
    assert len(wf.steps) == 1
    assert wf.steps[0].type == StepType.ATOM

def test_workflow_definition_invalid_type():
    """Test that invalid step types are rejected."""
    data = {
        "name": "InvalidFlow",
        "steps": [
            {
                "id": "step1",
                "type": "magic_spell", # Invalid
                "ref": "Render_Template"
            }
        ]
    }
    with pytest.raises(ValidationError):
        WorkflowDefinition(**data)

def test_workflow_step_missing_ref():
    """Test that missing ref is rejected."""
    data = {
        "id": "step1",
        "type": "atom"
    }
    with pytest.raises(ValidationError):
        WorkflowStep(**data)
