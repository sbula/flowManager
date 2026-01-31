import subprocess
from typing import Dict, Any
from pathlib import Path

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes Git operations.
    Args:
        action: "commit", "push", "commit_push"
        message: Commit message
        files: List of files to add (default: ".")
    """
    action = args.get("action", "status")
    message = args.get("message", "chore: update")
    files = args.get("files", ".") # Default stage all
    
    if action not in ["commit", "push", "commit_push", "status"]:
        return {"status": "FAILED", "message": f"Unknown Git Action: {action}"}

    # Helper to run git
    def git(*cmd_args):
        return subprocess.run(
            ["git"] + list(cmd_args),
            capture_output=True,
            text=True,
            check=False
        )

    if action == "status":
        res = git("status")
        return {"status": "DONE", "stdout": res.stdout}

    if action in ["commit", "commit_push"]:
        # Add
        if isinstance(files, list):
            git("add", *files)
        else:
            git("add", files)
            
        # Commit
        # TODO: Inject Signed logic if needed
        res = git("commit", "-m", message)
        if res.returncode != 0 and "nothing to commit" not in res.stdout:
             return {"status": "FAILED", "message": "Commit Failed", "stderr": res.stderr}
        
    if action in ["push", "commit_push"]:
        # Push
        res = git("push")
        if res.returncode != 0:
            return {"status": "FAILED", "message": "Push Failed", "stderr": res.stderr}

    return {"status": "DONE", "message": f"Git {action} completed."}
