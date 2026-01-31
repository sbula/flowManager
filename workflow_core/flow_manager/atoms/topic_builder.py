from typing import Dict, Any, List
from workflow_core.flow_manager.atoms.review_logic import Topic_Builder

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Adapter for Topic_Builder Atom.
    """
    atom = Topic_Builder()
    
    team = args.get("team", [])
    # Parse team if it's a string (Handle Python repr)
    if isinstance(team, str):
        import json
        import ast
        try:
            team = json.loads(team)
        except:
            try:
                team = ast.literal_eval(team)
            except:
                team = [team]

    review_context = args.get("context", "Analysis")
    
    return {"assignments": atom.execute(team, review_context)}
