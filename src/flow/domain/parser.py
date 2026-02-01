from __future__ import annotations
from typing import List, Optional, Dict, Any
from pathlib import Path
import re
import hashlib
import json
import shutil
from flow.domain.models import Task, StatusTree, StatusParsingError, IntegrityError

# --- Parser ---

class StatusParser:
    def __init__(self, root_path: Path):
        self.root = root_path
        self.flow_dir = root_path / ".flow"
        self.backups_dir = self.flow_dir / "backups"

    def load(self, status_path: str = "status.md") -> StatusTree:
        """
        Loads and parses the status file.
        Checks Integrity.
        """
        full_path = self.flow_dir / status_path
        if not full_path.exists():
            return StatusTree()
            
        # Integrity Check (T1.13)
        self._check_integrity(full_path)
            
        return self._parse_content(full_path.read_text(encoding="utf-8"))

    def accept_changes(self, status_path: str = "status.md"):
        """Updates .meta hash to match current file (T1.14)."""
        full_path = self.flow_dir / status_path
        if not full_path.exists():
            raise FileNotFoundError(f"{status_path} not found.")
        self._update_hash(full_path)

    def decline_changes(self, status_path: str = "status.md"):
        """Restores from latest backup (T1.15)."""
        full_path = self.flow_dir / status_path
        
        # Find latest backup
        if not self.backups_dir.exists():
             raise FileNotFoundError("No backups directory found.")
             
        backups = sorted(list(self.backups_dir.glob(f"{full_path.stem}_*{full_path.suffix}")))
        if not backups:
             raise FileNotFoundError("No backups found to restore.")
             
        latest = backups[-1]
        
        # Restore
        shutil.copy2(latest, full_path)
        
        # Sync Hash
        self._update_hash(full_path)

    def _check_integrity(self, file_path: Path):
        meta_path = file_path.with_suffix(".meta")
        if not meta_path.exists():
             # If meta missing, assume First Run or Tampered?
             # Spec implies Strict Mode. But for bootstrap, maybe warn?
             # Let's assume strict for now, but handle 'First Run' by creating meta on save.
             # If loading and meta missing, it's suspicious.
             # But if file created manually?
             # Let's Raise IntegrityError("Meta missing").
             return # For now, allow load if meta missing (legacy support), or decide Strict.
             # User said: "prevent human ability to modify".
             # So if meta missing, we can't verify.
             pass 
        
        content = file_path.read_bytes()
        current_hash = hashlib.sha256(content).hexdigest()
        
        try:
            meta = json.loads(meta_path.read_text())
            expected_hash = meta.get("hash")
            if current_hash != expected_hash:
                raise IntegrityError(f"Integrity Mismatch! Expected {expected_hash[:8]}, got {current_hash[:8]}. File tampered.")
        except (json.JSONDecodeError, KeyError):
            raise IntegrityError("Corrupt Meta file.")

    def _update_hash(self, file_path: Path):
        # Duplicated from Persister (Shared Utility?)
        # Ideally move to a util, but for now copying is fine to avoid large refactor.
        content = file_path.read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        
        meta_path = file_path.with_suffix(".meta")
        # Load existing for timestamp or create new?
        # Update hash, keep timestamp if exists? No, accept = new state.
        import time
        meta = {"hash": sha, "timestamp": time.time()}
        
        with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, indent=2)

    def _parse_content(self, content: str) -> StatusTree:
        tree = StatusTree()
        lines = content.splitlines()
        
        # Stack for recursion: [(Task, indent_level)]
        # We start with a dummy root to hold top-level tasks
        stack: List[Task] = [] 
        
        # ID State: reset for each parse
        # List[int], where index is indent_level. 
        # But wait, indent_level is 0, 1, 2...
        # Initial state should be ready for [1].
        # Actually logic inside loop handles initialization if empty?
        # Let's verify my logic block above: `if indent_level > len - 1`. 
        # If len is 0, indent 0 > -1. Enters loop. append(1). counters=[1]. ID="1". Correct.
        self._id_counters: List[int] = [] 
        
        # Regexes
        header_re = re.compile(r"^([^:]+):\s*(.*)$")
        task_re = re.compile(r"^(\s*)-\s*\[([ xXvV/-])\]\s*(.+)$")
        ref_re = re.compile(r"(.*?)\s*@\s*(\"?)(.+?)\2\s*$") # Captures: Name, Quote, Path

        line_idx = 0
        parsing_headers = True

        for line in lines:
            line_idx += 1
            if not line.strip(): 
                continue # Skip empty lines

            # 1. Parse Headers
            if parsing_headers:
                header_match = header_re.match(line)
                if header_match:
                    key, val = header_match.groups()
                    tree.headers[key.strip()] = val.strip()
                    continue
                else:
                    # First non-header line stops header parsing
                    parsing_headers = False

            # 2. Parse Tasks
            task_match = task_re.match(line)
            if not task_match:
                # T2.04: Syntax Error (unless it was a header fail, but we assume structural valid)
                # If indentation is present but no marker -> Error
                if line.lstrip().startswith("-"):
                     raise StatusParsingError(f"Line {line_idx}: Missing status marker or invalid format.")
                # T2.01/02/03: Indent check happens via regex capture of group 1
                raise StatusParsingError(f"Line {line_idx}: Invalid format.")

            indent_str, marker, full_text = task_match.groups()
            
            # T2.01-03: Strict Indentation (4 spaces)
            if "\t" in indent_str:
                 raise StatusParsingError(f"Line {line_idx}: Tabs are forbidden.")
            if len(indent_str) % 4 != 0:
                 raise StatusParsingError(f"Line {line_idx}: Invalid indentation. Must be multiple of 4 spaces.")
            
            indent_level = len(indent_str) // 4
            
            # Normalize Marker (T1.05)
            marker = marker.lower()
            if marker in ['x', 'v']: 
                status = 'done'
            elif marker == ' ': 
                status = 'pending'
            elif marker == '/': 
                status = 'active'
            elif marker == '-': 
                status = 'skipped'
            else:
                # T2.05: Bad Marker
                raise StatusParsingError(f"Line {line_idx}: Unknown marker '[{marker}]'")

            # Parse Ref (Fractal)
            ref = None
            name = full_text.strip()
            ref_match = ref_re.match(name)
            if ref_match:
                name, _, ref = ref_match.groups()
                name = name.strip()
                ref = ref.strip()
                
                # T2.10: Path Traversal
                if ".." in ref:
                    raise StatusParsingError(f"Line {line_idx}: Jailbreak attempt detected in path '{ref}'")

            # ID Generation (Hierarchical)
            # Logic:
            # - Maintain a list of counters for each level.
            # - When going deeper (indent > prev), append 1.
            # - When staying same, increment last.
            # - When going up, pop and increment last.

            if indent_level == 0:
                # Root level
                if not stack:
                   # Very first task
                   counters = [1]
                else:
                   # Sibling of previous root
                   counters = [counters[0] + 1]
            else:
                 # Calculate relative to parent
                 # We need to know the parent's ID or keep a global state?
                 # Better: Keep `counters` list where index = indent_level.
                 pass

            # Redesigned ID Logic:
            # `counters` list tracks the count at each depth.
            # e.g. [1, 2, 1] -> 1.2.1
            
            non_local_counters = getattr(self, "_id_counters", [])
            
            if indent_level > len(non_local_counters) - 1:
                # Deeper: Start new counter
                # Fill gaps if skipped reference levels (unlikely with strict parser)
                while len(non_local_counters) <= indent_level:
                    non_local_counters.append(1)
            else:
                # Same or Shallower: Increment at current level and reset deeper
                non_local_counters = non_local_counters[:indent_level + 1]
                non_local_counters[indent_level] += 1
            
            self._id_counters = non_local_counters
            
            # Form ID string
            task_id = ".".join(map(str, non_local_counters))

            # Create Task
            new_task = Task(
                id=task_id,
                name=name,
                status=status,
                indent_level=indent_level,
                ref=ref
            )

            # Tree Logic
            if indent_level == 0:
                tree.root_tasks.append(new_task)
                stack = [new_task]
            else:
                # Find parent
                while stack and stack[-1].indent_level >= indent_level:
                    stack.pop()
                
                if not stack:
                    raise StatusParsingError(f"Line {line_idx}: Orphaned task (indent {indent_level} with no parent).")
                
                parent = stack[-1]
                
                # T2.06: Logic Conflict (Shallow)
                if parent.status == 'done' and new_task.status == 'pending':
                    raise StatusParsingError(f"Line {line_idx}: Logic Conflict - Parent is Done but Child is Pending.")

                parent.children.append(new_task)
                new_task.parent = parent
                stack.append(new_task)

            # T2.07: Referential Integrity (Active + Ref)
            if status == 'active' and ref:
                # Anchor Rule: relative to .flow/
                target_path = self.flow_dir / ref
                if not target_path.exists():
                    raise StatusParsingError(f"Line {line_idx}: Missing sub-status file: {ref}")

        # T2.08 & T2.09: Sibling Validation (Post-Processing or On-Insert)
        # We can do a quick walk or check during insert.
        # Let's do a recursive validator for the whole tree to catch Sibling Conflicts globally.
        self._validate_tree(tree.root_tasks)

        return tree

    def _validate_tree(self, tasks: List[Task]):
        names = set()
        active_count = 0
        
        for t in tasks:
            # T2.09: Duplicate Name
            if t.name in names:
                raise StatusParsingError(f"Duplicate Task Name: '{t.name}'")
            names.add(t.name)
            
            # T2.08: Sibling Activity
            if t.status == 'active':
                active_count += 1
            
            if t.children:
                self._validate_tree(t.children)
        
        if active_count > 1:
            raise StatusParsingError("Ambiguous Focus: Multiple active siblings found.")

