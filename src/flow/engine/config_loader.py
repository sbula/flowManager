import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Loads project configuration from .flow/config.json.
    """
    DEFAULT_CONFIG = {
        "security": {
            "isolation_level": "STRICT",
            "allowed_tools": ["all"],
        },
        "limits": {
            "max_file_size": 1024 * 1024 * 5,  # 5MB
            "timeout_seconds": 300
        }
    }

    def load_config(self, project_root: Path) -> Dict[str, Any]:
        """
        Load config from project root, merging with defaults.
        """
        config_path = project_root / ".flow" / "config.json"

        if not config_path.exists():
            return self.DEFAULT_CONFIG.copy()

        try:
            content = config_path.read_text(encoding="utf-8")
            user_config = json.loads(content)

            # Deep merge could be implemented here, but for V1 simple update
            # We start with default and overlay user config
            config = self.DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {config_path}. Using defaults.")
            return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return self.DEFAULT_CONFIG.copy()
