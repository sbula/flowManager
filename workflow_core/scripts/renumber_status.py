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
import sys
from pathlib import Path

def renumber_status(file_path):
    print(f"Reading {file_path}...")
    content = Path(file_path).read_text(encoding='utf-8')
    lines = content.splitlines()
    new_lines = []
    
    # Track counters for each parent prefix
    # e.g., "4.1." -> 1
    counters = {}
    
    # Regex to match task lines
    # Matches: indent, [x] or [ ], numbering (digits.dots), content
    # Group 1: indent
    # Group 2: mark (x, /, or space)
    # Group 3: numbering 4.1.2
    # Group 4: content
    pattern = re.compile(r"^(\s*)- \[(.| )\] (\d+(?:\.\d+)+)\.? (.*)")
    
    for line in lines:
        match = pattern.match(line)
        if match:
            indent = match.group(1)
            mark = match.group(2)
            original_number = match.group(3)
            rest = match.group(4)
            
            parts = original_number.split('.')
            if len(parts) >= 3: # We only renumber leaf tasks (Depth >= 3, e.g. 4.1.1)
                # Parent prefix is everything except the last digit
                parent_prefix = ".".join(parts[:-1])
                
                # Initialize or increment
                if parent_prefix not in counters:
                    counters[parent_prefix] = 1
                else:
                    counters[parent_prefix] += 1
                
                new_number = f"{parent_prefix}.{counters[parent_prefix]}"
                
                # Reconstruct line
                # Note: Adding '.' after number if it was present or standardizing?
                # The regex didn't capture the trailing dot in group 3, so we add it back.
                new_line = f"{indent}- [{mark}] {new_number}. {rest}"
                new_lines.append(new_line)
                
                if new_number != original_number:
                    # print(f"Renumbered: {original_number} -> {new_number}")
                    pass
            else:
                # Top level headers (4.1, 5.2) - reset their children counters?
                # Actually, if we see 4.2, we don't need to reset 4.1, as they are distinct keys.
                # Just keep line as is.
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    return "\n".join(new_lines)

if __name__ == "__main__":
    target = "design/roadmap/phases/phase5/status.md"
    if len(sys.argv) > 1:
        target = sys.argv[1]
        
    updated = renumber_status(target)
    Path(target).write_text(updated, encoding='utf-8')
    print(f"Updated {target}")
