from typing import Dict, Any
from workflow_core.flow_manager.atoms.review_logic import Artifact_Resolver

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Adapter for Artifact_Resolver Atom.
    """
    atom = Artifact_Resolver()
    
    # In CLI usages, we might pass direct args.
    # In workflow usage, we might rely on context variables.
    
    task_id = args.get("task_id", context.get("task_id"))
    root_path = args.get("root_path", context.get("root"))
    
    # If root_path is not passed, try to infer from context config
    if not root_path and "config" in context and "root" in context["config"]:
        root_path = context["config"]["root"]
        
    return atom.execute(task_id, root_path)
