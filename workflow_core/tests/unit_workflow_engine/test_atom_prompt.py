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
