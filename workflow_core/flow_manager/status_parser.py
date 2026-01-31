import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Set

class StatusParsingError(Exception):
    pass

class StatusParser:
    def __init__(self, start_path: Optional[Path] = None, config_root: Optional[Path] = None):
        self.config_root = config_root or (Path(__file__).parent.parent / "config")
        self.config = self._load_config()
        # If start_path not provided, valid defaults might be CWD or this file's location
        start = start_path or Path.cwd()
        self.root = self._find_root(start)
        self.status_file = self._find_status_file()

    def _load_config(self) -> Dict[str, Any]:
        """Loads flow_config.json from config directory."""
        # workflow_core/config/flow_config.json
        config_path = self.config_root / "flow_config.json"
        
        if config_path.exists():
            # [V7] Hardening: Let JSON errors propagate to crash early on bad config
            return json.loads(config_path.read_text(encoding='utf-8'))
            
        # [V7] Hardening: Source of Truth = Config Template
        # Try to load from templates/default_flow_config.json
        # templates dir is sibling to config dir
        templates_dir = self.config_root.parent / "templates"
        template_path = templates_dir / "default_flow_config.json"
        
        if template_path.exists():
             try:
                 content = template_path.read_text(encoding='utf-8')
                 # Save as new config
                 self.config_root.mkdir(parents=True, exist_ok=True)
                 config_path.write_text(content, encoding='utf-8')
                 logging.getLogger("flow_manager").info(f"Generated config from template at {config_path}")
                 return json.loads(content)
             except Exception as e:
                 logging.getLogger("flow_manager").warning(f"Failed to generate config from template: {e}")
        
        if not self.config_root.exists():
            # Try to populate if directory completely missing? 
            # Actually, just throwing error is "Hard Failure".
            pass

        raise RuntimeError(f"Flow Config missing at {config_path} and could not be generated from template {template_path}. System Halted.")

    def _find_root(self, start_path: Path) -> Path:
        """
        Robustly finds the repository root by looking for markers.
        """
        markers = self.config.get("root_markers", [])
        current = start_path.resolve()
        
        # Security: Limit traversal depth to avoid hitting system root inappropriately
        for _ in range(15):
            if any((current / m).exists() for m in markers):
                return current
            
            parent = current.parent
            if parent == current: # Reached filesystem root
                break
            current = parent
            
        raise FileNotFoundError(f"Repository root not found. Searched up from {start_path} looking for {markers}")

    def _find_status_file(self) -> Optional[Path]:
        """
        Finds status.md based on configured paths.
        """
        candidates = self.config.get("status_files", [])
        
        # Priority 1: Configured relative paths
        for c in candidates:
            p = self.root / c
            if p.exists():
                return p
        
        # Priority 2: Recursive search (fallback)
        logger = logging.getLogger("flow_manager")
        for p in self.root.rglob("status.md"):
            logger.warning(f"Status file not found in configured paths. Falling back to recursive search found: {p}")
            return p
            
        return None

    def validate_structure(self) -> None:
        """
        Strictly validates the status file structure.
        Raises StatusParsingError if invalid.
        """
        if not self.status_file:
            raise StatusParsingError("No status.md found")

        content = self.status_file.read_text(encoding='utf-8')
        lines = content.splitlines()
        
        # Regex for valid task line: "- [ ] 1.2.3 Rest"
        # Groups: 1=indent, 2=mark, 3=id, 4=rest
        task_pattern = re.compile(r"^(\s*)- \[(.| )\] (\d+(?:\.\d+)*)\.?\s+(.*)")
        
        active_tasks = []
        seen_ids = set()
        
        for i, line in enumerate(lines):
            line_num = i + 1
            if not line.strip():
                continue
                
            match = task_pattern.match(line)
            if match:
                indent, mark, task_id, rest = match.groups()
                
                # Rule 1: Indentation (warn only for now, strict later?)
                if len(indent) % 2 != 0:
                    pass # lax for now
                
                # Rule 2: Duplicate IDs
                if task_id in seen_ids:
                    raise StatusParsingError(f"Line {line_num}: Duplicate Task ID '{task_id}'")
                seen_ids.add(task_id)
                
                # Rule 3: Active Task Uniqueness
                if mark == "/":
                    active_tasks.append((task_id, line_num))

                # Rule 4: Prefix Validation (Strict)
                if mark == "/" or mark == "x": 
                    # We check active or recently completed? 
                    # Strict validation mostly matters for active tasks to fail fast.
                    # Let's stick to active tasks for now to avoid breaking history.
                    if mark == "/":
                        name = rest.strip()
                        prefix = self._extract_prefix(name)
                        if not prefix:
                             # If no prefix found (e.g. just "Do check"), and we expect Strictness?
                             if self.config.get("strict_mode", False):
                                 raise StatusParsingError(f"Line {line_num}: Strict Mode enforced. Task must have a valid prefix (e.g. 'Impl.Feature: ...'). Found: '{name}'")
                             pass
                             # But sticking to the user request: "cross-reference ... and raise warning/error if [prefix] is unknown".
                             # This implies we have a prefix. If we don't have one, that's also an issue?
                        
                        if prefix:
                            self._validate_prefix_defined(prefix, line_num)
                    
        # Rule 3 Check
        if len(active_tasks) > 1:
            raise StatusParsingError(f"Multiple active tasks found: {active_tasks}. context slicing requires single-task focus.")

    def _validate_prefix_defined(self, prefix: str, line_num: int):
        """
        Checks if the prefix matches any defined category in config.
        """
        prefixes = self.config.get("prefixes", {})
        
        # Flatten lists
        valid_prefixes = []
        for cat_list in prefixes.values():
            if isinstance(cat_list, list):
                valid_prefixes.extend(cat_list)
        
        # Check if prefix starts with any valid prefix
        # e.g. prefix="Impl.Feature", valid="Impl" -> OK
        found = False
        for valid in valid_prefixes:
            if prefix.startswith(valid):
                found = True
                break
                
        if not found:
            raise StatusParsingError(f"Line {line_num}: Unknown prefix '{prefix}'. Defined: {valid_prefixes}")

    def get_active_context(self) -> Dict[str, Any]:
        """
        Parses the status file to find the active task ([/]).
        Returns enriched context with Smart Dispatch (workflow mode).
        """
        if not self.status_file:
            return {"error": "No status.md found", "workflow": "Phase.Planning"}

        # Validate first (Fail Fast)
        try:
            self.validate_structure()
        except StatusParsingError as e:
            return {"error": str(e), "workflow": "Phase.Planning"}

        content = self.status_file.read_text(encoding='utf-8')
        lines = content.splitlines()
        
        task_pattern = re.compile(r"^(\s*)- \[\/\] (\d+(?:\.\d+)*)\.?\s+(.*)")
        
        for line in lines:
            match = task_pattern.match(line)
            if match:
                indent, task_id, raw_name = match.groups()
                name = raw_name.strip()
                
                prefix = self._extract_prefix(name)
                workflow = self._determine_workflow(prefix)
                
                return {
                    "id": task_id,
                    "name": name,
                    "prefix": prefix,
                    "status": "in_progress",
                    "file": self.status_file,
                    "workflow": workflow
                }
        
        return {"status": "idle", "file": self.status_file, "workflow": "Phase.Planning"}

    def _extract_prefix(self, name: str) -> Optional[str]:
        # e.g. "Impl.Feature: Create ..." -> prefix="Impl.Feature"
        # Also supports simple "Impl: ..."
        prefix_match = re.match(r"^([A-Za-z]+(?:\.[A-Za-z]+)?)(?::|\s)", name)
        return prefix_match.group(1) if prefix_match else None

    def _determine_workflow(self, prefix: Optional[str]) -> str:
        """
        Smart Dispatch Logic using Config.
        """
        if not prefix:
            if self.config.get("strict_mode", False):
                raise StatusParsingError("Strict Mode: Task must have a prefix to determine workflow.")
            return "Phase.Planning"
            
        prefixes = self.config.get("prefixes", {})
        planning_list = prefixes.get("planning", [])
        execution_list = prefixes.get("execution", [])
        
        # Check Execution first (specifics)
        for p in execution_list:
            if prefix.startswith(p):
                return "Phase.Execution"
                
        # Check Planning
        for p in planning_list:
            if prefix.startswith(p):
                return "Phase.Planning"
            
        # [V7] Hardening: Strict Mode
        strict = self.config.get("strict_mode", False)
        if strict:
            raise StatusParsingError(f"Strict Mode: Unknown prefix '{prefix}'. Defined: {list(prefixes.keys())}")

        # Defaults to Planning if unknown
        logger = logging.getLogger("flow_manager")
        logger.warning(f"Unknown prefix '{prefix}'. Defaulting to Planning Mode.")
        return "Phase.Planning"

    def get_task_by_id(self, task_id: str) -> Dict[str, Any]:
        """
        Finds a specific task by ID.
        """
        if not self.status_file:
            return {"error": "No status.md found"}

        content = self.status_file.read_text(encoding='utf-8')
        lines = content.splitlines()
        
        escaped_id = re.escape(task_id)
        pattern = re.compile(rf"^(\s*)- \[(.)\] ({escaped_id})\.?\s+(.*)")
        
        for line in lines:
            match = pattern.match(line)
            if match:
                return {
                    "id": match.group(3),
                    "name": match.group(4).strip(),
                    "mark": match.group(2),
                    "file": self.status_file
                }
        return None
