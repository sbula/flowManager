import subprocess
import shlex
from typing import Dict, Any
from pathlib import Path

def run(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a shell command.
    """
    command_str = args.get("command")
    cwd = args.get("cwd", ".")
    
    if not command_str:
         return {"status": "FAILED", "message": "No command specified"}

    # Resolve CWD
    root = Path.cwd()
    work_dir = root / cwd
    
    try:
        # Security: Shlex split to avoid shell injection if using shell=False (Recommended)
        # But for complex commands (pipes), shell=True might be needed or explicit sequence.
        # User requirement implies specific commands like "poetry run pytest ..."
        
        # Split command
        args_list = shlex.split(command_str)
        
        result = subprocess.run(
            args_list,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            check=False # We handle return code manually
        )
        
        if result.returncode == 0:
            status = "DONE"
            msg = "Command Succeeded"
        else:
            status = "FAILED"
            msg = f"Command Failed (Exit Code {result.returncode})"

        # Output Capture
        output_file = args.get("output_file")
        if output_file:
            o_path = Path(output_file)
            if not o_path.is_absolute():
                o_path = Path.cwd() / o_path
            
            o_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Format Output for Markdown Report
            desc = args.get("description", "Command Output")
            import datetime
            timestamp = datetime.datetime.now().isoformat()
            
            # Read existing to append safely?
            mode = args.get("output_mode", "append")
            write_mode = "a" if mode == "append" else "w"
            
            with open(o_path, write_mode, encoding="utf-8") as f:
                f.write(f"\n\n## {desc}\n")
                f.write(f"> Executed: `{command_str}` at {timestamp}\n")
                f.write(f"> Status: {status}\n\n")
                
                if result.stdout:
                    f.write("```\n")
                    f.write(result.stdout)
                    f.write("\n```\n")
                
                if result.stderr:
                    f.write("**Standard Error**:\n```\n")
                    f.write(result.stderr)
                    f.write("\n```\n")
                    
        return {
            "status": status, 
            "message": msg,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
            
    except Exception as e:
        return {"status": "FAILED", "message": str(e)}
