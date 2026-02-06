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

from typing import Any, Dict, List

from workflow_core.flow_manager.atoms.review_logic import Topic_Builder


def run(args: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Adapter for Topic_Builder Atom.
    """
    atom = Topic_Builder()

    team = args.get("team", [])
    # Parse team if it's a string (Handle Python repr)
    if isinstance(team, str):
        import ast
        import json

        try:
            team = json.loads(team)
        except:
            try:
                team = ast.literal_eval(team)
            except:
                team = [team]

    review_context = args.get("context", "Analysis")

    return {"assignments": atom.execute(team, review_context)}
