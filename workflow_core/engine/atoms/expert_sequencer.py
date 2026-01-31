from typing import Dict, Any, List, Set, Optional
from pathlib import Path
import json
from workflow_core.core.template_factory.core import TemplateFactory, ReviewContext
from workflow_core.engine.atoms import agent, prompt

def _load_teams_config(config_root: Path) -> Dict[str, Any]:
    """Loads the core_teams.json configuration."""
    teams_file = config_root / "core_teams.json"
    if not teams_file.exists():
        return {}
    return json.loads(teams_file.read_text(encoding="utf-8"))

def _load_personas(config_root: Path) -> Dict[str, Any]:
    """Loads the expert_personas.json configuration."""
    p_file = config_root / "expert_personas.json"
    if not p_file.exists():
        return {}
    return json.loads(p_file.read_text(encoding="utf-8"))

def _resolve_experts(factory_modules: List[Dict[str, Any]], expert_set_name: Optional[str], teams_config: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Resolves the final list of required experts.
    """
    base_pool = {m["Role"]: m for m in factory_modules if m.get("Type") == "Expert"}
    
    if expert_set_name:
        required_roles = teams_config.get("ExpertSets", {}).get(expert_set_name, [])
        if not required_roles:
            return []
    else:
        required_roles = list(base_pool.keys())

    author_role = context.get("author_role")
    final_list = []
    for role in required_roles:
        if role == author_role:
            continue
        
        module = base_pool.get(role)
        if module:
            final_list.append(module)
            
    return final_list

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manages Strict Sequential Expert Injection.
    Supports Modes: 'draft' (Scribing) and 'review' (Approval).
    """
    target_file = args.get("target_file", "Review.md")
    mode = args.get("mode", "review") # Default to review
    target_path = Path(target_file)
    if not target_path.is_absolute():
        target_path = Path.cwd() / target_path
    
    # 1. Initialize Context & Factory
    factory = TemplateFactory()
    r_ctx = ReviewContext(
        task_id=context.get("task_id", "0.0.0"),
        task_type="Impl.Feature", 
        service_path=Path(context.get("service_path", ".")),
        service_type=context.get("service_type", "Service"), 
        language="Python",
        feature_name=context.get("feature_name", ""),
        tags=set(context.get("tags", []))
    )

    # 2. Get Experts
    config_root = Path(__file__).parent.parent.parent / "config"
    teams_config = _load_teams_config(config_root)
    personas_config = _load_personas(config_root)
    
    all_active_modules = factory.get_active_modules(r_ctx)
    expert_set_name = args.get("expert_set")
    required_experts = _resolve_experts(all_active_modules, expert_set_name, teams_config, context)
    
    if not target_path.exists():
        return {"status": "FAILED", "message": f"Target file {target_file} not found"}

    content = target_path.read_text(encoding="utf-8")
    
    # --- DRAFT MODE (Sequential Scribing) ---
    if mode == "draft":
        prompt_template = args.get("prompt_template")
        updated_any = False
        
        for expert in required_experts:
            role = expert.get("Role")
            header = f"## {role} Analysis"
            
            if header in content:
                continue # Already done
            
            # 1. Write Header
            content += f"\n\n{header}\n"
            target_path.write_text(content, encoding="utf-8")
            
            # 2. Prepare Prompt
            prompt_ctx = context.copy()
            prompt_ctx.update({
                "role": role,
                "persona": personas_config.get(role, {}),
                "current_content": content # Give agent the full file so far
            })
            
            # Simple Template Loading logic (Hack for MVP)
            p_tmpl_content = prompt_template
            if prompt_template and str(prompt_template).endswith(".j2"):
                 # Try to load if absolute path or exists
                 p_path = Path(prompt_template)
                 if p_path.exists():
                     p_tmpl_content = p_path.read_text(encoding="utf-8")
            
            # 3. Render & Query
            # We use prompt.render_string even if it's simple text
            final_prompt = prompt.render_string(str(p_tmpl_content), prompt_ctx)
            
            response = agent.query(final_prompt)
            
            # 4. Append Result
            content += f"\n{response}\n"
            target_path.write_text(content, encoding="utf-8")
            updated_any = True
            
        return {"status": "DONE", "message": "Drafting Complete"}

    # --- REVIEW MODE (Approval Gates) ---
    last_expert_index = -1
    for idx, expert in enumerate(required_experts):
        role_name = expert.get("Role", expert.get("Name"))
        if f"### Reviewer: {role_name}" in content:
            last_expert_index = idx
        else:
            break
            
    # Case A: Inject First
    if last_expert_index == -1:
        if not required_experts:
            return {"status": "DONE", "message": "No experts required."}
        first_expert = required_experts[0]
        _inject_expert(factory, first_expert, r_ctx, target_path, content)
        return _build_waiting_msg(first_expert, personas_config, "Injected First Expert")

    # Case B: Check Last
    last_expert = required_experts[last_expert_index]
    last_role = last_expert.get("Role")
    expert_header = f"### Reviewer: {last_role}"
    segment = content.split(expert_header)[-1]
    
    if "[x] APPROVE" not in segment:
        return _build_waiting_msg(last_expert, personas_config, f"Waiting for Approval from {last_role}")
    
    # Case C: Inject Next
    next_idx = last_expert_index + 1
    if next_idx < len(required_experts):
        next_expert = required_experts[next_idx]
        _inject_expert(factory, next_expert, r_ctx, target_path, content)
        return _build_waiting_msg(next_expert, personas_config, f"Injected Next Expert: {next_expert.get('Role')}")
        
    return {"status": "DONE", "message": "All Experts Approved."}

def _build_waiting_msg(expert_mod, personas, base_msg, error=False):
    role = expert_mod.get("Role")
    persona = personas.get(role, {})
    msg = f"{base_msg}"
    if error: msg += " (Review Blocked)"
    if persona:
        msg += f"\n\n>> [REVIEW INSTRUCTIONS: {role}]"
        for item in personas.get("Checklist", []): # BUG FIX: was persona.get
             msg += f"\n   - {item}"
    return {"status": "WAITING", "message": msg}

def _inject_expert(factory, expert_mod, ctx, path, current_content):
    rendered = factory._render_module(expert_mod, ctx, {})
    new_content = current_content + "\n\n" + rendered
    path.write_text(new_content, encoding="utf-8")
