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

import importlib
import json
import sys
from pathlib import Path


def validate_config():
    print(">> [V7 Config Check] Starting...")

    root = Path(__file__).parent.parent / "config"
    has_errors = False

    # 1. Validate Atoms Registry
    atoms_file = root / "atoms.json"
    if not atoms_file.exists():
        print("!! atoms.json missing")
        return False

    try:
        atoms_data = json.loads(atoms_file.read_text(encoding="utf-8"))
        atoms_registry = atoms_data.get("Atoms", {})
        print(f">> Loaded {len(atoms_registry)} Atoms")

        # 1.1 Deep Validation: Import Check
        print("   >> Verifying Atom Implementations...")
        for atom_name, atom_def in atoms_registry.items():
            module_path = atom_def.get("python_module")
            if not module_path:
                print(f"   X Atom '{atom_name}': Missing 'python_module' definition")
                has_errors = True
                continue

            try:
                importlib.import_module(module_path)
                # print(f"      OK: {atom_name} -> {module_path}") # Auto-suppress success noise
            except (ImportError, ModuleNotFoundError) as e:
                print(
                    f"   X Atom '{atom_name}': Import Failed for '{module_path}'\n     Error: {e}"
                )
                has_errors = True

    except Exception as e:
        print(f"!! XML/JSON Error in atoms.json: {e}")
        return False

    # 2. Validate Workflows
    workflows_dir = root / "workflows"
    if not workflows_dir.exists():
        print("!! workflows directory missing")
        return False

    for wf_file in workflows_dir.glob("*.json"):
        try:
            wf_data = json.loads(wf_file.read_text(encoding="utf-8"))
            steps = wf_data.get("steps", [])
            print(f">> Validating Workflow: {wf_file.name} ({len(steps)} steps)")

            for step in steps:
                step_id = step.get("id")
                atom_ref = step.get("atom")

                if atom_ref and atom_ref not in atoms_registry:
                    print(f"   X Step {step_id}: Unknown Atom '{atom_ref}'")
                    has_errors = True

                # Check Prompt Existence?
                args = step.get("args", {})
                tpl = args.get("prompt_template")
                if tpl and "${config.prompts}" in tpl:
                    # Resolve path approximation
                    rel_path = tpl.replace("${config.prompts}", "").lstrip("/")
                    prompt_path = root / "prompts" / rel_path
                    if not prompt_path.exists():
                        print(f"   X Step {step_id}: Missing Prompt File '{rel_path}'")
                        has_errors = True

        except Exception as e:
            print(f"!! Error parsing {wf_file.name}: {e}")
            has_errors = True

    if has_errors:
        print("\n!! Validation Failed")
        return False
    else:
        print("\n>> Validation Passed")
        return True


if __name__ == "__main__":
    if not validate_config():
        sys.exit(1)
