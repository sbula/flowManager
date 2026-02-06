import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flow.engine.atoms import AtomResult, LoomAtom
from flow.engine.loom import Loom


@pytest.fixture
def mock_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / ".flow").mkdir()
    return root


def test_loom_atom_insert_success(mock_root):
    # Setup
    flow_dir = mock_root / ".flow"
    op_file = flow_dir / "op.json"
    op_file.write_text(
        json.dumps(
            {
                "op": "insert",
                "path": "target.py",
                "anchor": "ANCHOR",
                "content": "INSERTED",
            }
        ),
        encoding="utf-8",
    )

    target = mock_root / "target.py"
    target.write_text("ANCHOR\n", encoding="utf-8")

    context = {"__root__": mock_root, "__task_ref__": "op.json"}

    atom = LoomAtom()
    result = atom.run(context)

    assert result.success
    assert "INSERTED" in target.read_text("utf-8")


def test_loom_atom_missing_ref(mock_root):
    context = {"__root__": mock_root}  # No ref
    atom = LoomAtom()
    result = atom.run(context)
    assert not result.success
    assert "requires a 'ref'" in result.message


def test_loom_atom_missing_root():
    context = {"__task_ref__": "op.json"}
    atom = LoomAtom()
    result = atom.run(context)
    assert not result.success
    assert "Root context missing" in result.message


def test_loom_atom_security_boundary(mock_root):
    # Reference outside .flow
    context = {"__root__": mock_root, "__task_ref__": "../op.json"}
    atom = LoomAtom()
    result = atom.run(context)
    assert not result.success
    assert "Loom Error" in result.message or "SecurityError" in result.message
