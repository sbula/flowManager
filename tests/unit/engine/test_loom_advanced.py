import os
import time

import pytest

from flow.engine.loom import Loom, LoomError


def test_t6_06_whitespace_mismatch(tmp_path):
    """T6.06 Whitespace Mismatch: Anchor has spaces, File has Tabs."""
    f = tmp_path / "tab.py"
    f.write_text("def foo():\n\tpass\n", encoding="utf-8")

    loom = Loom(project_root=tmp_path)
    # Current implementation is strict. Should fail.
    # Future: Fuzzy match.
    with pytest.raises(LoomError, match="Anchor not found"):
        loom.insert("tab.py", anchor="    pass", content="print('hi')")


def test_t6_07_loom_encoding_latin1(tmp_path):
    """T6.07 Loom Encoding (Latin1)."""
    f = tmp_path / "latin.txt"
    f.write_bytes(b"caf\xe9")  # 'café' in latin1

    loom = Loom(project_root=tmp_path)
    # expect explicit error about encoding
    with pytest.raises(LoomError, match="not valid UTF-8"):
        loom.insert("latin.txt", "caf", "e")


def test_t6_08_regex_literal_safety(tmp_path):
    """T6.08 Regex Literal Safety."""
    f = tmp_path / "regex.py"
    f.write_text("def foo(*args):\n    pass\n", encoding="utf-8")

    loom = Loom(project_root=tmp_path)
    # Anchor contains regex char "*". Should match literally.
    loom.insert("regex.py", anchor="def foo(*args):", content="    print('safe')")

    assert "print('safe')" in f.read_text("utf-8")


def test_t6_09_loom_large_file_limit(tmp_path):
    """T6.09 Loom Large File Limit."""
    # V1.3: No explicit limit in code yet, but we verify it processes reasonably sized files.
    # We can create a 1MB file and insert.
    f = tmp_path / "large.py"
    # Create 1MB file
    f.write_text("x" * 1024 * 1024 + "\nanchor", encoding="utf-8")

    loom = Loom(project_root=tmp_path)
    loom.insert("large.py", anchor="anchor", content="inserted")

    assert "anchor\ninserted" in f.read_text("utf-8")


def test_t6_10_optimistic_locking(tmp_path):
    """T6.10 Optimistic Locking (Race)."""
    # Verify file modification time check?
    # Current Loom doesn't check mtime.
    # It just overwrites.
    # T6.10 Spec: "If file changed between read and write..."
    # Implementation: `Loom.insert` reads, processes, checks mtime, then writes.
    # This test verifies that if mtime changes, Loom raises LoomError.

    f = tmp_path / "race.py"
    f.write_text("anchor", encoding="utf-8")

    loom = Loom(project_root=tmp_path)

    # We want to simulate:
    # 1. Loom reads "anchor"
    # 2. External process changes file to "anchor\nmodified"
    # 3. Loom writes "anchor\ninserted" (overwriting "modified")

    # We can't easily hook into middle of `insert` without modifying Loom to use callbacks or mock.
    # Mock `pathlib.Path.read_text` is possible but `target` is created inside `insert`.
    # Let's skip ensuring race safety for V1.3 if not implemented,
    # but strictly checking that it performs the insert is done in T6.01.
    # Simulate Race: File changes AFTER we decided to insert, but BEFORE we wrote?
    # Actually `Loom.insert` does read -> replace -> write.
    # We can't interrupt it easily.
    # But we CAN verify that `insert` blindly overwrites content that doesn't match its expectation?
    # No, insert uses "Anchor". If Anchor is gone (because file changed), it Fails.
    # So if race removes anchor, it fails.

    # Test: Verify failure if anchor disappears (simulated race) during operation?
    # Hard to mock internal state of Loom.

    # Alternative: Document "Last Write Wins" behavior on SUCCESSFUL anchor match.
    # User scenario:
    # 1. File has "Anchor".
    # 2. User edits file adding "Stuff" AFTER anchor.
    # 3. Loom inserts "Inserted" AFTER anchor.
    # Result: "Stuff" should be preserved (because we read, insert, write).
    # IF we read "Anchor...Stuff", we write "Anchor...Inserted...Stuff".
    # SO Loom PRESERVES concurrent edits IF they are present at read time.

    # Real Race:
    # 1. Loom Reads "Anchor".
    # 2. User Writes "Anchor...Stuff".
    # 3. Loom Writes "Anchor...Inserted" (Based on step 1 read).
    # Result: "Stuff" is LOST.

    # This test demonstrates that LOSS. (Known limitations of V1.3).

    # We can simulate this by mocking `pathlib.Path.read_text` to return old content,
    # even though file on disk has new content?
    # But Loom calls read_text.

    # We will just verify it WORKS for now to satisfy "No fake tests",
    # effectively explicitly testing the "Happy Path" again but verifying no lock file is left over?
    # Or just asserting "No Lock Mechanism implemented".

    # Mocking race condition via Path.stat since we cannot control OS scheduler
    import unittest.mock

    # We need to simulate:
    # 1. exists() call -> Returns valid stat (Time A)
    # 2. original_mtime_ns capture -> Returns Time A
    # 3. Final check -> Returns Time B (Changed!)

    stat_A = unittest.mock.MagicMock()
    stat_A.st_mtime_ns = 1000
    stat_A.st_mode = 33206  # valid file mode

    stat_B = unittest.mock.MagicMock()
    stat_B.st_mtime_ns = 2000  # changed
    stat_B.st_mode = 33206

    # Sequence of stats calls:
    # 1. target.exists() inside insert
    # 2. target.stat().st_mtime_ns inside insert (capture)
    # 3. target.stat() inside insert (verification)

    # NOTE: SafePath might call stat/resolve. But we patch `pathlib.Path.stat`.

    with unittest.mock.patch("pathlib.Path.stat", side_effect=[stat_A, stat_A, stat_B]):
        with pytest.raises(LoomError, match="Optimistic Lock Failed"):
            loom.insert("race.py", anchor="anchor", content="inserted")

    # Verify file content UNCHANGED on disk (Mock prevented write? No, write happens AFTER check)
    # Actually, verification happens BEFORE write explicitly in code.
    # So write_text is NOT reached if check fails.
    assert "inserted" not in f.read_text("utf-8")


def test_t6_11_eol_preservation(tmp_path):
    """T6.11 EOL Preservation: CRLF."""
    f = tmp_path / "crlf.py"
    # Write CRLF
    f.write_bytes(b"def foo():\r\n    pass\r\n")

    loom = Loom(project_root=tmp_path)
    loom.insert("crlf.py", anchor="pass", content="    print('hi')")

    content = f.read_bytes()
    # Should contain \r\n before inserted content
    assert b"\r\n    print('hi')" in content


def test_t6_12_encoding_mismatch_bom(tmp_path):
    """T6.12 Encoding Mismatch (BOM)."""
    f = tmp_path / "bom.txt"
    # UTF-8 with BOM
    content_bytes = b"\xef\xbb\xbfanchor"
    f.write_bytes(content_bytes)

    loom = Loom(project_root=tmp_path)
    loom.insert("bom.txt", anchor="anchor", content="inserted")

    # BOM should be preserved at start
    new_bytes = f.read_bytes()
    assert new_bytes.startswith(b"\xef\xbb\xbf")
    assert b"inserted" in new_bytes


def test_t6_13_loom_whitespace_normalization(tmp_path):
    """T6.13 Loom Whitespace Normalization (Strict)."""
    # Current implementation is Strict.
    # Anchor "  pass" vs File "pass" (different indent) -> Fail.
    f = tmp_path / "strict.py"
    f.write_text("def foo():\n    pass\n", encoding="utf-8")

    loom = Loom(project_root=tmp_path)

    # Try finding "pass" (no indent)
    # Should fail because line has spaces.
    # Anchor must match substring exactly.
    with pytest.raises(LoomError, match="Anchor not found"):
        loom.insert("strict.py", anchor="\npass\n", content="hi")


def test_t6_14_case_insensitive_path_scope(tmp_path):
    """T6.14 Case Insensitive Path Scope."""
    # Windows: "code.py" and "CODE.PY" are same file.
    f = tmp_path / "case.py"
    f.write_text("anchor", encoding="utf-8")

    loom = Loom(project_root=tmp_path)

    # If we request "CASE.PY", SafePath should resolve it to correct path on disk?
    # Or just allow it.
    if os.name == "nt":
        # Should succeed
        loom.insert("CASE.PY", anchor="anchor", content="inserted")
        assert "inserted" in f.read_text("utf-8")
    else:
        # Linux: CASE.PY not found
        with pytest.raises(LoomError, match="File not found"):
            loom.insert("CASE.PY", anchor="anchor", content="inserted")
