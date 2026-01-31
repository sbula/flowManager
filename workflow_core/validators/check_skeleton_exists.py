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

import sys
from pathlib import Path
import os
import re

def check_skeleton_exists():
    # Locate status.md
    status_path_env = os.environ.get("GEMINI_STATUS_FILE")
    if status_path_env:
        status_path = Path(status_path_env)
    else:
        # Fallback for phase 5
        cwd = Path.cwd()
        status_path = cwd / "design" / "roadmap" / "phases" / "phase5" / "status.md"

    # Logic: "Skeleton Creation" means extracting nodes from project_map.md and listing them as Headers.
    # We cannot strictly validate WHICH headers are there without parsing project_map (complex),
    # but we can validate that *something* has been added beyond the Bootstrap section.
    
    # We look for Parent Tasks (Feature Scope): Lines starting with "- [ ] N. **Title**"
    # The Bootstrap section is always Task 1.
    # So if we find Task 2, Task 3, etc., the Skeleton is populated.
    
    parent_task_pattern = r"^\s*-\s*\[[ x/]+\]\s*\d+\.\s*\*\*.*\*\*"
    
    parent_tasks = []
    for line in content.splitlines():
        if re.match(parent_task_pattern, line):
            parent_tasks.append(line.strip())
            
    print(f">> Found {len(parent_tasks)} Parent Task scopes:")
    for pt in parent_tasks:
        print(f"   {pt}")
        
    # We expect > 1 (Task 1 is Bootstrap, Task 2+ are the Scope)
    if len(parent_tasks) > 1:
        print(">> SUCCESS: Skeleton Headers detected (More than just Bootstrap identified).")
        return 0
    else:
        print("!! FAILURE: Status file only contains the Bootstrap section.")
        print("!! You must append the Service Headers (Scope) from project_map.md.")
        return 1

if __name__ == "__main__":
    sys.exit(check_skeleton_exists())
