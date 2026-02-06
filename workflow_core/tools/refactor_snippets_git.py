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


def refactor_git_snippets():
    with open(REGISTRY_PATH, "r") as f:
        registry = json.load(f)

    snippets = registry.get("Snippets", {})
    impl_snippets = snippets.get("Impl", {})

    # Check if Impl.Git snippet exists
    if "Git" in impl_snippets:
        git_snippets = impl_snippets.pop("Git")

        # Create top-level Git snippet group
        if "Git" not in snippets:
            snippets["Git"] = {}

        # Assign to Git.Branch
        snippets["Git"]["Branch"] = git_snippets

        # Add placeholder for Git.Merge
        snippets["Git"]["Merge"] = [
            {
                "Title": "Git Merge Operation",
                "Ref": "handbook/protocols/status/execution_rules.md",
                "Text": "1. Verify all tests pass.\n2. Squash & Merge to Master.\n3. Delete local and remote feature branch.",
            }
        ]

    # Clean up empty Impl group if needed (though it has Feature/Fix likely)
    if not impl_snippets:
        del snippets["Impl"]

    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=4)

    print("Refactored Snippets: Impl.Git -> Git.Branch/Merge")


if __name__ == "__main__":
    refactor_git_snippets()
