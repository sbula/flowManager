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

from typing import Dict, Any, List
from pathlib import Path
import json
import re

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

def _to_snake_case(name: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower().replace(" ", "_")

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manages the Research Phase Loop.
    Iterates through ALL experts in the 'expert_set' and checks for existence of 'audit/focus_[role].md'.
    """
    expert_set_name = args.get("expert_set")
    target_dir_name = args.get("target_dir", "audit")
    
    # 1. Resolve Config
    # Assume relative to this file: .../engine/atoms/research_sequencer.py -> .../config/
    config_root = Path(__file__).parent.parent.parent / "config"
    teams_config = _load_teams_config(config_root)
    personas_config = _load_personas(config_root)
    
    # 2. Resolve Expert List
    if not expert_set_name:
        return {"status": "FAILED", "message": "Research_Sequencer requires 'expert_set' argument."}
        
    expert_roles = teams_config.get("ExpertSets", {}).get(expert_set_name, [])
    if not expert_roles:
         return {"status": "FAILED", "message": f"Expert Set '{expert_set_name}' not found or empty."}

    # 3. Check Artifacts
    cwd = Path.cwd()
    target_dir = cwd / target_dir_name
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        
    # Iterate ALL experts (No filtering)
    for role in expert_roles:
        safe_role = _to_snake_case(role)
        focus_file = target_dir / f"focus_{safe_role}.md"
        
        if not focus_file.exists():
            # Found a missing artifact -> BLOCK and Request Action
            persona = personas_config.get(role, {})
            checklist = "\n".join([f"   - {item}" for item in persona.get("Checklist", [])])
            
            msg = (
                f"RESEARCH REQUIRED: {role}\n"
                f"Please research the task and create the Focus Document.\n"
                f"Target File: {focus_file}\n"
                f"Focus: {persona.get('Focus', 'General')}\n"
                f"Checklist:\n{checklist}"
            )
            return {"status": "WAITING", "message": msg}
            
    # 4. Success
    return {"status": "DONE", "message": f"All Focus Documents for {expert_set_name} are present."}
