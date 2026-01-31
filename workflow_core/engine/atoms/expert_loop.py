from typing import List, Dict, Any, Union
from workflow_core.engine.atoms import prompt, agent

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Iterates through experts, prompting the agent for each, and aggregating results.
    """
    experts: List[str] = args.get("experts", [])
    mode: str = args.get("mode", "research")
    prompt_template: Union[str, Any] = args.get("prompt_template")
    loop_context: Dict[str, Any] = args.get("context", {}) # Use args context, not global context?
    # Context injection from args is usually preferred for specific variables.
    
    results = {}
    blocked = False
    

    for expert_role in experts:
        # 1. Prepare Context (Inject Role)
        iteration_ctx = loop_context.copy()
        iteration_ctx["role"] = expert_role
        
        # 2. Render Prompt
        # Assuming prompt_template is a string template for now, or we might load file atom internally?
        # To keep it simple, we assume the caller passed the TEMPLATE STRING or we use a basic resolver.
        # If it's a file path string, we should handle it? 
        # For simplicity in this atom, we expect `prompt_template` to be the template string content 
        # OR we rely on a higher level loader. 
        # But wait, atoms are low level. Let's assume input is template content for maximum flexibility OR path.
        # For now, let's treat it as template content string to match test expectation "dummy_template".
        
        prompt_text = prompt.render_string(str(prompt_template), iteration_ctx)
        
        # 3. Query Agent
        response = agent.query(prompt_text)
        results[expert_role] = response
        
        # 4. Logic for Review Mode
        if mode == "review":
            if "[ ]" in response or "Reject" in response:
                blocked = True

    if mode == "review":
        return {
            "status": "BLOCKED" if blocked else "PASSED",
            "results": results
        }
    
    return {"results": results}
