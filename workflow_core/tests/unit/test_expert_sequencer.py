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
from pathlib import Path
from workflow_core.engine.atoms import expert_sequencer
from workflow_core.engine.atoms.expert_sequencer import run
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_template_factory():
    with patch("workflow_core.engine.atoms.expert_sequencer.TemplateFactory") as mock:
        yield mock

@pytest.fixture
def review_file(tmp_path):
    f = tmp_path / "Review.md"
    f.write_text("# Review Header\n", encoding="utf-8")
    return f

@pytest.fixture
def mock_teams_config():
    """Mock loading of core_teams.json"""
    with patch("workflow_core.engine.atoms.expert_sequencer._load_teams_config") as mock:
        mock.return_value = {
            "ExpertSets": {
                "AlphaSquad": [
                    "Quantitative Trader",
                    "Data Scientist",
                    "ML Engineer", 
                    "Risk Officer"
                ]
            }
        }
        yield mock

@pytest.fixture
def mock_personas_config():
    """Mock loading of expert_personas.json"""
    with patch("workflow_core.engine.atoms.expert_sequencer._load_personas") as mock:
        mock.return_value = {
            "Quantitative Trader": {
                "Focus": "PnL",
                "Checklist": ["Check ROI"]
            },
            "Data Scientist": {
                "Focus": "Data Integrity",
                "Checklist": ["Check Schema"]
            },
            "Security": {
                "Focus": "Sec",
                "Checklist": ["Check Auth"]
            },
            "QA": {
                "Focus": "Quality",
                "Checklist": ["Check Tests"]
            }
        }
        yield mock

def test_sequencer_uses_expert_set(mock_template_factory, review_file, mock_teams_config, mock_personas_config):
    """Test using 'expert_set' arg instead of implicit discovery."""
    
    # Mock Factory to return generic modules (should be filtered/selected by set)
    mock_factory = mock_template_factory.return_value
    # The factory returns ALL possible experts. The sequencer must filter them based on the SET.
    mock_factory.get_active_modules.return_value = [
        {"Type": "Expert", "Role": "Quantitative Trader"},
        {"Type": "Expert", "Role": "Product Owner"}, # Not in AlphaSquad
        {"Type": "Expert", "Role": "Data Scientist"}
    ]

    with patch("workflow_core.engine.atoms.expert_sequencer._inject_expert") as mock_inject:
        result = run(
            args={
                "target_file": str(review_file),
                "expert_set": "AlphaSquad"
            },
            context={}
        )
        
        assert result["status"] == "WAITING"
        # Should inject first from AlphaSquad: Quantitative Trader
        # Note: The base message is generic "Injected First Expert", the role is in instructions
        assert "Injected First Expert" in result["message"]
        assert "Quantitative Trader" in result["message"]
        
        # Verify Product Owner was skipped
        # Logic: required_experts = [QT, DS] (PO filtered out)
        
def test_sequencer_excludes_author(mock_template_factory, review_file, mock_teams_config, mock_personas_config):
    """Test that the author is excluded from the required expert list."""
    
    # Context defines Author as "Quantitative Trader"
    context = {"author_role": "Quantitative Trader"}
    
    mock_factory = mock_template_factory.return_value
    mock_factory.get_active_modules.return_value = [
        {"Type": "Expert", "Role": "Quantitative Trader"},
        {"Type": "Expert", "Role": "Data Scientist"}
    ]

    with patch("workflow_core.engine.atoms.expert_sequencer._inject_expert") as mock_inject:
        result = run(
            args={
                "target_file": str(review_file),
                "expert_set": "AlphaSquad"
            },
            context=context
        )
        
        # QT is author, so should skip to Data Scientist
        assert result["status"] == "WAITING"
        assert "Injected First Expert" in result["message"]
        assert "Data Scientist" in result["message"]

def test_sequencer_fallback_to_factory(mock_template_factory, review_file, mock_personas_config):
    """Test fallback to original behavior if no expert_set provided."""
    mock_factory = mock_template_factory.return_value
    mock_factory.get_active_modules.return_value = [
        {"Type": "Expert", "Role": "Security"},
        {"Type": "Expert", "Role": "QA"}
    ]
    
    with patch("workflow_core.engine.atoms.expert_sequencer._inject_expert") as mock_inject:
        result = run(
            args={"target_file": str(review_file)},
            context={}
        )
        # Fallback uses base_pool keys (Security, QA)
        assert "Injected First Expert" in result["message"]
        assert "Security" in result["message"]
