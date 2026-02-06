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

from typing import Any, Dict

from workflow_core.flow_manager.atoms.review_logic import Team_Builder


def run(args: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Adapter for Team_Builder Atom.
    Args:
        tags: List[str] (Parsed from context or args)
        context: str (Review Context e.g. "Analysis")
    """
    atom = Team_Builder()

    # Handle direct args or injection
    tags = args.get("tags", [])
    if isinstance(tags, str):
        # Determine if it's a JSON string or need parsing
        import ast
        import json

        try:
            tags = json.loads(tags)
        except:
            try:
                tags = ast.literal_eval(tags)
            except:
                tags = [tags]

    # If tags passed as "list" object from engine context, it might be list

    review_context = args.get("context", "Analysis")

    return {"team": atom.execute(tags, review_context)}
