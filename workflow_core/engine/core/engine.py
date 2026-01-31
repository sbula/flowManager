import logging
import traceback
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime, timezone

from workflow_core.engine.schemas.models import (
    WorkflowState, WorkflowDefinition, WorkflowStep, StepState, StateStatus, StepType
)
from workflow_core.engine.core.state import PersistenceManager
from workflow_core.engine.core.loader import WorkflowLoader
from workflow_core.engine.core.executor import AtomExecutor

# Configure Logging (TODO: Centralize)
# logging.basicConfig(level=logging.INFO) <--- REMOVED SIDE EFFECT
logger = logging.getLogger("WorkflowEngine")

class WorkflowEngine:
    """
    The Core Workflow Engine V2.
    Orchestrates the execution of configured workflows.
    """

    def __init__(self, config_root: Path, state_root: Path = None):
        self.config_root = config_root
        # Default state root to project root if not provided
        self.state_root = state_root or config_root.parent.parent
        
        self.loader = WorkflowLoader(config_root)
        self.persistence = PersistenceManager(self.state_root)
        
        # Load Atoms Registry
        atoms_file = config_root / "atoms.json"
        if not atoms_file.exists():
            raise FileNotFoundError(f"Atoms registry missing at {atoms_file}")
            
        import json
        self.atoms_registry = json.loads(atoms_file.read_text(encoding="utf-8"))
        self.executor = AtomExecutor(self.atoms_registry)

    def _resolve_args(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolves `${var}` placeholders in arguments from context using Regex.
        Supports complex strings like "${dir}/${file}.txt".
        """
        import re
        
        def replace_match(match):
            key = match.group(1)
            
            # Support nested keys (e.g. config.root)
            parts = key.split('.')
            val = context
            try:
                for p in parts:
                    if isinstance(val, dict):
                        val = val.get(p)
                    else:
                        val = None
                        break
            except (AttributeError, TypeError):
                val = None

            # Fallback to direct key lookup (if key has dots but is stored flat)
            if val is None:
                val = context.get(key)
                
            return str(val) if val is not None else f"${{{key}}}"

        resolved = {}
        for k, v in args.items():
            if isinstance(v, str) and "${" in v:
                resolved[k] = re.sub(r'\$\{([a-zA-Z0-9_.]+)\}', replace_match, v)
            else:
                resolved[k] = v
        return resolved

    def _export_context(self, output: Dict[str, Any], export_map: Dict[str, str], context: Dict[str, Any]):
        """
        Maps step outputs to global context variables based on export definition.
        """
        if not export_map or not output:
            return
            
        for internal_key, context_key in export_map.items():
            if internal_key in output:
                val = output[internal_key]
                logger.info(f"Exporting Context: {context_key} = {val} (from {internal_key})")
                context[context_key] = val

    def _resolve_instructions(self, instructions: Optional[str], context: Dict[str, Any]) -> Optional[str]:
        """
        Resolves ${var} placeholders in the instructions string.
        """
        if not instructions:
            return None
            
        resolved = instructions
        # Simple string replacement for now. 
        # For more robust parsing we could use string.Template or regex.
        # But we need to handle "missing" keys gracefully (keep placeholder).
        import re
        
        def replace_match(match):
            key = match.group(1)
            return str(context.get(key, f"${{{key}}}"))
            
        # Regex to find ${key}
        resolved = re.sub(r'\$\{([a-zA-Z0-9_]+)\}', replace_match, instructions)
        return resolved

    def run_workflow(self, task_id: str, workflow_name: str, context: Dict[str, Any] = None) -> WorkflowState:
        """
        Main Entry Point.
        Executes the workflow for a given task_id.
        """
        context = context or {}
        
        # 1. Load or Initialize State
        state = self.persistence.load_state(task_id)
        if not state:
            logger.info(f"Initializing new state for Task {task_id} (Workflow: {workflow_name})")
            state = WorkflowState(
                task_id=task_id,
                workflow_ref=workflow_name,
                context_cache=context
            )
        else:
            # Verify Workflow Match (or Migration logic TODO)
            if state.workflow_ref != workflow_name:
                logger.warning(f"Workflow mismatch! State has {state.workflow_ref}, requested {workflow_name}. Using State.")
                workflow_name = state.workflow_ref
            
            # Merge Runtime Context (e.g. Config Injection)
            if context:
                state.context_cache.update(context)
        
        # Ensure Critical Task Variables are in Context
        state.context_cache["task_id"] = task_id
        state.context_cache["task_id_snake"] = task_id.replace('.', '_')

        # 2. Load Definition
        try:
            workflow_def = self.loader.load_workflow(workflow_name)
        except Exception as e:
            logger.error(f"Failed to load workflow {workflow_name}: {e}")
            raise

        # 3. Execution Loop
        try:
            self._execute_steps(state, workflow_def)
        except Exception as e:
            logger.error(f"Workflow Execution Failed: {e}")
            logger.debug(traceback.format_exc())
            # We do NOT save state on crash to avoid corruption, OR we save a "CRASHED" status?
            # Better to save partial progress if possible.
            # Here we just re-raise.
            raise
        finally:
            # 4. Persistence
            self.persistence.save_state(state)
            
        return state

    def _execute_steps(self, state: WorkflowState, workflow_def: WorkflowDefinition):
        """
        Internal loop to execute steps sequentially.
        """
        state.status = StateStatus.IN_PROGRESS
        total_steps = len(workflow_def.steps)
        
        while state.current_step_index < total_steps:
            step_def = workflow_def.steps[state.current_step_index]
            step_id = step_def.id
            
            # Check Step State
            step_state = state.steps_history.get(step_id)
            if not step_state:
                step_state = StepState(step_id=step_id, status=StateStatus.PENDING)
                state.steps_history[step_id] = step_state

            if step_state.status == StateStatus.COMPLETED:
                # Already done, move next
                state.current_step_index += 1
                continue
                
            # Execute
            logger.info(f"Executing Step: {step_id} ({step_def.type.value}: {step_def.ref})")
            step_state.status = StateStatus.IN_PROGRESS
            step_state.started_at = datetime.now(timezone.utc).isoformat()
            
            # DEBUG INJECTION
            ad = state.context_cache.get('artifact_dir')
            print(f">> [DEBUG] Step {step_id} Context artifact_dir: {ad}")
            
            try:
                # Resolve Args from Context
                resolved_args = self._resolve_args(step_def.args, state.context_cache)
                
                # Resolve Instructions (Prompt)
                resolved_instructions = self._resolve_instructions(step_def.instructions, state.context_cache)
                if resolved_instructions:
                    logger.info(f"Step Instructions: {resolved_instructions}")
                    # TODO: In a real interactive mode, this would be printed to the user/HUD.

                if step_def.type == StepType.ATOM:
                    # Pass RESOLVED args, not raw def args. 
                    # Note: AtomExecutor currently expects step_def. 
                    # We might need to construct a temporary step_def or pass args separately.
                    # Looking at executor.py (assumed), it likely reads step_def.args.
                    # Let's verify executor signatue. 
                    # self.executor.execute_step(step_def, state.context_cache)
                    # We should probably modify step_def.args in memory for this execution.
                    
                    # Create a standard copy with resolved args for execution
                    # Pydantic models are immutable-ish by default but we can use model_copy
                    # Also inject resolved instructions if the atom uses them (e.g. Wait_Approval)
                    update_dict = {"args": resolved_args}
                    if resolved_instructions:
                        update_dict["instructions"] = resolved_instructions
                        
                    step_def_runtime = step_def.model_copy(update=update_dict)
                    
                    output = self.executor.execute_step(step_def_runtime, state.context_cache)
                
                    # Check for Blocking Condition (e.g. Wait_Approval returns "WAITING")
                    if output.get("status") == "WAITING":
                        # Stop Execution, Persist State
                        logger.info(f"Workflow Blocked at {step_id}: {output.get('message')}")
                        step_state.output = output
                        return 
                        
                    step_state.output = output
                    step_state.status = StateStatus.COMPLETED
                    step_state.completed_at = datetime.now(timezone.utc).isoformat()
                    
                    # Export Outputs to Context
                    if step_def.export:
                        self._export_context(output, step_def.export, state.context_cache)

                    # Auto-Advance
                    state.current_step_index += 1
                
                elif step_def.type == StepType.WORKFLOW:
                    # Recursive Call
                    # Sub-Context: specific overrides from args + global context
                    # If args has {"foo": "bar"}, it overrides context["foo"]?
                    # Or is it strictly for the sub-workflow's 'external' interface?
                    # For now: Merge Global Context + Resolved Args
                    sub_context = {**state.context_cache, **resolved_args}
                    
                    sub_task_id = f"{state.task_id}#{step_id}"
                    sub_state = self.run_workflow(sub_task_id, step_def.ref, sub_context)
                    
                    if sub_state.current_step_index >= len(self.loader.load_workflow(step_def.ref).steps):
                            # Sub-workflow complete
                            # Logic: How do we get OUTPUT from a sub-workflow? 
                            # Maybe the sub-workflow state has an 'output' field? 
                            # Or we just assume side-effects? 
                            # For strict V2, we might want to export from sub-workflow context?
                            # TODO: Implement Sub-Workflow Output Mapping
                            
                            step_state.status = StateStatus.COMPLETED
                            state.current_step_index += 1
                    else:
                        # Sub-workflow blocked
                        logger.info(f"Sub-Workflow {step_def.ref} Blocked.")
                        return

            except Exception as e:
                state.status = StateStatus.FAILED
                step_state.status = StateStatus.FAILED
                step_state.error = str(e)
                logger.error(f"Step {step_id} Failed: {e}")
                raise e

        # If loop finishes, workflow is complete
        state.status = StateStatus.COMPLETED
