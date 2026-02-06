import os
from pathlib import Path
from unittest.mock import patch

import pytest

from flow.engine.core import Engine
from flow.engine.models import RegistryError, RootNotFoundError, SecurityError
from flow.engine.security import SafePath

# Constants for Testing
FLOW_DIR_NAME = ".flow"

# Constants for Testing
FLOW_DIR_NAME = ".flow"
# Fixtures moved to conftest.py


def test_t1_01_root_discovery_standard(valid_project):
    """T1.01 Root Discovery (Standard): CWD is strictly inside .flow/."""
    # Run from root
    os.chdir(valid_project)
    engine = Engine()
    engine.hydrate()
    assert engine.root == valid_project
    assert engine.flow_dir == valid_project / FLOW_DIR_NAME


def test_t1_02_root_missing_strict(clean_env):
    """T1.02 Root Missing (Strict): CWD has no .flow/."""
    os.chdir(clean_env)
    engine = Engine()
    with pytest.raises(RootNotFoundError):
        engine.hydrate()


def test_t1_03_path_resolution_safe(valid_project):
    """T1.03 Path Resolution (Safe): Resolves paths relative to root."""
    root = valid_project
    safe = SafePath(root, "subdir/file.txt")
    expected = root / "subdir" / "file.txt"
    assert safe == expected


def test_t1_04_jailbreak_attempt_parent(valid_project):
    """T1.04 Jailbreak Attempt (Parent): .. traversal."""
    root = valid_project
    with pytest.raises(SecurityError):
        SafePath(root, "../../etc/passwd")


def test_t1_05_jailbreak_attempt_symlink(valid_project):
    """T1.05 Jailbreak Attempt (Symlink): escape via symlink."""
    root = valid_project
    # Create a symlink pointing outside
    external = valid_project.parent / "external_secret.txt"
    external.touch()

    link = valid_project / "bad_link"
    try:
        link.symlink_to(external)
    except OSError:
        pytest.skip("Symlinks not supported on this OS/Permission")

    with pytest.raises(SecurityError):
        SafePath(root, "bad_link")


def test_t1_15_windows_device_paths(valid_project):
    """T1.15 Windows Device Paths."""
    root = valid_project
    with pytest.raises(SecurityError):
        SafePath(root, "CON")


def test_t1_06_explicit_registry_loading(valid_project):
    """T1.06 Explicit Registry Loading: Atom loaded successfully."""
    # Create valid registry
    registry_path = valid_project / FLOW_DIR_NAME / "flow.registry.json"
    # Use real class to pass integrity check
    registry_path.write_text(
        '{"git": "flow.engine.atoms.ManualInterventionAtom"}', encoding="utf-8"
    )

    os.chdir(valid_project)
    engine = Engine()
    engine.hydrate()

    assert "git" in engine.registry_map
    assert engine.registry_map["git"] == "flow.engine.atoms.ManualInterventionAtom"


def test_t1_17_registry_validation_failure(valid_project):
    """T1.17 Registry Validation Failure: Integrity check."""
    registry_path = valid_project / FLOW_DIR_NAME / "flow.registry.json"
    registry_path.write_text('{"ghost": "flow.ghost.Atom"}', encoding="utf-8")

    os.chdir(valid_project)
    engine = Engine()

    with pytest.raises(RegistryError, match="Registry Integrity Failed"):
        engine.hydrate()


def test_t1_07_unregistered_atom(valid_project):
    """T1.07 Unregistered Atom: Cannot be dispatched."""
    registry_path = valid_project / FLOW_DIR_NAME / "flow.registry.json"
    registry_path.write_text("{}", encoding="utf-8")  # Empty registry

    os.chdir(valid_project)
    engine = Engine()
    engine.hydrate()

    assert "malware" not in engine.registry_map

    # Try to resolve generic/unknown
    with pytest.raises(RegistryError):
        engine.get_atom_class("malware")


def test_t1_09_root_is_file(clean_env):
    """T1.09 Root Is File: InvalidRootError."""
    (clean_env / FLOW_DIR_NAME).touch()  # It's a file
    os.chdir(clean_env)
    engine = Engine()

    with pytest.raises(RootNotFoundError, match="is not a directory"):
        engine.hydrate()


def test_t1_12_null_byte_path(valid_project):
    """T1.12 Null Byte Path."""
    cwd = valid_project
    # SafePath check
    with pytest.raises(SecurityError, match="Null byte"):
        SafePath(cwd, "file\0.txt")


def test_t1_16_unc_path_injection(valid_project):
    """T1.16 UNC Path Injection."""
    # Windows specific: \\Server\Share
    # SafePath should block assuming it is absolute or outside root.
    cwd = valid_project
    path = "\\\\Server\\Share\\File"
    with pytest.raises(SecurityError):
        SafePath(cwd, path)


def test_t1_08_root_symlink_loop_real(tmp_path):
    """T1.08 Root Symlink Loop (Real): Verify NO Hang."""
    # Create loop: root/link -> root
    root = tmp_path / "root"
    root.mkdir()
    (root / ".flow").mkdir()

    link = root / "loop"

    try:
        # Symlink creation might fail on Windows without Admin/DevMode
        link.symlink_to(root)
    except OSError:
        pytest.skip("Symlinks not supported in this environment")
        return

    os.chdir(link)
    engine = Engine()
    engine.hydrate()

    # It should resolve the real path
    assert engine.root.resolve() == root.resolve()


def test_t1_08_root_symlink_loop_simulated(tmp_path):
    """T1.08 Root Symlink Loop (Simulated): Verify Logic catches recursion."""
    engine = Engine()

    # We need to handle:
    # 1. hydrate() -> cwd.resolve()  (Must Succeed)
    # 2. hydrate() -> candidate.resolve() (Must Fail with Recursion/Loop)

    def mock_resolve(strict=False):
        # We can distinguish based on the path instance, but simpler is sequential.
        # However, 'self' is not passed to side_effect if it's a function on instance?
        # Actually side_effect receives args/kwargs.
        # But we mocked the method on the class. Mocks replace the method.
        # The first arg to the method is 'self' (the path instance).
        pass

    # Easier approach: side_effect as list.
    # First call: returns strict path (cwd)
    # Second call: raises RuntimeError

    # But wait, cwd.resolve() changes the path.
    # We can just return 'tmp_path' for the first call.

    with patch("pathlib.Path.resolve", side_effect=[tmp_path, RuntimeError("Loop")]):
        # We need to ensure exists() returns True so it tries to resolve
        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(RootNotFoundError, match="Symlink loop"):
                # Force hydration scan
                engine.hydrate()
