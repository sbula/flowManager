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


def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates the context/state with a key-value pair.
    Args:
        args: {"key": "...", "value": "..."}
        context: The workflow context
    """
    key = args.get("key")
    value = args.get("value")

    if not key:
        return {"status": "FAILED", "error": "Missing 'key' argument"}

    # Is this 'Update State' meant to update the *context* passed to future steps?
    # Context in Engine is state.context_cache.
    # The Executor passes `context` (which is state.context_cache).
    # Since dicts are mutable, modifying it here DOES update the state.
    # BUT, the Engine might not propagate side-effects if it passes a copy?
    # Engine.py line 199: output = self.executor.execute_step(..., state.context_cache)
    # It passes the object reference.

    # However, logic in engine usually relies on `export` to update context.
    # Step definition:
    # "export": {"output_key": "context_key"}

    # If this Atom is purely side-effect based, it might directly modify context?
    # "Update_State" implies direct modification.

    context[key] = value

    return {"status": "COMPLETED", "updated_key": key, "new_value": value}
