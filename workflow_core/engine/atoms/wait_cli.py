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

import sys
from typing import Any, Dict


def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pauses workflow execution for User Confirmation via CLI.
    Useful for transitions like Draft -> Review where no file artifact is desired.
    """
    message = args.get("message", "Continue?")

    # Check if running in non-interactive mode (e.g. CI)
    # For now, we assume interactive if this atom is used.

    print(f"\n>> INTERACTION REQUIRED: {message} [y/N]")
    try:
        response = input(">> ").strip().lower()
    except EOFError:
        return {"status": "WAITING", "message": "Input stream closed."}

    if response == "y":
        return {"status": "DONE", "message": "User confirmed."}
    else:
        return {"status": "WAITING", "message": "User deferred execution."}
