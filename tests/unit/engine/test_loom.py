import pytest

from flow.engine.loom import Loom, LoomError
from flow.engine.models import SecurityError


def test_t6_01_surgical_insert(tmp_path):
    """T6.01 Surgical Insert: After anchor."""
    f = tmp_path / "code.py"
    f.write_text("def foo():\n    pass\n", encoding="utf-8")

    loom = Loom(project_root=tmp_path)
    # Pass relative path string, as agents would.
    loom.insert("code.py", anchor="pass", content="    print('hi')")

    assert "    pass\n    print('hi')" in f.read_text("utf-8")


def test_t6_02_ambiguous_anchor(tmp_path):
    """T6.02 Ambiguous Anchor: Fail Safe."""
    f = tmp_path / "ambiguous.py"
    f.write_text("def foo():\n    pass\n\ndef bar():\n    pass\n", encoding="utf-8")

    loom = Loom(project_root=tmp_path)

    with pytest.raises(LoomError, match="Ambiguous anchor"):
        loom.insert("ambiguous.py", anchor="pass", content="print('hi')")


def test_t6_03_loom_vs_writefile(tmp_path):
    """T6.03 Loom explicit permission/Project Scope check (simplified)."""
    # Context usually restricts write_file. Loom enforces scope.
    # Here we test Loom blocking writes outside root.

    loom = Loom(project_root=tmp_path)

    # Outside file (Absolute path)
    external = tmp_path.parent / "external.txt"
    # Create via os to avoid FileNotFoundError during open if not exists,
    # but Loom should block path first.

    with pytest.raises(SecurityError):
        # We pass absolute path of external file
        loom.insert(str(external), "anchor", "content")


def test_t6_05_anchor_not_found(tmp_path):
    """T6.05 Anchor Not Found: Fail Safe."""
    f = tmp_path / "missing.py"
    f.write_text("print('hello')", encoding="utf-8")

    loom = Loom(project_root=tmp_path)
    with pytest.raises(LoomError, match="Anchor not found"):
        loom.insert("missing.py", anchor="godot", content="wont happen")


def test_t6_04_loom_project_scope(tmp_path):
    """T6.04 Loom Project Scope: Whitelist check."""
    # Input: Agent attempts Loom.edit("src/main.py").
    # Expect: ALLOWED (if path in Whitelist).
    # Loom defaults to allowing anything inside root.

    f = tmp_path / "src" / "main.py"
    f.parent.mkdir()
    f.write_text("anchor", encoding="utf-8")

    loom = Loom(project_root=tmp_path)

    # Should allow
    loom.insert("src/main.py", anchor="anchor", content="inserted")
    assert "inserted" in f.read_text("utf-8")

    # Should block outside (Already tested in T6.03, but explicit here)
    with pytest.raises(SecurityError):
        loom.insert("../outside.py", "anchor", "content")
