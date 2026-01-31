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

import pytest
from workflow_core.core.context.models import Task, StatusFile
from workflow_core.core.context.status_reader import StatusFile as RealStatusFile

# Mock Model Helper
def create_task(id, mark, name="Test Task"):
    return Task(id=id, mark=mark, name=name, indentation="", line_number=0)

class TestStatusReaderLogic:
    
    def test_get_active_task_success(self):
        """Should return the task marked with '/'."""
        tasks = [
            create_task("1", "x"),
            create_task("2", "/"),
            create_task("3", " ")
        ]
        sf = RealStatusFile(tasks=tasks)
        active = sf.get_active_task()
        assert active is not None
        assert active.id == "2"

    def test_no_active_task(self):
        """Should return None if no task is marked '/'."""
        tasks = [
            create_task("1", "x"),
            create_task("2", " "),
            create_task("3", " ")
        ]
        sf = RealStatusFile(tasks=tasks)
        active = sf.get_active_task()
        assert active is None

    def test_multiple_active_error(self):
        """V8.5 Strict Mode: Multiple Active Tasks must raise ValueError."""
        tasks = [
            create_task("1", "/"),
            create_task("2", "/")
        ]
        sf = RealStatusFile(tasks=tasks)
        
        with pytest.raises(ValueError):
            sf.get_active_task()

    def test_is_active_property(self):
        """Verify Task.is_active property."""
        t1 = create_task("1", "/")
        t2 = create_task("2", "x")
        t3 = create_task("3", " ")
        
        assert t1.is_active is True
        assert t2.is_active is False
        assert t3.is_active is False

    def test_is_completed_property(self):
        """Verify Task.is_completed property."""
        t1 = create_task("1", "x")
        t2 = create_task("2", " ")
        
        assert t1.is_completed is True
        assert t2.is_completed is False
