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
