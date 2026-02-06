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

from pathlib import Path
from typing import Any, Dict


def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Checks if a target file contains a specific marker.
    Returns:
        {"status": "DONE"} if found.
        {"status": "WAITING", "message": "..."} if not found.
    """
    target_file = args.get("target_file")
    marker = args.get("marker")

    if not target_file or not marker:
        return {"status": "FAILED", "message": "Missing arguments"}

    path = Path(target_file)
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        return {
            "status": "WAITING",
            "message": f"File {target_file} does not exist yet.",
        }

    content = path.read_text(encoding="utf-8")

    if marker == "*" or marker in content:
        return {"status": "DONE", "message": f"Found marker '{marker}'"}
    else:
        return {
            "status": "WAITING",
            "message": f"Waiting for '{marker}' in {target_file}",
        }
