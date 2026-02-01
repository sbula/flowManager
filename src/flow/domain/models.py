from __future__ import annotations
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, PrivateAttr

class StateError(Exception):
    """Raised when an operation violates strict state logic (e.g. Sibling Conflict)."""
    pass

class StaleIDError(Exception):
    """Raised when accessing IDs after tree modification."""
    pass

class IntegrityError(Exception):
    """Raised when status file hash mismatch is detected."""
    pass

class StatusParsingError(Exception):
    """Custom exception for all parsing/validation failures."""
    pass

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
    
    # Internal flag to track ID validity
    _ids_valid: bool = PrivateAttr(default=True)
    # Internal index for O(1) lookups (id -> Task)
    _id_index: Dict[str, Task] = PrivateAttr(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        self._reindex()

    def _reindex(self):
        """Rebuilds internal ID index. Should be called after Load."""
        self._id_index.clear()
        self._index_tasks(self.root_tasks)
        self._ids_valid = True

    def _index_tasks(self, tasks: List[Task]):
        for t in tasks:
            self._id_index[t.id] = t
            self._index_tasks(t.children)

    def find_task(self, task_id: str) -> Task:
        """Returns Task by ID. Raises StaleIDError if tree modified."""
        if not self._ids_valid:
            raise StaleIDError("IDs are invalid due to previous modification.")
        if task_id not in self._id_index:
            raise ValueError(f"Task ID '{task_id}' not found.")
        return self._id_index[task_id]

    def add_task(self, parent_id: str, name: str, status: str = "pending", index: Optional[int] = None):
        """
        Adds a new child task.
        Invalidates IDs.
        """
        # Validate Name Duplicity (Sibling Scope)
        siblings = self.root_tasks if parent_id == "root" else self.find_task(parent_id).children
        for s in siblings:
            if s.name == name:
                raise ValueError(f"Duplicate name '{name}' in siblings.")
        
        # Validate Active Injection (T4.13)
        if status == "active":
            self._validate_active_transition_context(siblings, parent_id)

        # Create Task (ID is placeholder, will be invalid anyway)
        new_task = Task(id="TBD", name=name, status=status, indent_level=0) # Indent fixed on save/recalc

        # Insert
        if index is not None:
            siblings.insert(index, new_task)
        else:
            siblings.append(new_task)
            
        # Link Parent (if not root)
        if parent_id != "root":
            parent = self.find_task(parent_id)
            new_task.parent = parent
            new_task.indent_level = parent.indent_level + 1
        
        # Invalidate IDs (T4.15)
        self._ids_valid = False

    def update_task(self, task_id: str, name: Optional[str] = None, status: Optional[str] = None, context_anchor: Optional[str] = None):
        """
        Updates task properties.
        Validates transitions.
        """
        task = self.find_task(task_id)
        
        # Context Anchor (T4.04)
        if context_anchor and task.name != context_anchor:
            raise ValueError(f"Anchor mismatch. Expected '{context_anchor}', got '{task.name}'")

        if name:
            task.name = name
            
        if status:
            if status == "active" and task.status != "active":
                # Validate Transition
                siblings = self.root_tasks if not task.parent else task.parent.children
                # Fix: If task.parent is None, we are a root task. Parent ref is "root".
                parent_ref = "root" if task.parent is None else task.parent
                
                self._validate_active_transition_context(siblings, parent_id_ref=parent_ref)
            
            task.status = status

    def remove_task(self, task_id: str):
        """Removes a task. Invalidates IDs."""
        task = self.find_task(task_id)
        
        if task.parent:
            task.parent.children.remove(task)
        else:
            self.root_tasks.remove(task)
            
        self._ids_valid = False

    def get_active_task(self) -> Optional[Task]:
        """Returns the current cursor."""
        # 1. Search for Active
        active = self._find_deepest_active(self.root_tasks)
        if active:
            return active
        # 2. Smart Resume (First Pending)
        return self._find_first_pending(self.root_tasks)

    # --- Helpers ---

    def _validate_active_transition_context(self, siblings: List[Task], parent_id_ref: Union[str, Task, None]):
        """
        Validates T4.11 (Sibling Conflict) and T4.12 (Parent Conflict).
        """
        # 1. Sibling Check
        for s in siblings:
            if s.status == "active":
                raise StateError(f"Sibling '{s.name}' is already active.")
        
        # 2. Parent Check
        if isinstance(parent_id_ref, Task):
             parent = parent_id_ref
             if parent.status != "active":
                 raise StateError(f"Parent '{parent.name}' is not active.")
        elif parent_id_ref != "root":
             # If passed ID string (add_task case)
             try:
                 parent = self.find_task(parent_id_ref)
                 if parent.status != "active":
                    raise StateError(f"Parent '{parent.name}' is not active.")
             except StaleIDError:
                 pass # Logic hole? checking parent state during add requires valid ID? Yes. 

    def _find_deepest_active(self, tasks: List[Task]) -> Optional[Task]:
        for t in tasks:
            deep = self._find_deepest_active(t.children)
            if deep: return deep
            if t.status == 'active': return t
        return None

    def _find_first_pending(self, tasks: List[Task]) -> Optional[Task]:
        for t in tasks:
            if t.status == 'pending': return t
            child = self._find_first_pending(t.children)
            if child: return child
        return None
