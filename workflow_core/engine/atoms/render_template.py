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

from typing import Dict, Any
from pathlib import Path
from workflow_core.core.template_factory.core import TemplateFactory, ReviewContext

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Renders a template using the TemplateFactory.
    Args:
        template_name: Name of the module/template to render.
        target_file: Relative path to write the output to.
    """
    template_name = args.get("template_name")
    target_file = args.get("target_file")
    
    if not template_name or not target_file:
        return {"status": "FAILED", "message": "Missing arguments"}

    # Initialize Factory
    # TODO: Config Path should be injected or standard
    project_root = Path.cwd()
    # config_path = project_root / "workflow_core" / "config" / "modules.json"
    
    factory = TemplateFactory()
    
    # Render
    # We might need to map "Template Name" to "Module Name" or support raw prompts
    # For now, assume it refers to a Module in modules.json
    
    # Create Context
    # Map Engine Context (dict) to ReviewContext (object) for Factory
    r_ctx = ReviewContext(
        task_id=context.get("task_id", "0.0.0"),
        task_type="Impl.Feature", # TODO: Dynamic?
        service_path=Path(context.get("service_path", ".")), 
        service_type=context.get("service_type", "Service"), # Updated for V2
        language="Python", # TODO: Dynamic
        feature_name=context.get("feature_name", ""),
        tags=set(context.get("tags", []))
    )
    
    # HACK: If template_name is "Mini_Planning_Prompt", we just render that module.
    # But TemplateFactory.create_review_report renders a LIST of modules.
    
    # Current V1 logic: template_factory.render_module(module, context)
    # We need to expose a single module render in Factory?
    # Yes, _render_module is internal but we can use it, or add public method.
    # Or we use 'render_template' method if added.
    
    # Let's assume we want to APPEND or CREATE the file.
    
    # For V2 MVP: Just Write a String to file if it is a prompt.
    # But we want to use the Factory logic (dynamic substitution).
    
    # Let's try to load the module def from Factory and render it.
    
    # Logic for Dynamic Expert Panel
    if template_name == "Expert_Panel_Dynamic":
        # Select all Expert modules
        expert_modules = [m for m in factory.modules if m.get("Type") == "Expert"]
        # Allow Factory to filter by Activation (via generate_from_modules)
        rendered_content = factory.generate_from_modules(expert_modules, r_ctx, {})
        if not rendered_content:
             return {"status": "SKIPPED", "message": "No active experts found for this context."}
        
        mode = "append"
        
    else:
        # Standard Single Module Render
        module_def = next((m for m in factory.modules if m.get("Name") == template_name), None)
        if not module_def:
             return {"status": "FAILED", "message": f"Module {template_name} not found in Factory"}
        
        # FIX: Pass full engine context as extra_context to allow {{ phase }}, {{ level }} etc.
        rendered_content = factory._render_module(module_def, r_ctx, context)
        mode = "overwrite" # Default for single template (e.g. Prompt)
    
    if rendered_content:
        # Write to file
        target = Path(target_file)
        if not target.is_absolute():
            target = project_root / target
            
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if we append or overwrite. Default to Overwrite?
        # Or check if content exists.
        # For "Planning", we usually Create or Update.
        
        if target.exists():
             if mode == "append":
                 # Check if content already exists to avoid duplication?
                 # For now, simple append with newline
                 current = target.read_text(encoding="utf-8")
                 if rendered_content.strip() not in current:
                     target.write_text(current + "\n\n" + rendered_content, encoding="utf-8")
                     msg = f"Appended to {target}"
                 else:
                     msg = f"Content already in {target} (Skipped Append)"
             else:
                 target.write_text(rendered_content, encoding="utf-8")
                 msg = f"Overwrote {target}"
        else:
             target.write_text(rendered_content, encoding="utf-8")
             msg = f"Created {target}"
             
        return {"status": "DONE", "message": msg}
    
    return {"status": "SKIPPED", "message": "No content rendered"}
