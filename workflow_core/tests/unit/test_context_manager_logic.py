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
from unittest.mock import MagicMock, patch
from workflow_core.core.context.context_manager import ContextManager
from workflow_core.core.context.models import Task, StatusFile
from workflow_core.infrastructure.config.loader import FlowConfig
from workflow_core.core.context.status_reader import StatusReader

@pytest.fixture
def mock_config():
    config = MagicMock(spec=FlowConfig)
    config.prefixes = {"planning": ["Plan"], "execution": ["Impl"]}
    config.strict_mode = False
    config.root = Path("/mock/root")
    return config

@pytest.fixture
def mock_reader():
    reader = MagicMock(spec=StatusReader)
    # returns a status file object
    sf = MagicMock(spec=StatusFile)
    sf.file_path = Path("/mock/root/status.md")
    reader.parse.return_value = sf
    return reader

@pytest.fixture
def context_manager(mock_config, mock_reader):
    return ContextManager(mock_config, mock_reader)

class TestContextManagerLogic:

    def test_cleanup_resources(self, context_manager):
        """Verify correct files are targeted for deletion during reset."""
        
        # We Mock the Path globbing and unlinking
        task_id = "4.3.5"
        status_path = Path("/mock/root/status.md")
        
        with patch("pathlib.Path.rglob") as mock_rglob:
            with patch("pathlib.Path.glob") as mock_glob:
                with patch("pathlib.Path.exists", return_value=True): # For state_dir check
                    
                    # 1. Setup Mock Artifacts
                    art1 = MagicMock(spec=Path)
                    art1.is_file.return_value = True
                    art1.name = "4_3_5_Plan.md"
                    
                    mock_rglob.return_value = [art1]
                    
                    # 2. Setup Mock State Files
                    state1 = MagicMock(spec=Path)
                    state1.name = "4_3_5.state.json"
                    
                    mock_glob.return_value = [state1]
                    
                    # 3. Execute
                    context_manager._cleanup_resources(task_id, status_path)
                    
                    # 4. Verify Unlinks
                    assert art1.unlink.called
                    assert state1.unlink.called
