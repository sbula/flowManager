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

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from workflow_core.core.context.models import StatusFile, Task
from workflow_core.core.context.status_reader import StatusReader
from workflow_core.infrastructure.config.loader import FlowConfig
from workflow_core.infrastructure.logging import get_logger

logger = get_logger("ContextManager")


class ContextManager:
    def __init__(self, config: FlowConfig, reader: StatusReader):
        self.config = config
        self.reader = reader

    def get_current_context(self) -> Dict[str, Any]:
        """
        Returns full context: active task, workflow mode, etc.
        """
        status_file = self.reader.parse()
        active_task = status_file.get_active_task()

        workflow = "Phase.Planning"
        task_id = None

        if active_task:
            task_id = active_task.id
            workflow = self._determine_workflow(active_task.name)
            logger.info(f"Active Task Detected: {task_id} -> {workflow}")

        # Resolve Artifact Directory
        status_path = Path(status_file.file_path)
        if active_task:
            artifact_dir = self._resolve_artifact_dir(status_path, active_task)
        else:
            artifact_dir = status_path.parent

        # Return relative path string for cleaner context usage if possible,
        # but absolute path is safer for file operations.
        # Let's return absolute path as string (or Path object? JSON serialization might need string)

        return {
            "status_file": str(status_file.file_path),
            "active_task": active_task,
            "workflow": workflow,
            "task_id": task_id,
            "task_id_snake": task_id.replace(".", "_") if task_id else None,
            "artifact_dir": str(artifact_dir),
        }

    def _determine_workflow(self, task_name: str) -> str:
        """
        Smart Dispatch: Name -> Prefix -> Workflow
        """
        # Cleanup Markdown (Bold/Italic/Code)
        clean_name = task_name.strip("*_ `")

        # Extract prefix: "Impl.Feature: ..." -> "Impl.Feature"
        import re

        match = re.match(r"^([A-Za-z]+(?:\.[A-Za-z]+)?)(?::|\s)", clean_name)
        if not match:
            # Check if the entire first word is a known prefix (e.g. "Workflow Core...")
            first_word = clean_name.split(" ")[0]
            # We will check this first_word against config below
            prefix = first_word
        else:
            prefix = match.group(1)

        # Check Execution
        for p in self.config.prefixes.get("execution", []):
            if prefix.startswith(p):
                return "Phase.Execution"

        # Check Planning
        for p in self.config.prefixes.get("planning", []):
            if prefix.startswith(p):
                return "Phase.Planning"

        if self.config.strict_mode:
            raise ValueError(f"Unknown Prefix '{prefix}' in Strict Mode.")

        return "Phase.Planning"

    def reset_task(self, task_id: str) -> bool:
        """
        Resets task to [ ] and cleans up artifacts/state.
        """
        # 1. Verify existence
        status_file = self.reader.parse()
        task = status_file.get_task_by_id(task_id)
        if not task:
            logger.error(f"Task {task_id} not found.")
            return False

        # 2. Cleanup Artifacts & State
        status_path = Path(status_file.file_path)
        # We need the task object to resolve the directory!
        # StatusFile.get_task_by_id returns the task model with indentation,
        # but we need to trace hierarchy.
        # However, for reset, we might just want to be aggressive OR specific.
        # If we use _resolve_artifact_dir, we need the "full" task context (parent links potentially?)
        # Current Task model doesn't have parent links.
        # But _resolve_artifact_dir logic (implemented below) will use ID parsing.

        artifact_dir = self._resolve_artifact_dir(status_path, task)
        self._cleanup_resources(task_id, status_path, artifact_dir)

        # 3. Update file
        path = Path(status_file.file_path)  # type: ignore
        return self.reader.update_status(path, task_id, " ")

    def _cleanup_resources(self, task_id: str, status_path: Path, artifact_dir: Path):
        """
        Deletes generated artifacts and state files.
        """
        task_id_snake = task_id.replace(".", "_")
        root = (
            self.config.root if hasattr(self.config, "root") else Path.cwd()
        )  # Fallback

        logger.info(f"Cleaning updates for Task {task_id} in {artifact_dir}...")

        # A. Artifacts (Heuristic: *{id}_*)
        # Scope: Artifact Directory (Recursive? No, usually flat in the resolved dir)
        if artifact_dir.exists():
            artifacts = list(artifact_dir.glob(f"*{task_id_snake}_*"))
            for art in artifacts:
                if art.is_file():
                    try:
                        art.unlink()
                        logger.info(f"Deleted Artifact: {art.name}")
                    except Exception as e:
                        logger.error(f"Failed to delete {art.name}: {e}")

        # B. State Files (.flow_state/{id}*)
        state_dir = root / ".flow_state"
        if state_dir.exists():
            states = list(state_dir.glob(f"{task_id_snake}*"))
            for st in states:
                try:
                    st.unlink()
                    logger.info(f"Deleted State: {st.name}")
                except Exception as e:
                    logger.error(f"Failed to delete {st.name}: {e}")

    def _resolve_artifact_dir(self, status_path: Path, task: Task) -> Path:
        """
        Resolves the target directory for artifacts based on Task Hierarchy.
        Logic:
        1. Parse Task ID (e.g. 3.2.1)
        2. Identify Root ID (3)
        3. Search status_path.parent (e.g. phase5) for matching directory (3_*)
        4. If found, return it. Else return status_path.parent
        """
        try:
            # 1. Extract Root ID
            # ID format: "3", "3.1", "3.1.1"
            parts = task.id.split(".")
            if not parts:
                return status_path.parent

            root_id = parts[0]

            # 2. Search for matching directory in the status file's folder
            phase_dir = status_path.parent
            if not phase_dir.exists():
                return phase_dir

            # glob for directories starting with "{root_id}_"
            # e.g. "3_Refactor_Market_Price_Service"
            # ENHANCEMENT: Strict ID Check to avoid matching "4_3_..." when looking for "4"
            candidates = [
                p
                for p in phase_dir.iterdir()
                if p.is_dir() and p.name.startswith(f"{root_id}_")
            ]

            matches = []
            for c in candidates:
                # Split "4_Refactor..." -> "4"
                # Split "4_3_Signal..." -> "4" but next char is number? No, check strict split.
                # Naming Convention: {ID}_{Name}
                # If ID is "4", candidate matches if parts[0] == "4" AND parts[1] is NOT numeric part of ID

                # Simpler: The "ID" part of the folder is everything up to the first underscore that is NOT a digit?
                # No, standard is {id}_{snake_case_name}. ID usually has dots replaced by underscores ONLY if deep.
                # BUT Top Level Folders usually follow Status Root IDs.

                # Check 1: exact string match of prefix
                parts = c.name.split("_")
                if parts and parts[0] == root_id:
                    # Check if it is "4_3" (which implies root ID 4.3 or sub-directory)
                    # If we are looking for "4", "4_Refactor" splits to ["4", "Refactor"]. "Refactor" is not digit.
                    # "4_3_Signal" splits to ["4", "3", "Signal"]. "3" IS digit.

                    if len(parts) > 1 and parts[1].isdigit():
                        continue

                    matches.append(c)

            if matches:
                # Return the first match (Ambiguity should be avoided by strict naming)
                logger.debug(f"Resolved Artifact Dir for Task {task.id}: {matches[0]}")
                return matches[0]

            # Fallback
            return phase_dir

        except Exception as e:
            logger.error(f"Error resolving artifact dir: {e}")
            return status_path.parent
