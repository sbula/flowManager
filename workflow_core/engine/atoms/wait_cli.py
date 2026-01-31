from typing import Dict, Any
import sys

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pauses workflow execution for User Confirmation via CLI.
    Useful for transitions like Draft -> Review where no file artifact is desired.
    """
    message = args.get("message", "Continue?")
    
    # Check if running in non-interactive mode (e.g. CI)
    # For now, we assume interactive if this atom is used.
    
    print(f"\n>> INTERACTION REQUIRED: {message} [y/N]")
    try:
        response = input(">> ").strip().lower()
    except EOFError:
        return {"status": "WAITING", "message": "Input stream closed."}
        
    if response == 'y':
        return {"status": "DONE", "message": "User confirmed."}
    else:
        return {"status": "WAITING", "message": "User deferred execution."}
