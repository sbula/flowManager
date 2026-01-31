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
from unittest.mock import MagicMock, patch
from workflow_core.engine.atoms import run_command, wait_approval, render_template, git_command

def test_run_command_success():
    """Test successful command execution."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Hello"
        mock_run.return_value.stderr = ""
        
        res = run_command.run({"command": "echo Hello"}, {})
        assert res["status"] == "DONE"
        assert res["stdout"] == "Hello"

def test_wait_approval_missing_file(tmp_path):
    """Test waiting for non-existent file."""
    target = tmp_path / "review.md"
    res = wait_approval.run({"target_file": str(target), "marker": "OK"}, {})
    assert res["status"] == "WAITING"

def test_wait_approval_success(tmp_path):
    """Test finding property marker."""
    target = tmp_path / "review.md"
    target.write_text("Stuff... [x] APPROVE ...Stuff")
    res = wait_approval.run({"target_file": str(target), "marker": "[x] APPROVE"}, {})
    assert res["status"] == "DONE"

@patch("workflow_core.engine.atoms.render_template.TemplateFactory")
def test_render_template_mock(mock_factory_cls, tmp_path):
    """Test render template calls factory."""
    mock_instance = MagicMock()
    mock_factory_cls.return_value = mock_instance
    mock_module = MagicMock()
    mock_module.name = "TestPrompt"
    mock_instance.modules = [mock_module]
    mock_instance._render_module.return_value = "Rendered Content"
    
    target = tmp_path / "out.md"
    res = render_template.run({
        "template_name": "TestPrompt",
        "target_file": str(target)
    }, {})
    
    assert res["status"] == "DONE"
    assert target.read_text(encoding="utf-8") == "Rendered Content"

def test_git_command_commit():
    """Test git commit action."""
    with patch("subprocess.run") as mock_run:
        # Mock status logic (first call?) No, we simulate commit
        mock_run.return_value.returncode = 0
        
        res = git_command.run({
            "action": "commit",
            "message": "feat: test",
            "files": ["foo.py"]
        }, {})
        
        assert res["status"] == "DONE"
        # Verify calls?
        assert mock_run.call_count >= 2 # add, commit
