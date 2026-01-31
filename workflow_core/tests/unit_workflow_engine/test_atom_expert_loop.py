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
from unittest.mock import patch, MagicMock
from workflow_core.engine.atoms import expert_loop

@patch("workflow_core.engine.atoms.expert_loop.agent.query")
@patch("workflow_core.engine.atoms.expert_loop.prompt.render_string")
def test_expert_loop_research_mode(mock_render, mock_query):
    """Test standard research loop with aggregation."""
    mock_render.return_value = "Rendered Prompt"
    mock_query.return_value = "Expert Analysis"
    
    experts = ["#Quant", "#Sec"]
    result = expert_loop.run(
        experts=experts,
        mode="research",
        prompt_template="dummy_template",
        context={}
    )
    
    # Assert query called for each expert
    assert mock_query.call_count == 2
    assert result["#Quant"] == "Expert Analysis"
    assert result["#Sec"] == "Expert Analysis"

@patch("workflow_core.engine.atoms.expert_loop.agent.query")
@patch("workflow_core.engine.atoms.expert_loop.prompt.render_string")
def test_expert_loop_review_gate(mock_render, mock_query):
    """Test review mode where it acts as a gate."""
    # Scenario: Quant Passes, Sec Rejects
    mock_query.side_effect = ["[x] Approve", "[ ] Reject: bad"]
    
    experts = ["#Quant", "#Sec"]
    result = expert_loop.run(
        experts=experts,
        mode="review",
        prompt_template="dummy_template",
        context={}
    )
    
    assert result["status"] == "BLOCKED"
    assert result["reviews"]["#Sec"] == "[ ] Reject: bad"
