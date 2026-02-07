from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

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
    status: str = Field(..., pattern=r"^(pending|active|done|skipped|error)$")
    indent_level: int
    ref: Optional[str] = None  # Fractal link (relative to .flow/)
    parent: Optional[Task] = Field(None, exclude=True)  # Backref (not serialized)
    children: List[Task] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True, "validate_assignment": True}


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
        """
        Rebuilds internal ID index and Recalculates Virtual IDs.
        Should be called after Load or Structure Modification.
        """
        self._id_index.clear()

        # Recalculate IDs recursively
        self._assign_ids_recursive(self.root_tasks, parent_id_prefix="")

        self._ids_valid = True

    def _assign_ids_recursive(self, tasks: List[Task], parent_id_prefix: str):
        """Helper to assign 1.1, 1.2 style IDs."""
        for idx, task in enumerate(tasks, start=1):
            if parent_id_prefix:
                new_id = f"{parent_id_prefix}.{idx}"
            else:
                new_id = str(idx)  # Root level "1", "2"

            task.id = new_id
            self._id_index[new_id] = task

            # Recurse
            if task.children:
                self._assign_ids_recursive(task.children, parent_id_prefix=new_id)

    def find_task(self, task_id: str) -> Task:
        """Returns Task by ID. Raises StaleIDError if tree modified."""
        if not self._ids_valid:
            raise StaleIDError("IDs are invalid due to previous modification.")
        if task_id not in self._id_index:
            raise ValueError(f"Task ID '{task_id}' not found.")
        return self._id_index[task_id]

    def add_task(
        self,
        parent_id: str,
        name: str,
        status: str = "pending",
        index: Optional[int] = None,
    ):
        """
        Adds a new child task.
        Invalidates IDs.
        """
        # Validate Name Duplicity (Sibling Scope)
        siblings = (
            self.root_tasks
            if parent_id == "root"
            else self.find_task(parent_id).children
        )
        for s in siblings:
            if s.name == name:
                raise ValueError(f"Duplicate name '{name}' in siblings.")

        # Validate Active Injection (T4.13)
        if status == "active":
            self._validate_active_transition_context(siblings, parent_id)

        # Create Task (ID is placeholder, will be invalid anyway)
        # Note: parent defaults to None, which is valid for BaseModel if Optional
        new_task = Task(
            id="TBD", name=name, status=status, indent_level=0, parent=None
        )  # Indent fixed on save/recalc

        # Insert
        if index is not None:
            siblings.insert(index, new_task)
        else:
            siblings.append(new_task)

        # Link Parent (if not root)
        if parent_id != "root":
            # Ensure parent_id is str
            if parent_id is None:
                raise ValueError("parent_id cannot be None")
            parent = self.find_task(parent_id)

            # T3.11 Prevention: Cannot add Pending/Active child to Done parent
            if parent.status == "done" and status not in ["done", "skipped", "error"]:
                raise StateError(
                    f"Cannot add {status} child '{name}' to Done parent '{parent.name}'."
                )

            new_task.parent = parent
            new_task.indent_level = parent.indent_level + 1

        # Invalidate IDs (T4.15)
        self._ids_valid = False

    def find_active_task(self) -> Optional[Task]:
        """Returns the single active task, if any."""
        for task in self._id_index.values():
            if task.status == "active":
                return task
        return None

    def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        status: Optional[str] = None,
        context_anchor: Optional[str] = None,
    ):
        """
        Updates task properties.
        Validates transitions.
        """
        task = self.find_task(task_id)

        # Context Anchor (T4.04)
        if context_anchor and task.name != context_anchor:
            raise ValueError(
                f"Anchor mismatch. Expected '{context_anchor}', got '{task.name}'"
            )

        if name:
            task.name = name

        if status:
            if status == "active" and task.status != "active":
                # Validate Transition
                siblings = self.root_tasks if not task.parent else task.parent.children
                # Fix: If task.parent is None, we are a root task. Parent ref is "root".
                parent_ref = "root" if task.parent is None else task.parent

                self._validate_active_transition_context(
                    siblings, parent_id_ref=parent_ref
                )

            task.status = status

            # Auto-Propagation (Protocol V2)
            self._propagate_state(task)

    def _propagate_state(self, task: Task):
        """
        Recursively updates parent state based on children.
        1. Activation Bubble: Child Active/Done -> Parent Active (if pending).
        2. Completion Bubble: ALL Children Done -> Parent Done.
        """
        if not task.parent:
            return

        parent = task.parent
        siblings = parent.children

        # 1. Activation Bubble
        if task.status in ["active", "done"]:
            if parent.status == "pending":
                parent.status = "active"
                # Recurse up (Parent became active, so Grandparent might need to)
                self._propagate_state(parent)

        # 2. Completion Bubble
        # Only trigger if task became done
        if task.status == "done":
            all_done = all(s.status == "done" for s in siblings)
            if all_done:
                parent.status = "done"
                # Recurse up
                self._propagate_state(parent)

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

    def _validate_active_transition_context(
        self, siblings: List[Task], parent_id_ref: Union[str, Task, None]
    ):
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
        elif parent_id_ref != "root" and parent_id_ref is not None:
            # If passed ID string (add_task case)
            try:
                parent = self.find_task(parent_id_ref)
                if parent.status != "active":
                    raise StateError(f"Parent '{parent.name}' is not active.")
            except StaleIDError:
                pass  # Logic hole? checking parent state during add requires valid ID? Yes.

    def _find_deepest_active(self, tasks: List[Task]) -> Optional[Task]:
        for t in tasks:
            deep = self._find_deepest_active(t.children)
            if deep:
                return deep
            if t.status == "active":
                return t
        return None

    def _find_first_pending(self, tasks: List[Task]) -> Optional[Task]:
        for t in tasks:
            if t.status == "pending":
                return t
            child = self._find_first_pending(t.children)
            if child:
                return child
        return None

    # --- Validation ---

    def validate_consistency(self):
        """
        Deep validation of the tree.
        1. Cycle Detection (T4.18)
        2. State Consistency (T3.11)
        """
        # 1. Cycle Detection
        visited = set()
        self._check_cycles(self.root_tasks, visited, path=set())

        # 2. State Logic
        self._check_state_logic(
            self.root_tasks, parent_status="active"
        )  # Root is effectively active/open

    def _check_cycles(self, tasks: List[Task], visited: set, path: set):
        for task in tasks:
            if id(task) in path:
                raise ValueError(f"Cycle detected in task structure: '{task.name}'")
            if id(task) in visited:
                continue

            visited.add(id(task))
            path.add(id(task))

            if task.children:
                self._check_cycles(task.children, visited, path)

            path.remove(id(task))

    def _check_state_logic(self, tasks: List[Task], parent_status: str):
        """
        Enforces Strict Hierarchy:
        1. Sibling Exclusivity: Only one task can be active among siblings.
        2. Parent Constraints:
           - If Parent is DONE, Children MUST be DONE (or Skipped/Error).
           - If Parent is PENDING, Children CANNOT be ACTIVE.
        """
        # 1. Sibling Exclusivity
        active_siblings = [t.name for t in tasks if t.status == "active"]
        if len(active_siblings) > 1:
            raise ValueError(
                f"Ambiguous Focus: Multiple active siblings found: {active_siblings}"
            )

        for task in tasks:
            # 2. Parent Conflict (Done Parent)
            if parent_status == "done" and task.status not in [
                "done",
                "skipped",
                "error",
            ]:
                raise ValueError(
                    f"Logic Conflict: Parent is Done but Child '{task.name}' is {task.status}."
                )

            # 3. Parent Conflict (Pending Parent)
            # Exception: Root level (parent_status="active" passed by caller)
            if parent_status == "pending" and task.status == "active":
                raise ValueError(
                    f"Logic Conflict: Child '{task.name}' is active but Parent is pending."
                )

            if task.children:
                self._check_state_logic(task.children, parent_status=task.status)
