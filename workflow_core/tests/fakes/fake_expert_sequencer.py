from typing import Dict, Any, List
import json
import logging

logger = logging.getLogger("flow_manager.atoms.expert_sequencer.FAKE")

def load_json_config(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    V8 Expert Sequencer FAKE.
    Iterates through 'assignments' (Role -> [Topics]) and executes review.
    For Verification/Dry-Run, this mocks the expert feedback.
    """
    logger.warning("!!! RUNNING FAKE EXPERT SEQUENCER (FOR TESTING ONLY) !!!")
    # V8 Argument Resolution
    assignments = args.get("assignments")
    review_object = args.get("object") or args.get("review_file") or "Unknown Object"
    review_context = args.get("context", "General Review")

    # Legacy / Compat Mode: "expert_set"
    if not assignments and args.get("expert_set"):
        expert_set_name = args.get("expert_set")
        try:
            import os
            config_path = os.path.join(os.getcwd(), 'workflow_core/config/core_teams.json')
            
            # Helper to load config (Inline for now or import)
            team_data = load_json_config(config_path)
                
            experts = team_data.get("ExpertSets", {}).get(expert_set_name, [])
            if not experts:
                logger.warning(f"Expert Set {expert_set_name} not found or empty.")
            
            # Generate default assignments
            assignments = {role: ["General Review"] for role in experts}
            logger.info(f"Resolved Legacy Expert Set '{expert_set_name}' to: {list(assignments.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to resolve expert_set: {e}")
            assignments = {}

    if not assignments:
        assignments = {}
    
    # Handle string input for assignments (JSON or Python repr)
    if isinstance(assignments, str):
        import ast
        try:
            assignments = json.loads(assignments)
        except:
            try:
                assignments = ast.literal_eval(assignments)
            except:
                logger.warning(f"Failed to parse assignments: {assignments}")
                assignments = {}

    results = {}
    
    logger.info(f"Starting {review_context} Review on {review_object}...")
    
    global_status = "APPROVED"
    
    for role, topics in assignments.items():
        logger.info(f">> Expert: {role}")
        logger.info(f"   Topics: {topics}")
        
        # Mock Feedback Logic
        # allow testing negative flows
        if "TRIGGER_REJECT" in topics:
            status = "REQUEST_CHANGES"
            feedback = f"As {role}, I found CRITICAL ISSUES in {review_object}."
            global_status = "REQUEST_CHANGES"
        else:
            status = "APPROVED"
            feedback = f"As a {role}, I have reviewed {review_object} focusing on {topics}. Status: APPROVED."

        results[role] = {
            "status": status,
            "feedback": feedback
        }
        
    return {"review_results": results, "status": global_status}
