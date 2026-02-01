import pytest
import json
import hashlib
from pathlib import Path
from flow.domain.models import StatusTree, Task
from flow.domain.persister import StatusPersister, IntegrityError
from flow.domain.parser import StatusParser

# Note: We need StatusParser to implement integrity too.
# Assuming StatusParser exists and needs update.

@pytest.fixture
def temp_flow(tmp_path):
    flow_dir = tmp_path / ".flow"
    flow_dir.mkdir()
    return flow_dir

def create_valid_state(flow_dir):
    """Creates a valid status.md and status.meta using Persister."""
    p = StatusPersister(flow_dir)
    t = StatusTree()
    t.root_tasks.append(Task(id="1", name="Original", status="pending", indent_level=0))
    p.save(t, "status.md")
    return t

# --- T1.13 Tamper Detection ---
def test_t1_13_tamper_detection(temp_flow):
    create_valid_state(temp_flow)
    
    # Tamper
    status_path = temp_flow / "status.md"
    status_path.write_text(status_path.read_text() + "\n- [ ] Hack", encoding="utf-8")
    
    # Load -> IntegrityError
    # Parser expects Root, so pass temp_flow.parent (Project Root)
    parser = StatusParser(temp_flow.parent)
    with pytest.raises(IntegrityError):
        parser.load("status.md")

# --- T1.14 Integrity Accept ---
def test_t1_14_integrity_accept(temp_flow):
    create_valid_state(temp_flow)
    
    # Tamper
    status_path = temp_flow / "status.md"
    new_content = status_path.read_text() + "\n- [ ] Accepted Hack"
    status_path.write_text(new_content, encoding="utf-8")
    
    parser = StatusParser(temp_flow.parent)
    
    # Verify Failure First
    with pytest.raises(IntegrityError):
        parser.load("status.md")
        
    # Accept
    parser.accept_changes("status.md")
    
    # Verify Success
    tree = parser.load("status.md")
    assert tree.root_tasks[-1].name == "Accepted Hack"
    
    # Verify Hash Updated
    meta = json.loads((temp_flow / "status.meta").read_text())
    file_bytes = (temp_flow / "status.md").read_bytes()
    expected = hashlib.sha256(file_bytes).hexdigest()
    assert meta["hash"] == expected

# --- T1.15 Integrity Decline ---
def test_t1_15_integrity_decline(temp_flow):
    # 1. Create Initial (Valid)
    create_valid_state(temp_flow)
    
    # 2. Modify & Save (Creates Backup of Initial)
    p = StatusPersister(temp_flow)
    t = StatusTree()
    t.root_tasks.append(Task(id="1", name="Modified", status="pending", indent_level=0))
    p.save(t, "status.md")
    
    # 3. Tamper (Corrupt the Modified version)
    status_path = temp_flow / "status.md"
    status_path.write_text("Corrupted content", encoding="utf-8")
    
    parser = StatusParser(temp_flow.parent)
    
    # Decline (Should restore "Original" from backup of step 1?)
    # Wait, Step 2 overwrote "Original". It backed up "Original" to backups/.
    # Step 2 wrote "Modified".
    # Step 3 Corrupted "Modified".
    # Decline restores Latest Backup -> "Original".
    
    parser.decline_changes("status.md")
    
    # Verify Restore
    tree = parser.load("status.md")
    assert tree.root_tasks[0].name == "Original"
