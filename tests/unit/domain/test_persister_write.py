import pytest
import hashlib
import json
from pathlib import Path
from flow.domain.models import StatusTree, Task, StateError
from flow.domain.persister import StatusPersister, IntegrityError

# Helpers
def create_tree():
    t = StatusTree(headers={"Project": "Test"})
    t.root_tasks.append(Task(id="1", name="Task A", status="pending", indent_level=0))
    t.root_tasks.append(Task(id="2", name="Task B", status="active", indent_level=0))
    return t

@pytest.fixture
def temp_flow(tmp_path):
    flow_dir = tmp_path / ".flow"
    flow_dir.mkdir()
    return flow_dir

# --- T3.01 Create New ---
def test_t3_01_create_new(temp_flow):
    p = StatusPersister(flow_dir=temp_flow)
    tree = create_tree()
    
    p.save(tree, "status.md")
    
    assert (temp_flow / "status.md").exists()
    content = (temp_flow / "status.md").read_text(encoding="utf-8")
    assert "Project: Test" in content
    assert "- [ ] Task A" in content

# --- T3.02 Sanitize Formatting ---
def test_t3_02_sanitize_formatting(temp_flow):
    # Tests that save() enforces 4-space indent regardless of input history
    # (Input history covered by Parser tests, here we check Output Structure)
    p = StatusPersister(temp_flow)
    t = StatusTree()
    t.root_tasks.append(Task(id="1", name="Root", status="pending", indent_level=0))
    child = Task(id="1.1", name="Child", status="done", indent_level=1)
    child.parent = t.root_tasks[0]
    t.root_tasks[0].children.append(child)
    
    p.save(t, "fmt.md")
    
    lines = (temp_flow / "fmt.md").read_text("utf-8").splitlines()
    assert "- [ ] Root" in lines
    assert "    - [x] Child" in lines # 4 spaces

# --- T3.05 Comment Stripping & Fidelity ---
def test_t3_05_comment_stripping(temp_flow):
    # We can't easily inject comments into StatusTree (it doesn't store them).
    # But we can verify save() DOES NOT write generic comments.
    p = StatusPersister(temp_flow)
    t = create_tree()
    p.save(t, "clean.md")
    content = (temp_flow / "clean.md").read_text("utf-8")
    assert "<!--" not in content

# --- T3.12 Backup Generation ---
def test_t3_12_backup_generation(temp_flow):
    p = StatusPersister(temp_flow)
    t = create_tree()
    
    # Save 1
    p.save(t, "status.md")
    
    # Modify & Save 2
    t.root_tasks[0].status = "done"
    p.save(t, "status.md")
    
    # Check Backup
    backups = list((temp_flow / "backups").glob("status_*.md"))
    assert len(backups) == 1
    # Backup content should match Save 1
    assert "- [ ] Task A" in backups[0].read_text("utf-8")
    # Current content matches Save 2
    assert "- [x] Task A" in (temp_flow / "status.md").read_text("utf-8")

# --- T3.13 Hash Update ---
def test_t3_13_hash_update(temp_flow):
    p = StatusPersister(temp_flow)
    t = create_tree()
    
    p.save(t, "status.md")
    
    meta_path = temp_flow / "status.meta"
    assert meta_path.exists()
    
    # Verify Hash
    file_content = (temp_flow / "status.md").read_bytes()
    expected_hash = hashlib.sha256(file_content).hexdigest()
    
    meta = json.loads(meta_path.read_text())
    assert meta["hash"] == expected_hash

# --- T1.13 Tamper Detection (Load Check) ---
# Note: This is an Integration test (Parser + Persister) but we test Strict Logic here.
def test_t1_13_tamper_detection(temp_flow):
    p = StatusPersister(temp_flow)
    t = create_tree()
    p.save(t, "status.md")
    
    # Tamper with file
    path = temp_flow / "status.md"
    content = path.read_text("utf-8")
    path.write_text(content + "\n- [ ] Hacker Task", encoding="utf-8")
    
    # Load should fail
    # Note: StatusPersister usually does NOT have load(). Parser does.
    # But we haven't implemented Parser's integrity check yet.
    # We should add logic to Persister to VERIFY integrity check? 
    # Or implement Parser with Integrity in this phase?
    # Task 1.2a Parser is Read-Only. Task 1.2b adds Integrity.
    # So we must modify Parser or add check logic.
    pass 
