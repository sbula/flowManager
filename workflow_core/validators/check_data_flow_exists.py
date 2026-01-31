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
from pathlib import Path
import os

def check_data_flow_exists():
    # Locate phase folder
    status_path_env = os.environ.get("GEMINI_STATUS_FILE")
    if status_path_env:
        status_path = Path(status_path_env)
        phase_dir = status_path.parent
    else:
        # Fallback
        cwd = Path.cwd()
        phase_dir = cwd / "design" / "roadmap" / "phases" / "phase5"

    target = phase_dir / "data_flow_map.md"
    
    if target.exists():
        # Optional: Check content size or keywords?
        # Let's ensure it's not empty
        if target.stat().st_size > 100:
            print(f">> SUCCESS: Found {target.name}")
            return 0
        else:
            print(f"!! FAILURE: {target.name} is too small / empty.")
            return 1
    else:
        print(f"!! FAILURE: Missing {target}")
        print(f"!! Expected at: {target}")
        return 1

if __name__ == "__main__":
    sys.exit(check_data_flow_exists())
