from typing import Dict, Any
from workflow_core.flow_manager.atoms.review_logic import Team_Builder

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Adapter for Team_Builder Atom.
    Args:
        tags: List[str] (Parsed from context or args)
        context: str (Review Context e.g. "Analysis")
    """
    atom = Team_Builder()
    
    # Handle direct args or injection
    tags = args.get("tags", [])
    if isinstance(tags, str):
        # Determine if it's a JSON string or need parsing
        import json
        import ast
        try:
            tags = json.loads(tags)
        except:
             try:
                 tags = ast.literal_eval(tags)
             except:
                 tags = [tags]
             
    # If tags passed as "list" object from engine context, it might be list
    
    review_context = args.get("context", "Analysis")
    
    return {"team": atom.execute(tags, review_context)}
