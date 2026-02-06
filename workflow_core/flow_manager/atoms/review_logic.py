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
import os
import pathlib
from typing import Any, Dict, List, Set


# Helper to mock config loading
def load_json_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class Team_Builder:
    def execute(self, tags: List[str], context: str) -> List[str]:
        config_path = os.path.join(os.getcwd(), "workflow_core/config/modules.json")
        data = load_json_config(config_path)

        team: Set[str] = set()

        for module in data.get("Modules", []):
            if module.get("Type") != "Expert":
                continue

            role = module.get("Role")
            activation = module.get("Activation", {})
            activations = []
            if isinstance(activation, list):
                activations = activation
            else:
                activations = [activation]

            is_active = False
            for act in activations:
                # 1. Always Active
                if act.get("Always"):
                    is_active = True
                    break

                # 2. Tag Activation
                module_tags = set(act.get("Tags", []))
                if module_tags.intersection(tags):
                    is_active = True
                    break

                # 3. Context/TaskType Activation
                task_types = act.get("TaskTypes", [])
                if context in task_types:
                    is_active = True
                    break

            if is_active:
                team.add(role)

        return list(team)


class Topic_Builder:
    def execute(self, team: List[str], context: str) -> Dict[str, List[str]]:
        config_path = os.path.join(os.getcwd(), "workflow_core/config/core_topics.json")
        data = load_json_config(config_path)

        assignments: Dict[str, List[str]] = {role: [] for role in team}

        for topic, criteria in data.get("TopicResponsibilities", {}).items():
            # Support V8 Schema (Dict with Roles/Contexts) and Legacy (List of Roles)
            if isinstance(criteria, list):
                roles = criteria
                contexts = ["All"]
            else:
                roles = criteria.get("Roles", [])
                contexts = criteria.get("Contexts", ["All"])

            # Check Context Filter
            # Matches if "All" is present OR context matches exactly OR context matches a partial key?
            # Proposal: "Code" matches "Code", "All" matches everything.
            if "All" not in contexts and context not in contexts:
                continue

            # Assign to Roles
            for role in roles:
                if role in team:
                    assignments[role].append(topic)

        return assignments


class Artifact_Resolver:
    def execute(self, task_id: str, root_path: str) -> str:
        parts = task_id.split(".")
        if len(parts) < 2:
            return root_path

        # Parent ID logic: 4.3.5 -> 4.3 -> "4_3" prefix
        parent_id = f"{parts[0]}.{parts[1]}"
        prefix = parent_id.replace(".", "_")

        if not os.path.exists(root_path):
            return root_path

        # Scan for matching folder
        with os.scandir(root_path) as it:
            for entry in it:
                if entry.is_dir() and entry.name.startswith(prefix):
                    return entry.path

        return root_path
