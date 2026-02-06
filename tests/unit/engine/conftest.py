import os
from pathlib import Path

import pytest

FLOW_DIR_NAME = ".flow"


@pytest.fixture
def clean_env(tmp_path):
    """Creates a clean temp directory."""
    return tmp_path


@pytest.fixture
def valid_project(clean_env):
    """Creates a valid project with .flow directory."""
    (clean_env / FLOW_DIR_NAME).mkdir()
    return clean_env
