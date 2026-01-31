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
from typing import Dict, Any
from workflow_core.engine.schemas.models import WorkflowStep, StepType

class AtomExecutor:
    """Executes Atomic Tasks by mapping them to Python functions."""
    
    def __init__(self, atoms_registry: Dict[str, Any]):
        self.registry = atoms_registry

    def execute_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single atomic step.
        Returns the output dictionarly.
        """
        if step.type != StepType.ATOM:
            raise ValueError(f"AtomExecutor cannot execute step type: {step.type}")

        atom_def = self.registry.get("Atoms", {}).get(step.ref)
        if not atom_def:
            raise ValueError(f"Unknown Atom Reference: {step.ref}")

        module_name = atom_def.get("python_module")
        if not module_name:
             # Fallback for testing/mocking if no module defined
             return {"status": "MOCKED", "message": f"Executed {step.ref}"}

        try:
            # Dynamic Import
            module = importlib.import_module(module_name)
            if not hasattr(module, "run"):
                 raise AttributeError(f"Module {module_name} missing 'run' function")
            
            # Merit arguments: Step Args override Default Args
            # Interpolation Logic
            final_args = {}
            for k, v in step.args.items():
                if isinstance(v, str):
                    try:
                        # Allow interpolation from context
                        final_args[k] = v.format(**context)
                    except KeyError:
                        # If context key missing, leave as is or fail?
                        # Best effort: leave as is if format fails?
                        # Or safe_substitute? .format() raises KeyError.
                        # Let's fallback to original string to avoid complex crashes
                        final_args[k] = v
                else:
                    final_args[k] = v
            
            # Execute
            result = module.run(final_args, context)
            return result
            
        except ImportError as e:
            raise ImportError(f"Failed to load atom module {module_name}: {e}")
        except Exception as e:
            raise RuntimeError(f"Atom Execution Failed: {e}")
