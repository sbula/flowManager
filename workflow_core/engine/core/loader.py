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

import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import ValidationError
from workflow_core.engine.schemas.models import WorkflowDefinition

class WorkflowLoader:
    def __init__(self, config_root: Path):
        self.config_root = config_root
        self.workflows_dir = config_root / "workflows"
        self._cache: Dict[str, WorkflowDefinition] = {}
        self._index: Dict[str, Path] = {}
        self._build_index()

    def _build_index(self):
        """Scan all JSON files and map internal 'name' to file path."""
        if not self.workflows_dir.exists():
             return

        for file_path in self.workflows_dir.rglob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if "name" in data:
                    self._index[data["name"]] = file_path
                    # Also map filename stem as alias if unique
                    if file_path.stem not in self._index:
                         self._index[file_path.stem] = file_path
            except (json.JSONDecodeError, OSError):
                continue

    def load_workflow(self, name: str) -> WorkflowDefinition:
        """
        Load a workflow definition by name (Internal Name or Filename).
        """
        if name in self._cache:
            return self._cache[name]

        # Check Index
        if name not in self._index:
             # Try mapping "Impl.Feature" -> "feature_impl" manually if needed, 
             # but prefer the index finding "Impl.Feature" via internal name.
             raise FileNotFoundError(f"Workflow config not found for: {name}")

        file_path = self._index[name]
        
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            workflow = WorkflowDefinition(**data)
            self._cache[name] = workflow
            return workflow
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path}: {e}")
        except ValidationError as e:
            raise ValueError(f"Schema Validation Failed for {file_path}: {e}")
