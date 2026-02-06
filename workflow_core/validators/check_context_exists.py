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

import os
import sys
from pathlib import Path


def check_context_exists():
    # 1. Resolve Phase Directory from status.md path or CWD
    # Assumption: We run this from project root, and status.md is at design/roadmap/phases/phaseX/status.md
    # We need to find the active phase folder.

    cwd = Path.cwd()

    # Try to find status.md to locate phase folder
    status_path = os.environ.get("GEMINI_STATUS_FILE")
    if not status_path:
        # scan for active phase in design/roadmap/phases
        # This is a bit weak, but for now let's assume valid standard path
        base = cwd / "design" / "roadmap" / "phases"
        if not base.exists():
            print("!! Error: Cannot locate design/roadmap/phases")
            return 1

        phase_dirs = sorted(
            [d for d in base.iterdir() if d.is_dir() and "phase" in d.name]
        )
        if not phase_dirs:
            print("!! Error: No phase directories found.")
            return 1

        # Optimization: assume the last phase is the active one?
        # Or checking env var is safer. Flow Manager sets it?
        # flow_manager.sh sets GEMINI_STATUS_FILE.
        # But if running python directly, we might miss it.
        # However, check_context_exists.py is called BY flow_manager, which sets the env var?
        # Actually flow_manager (python) reads it. subprocess inherits env? Yes.
        pass

    if status_path:
        phase_dir = Path(status_path).parent
    else:
        # Fallback: Assume phase5 for this session or search
        # We really rely on the environment or the CWD being correct if passed
        # But commonly we run from root.
        print("!! Warning: GEMINI_STATUS_FILE not set. Attempting to infer phase.")
        phase_dir = (
            cwd / "design" / "roadmap" / "phases" / "phase5"
        )  # Hardcoded fallback for reliability in this specific task

    target = phase_dir / "context_brief.md"

    if target.exists():
        print(f">> SUCCESS: Found {target.name}")
        return 0
    else:
        print(f"!! FAILURE: Missing {target}")
        print(f"!! Expected at: {target}")
        return 1


if __name__ == "__main__":
    sys.exit(check_context_exists())
