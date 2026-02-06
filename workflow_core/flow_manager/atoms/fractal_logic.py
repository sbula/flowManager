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
from pathlib import Path
from typing import Any, Dict, List


class Context_Loader:
    """
    Parses a Markdown Plan to extract Fractal Metadata and Action Items.
    Expected Headers:
    - Level: int
    - Parent-Link: relative_path
    """

    def execute(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        target_file = Path(args.get("target_file"))

        # In test/mock scenarios we might read from a stub if file doesn't exist,
        # but here we follow the standard pattern of reading the file.
        # The test patches Path.read_text, so this is fine.
        content = target_file.read_text(encoding="utf-8")

        # 1. Parse Headers
        # Support both Legacy "Level: 1" and New "> **Planning Level**: 1"
        level_match = re.search(
            r"(?:Level:|> \*\*Planning Level\**:)\s*(\d+)", content, re.MULTILINE
        )

        # Parent Link is now optional or part of "Top Down" context
        parent_match = re.search(
            r"(?:Parent-Link:|> \*\*Parent\**:)\s*\[.*?\]\((.*?)\)",
            content,
            re.MULTILINE,
        )

        if not level_match:
            raise ValueError("Missing required Fractal Header: Level")

        fractal_level = int(level_match.group(1))
        parent_link = parent_match.group(1) if parent_match else None

        # 2. Extract Action Items
        # Pattern: - **[ACTION] Title**: Description
        actions = []
        for line in content.splitlines():
            m = re.match(r"^\s*-\s*\*\*\[ACTION\]\s*(.*?)\*\*:", line)
            if m:
                actions.append(m.group(1).strip())

        return {
            "fractal_level": fractal_level,
            "parent_link": parent_link,
            "action_items": actions,
            "raw_content": content,
        }


class Recursive_Planner:
    """
    Generates a Child Plan based on a Parent Plan's Action Item.
    """

    def _generate_content(self, prompt: str) -> str:
        # This would call the LLM in production.
        # For TDD, this method is mocked.
        raise NotImplementedError("LLM Generation not implemented")

    def execute(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        parent_file = Path(args.get("parent_artifact"))
        parent_level = int(args.get("parent_level"))
        action_item = args.get("action_item")

        child_level = parent_level + 1
        # Resolve parent link relative to child (simple heuristic for now)
        link_to_parent = f"../{parent_file.name}"

        content = self._generate_content(
            f"Create Level {child_level} plan for: {action_item}"
        )

        # In a real scenario, we'd determine the child filename dynamically
        child_filename = f"Child_Plan_L{child_level}.md"
        child_path = parent_file.parent / child_filename

        child_path.write_text(content, encoding="utf-8")

        return {
            "child_level": child_level,
            "child_parent_link": link_to_parent,
            "child_path": str(child_path),
        }
