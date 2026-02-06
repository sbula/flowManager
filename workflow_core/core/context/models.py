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
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Task(BaseModel):
    id: str
    name: str
    mark: Literal[" ", "x", "/"]  # Pending, Done, In-Progress
    indentation: str = ""  # Preserve indentation for round-tripping
    line_number: int = -1  # For error reporting

    @property
    def is_active(self) -> bool:
        return self.mark == "/"

    @property
    def is_completed(self) -> bool:
        return self.mark == "x"


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
