from typing import Dict, Any
from pathlib import Path

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Checks if a target file contains a specific marker.
    Returns:
        {"status": "DONE"} if found.
        {"status": "WAITING", "message": "..."} if not found.
    """
    target_file = args.get("target_file")
    marker = args.get("marker")
    
    if not target_file or not marker:
        return {"status": "FAILED", "message": "Missing arguments"}

    path = Path(target_file)
    if not path.is_absolute():
        path = Path.cwd() / path
        
    if not path.exists():
        return {"status": "WAITING", "message": f"File {target_file} does not exist yet."}
        
    content = path.read_text(encoding="utf-8")
    
    if marker == "*" or marker in content:
        return {"status": "DONE", "message": f"Found marker '{marker}'"}
    else:
        return {"status": "WAITING", "message": f"Waiting for '{marker}' in {target_file}"}
