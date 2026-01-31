# Copyright 2026 Steve Bula @ pitBula
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import sys
from pathlib import Path
import logging

from workflow_core.infrastructure.logging import setup_logger
from workflow_core.infrastructure.config.loader import ConfigLoader
from workflow_core.core.context.status_reader import StatusReader
from workflow_core.core.context.context_manager import ContextManager
from workflow_core.engine.core.engine import WorkflowEngine

# Setup Logger immediately for boot
logger = setup_logger()

def main():
    parser = argparse.ArgumentParser(description="Gemini Flow Manager V7")
    parser.add_argument("command", choices=["start", "resume", "reopen", "status", "reset", "validate"], nargs="?", default="start")
    parser.add_argument("task_id", nargs="?", default=None)
    parser.add_argument("--force-workflow", help="Override the detected workflow", default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
        
    try:
        # 1. Infrastructure Boot
        root = Path.cwd()
        # Assume we are at repo root. 
        # Config is in workflow_core/config
        config_root = root / "workflow_core" / "config"
        
        config_loader = ConfigLoader(config_root)
        config = config_loader.load_config()
        
        # 2. Context Initialization
        status_reader = StatusReader(config, root)
        context_manager = ContextManager(config, status_reader)
        
        # 3. Engine Initialization
        engine = WorkflowEngine(config_root)
        
        # 4. Command Dispatch
        if args.command == "validate":
            logger.info("Running System Validation...")
            # 1. Config Check (Implicitly done by loader)
            logger.info("[V7] Configuration: OK")
            
            # 2. Status Structure Check
            try:
                msg = status_reader.parse()
                logger.info(f"[V7] Status File ({msg.file_path}): OK")
                print("\n>> [V7 Status] Valid.")
            except Exception as e:
                logger.error(f"[V7] Status Validation Failed: {e}")
                sys.exit(1)
                
            # 3. Context Check
            ctx = context_manager.get_current_context()
            print(f"   Active Task: {ctx.get('task_id', 'None')}")
            print(f"   Workflow: {ctx.get('workflow', 'None')}")
            return

        # For specific commands, ensure status valid
        if args.command in ["start", "resume", "status"]:
             status_reader.parse()

        if args.command == "status":
            ctx = context_manager.get_current_context()
            print("\n>> [V7] Status Check")
            print(f"   Active Task: {ctx.get('task_id', 'None')}")
            print(f"   Workflow: {ctx.get('workflow', 'None')}")
            return

        if args.command == "reset":
            if not args.task_id:
                # Try to infer active
                ctx = context_manager.get_current_context()
                if ctx.get('task_id'):
                    args.task_id = ctx['task_id']
                else:
                    logger.error("No active task to reset. Provide a Task ID.")
                    sys.exit(1)
            
            if context_manager.reset_task(args.task_id):
                print(f"\n>> [V7] Task {args.task_id} reset successfully.")
            else:
                 print(f"\n!! [V7] Failed to reset task {args.task_id}.")
            return

        # Execution Commands (start, resume, reopen)
        ctx = context_manager.get_current_context()
        
        target_task_id = args.task_id
        if not target_task_id and ctx.get('active_task'):
             target_task_id = ctx['active_task'].id
        
        if not target_task_id:
             # If "start" without ID, maybe pick next pending?
             # For now, strict: require ID
             # Or engine handles it? Dictionary says "picks next pending".
             # Let's keep it simple: Require ID or Active.
             logger.info("No Task ID provided. Searching for pending tasks...")
             status = status_reader.parse()
             for t in status.tasks:
                 if not t.is_completed and not t.is_active:
                     target_task_id = t.id
                     print(f">> Auto-Selecting Pending Task: {t.id} - {t.name}")
                     break
        
        if not target_task_id:
            logger.error("No Target Task ID found.")
            sys.exit(1)

        # Determine Workflow
        workflow_name = args.force_workflow
        if not workflow_name:
            if ctx.get('active_task') and ctx['active_task'].id == target_task_id:
                workflow_name = ctx['workflow']
            else:
                # Get task definition
                status = status_reader.parse()
                task = status.get_task_by_id(target_task_id)
                if task:
                    workflow_name = context_manager._determine_workflow(task.name)
                else:
                    logger.error(f"Task {target_task_id} not found in status file.")
                    sys.exit(1)

        print(f"\n>> [V7] Executing Task {target_task_id}")
        print(f">> Workflow: {workflow_name}")
        
        # Run Engine
        # Inject Initial Context (Config, Paths)
        # Convert Pydantic config to dict if needed, or just specific keys
        initial_context = config.dict()
        initial_context["root"] = str(root)
        initial_context["prefixes"] = config.prefixes # explicit
        
        # Get Active Status File Path
        try:
             status_obj = status_reader.parse()
             initial_context["status_file"] = str(status_obj.file_path)
        except:
             initial_context["status_file"] = str(root / "status.md") # Fallback

        # Merge with context manager context (task info)
        initial_context.update(ctx)
        
        # We nest config under "config" key?
        # planning.json uses ${config.root}. So we need a "config" dict in context.
        # Let's restructure.
        engine_context = {
            "config": {
                "root": str(root),
                "prompts": str(config_root.parent / "templates" / "prompts"), # Heuristic or Configured?
                **config.dict()
            },
            **ctx
        }
        
        engine.run_workflow(target_task_id, workflow_name, context=engine_context)
        print("\n>> [V7] Workflow Execution Complete.")

    except Exception as e:
        logger.exception("System Failure")
        sys.exit(1)

if __name__ == "__main__":
    main()
