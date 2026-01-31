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
from workflow_core.engine.atoms import agent

def test_agent_mock_response():
    """Test that agent returns mock response when provided."""
    result = agent.query(
        prompt="Hello", 
        mock_response="I am a Mock"
    )
    assert result == "I am a Mock"

def test_agent_dummy_cleanup():
    """Test that agent strips whitespace."""
    result = agent.query(
        prompt="Hello", 
        mock_response="   Trim Me   "
    )
    assert result == "Trim Me"
