import json

import pytest

from src.flow.engine.config_loader import ConfigLoader


@pytest.fixture
def config_loader():
    return ConfigLoader()


def test_load_default_config(config_loader, tmp_path):
    """Verify loading defaults when no config file exists."""
    config = config_loader.load_config(tmp_path)
    assert config["security"]["isolation_level"] == "STRICT"


def test_load_custom_config(config_loader, tmp_path):
    """Verify loading custom config."""
    flow_dir = tmp_path / ".flow"
    flow_dir.mkdir()
    (flow_dir / "config.json").write_text(
        json.dumps({"security": {"isolation_level": "RELAXED"}})
    )

    config = config_loader.load_config(tmp_path)
    assert config["security"]["isolation_level"] == "RELAXED"


def test_load_invalid_json(config_loader, tmp_path):
    """Verify error handling for invalid JSON."""
    flow_dir = tmp_path / ".flow"
    flow_dir.mkdir()
    (flow_dir / "config.json").write_text("{invalid_json}")

    # Should fall back to default or raise?
    # Robustness says log error and use default.
    config = config_loader.load_config(tmp_path)
    assert config["security"]["isolation_level"] == "STRICT"
