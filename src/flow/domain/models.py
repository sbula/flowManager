from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

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
