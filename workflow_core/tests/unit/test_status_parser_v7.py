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
import textwrap
from pathlib import Path
from unittest.mock import patch
from workflow_core.flow_manager.status_parser import StatusParser, StatusParsingError

@pytest.fixture
def mock_repo(tmp_path):
    # improved: Create marker file so _find_root succeeds!
    (tmp_path / "gemini.md").touch()
    
    # Create status file
    status = tmp_path / "status.md"
    content = textwrap.dedent("""
    - [x] 1. Done
    - [/] 2. Active
    """)
    status.write_text(content, encoding='utf-8')
    
    # Patch load_config to return deterministic config
    with patch.object(StatusParser, '_load_config', return_value={
        "root_markers": ["gemini.md"],
        "status_files": ["status.md"],
        "prefixes": {
            "planning": ["Plan"],
            "execution": ["Impl"]
        },
        "strict_mode": False
    }):
        yield tmp_path

def test_find_status_file(mock_repo):
    # The status.md is now created by the fixture, so we just check it
    parser = StatusParser(mock_repo)
    assert parser.status_file == mock_repo / "status.md"

def test_validate_structure_valid(mock_repo):
    # The status.md is now created by the fixture with valid content
    parser = StatusParser(mock_repo)
    parser.validate_structure() # Should not raise

def test_validate_structure_duplicate_id(mock_repo):
    p = mock_repo / "status.md"
    p.write_text("""
- [x] 1. One
- [ ] 1. Duplicate
""")
    parser = StatusParser(mock_repo)
    with pytest.raises(StatusParsingError, match="Duplicate Task ID '1'"):
        parser.validate_structure()

def test_validate_structure_multiple_active(mock_repo):
    p = mock_repo / "status.md"
    p.write_text("""
- [/] 1. Plan.ActiveOne
- [/] 2. Plan.ActiveTwo
""")
    parser = StatusParser(mock_repo)
    with pytest.raises(StatusParsingError, match="Multiple active tasks"):
        parser.validate_structure()

def test_smart_dispatch_planning(mock_repo):
    p = mock_repo / "status.md"
    p.write_text("- [/] 1. Plan.Arch: Design something")
    parser = StatusParser(mock_repo)
    ctx = parser.get_active_context()
    
    assert ctx["workflow"] == "Phase.Planning"
    assert ctx["prefix"] == "Plan.Arch"

def test_smart_dispatch_execution(mock_repo):
    p = mock_repo / "status.md"
    p.write_text("- [/] 1. Impl.Feature: Code something")
    parser = StatusParser(mock_repo)
    ctx = parser.get_active_context()
    
    assert ctx["workflow"] == "Phase.Execution"
    assert ctx["prefix"] == "Impl.Feature"

def test_smart_dispatch_fallback(mock_repo):
    p = mock_repo / "status.md"
    p.write_text("- [/] 1. (Just a name)")
    parser = StatusParser(mock_repo)
    ctx = parser.get_active_context()
    
    assert ctx["workflow"] == "Phase.Planning"
    assert ctx["prefix"] is None
