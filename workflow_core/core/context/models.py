from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
import re

class Task(BaseModel):
    id: str
    name: str
    mark: Literal[' ', 'x', '/']  # Pending, Done, In-Progress
    indentation: str = "" # Preserve indentation for round-tripping
    line_number: int = -1 # For error reporting

    @property
    def is_active(self) -> bool:
        return self.mark == '/'

    @property
    def is_completed(self) -> bool:
        return self.mark == 'x'

class StatusFile(BaseModel):
    tasks: List[Task] = []
    file_path: Optional[str] = None
    
    def get_active_task(self) -> Optional[Task]:
        active = [t for t in self.tasks if t.is_active]
        if len(active) > 1:
            raise ValueError(f"CRITICAL: Multiple active tasks found! {active}")
        return active[0] if active else None

    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None
