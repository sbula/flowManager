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

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class StepType(str, Enum):
    ATOM = "atom"
    WORKFLOW = "workflow"


class AtomType(str, Enum):
    RENDER_TEMPLATE = "Render_Template"
    RUN_COMMAND = "Run_Command"
    WAIT_APPROVAL = "Wait_For_Manual_Approval"
    GIT_OPERATION = "Git_Operation"
    CHECK_CONDITION = "Check_Condition"


class WorkflowStep(BaseModel):
    id: str = Field(..., description="Unique ID for this step within the workflow")
    type: StepType
    ref: str = Field(..., description="Reference name of the Atom or Workflow")
    args: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments overrides or context injection"
    )
    export: Optional[Dict[str, str]] = Field(
        default=None, description="Map internal output keys to global context keys"
    )
    instructions: Optional[str] = Field(
        default=None, description="Template for the Mission Brief"
    )
    description: Optional[str] = None


class WorkflowDefinition(BaseModel):
    name: str
    version: str = "1.0"
    steps: List[WorkflowStep]
    gating_policy: Optional[str] = "Sequential"


class StateStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class StepState(BaseModel):
    step_id: str
    status: StateStatus = StateStatus.PENDING
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class WorkflowState(BaseModel):
    task_id: str
    workflow_ref: str
    status: StateStatus = StateStatus.PENDING
    current_step_index: int = 0
    steps_history: Dict[str, StepState] = Field(default_factory=dict)
    context_cache: Dict[str, Any] = Field(default_factory=dict)
