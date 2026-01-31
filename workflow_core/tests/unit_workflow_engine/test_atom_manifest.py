import pytest
from pathlib import Path
from workflow_core.engine.atoms import manifest

@pytest.fixture
def mock_status_file(tmp_path):
    f = tmp_path / "status.md"
    f.write_text("""# Feature: OANDA Connector
## Requirements
- Low Latency
- Strict Types

## Task List
- [x] 1.1. Research
- [ ] 1.2. Plan
- [ ] 1.3. Implement
""", encoding="utf-8")
    return f

def test_parse_feature_info(mock_status_file):
    """Test extracting feature name and strict requirements."""
    result = manifest.parse(mock_status_file)
    assert result["feature"] == "OANDA Connector"
    assert "Strict Types" in result["requirements"]

def test_find_active_task(mock_status_file):
    """Test finding the first pending task."""
    result = manifest.parse(mock_status_file)
    assert result["active_task"]["id"] == "1.2"
    assert result["active_task"]["name"] == "Plan"

def test_no_active_task(tmp_path):
    f = tmp_path / "status_done.md"
    f.write_text("""# Feature: Done
- [x] 1. Doing
""", encoding="utf-8")
    result = manifest.parse(f)
    assert result["active_task"] is None
