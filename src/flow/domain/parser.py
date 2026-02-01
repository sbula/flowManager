from __future__ import annotations
from typing import List, Optional, Dict, Any
from pathlib import Path
import re
from pydantic import BaseModel, Field

# --- Domain Models ---

class Task(BaseModel):
    """Represents a single task in the hierarchy."""
    id: str = Field(..., description="Unique identifier within sibling scope")
    name: str
    status: str = Field(..., pattern=r"^(pending|active|done|skipped)$")
    indent_level: int
    ref: Optional[str] = None  # Fractal link (relative to .flow/)
    parent: Optional[Task] = Field(None, exclude=True) # Backref (not serialized)
    children: List[Task] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

class StatusTree(BaseModel):
    """Represents the entire Status Document."""
    headers: Dict[str, str] = Field(default_factory=dict)
    root_tasks: List[Task] = Field(default_factory=list)

    def get_active_task(self) -> Optional[Task]:
        """
        Returns the current cursor.
        1. Deepest '[/]' (Active) node.
        2. OR First '[ ]' (Pending) node (Smart Resume).
        """
        # 1. Search for Active
        active = self._find_deepest_active(self.root_tasks)
        if active:
            return active
            
        # 2. Smart Resume (First Pending)
        return self._find_first_pending(self.root_tasks)

    def _find_deepest_active(self, tasks: List[Task]) -> Optional[Task]:
        for t in tasks:
            # Check children first (to find deepest)
            deep = self._find_deepest_active(t.children)
            if deep:
                return deep
            # If no children are active, check self
            if t.status == 'active':
                return t
        return None

    def _find_first_pending(self, tasks: List[Task]) -> Optional[Task]:
        for t in tasks:
            if t.status == 'pending':
                return t
            # If done/skipped, traverse children to find next pending
            child = self._find_first_pending(t.children)
            if child:
                return child
        return None

class StatusParsingError(Exception):
    """Custom exception for all parsing/validation failures."""
    pass

# --- Parser ---

class StatusParser:
    def __init__(self, root_path: Path):
        self.root = root_path
        self.flow_dir = root_path / ".flow"

    def load(self, status_path: str = "status.md") -> StatusTree:
        """
        Loads and parses the status file.
        Args:
            status_path: Relative path from .flow/ (default: "status.md")
        """
        full_path = self.flow_dir / status_path
        if not full_path.exists():
            return StatusTree()
            
        return self._parse_content(full_path.read_text(encoding="utf-8"))

    def _parse_content(self, content: str) -> StatusTree:
        tree = StatusTree()
        lines = content.splitlines()
        
        # Stack for recursion: [(Task, indent_level)]
        # We start with a dummy root to hold top-level tasks
        stack: List[Task] = [] 
        
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

            # Create Task
            new_task = Task(
                id=f"auto_{line_idx}", # Temporary ID
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

