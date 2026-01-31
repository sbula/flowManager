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
from workflow_core.engine.atoms import prompt

def test_render_string_success():
    """Test rendering a simple string template."""
    tpl = "Hello {{ name }}"
    ctx = {"name": "World"}
    result = prompt.render_string(tpl, ctx)
    assert result == "Hello World"

def test_render_file_success(tmp_path):
    """Test rendering from a file."""
    f = tmp_path / "test.j2"
    f.write_text("Hello {{ name }}", encoding="utf-8")
    
    ctx = {"name": "File"}
    result = prompt.render_file(f, ctx)
    assert result == "Hello File"

def test_render_missing_variable():
    """Test behavior when a variable is missing (Strict Undefined)."""
    tpl = "Hello {{ missing }}"
    ctx = {}
    # Jinja2 default is empty string, but we might want strict
    # For now, let's assume default behavior or explicit error?
    # Let's assert it returns empty string (standard jinja2) unless we configure StrictUndefined
    result = prompt.render_string(tpl, ctx)
    assert result == "Hello " 
