import json
from pathlib import Path
from typing import Dict, Any, List
from pydantic import BaseModel, Field

# Using Pydantic for Config Validation (Strong typing)
class FlowConfig(BaseModel):
    root_markers: List[str]
    prefixes: Dict[str, List[str]]
    status_files: List[str]
    backup_count: int = 3
    strict_mode: bool = True

class ConfigLoader:
    def __init__(self, config_root: Path):
        self.config_root = config_root
        self.config_path = config_root / "flow_config.json"

    def load_config(self) -> FlowConfig:
        """
        Loads and validates flow_config.json.
        Raises FileNotFoundError if missing (Proposal A: Ironclad Config).
        """
        if not self.config_path.exists():
            # STRICT MODE: No templates, no fallbacks.
            raise FileNotFoundError(
                f"CRITICAL: Flow Configuration missing at {self.config_path}. "
                "System halted to prevent undefined behavior."
            )

        try:
            content = self.config_path.read_text(encoding='utf-8')
            data = json.loads(content)
            return FlowConfig(**data)
        except json.JSONDecodeError as e:
            raise ValueError(f"CRITICAL: Invalid JSON in flow_config.json: {e}")
        except Exception as e:
            raise ValueError(f"CRITICAL: Configuration validation failed: {e}")
