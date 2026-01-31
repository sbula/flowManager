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

import re
from pathlib import Path
from typing import Dict, Any, Optional, List

def parse(path: Path, target_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Parses status.md to extract Feature Name, Requirements, Active Task,
    and hierarchical context (Phase, Service, Level).
    """
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    
    # 1. Feature Name (Top-Level Header) - Legacy/Backup
    feature_match = re.search(r"^# Feature: (.+)", content, re.MULTILINE)
    feature_name = feature_match.group(1).strip() if feature_match else "Unknown"
    
    # 2. Requirements
    requirements = []
    req_section = re.search(r"## Requirements\n([\s\S]*?)(?=\n##|\Z)", content)
    if req_section:
        req_text = req_section.group(1)
        requirements = [line.strip("- ").strip() for line in req_text.splitlines() if line.strip().startswith("-")]
        
    # 3. Active Task & Hierarchy
    active_task = None
    phase = "Unknown"
    service = "Unknown"
    level = 1 # Default Level
    
    # Hierarchy Tracking: Stack of (indent, name)
    # We iterate and track the "current parent" for each indentation level
    hierarchy_stack = [] # tuples of (indent_level, text)
    
    # Regex for Phase: # Phase X: Name
    phase_pattern = re.compile(r"^# (Phase \d+.*)")
    
    # Regex for Tasks: - [ ] 1.2. ID Name
    # Groups: 1=indent, 2=mark, 3=id, 4=name
    task_pattern = re.compile(r"^(\s*)- \[(.| )\] (\d+(?:\.\d+)*)\.?\s+(.*)")
    
    for line in lines:
        # Check Phase Header
        phase_match = phase_pattern.match(line)
        if phase_match:
            phase = phase_match.group(1).strip()
            continue
            
        # Check Task Line
        task_match = task_pattern.match(line)
        if task_match:
            indent_str, mark, task_id, name = task_match.groups()
            indent = len(indent_str)
            name = name.strip()
            
            # Update Hierarchy
            # Pop items that are deeper or same level as current
            while hierarchy_stack and hierarchy_stack[-1][0] >= indent:
                hierarchy_stack.pop()
                
            hierarchy_stack.append((indent, name))
            
            # Check if this is the Active Task
            # Logic: If target_id provided, match exactly. Else match first pending.
            is_match = False
            current_id = task_id.strip().rstrip('.')
            
            if target_id:
                if current_id == target_id:
                    is_match = True
            elif mark == " ": # Pending [ ]
                is_match = True
                
            if is_match:
                # Found active task! capture context
                active_task = {
                    "id": task_id.strip().rstrip('.'),
                    "name": name
                }
                
                # Calculate Level from ID Depth
                # 4 -> 1 segment (Level 1)
                # 4.3 -> 2 segments (Level 2)
                # 4.3.2 -> 3 segments (Level 3)
                if active_task and "id" in active_task:
                     parts = active_task["id"].split('.')
                     level = len(parts)
                
                # Extract Service (First Parent in Stack)
                # Stack usually: [ (0, "Phase Ramp-Up"), (2, "Task") ]?
                # or [ (0, "Implementation: Position Sizing"), (4, "Infra"), (8, "Current") ]
                # We want the Top-Level Parent Task (Service/Component)
                if hierarchy_stack:
                    # Filter for bold items? In status.md conventions, Parent Tasks are bold **Name**
                    # Let's try to find the "Service" level.
                    # Usually:
                    # - [ ] 5. **Implementation: Service**  <-- this is Service
                    #   - [ ] 5.1. **Service: Feature**     <-- this is Feature Group
                    #     - [ ] 5.1.1. Task                 <-- Active Task
                    
                    # Logic: Find the first item in stack with **Bold** that looks like a Service/Component
                    # Or just take the root-most task in the section.
                    if len(hierarchy_stack) > 1:
                         # 0 is usually the top grouping
                         service_candidate = hierarchy_stack[0][1]
                         # Clean markdown **
                         service = service_candidate.replace("*", "")
                         
                         # Feature name is the active task name
                         feature_name = name
                         
                break # Stop at first pending task
                
    return {
        "phase": phase,
        "service_name": service,
        "feature_name": feature_name,
        "level": level,
        "requirements": requirements,
        "active_task": active_task
    }

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target_file")
    if not target:
        raise ValueError("Manifest Atom: Missing 'target_file' argument")
        
    task_id = context.get("task_id")
    return parse(Path(target), target_id=task_id)
