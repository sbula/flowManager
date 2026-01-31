import argparse
import sys
import logging
from logging.handlers import RotatingFileHandler
import re
from pathlib import Path
import shutil

# Ensure workflow_core is in path if running as script, but prefer module execution
if __name__ == "__main__":
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from workflow_core.engine.core.engine import WorkflowEngine
from workflow_core.flow_manager.status_parser import StatusParser, StatusParsingError

def main():
    parser = argparse.ArgumentParser(description="Gemini Flow Manager V7")
    parser.add_argument("command", choices=["start", "resume", "reopen", "status", "reset", "validate"], nargs="?", default="start")
    parser.add_argument("task_id", nargs="?", default=None)
    parser.add_argument("--force-workflow", help="Override the detected workflow", default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configuration Root
    config_root = Path(__file__).parent.parent / "config"
    log_file = Path(__file__).parent.parent.parent / "flow.log"
    
    
    # Configure Logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    
    # [V7] Log Rotation: 5MB limit, 3 backups
    file_handler = RotatingFileHandler(
        str(log_file), 
        maxBytes=5*1024*1024, 
        backupCount=3, 
        encoding='utf-8'
    )
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            file_handler
        ]
    )
    logger = logging.getLogger("flow_manager")
    
    # Initialize Components
    # StatusParser now finds root automatically via config/markers
    status_parser = StatusParser()
    engine = WorkflowEngine(config_root)
    
    try:
        # 0. Validate Command
        if args.command == "validate":
            try:
                # 1. Status Check
                status_parser.validate_structure()
                print("\n>> [V7 Status] Valid.")
                
                # 2. System Config Check (Proposal B)
                from workflow_core.validators.system_validator import validate_config
                print(">> [V7 System] Verifying Configuration...")
                if not validate_config():
                    print("!! [V7 System] Configuration Errors Detected!")
                    sys.exit(1)
                
                # Also check active context to show what would happen
                ctx = status_parser.get_active_context()
                print(f"   Active Task: {ctx.get('id', 'None')} - {ctx.get('name', 'None')}")
                print(f"   Workflow: {ctx.get('workflow', 'None')}")
                return
            except StatusParsingError as e:
                print(f"\n!! [V7] Validation Failed: {e}")
                sys.exit(1)

        # [V7] Enforce Validation for all execution commands
        # We don't want to run on a corrupt state.
        if args.command in ["start", "resume", "status"]:
             try:
                 status_parser.validate_structure()
             except StatusParsingError as e:
                 logger.error(f"Status file validation failed: {e}")
                 print(f"\n!! [V7] Validation Failed: {e}")
                 print("   Run 'bash flow_manager.sh validate' for details.")
                 sys.exit(1)

        # 1. Status Command
        if args.command == "status":
            ctx = status_parser.get_active_context()
            print_status(ctx)
            return

        # 2. Reset Command
        if args.command == "reset":
            if not args.task_id:
                # If no ID, try to get active task
                ctx = status_parser.get_active_context()
                if ctx.get("status") == "in_progress":
                    args.task_id = ctx["id"]
                else:
                    logger.error("No active task to reset. Provide a Task ID.")
                    sys.exit(1)
            
            logger.info(f"Resetting task {args.task_id}...")
            if perform_reset(args.task_id, status_parser):
                 print(f"\n>> [V7] Task {args.task_id} reset successfully.")
            else:
                 print(f"\n!! [V7] Failed to reset task {args.task_id}.")
            return

        # 3. Determine Context & Workflow
        active_ctx = status_parser.get_active_context()
        target_task_id = resolve_task_id(args, active_ctx)
        
        if args.force_workflow:
            workflow_name = args.force_workflow
        else:
            workflow_name = determine_workflow(args.command, active_ctx, target_task_id, status_parser)

        print("\n>> [V7] Flow Manager Active")
        print(f">> Task: {target_task_id}")
        print(f">> Workflow: {workflow_name}")
        
        # 4. Execute Workflow
        engine.run_workflow(target_task_id, workflow_name)
        print("\n>> [V7] Workflow Execution Complete.")

    except Exception as e:
        logger.exception("Workflow failed")
        print(f"\n!! [V7] Workflow Failed: {e}")
        sys.exit(1)

def print_status(active_ctx: dict):
    print("\n>> [V7] Status Check")
    if "error" in active_ctx:
        print(f"!! Error: {active_ctx['error']}")
        return
        
    file_path = active_ctx.get('file', 'Not Found')
    task_info = f"{active_ctx.get('id', 'None')} - {active_ctx.get('name', 'None')}"
    workflow = f"Detected Mode: {active_ctx.get('workflow', 'None')}"
    
    print(f"   File: {file_path}")
    print(f"   Active Task: {task_info}")
    print(f"   {workflow}")

def resolve_task_id(args, active_ctx: dict) -> str:
    if args.task_id:
        return args.task_id
    if active_ctx.get("status") == "in_progress":
        return active_ctx["id"]
    return "current_task"

def determine_workflow(command: str, active_ctx: dict, task_id: str, parser: StatusParser) -> str:
    """
    Determines workflow based on command and Smart Dispatch (Prefixes).
    """
    if command == "start":
        return "Phase.Planning"
        
    # Resume/Reopen -> Trust the prefix from status parser
    if active_ctx.get("status") == "in_progress":
        return active_ctx.get("workflow", "Phase.Planning")
            
    return "Phase.Planning"

def perform_reset(task_id: str, parser: StatusParser) -> bool:
    """
    Resets a task status to [ ] in status.md.
    """
    if not parser.status_file:
        return False
        
    content = parser.status_file.read_text(encoding='utf-8')
    lines = content.splitlines()
    new_lines = []
    found = False
    
    # Regex for finding the task line to reset.
    # Must match indentation, marker, ID (with optional dot), and rest.
    escaped_id = re.escape(task_id)
    # Pattern: indent - [marker] ID(dot?) rest
    pattern = re.compile(rf"^(\s*)- \[(.| )\] {escaped_id}(\.?)\s+(.*)")
    
    for line in lines:
        match = pattern.match(line)
        if match:
             # Found the line. Force mark to [ ]
             new_line = line.replace("- [/]", "- [ ]").replace("- [x]", "- [ ]")
             new_lines.append(new_line)
             found = True
        else:
            new_lines.append(line)
            
    if found:
        # Backup Rotation
        backup_count = parser.config.get("backup_count", 3)
        base = parser.status_file
        
        # Shift existing backups: .bak.(N-1) -> .bak.N
        # Start from max-1 down to 1
        for i in range(backup_count - 1, 0, -1):
            src = base.with_suffix(f".md.bak.{i}")
            if i == backup_count - 1:
                # If we are shifting the last one, it gets overwritten or deleted? 
                # Actually, let's just shift simple.
                pass
            
            # Logic: move bak.2 -> bak.3
            src = base.with_suffix(f".md.bak.{i}")
            dst = base.with_suffix(f".md.bak.{i+1}")
            if src.exists():
                shutil.move(src, dst)
        
        # Shift .bak -> .bak.1
        first_backup = base.with_suffix(".md.bak")
        if first_backup.exists():
             shutil.move(first_backup, base.with_suffix(".md.bak.1"))
        
        # Create new .bak
        shutil.copy(base, first_backup)
        
        parser.status_file.write_text("\n".join(new_lines), encoding='utf-8')
        return True
        
    return False

if __name__ == "__main__":
    main()
