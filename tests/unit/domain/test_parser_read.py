import pytest
import pytest
from pathlib import Path
from flow.domain.models import Task, StatusTree, StatusParsingError
from flow.domain.parser import StatusParser

# Constants for Testing
FLOW_DIR_NAME = ".flow"

@pytest.fixture
def flow_env(tmp_path):
    """Creates a temporary project root with a .flow directory."""
    flow_dir = tmp_path / FLOW_DIR_NAME
    flow_dir.mkdir()
    return tmp_path

# --- 1. Happy Paths (T1.xx) ---

def test_t1_01_standard_load(flow_env):
    """T1.01 Standard Load: Valid headers and nested tasks."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("""Project: TDD
Version: 1.0

- [ ] Phase 1
    - [ ] Task A
    - [ ] Task B
""", encoding="utf-8")
    
    parser = StatusParser(flow_env)
    tree = parser.load("status.md")
    
    assert tree.headers["Project"] == "TDD"
    assert len(tree.root_tasks) == 1
    assert tree.root_tasks[0].name == "Phase 1"
    assert tree.root_tasks[0].status == "pending"
    assert len(tree.root_tasks[0].children) == 2
    assert tree.root_tasks[0].children[0].name == "Task A"

def test_t1_02_fractal_link_parsed(flow_env):
    """T1.02 Fractal Link Parsed: ref is extracted."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("- [ ] Link @ sub.md", encoding="utf-8")
    
    parser = StatusParser(flow_env)
    tree = parser.load()
    assert tree.root_tasks[0].ref == "sub.md"

def test_t1_03_missing_file(flow_env):
    """T1.03 Missing Parent File: Returns empty tree."""
    parser = StatusParser(flow_env)
    tree = parser.load("non_existent.md")
    assert isinstance(tree, StatusTree)
    assert len(tree.root_tasks) == 0

def test_t1_04_deep_nesting(flow_env):
    """T1.04 Deep Nesting: 10+ levels of indentation."""
    # Build 12 levels deep
    lines = ["- [ ] Level 0"]
    for i in range(1, 12):
        indent = "    " * i
        lines.append(f"{indent}- [ ] Level {i}")
    
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    
    tree = StatusParser(flow_env).load()
    # Verify depth logic (Level 0 -> Level 1 -> ... -> Level 11)
    current = tree.root_tasks[0]
    for i in range(12):
        if i == 11:
            assert len(current.children) == 0
        else:
            assert len(current.children) == 1
            current = current.children[0]
            assert current.name == f"Level {i+1}"

def test_t1_05_mixed_markers(flow_env):
    """T1.05 Mixed Markers: [x], [X], [v] normalize to done."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("""
- [x] Done 1
- [X] Done 2
- [v] Done 3
""", encoding="utf-8")
    tree = StatusParser(flow_env).load()
    assert all(t.status == "done" for t in tree.root_tasks)

def test_t1_06_find_cursor(flow_env):
    """T1.06 Find Cursor: Returns deepest [/] node."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("""
- [/] Phase 1
    - [ ] Task A
    - [/] Task B
""", encoding="utf-8")
    tree = StatusParser(flow_env).load()
    cursor = tree.get_active_task()
    assert cursor is not None
    assert cursor.name == "Task B" 

def test_t1_07_quoted_path(flow_env):
    """T1.07 Quoted Path: Handles spaces."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text('- [ ] A @ "my file.md"', encoding="utf-8")
    tree = StatusParser(flow_env).load()
    assert tree.root_tasks[0].ref == "my file.md"

def test_t1_08_anchor_assumption(flow_env):
    """T1.08 Anchor Assumption: ref is relative to .flow/."""
    # Scenario: Ref "sub/deep.md".
    # Case A: .flow/sub/deep.md exists -> Pass
    # Case B: ./sub/deep.md exists (but not in .flow) -> Fail (implied by T2.07 logic)
    
    # Setup: Create active task structure
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("- [/] Task @ sub/deep.md", encoding="utf-8")
    
    # 1. Ensure validation fails if missing
    with pytest.raises(StatusParsingError, match="Missing sub-status"):
         StatusParser(flow_env).load()
         
    # 2. Create file in .flow -> Should pass
    (flow_env / FLOW_DIR_NAME / "sub").mkdir()
    (flow_env / FLOW_DIR_NAME / "sub" / "deep.md").touch()
    
    StatusParser(flow_env).load() # Should not raise

def test_t1_09_duplicate_header(flow_env):
    """T1.09 Duplicate Header: Last write wins."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("""Proj: A
Proj: B""", encoding="utf-8")
    tree = StatusParser(flow_env).load()
    assert tree.headers["Proj"] == "B"

def test_t1_10_empty_file(flow_env):
    """T1.10 Empty File: Valid empty tree."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.touch()
    tree = StatusParser(flow_env).load()
    assert len(tree.root_tasks) == 0

def test_t1_11_smart_resume(flow_env):
    """T1.11 Smart Resume: Returns first pending if no active."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("""
- [x] Phase 1
- [ ] Phase 2
    - [ ] Task A
""", encoding="utf-8")
    tree = StatusParser(flow_env).load()
    cursor = tree.get_active_task()
    assert cursor is not None
    assert cursor.name == "Phase 2"

def test_t1_12_virtual_numbering(flow_env):
    """T1.12 Virtual Numbering: Hierarchical IDs."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("""
- [ ] Root 1
    - [ ] Child A
    - [ ] Child B
- [ ] Root 2
    - [ ] Child C
        - [ ] Grandchild D
""", encoding="utf-8")

    tree = StatusParser(flow_env).load()
    tasks = tree.root_tasks
    
    # Root 1
    assert tasks[0].name == "Root 1"
    assert tasks[0].id == "1"
    
    # Child A
    child_a = tasks[0].children[0]
    assert child_a.name == "Child A"
    assert child_a.id == "1.1"
    
    # Child B
    child_b = tasks[0].children[1]
    assert child_b.name == "Child B"
    assert child_b.id == "1.2"
    
    # Root 2
    assert tasks[1].name == "Root 2"
    assert tasks[1].id == "2"
    
    # Grandchild D (Root 2 -> Child C -> Grandchild D)
    # Expected: 2.1.1
    grandchild = tasks[1].children[0].children[0]
    assert grandchild.name == "Grandchild D"
    assert grandchild.id == "2.1.1"

# --- 2. Validation (T2.xx) ---

def test_t2_01_indent_error_1sp(flow_env):
    """T2.01 Indent Error: 1 space."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text(" - [ ] Bad", encoding="utf-8")
    with pytest.raises(StatusParsingError, match="Invalid indentation"):
        StatusParser(flow_env).load()

def test_t2_02_indent_error_3sp(flow_env):
    """T2.02 Indent Error: 3 spaces."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("   - [ ] Bad", encoding="utf-8")
    with pytest.raises(StatusParsingError):
        StatusParser(flow_env).load()

def test_t2_03_indent_error_tab(flow_env):
    """T2.03 Indent Error: Tab character."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("\t- [ ] Bad", encoding="utf-8")
    with pytest.raises(StatusParsingError, match="Tabs are forbidden"):
        StatusParser(flow_env).load()

def test_t2_04_syntax_error(flow_env):
    """T2.04 Syntax Error: Missing brackets."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("- Just Text", encoding="utf-8")
    with pytest.raises(StatusParsingError):
        StatusParser(flow_env).load()

def test_t2_05_unknown_marker(flow_env):
    """T2.05 Unknown Marker: [?], [XX]."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("- [?] What", encoding="utf-8")
    with pytest.raises(StatusParsingError):
        StatusParser(flow_env).load()

def test_t2_06_logic_conflict(flow_env):
    """T2.06 Logic Conflict: Parent Done, Child Pending."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("""
- [x] Parent
    - [ ] Child
""", encoding="utf-8")
    with pytest.raises(StatusParsingError, match="Logic Conflict"):
        StatusParser(flow_env).load()

def test_t2_07_referential_integrity(flow_env):
    """T2.07 Ref Integrity: Active task missing file."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    # missing.md does not exist
    p.write_text("- [/] Task @ missing.md", encoding="utf-8")
    with pytest.raises(StatusParsingError, match="Missing sub-status"):
        StatusParser(flow_env).load()

def test_t2_08_sibling_conflict(flow_env):
    """T2.08 Sibling Conflict: Two active siblings."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("""
- [/] A
- [/] B
""", encoding="utf-8")
    with pytest.raises(StatusParsingError, match="Ambiguous Focus"):
        StatusParser(flow_env).load()

def test_t2_09_duplicate_name(flow_env):
    """T2.09 Duplicate Name: Siblings with same name."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("""
- [ ] A
- [ ] A
""", encoding="utf-8")
    with pytest.raises(StatusParsingError, match="Duplicate Task Name"):
        StatusParser(flow_env).load()

def test_t2_10_path_traversal(flow_env):
    """T2.10 Path Traversal: .. usage."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("- [ ] Hack @ ../cmd.exe", encoding="utf-8")
    with pytest.raises(StatusParsingError, match="Jailbreak attempt"):
        StatusParser(flow_env).load()

def test_t2_11_keyword_ambiguity(flow_env):
    """T2.11 Keyword Ambiguity: Brackets in text."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("- [ ] Task with [x] inside name", encoding="utf-8")
    
    tree = StatusParser(flow_env).load()
    task = tree.root_tasks[0]
    assert task.status == "pending"
    assert task.name == "Task with [x] inside name"

def test_t2_12_path_protocol_safety(flow_env):
    """T2.12 Path Protocol Safety: malicious schemes."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    p.write_text("- [ ] Malicious @ javascript:alert(1)", encoding="utf-8")
    
    # Parser should probably catch this?
    # Current implementation check: regex captures ref. 
    # Logic: StatusParser._parse_content -> T2.10 check ("..") -> T2.12 check?
    # I need to ensure StatusParser HAS this logic or add it.
    # The spec says "Raises ValidationError".
    with pytest.raises(StatusParsingError, match="Invalid Protocol"):
        StatusParser(flow_env).load()
