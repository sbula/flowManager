import pytest
import json
from pathlib import Path

# Fix Path to be relative to Repo Root when running pytest from root
CONFIG_PATH = Path("workflow_core/config/modules.json")

@pytest.fixture
def modules_config():
    if not CONFIG_PATH.exists():
        pytest.fail(f"Modules config not found at {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

def test_implementation_header_structure(modules_config):
    """Verify Implementation_Header exists and has valid placeholders"""
    modules = modules_config.get("Modules", [])
    template = next((m for m in modules if m["Name"] == "Implementation_Header"), None)
    
    assert template is not None, "Implementation_Header template missing in modules.json"
    
    content = template.get("Content", "")
    
    # The TemplateFactory strictly replaces these keys:
    # "${feature_name}", "${task_id}", "${service_type}", "${language}"
    # Validating that we use the correct syntax.
    
    # Note: We added headers in V8.5 but might not strictly require all placeholders in metadata.
    # But checking for syntax errors is good.
    
    # Remove valid placeholders to ensure we don't match them when checking for invalid ones
    clean_content = content.replace("${feature_name}", "").replace("${task_id}", "") \
                           .replace("${service_path}", "").replace("${service_type}", "") \
                           .replace("${task_name}", "").replace("${service_name}", "")
    
    # Ensure no invalid placeholders (like old dot notation or missing braces)
    assert "{feature.name}" not in content, "Found invalid placeholder {feature.name}"
    assert "{task.id}" not in content, "Found invalid placeholder {task.id}"
    assert "{feature_name}" not in clean_content, "Found invalid placeholder {feature_name} (missing $)"
    assert "{task_id}" not in clean_content, "Found invalid placeholder {task_id} (missing $)"

def test_all_templates_have_valid_activations(modules_config):
    """Ensure all modules have an Activation field"""
    for m in modules_config.get("Modules", []):
         # Skip Headers? No, they should have Activation: Always
        assert "Activation" in m, f"Module {m.get('Name')} missing Activation field"
