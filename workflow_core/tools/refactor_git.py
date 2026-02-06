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

REGISTRY_PATH = Path("workflow_core/config/workflow_registry.json")
SCHEMA_PATH = Path("workflow_core/config/report_schema.json")


def refactor_git_bindings():
    with open(REGISTRY_PATH, "r") as f:
        registry = json.load(f)
    with open(SCHEMA_PATH, "r") as f:
        schema = json.load(f)

    # 1. Update WorkflowBindings: Move Impl.Git -> Git.Branch
    bindings = registry.get("WorkflowBindings", {})

    # Check if Impl exists and has Git
    impl_group = bindings.get("Impl", {})
    git_binding = None
    if "Git" in impl_group:
        git_binding = impl_group.pop("Git")

    # Create Git Group
    if "Git" not in bindings:
        bindings["Git"] = {}

    if git_binding:
        # Define Git.Branch (mapped from old Impl.Git)
        bindings["Git"]["Branch"] = git_binding.copy()
        bindings["Git"]["Branch"]["Description"] = "Git Branch Creation"
        bindings["Git"]["Branch"]["ExpertSet"] = "DevSquad"  # Ensure
        bindings["Git"]["Branch"][
            "TaskSet"
        ] = "GitBranchOps"  # New TaskSet? Or reuse FeatureSpec?

        # Define Git.Merge (New)
        bindings["Git"]["Merge"] = git_binding.copy()
        bindings["Git"]["Merge"]["Description"] = "Git Merge & Cleanup"
        bindings["Git"]["Merge"]["TaskSet"] = "GitMergeOps"  # New TaskSet

    # 2. Update Definitions
    # Remove Implementation.Git
    impl_def = registry.get("definitions", {}).get("Implementation", {})
    if "Git" in impl_def:
        del impl_def["Git"]

    # Add Git Definition
    registry["definitions"]["Git"] = {
        "Branch": {"name": "Branch Creation", "binding_ref": "Git.Branch"},
        "Merge": {"name": "Merge & Cleanup", "binding_ref": "Git.Merge"},
    }

    # 3. Update Schema TaskMappings
    mappings = schema.get("TaskMappings", {})
    if "Impl.Git" in mappings:
        del mappings["Impl.Git"]

    mappings["Git.Branch"] = {"Gate": "Git", "Level": "Branch"}
    mappings["Git.Merge"] = {"Gate": "Git", "Level": "Merge"}

    # 4. Add new TaskSets to Schema
    # Start with simple defaults
    schema["TaskSets"]["GitBranchOps"] = {
        "checklist": ["Verify Master Status", "Create Feature Branch", "Push Branch"],
        "command": None,
    }
    schema["TaskSets"]["GitMergeOps"] = {
        "checklist": ["Verify CI Status", "Squash & Merge", "Delete Remote Branch"],
        "command": None,
    }

    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=4)

    with open(SCHEMA_PATH, "w") as f:
        json.dump(schema, f, indent=4)

    print("Refactored Impl.Git -> Git.Branch/Merge")


if __name__ == "__main__":
    refactor_git_bindings()
