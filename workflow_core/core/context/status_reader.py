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
import shutil
from pathlib import Path
from typing import List, Optional

from workflow_core.core.context.models import Task, StatusFile
from workflow_core.infrastructure.config.loader import FlowConfig
from workflow_core.infrastructure.logging import get_logger

logger = get_logger("StatusReader")

class StatusReaderError(Exception):
    pass

class StatusReader:
    def __init__(self, config: FlowConfig, root: Path):
        self.config = config
        self.root = root
        
    def find_status_file(self) -> Path:
        """
        Locates status.md based on rigid configuration.
        NO recursive fallback (Proposal A).
        """
        candidates = self.config.status_files
        for c in candidates:
            p = self.root / c
            if p.exists():
                return p
        
        # Strict Mode Failure
        raise FileNotFoundError(
            f"CRITICAL: status.md not found in configured paths: {candidates}. "
            "Recursive search is disabled in V7 Strict Mode."
        )

    def parse(self, file_path: Optional[Path] = None) -> StatusFile:
        """
        Parses the status file into a StatusFile model.
        """
        target_path = file_path or self.find_status_file()
        content = target_path.read_text(encoding='utf-8')
        lines = content.splitlines()

        tasks: List[Task] = []
        seen_ids = set()
        
        # Regex: "- [x] ID Name"
        # Groups: 1=indent, 2=mark, 3=id, 4=rest
        task_pattern = re.compile(r"^(\s*)- \[(.| )\] (\d+(?:\.\d+)*)\.?\s+(.*)")

        for i, line in enumerate(lines):
            match = task_pattern.match(line)
            if match:
                indent, mark, task_id, rest = match.groups()
                
                if task_id in seen_ids:
                    raise StatusReaderError(f"Duplicate Task ID '{task_id}' on line {i+1}")
                seen_ids.add(task_id)
                
                # Strict Mark Check
                if mark not in [' ', 'x', '/']:
                    if self.config.strict_mode:
                        raise StatusReaderError(f"Invalid Task Mark '{mark}' on line {i+1}. Allowed: [ ], [x], [/]")
                
                tasks.append(Task(
                    id=task_id,
                    name=rest.strip(),
                    mark=mark, # type: ignore
                    indentation=indent,
                    line_number=i+1
                ))
                
        return StatusFile(tasks=tasks, file_path=str(target_path))

    def save_backup(self, file_path: Path):
        """
        Rotates backups: .bak -> .bak.1 -> .bak.2
        """
        count = self.config.backup_count
        # Shift existing
        for i in range(count - 1, 0, -1):
            src = file_path.with_suffix(f".md.bak.{i}")
            dst = file_path.with_suffix(f".md.bak.{i+1}")
            if src.exists():
                shutil.move(src, dst)
        
        # Shift first
        first = file_path.with_suffix(".md.bak")
        if first.exists():
             shutil.move(first, file_path.with_suffix(".md.bak.1"))
             
        # Create new
        shutil.copy(file_path, first)

    def update_status(self, file_path: Path, task_id: str, new_mark: str) -> bool:
        """
        Updates a specific task's status in the file (Token replacement).
        """
        self.save_backup(file_path)
        
        content = file_path.read_text(encoding='utf-8')
        lines = content.splitlines()
        updated = False
        
        escaped_id = re.escape(task_id)
        # We need to match the exact line to ensure we don't just replace the first string occurrence logic
        pattern = re.compile(rf"^(\s*)- \[(.| )\] {escaped_id}(\.?)\s+(.*)")
        
        new_lines = []
        for line in lines:
            match = pattern.match(line)
            if match and not updated:
                 # Reconstruct line with new mark
                 # Groups: 1=indent, 2=old_mark, 3, 4
                 indent = match.group(1)
                 rest = line[len(match.group(0)):] # Actually match.group(0) is full match? No.
                 # Using replace on the line is safer if we confirmed the match
                 # But we must be careful with "[ ]" vs "[x]"
                 
                 # Let's rebuild it cleanly
                 # "- [MARK] ID. Name"
                 # NOTE: The regex captured (dot?) after ID and (rest) name.
                 # Let's just swap the [char] part.
                 
                 # Pattern for exactly the bracket part:
                 # Replace only the first occurrence of `[` + match.group(2) + `]` with `[` + new_mark + `]`
                 # But we need to be safe.
                 
                 # prefix_len: indent (N) + "- [" (3 characters)
                 prefix_len = len(indent) + 3
                 # line[prefix_len] is the mark char
                 
                 if line[prefix_len] == match.group(2):
                      new_line = line[:prefix_len] + new_mark + line[prefix_len+1:]
                      new_lines.append(new_line)
                      updated = True
                 else:
                      # Falback
                      logger.warning(f"Regex mismatch during update for line: {line}")
                      new_lines.append(line)
            else:
                new_lines.append(line)
                
        if updated:
            file_path.write_text("\n".join(new_lines), encoding='utf-8')
            return True
        return False

    def cascade_completion(self, file_path: Optional[Path] = None) -> bool:
        """
        Scans for Parent Tasks whose children are ALL complete, and marks the parent complete.
        Returns True if any changes were made.
        """
        target_path = file_path or self.find_status_file()
        status = self.parse(target_path)
        tasks = status.tasks
        
        # 1. Build Tree
        # Simple Node structure
        class Node:
            def __init__(self, t):
                self.task = t
                self.children = []
                self.parent = None
        
        nodes = [Node(t) for t in tasks]
        root_dummy = Node(Task(id="ROOT", name="ROOT", mark=" ", indentation=""))
        # Indentation logic: We assume standard 4 or 2 spaces. 
        # Actually comparing length is sufficient?
        # Stack of active parents
        stack = [root_dummy]
        
        for node in nodes:
            current_indent = len(node.task.indentation)
            
            # Pop stack while top has deeper or equal indentation
            while len(stack) > 1:
                top_indent = len(stack[-1].task.indentation)
                if current_indent <= top_indent:
                    stack.pop()
                else:
                    break
            
            parent = stack[-1]
            parent.children.append(node)
            node.parent = parent
            stack.append(node)
            
        # 2. Iterate Bottom-Up (Post-Order) to propagate completion
        # We can just iterate the list of nodes efficiently?
        # If we iterate tasks in REVERSE order, we process children before parents?
        # Yes, because children appear after parents in file.
        
        changes = []
        reversed_nodes = list(reversed(nodes))
        
        for node in reversed_nodes:
            if not node.children:
                continue
                
            # It's a parent. Check children.
            all_done = all(child.task.mark == 'x' for child in node.children)
            
            if all_done:
                if node.task.mark != 'x':
                    logger.info(f"Auto-Completing Parent Task: {node.task.id}")
                    node.task.mark = 'x'
                    changes.append(node.task)
        
        # 3. Apply Changes
        if not changes:
            return False
            
        # Bulk Rewrite to avoid N backup rotations
        self.save_backup(target_path)
        
        # Reconstruct Content
        # We rely on the modified 'nodes' list (in original order)
        new_lines = []
        for node in nodes:
            t = node.task
            # Reconstruct line: INDENT- [MARK] ID. NAME
            # Logic from update_status match breakdown:
            # But here we construct scratch?
            # Safer to modify original lines? 
            # We have line_number. But multiple changes shifts nothing?
            # Actually, let's use the exact parsing logic to reconstruct format.
            # "    - [ ] 1. Foo"
            # t.indentation + "- [" + t.mark + "] " + t.id + (". " if needed?) + t.name
            
            # CAUTION: The regex parsing stripped things. The name might have lost spacing?
            # t.name was match.group(4).strip(). 
            # If original line had extra spaces, we lose them. 
            # Ideally we patch lines by line_number.
            pass
        
        # Patching Approach
        content = target_path.read_text(encoding='utf-8').splitlines()
        for t in changes:
            # line_number is 1-indexed
            idx = t.line_number - 1
            line = content[idx]
            # Replace [ ] or [/] with [x]
            # Careful with regex again or index
            # Known structure: indent + "- [" + mark + "]"
            # prefix_len calculation again
            indent_len = len(t.indentation)
            mark_index = indent_len + 3 # indent(N) + "- [" (3)
            
            # Verify correctness
            if line[mark_index-1:mark_index+2] == f"[{t.mark}]": 
                 # Wait, 't.mark' is already 'x' in our object, but file line is old.
                 # We need to find the old mark in the line.
                 pass
            
            # Just force inject 'x' at calculated position
            # Verify structure matches expectation
            if line[indent_len:indent_len+3] == "- [":
                 content[idx] = line[:mark_index] + "x" + line[mark_index+1:]
            else:
                 logger.warning(f"Line mismatch during cascade write for {t.id}: {line}")
        
        target_path.write_text("\n".join(content), encoding='utf-8')
        return True
