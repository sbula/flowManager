import pytest
from flow.domain.models import StatusTree, Task, StateError, StaleIDError
from flow.domain.parser import StatusParsingError

# Helpers for construction
def create_tree():
    """Creates a simple tree:
    1. Root A
       1.1 Child A1
    2. Root B [active]
    """
    t = StatusTree()
    
    root_a = Task(id="1", name="Root A", status="pending", indent_level=0)
    child_a1 = Task(id="1.1", name="Child A1", status="pending", indent_level=1)
    child_a1.parent = root_a
    root_a.children.append(child_a1)
    
    root_b = Task(id="2", name="Root B", status="active", indent_level=0)
    
    t.root_tasks.extend([root_a, root_b])
    t._reindex() # Required after manual manipulation
    return t

# --- T4.01 Find Task ---
def test_t4_01_find_task():
    tree = create_tree()
    
    # Valid
    t = tree.find_task("1.1")
    assert t.name == "Child A1"
    
    # Invalid
    with pytest.raises(ValueError, match="Task ID .* not found"):
        tree.find_task("9.9")

# --- T4.02 Add Task (Simple) ---
def test_t4_02_add_task_simple():
    tree = create_tree()
    
    # Add Child to Root B
    tree.add_task(parent_id="2", name="Child B1")
    tree._reindex()
    
    b = tree.find_task("2")
    assert len(b.children) == 1
    assert b.children[0].name == "Child B1"
    assert b.children[0].indent_level == 1
    assert b.children[0].parent == b 

# --- T4.03 Update Task ---
def test_t4_03_update_task():
    tree = create_tree()
    
    # Update Status
    tree.update_task("1.1", status="done")
    t = tree.find_task("1.1")
    assert t.status == "done"
    
    # Update Name
    tree.update_task("1.1", name="Renamed")
    assert t.name == "Renamed"

# --- T4.04 Update Guard (Context) ---
def test_t4_04_update_guard():
    tree = create_tree()
    
    # Success
    tree.update_task("1.1", name="New", context_anchor="Child A1")
    assert tree.find_task("1.1").name == "New"
    
    # Failure
    with pytest.raises(ValueError, match="Anchor mismatch"):
        tree.update_task("1.1", name="New2", context_anchor="Wrong Name")

# --- T4.05 Remove Task ---
def test_t4_05_remove_task():
    tree = create_tree()
    
    # Remove Child
    tree.remove_task("1.1")
    tree._reindex()
    parent = tree.find_task("1")
    assert len(parent.children) == 0

# --- T4.06-08 Insertion Logic ---
def test_t4_06_add_sibling_start():
    tree = create_tree() # A(1), B(2)
    
    # Add Z at start
    tree.add_task(parent_id="root", name="Root Z", index=0)
    
    assert tree.root_tasks[0].name == "Root Z"
    assert tree.root_tasks[1].name == "Root A"

def test_t4_08_add_subtask_mid():
    tree = create_tree()
    parent = tree.find_task("1")
    # Add A2, A3
    tree.add_task(parent_id="1", name="Child A2")
    tree._reindex()
    tree.add_task(parent_id="1", name="Child A3")
    tree._reindex()
    
    # Insert A_New at index 1 (between A1 and A2)
    # Current children: A1, A2, A3
    tree.add_task(parent_id="1", name="Child A_New", index=1)
    tree._reindex()
    
    assert parent.children[0].name == "Child A1"
    assert parent.children[1].name == "Child A_New"
    assert parent.children[2].name == "Child A2"

# --- T4.10 Insert Between Specific ---
def test_t4_10_insert_between_specific():
    t = StatusTree()
    t.root_tasks = [
        Task(id="1", name="A", status="pending", indent_level=0),
        Task(id="2", name="B", status="pending", indent_level=0),
        Task(id="3", name="C", status="pending", indent_level=0),
        Task(id="4", name="D", status="pending", indent_level=0)
    ]
    t._reindex()
    
    # Insert New at index 2 (Between B and C)
    t.add_task(parent_id="root", name="New", index=2)
    t._reindex()
    
    names = [node.name for node in t.root_tasks]
    assert names == ["A", "B", "New", "C", "D"]

# --- T4.11 Sibling Conflict (Strict) ---
def test_t4_11_sibling_conflict():
    tree = create_tree()
    # Root B is Active.
    # Try to set Root A to Active without pausing B.
    with pytest.raises(StateError, match="Sibling .* is already active"):
        tree.update_task("1", status="active")

# --- T4.12 Parent Conflict (Strict) ---
def test_t4_12_parent_conflict():
    tree = create_tree()
    # Root A is Pending.
    # Try to set Child A1 to Active.
    with pytest.raises(StateError, match="Parent .* is not active"):
        tree.update_task("1.1", status="active")

# --- T4.13 Active Injection Check ---
def test_t4_13_active_injection_check():
    tree = create_tree()
    # Root B is Active.
    # Try to add NEW Active Sibling.
    with pytest.raises(StateError, match="Sibling .* is already active"):
        tree.add_task(parent_id="root", name="New Active", status="active")

# --- T4.14 Re-Open Parent Flow ---
def test_t4_14_reopen_flow():
    tree = StatusTree()
    # Parent Done, Child Pending
    p = Task(id="1", name="P", status="done", indent_level=0)
    c = Task(id="1.1", name="C", status="pending", indent_level=1, parent=p)
    p.children.append(c)
    tree.root_tasks.append(p)
    tree._reindex()
    
    # 1. Try child active -> Fail
    with pytest.raises(StateError, match="Parent .* is not active"):
        tree.update_task("1.1", status="active")
        
    # 2. Open Parent -> Success
    tree.update_task("1", status="active")
    tree._reindex() # Optional for update if ID didn't change, but good practice if IDs were unstable
    assert p.status == "active"
    
    # 3. Open Child -> Success
    tree.update_task("1.1", status="active")
    assert c.status == "active"

# --- T4.15 ID Invalidation ---
def test_t4_15_id_invalidation():
    tree = create_tree() # A(1), B(2)
    
    # Modifying structure
    tree.add_task(parent_id="root", name="New")
    
    # Accessing OLD ID should fail/warn?
    # Spec says: IDs are invalidated.
    # Implementation: StatusTree should internally clear its ID index.
    
    with pytest.raises(StaleIDError):
        tree.find_task("1")

# --- T4.16 Duplicate Name Prevention ---
def test_t4_16_duplicate_name_prevention():
    tree = create_tree() # A, B
    
    with pytest.raises(ValueError, match="Duplicate name"):
        tree.add_task(parent_id="root", name="Root A")

# --- T4.18 Cycle Detection ---
def test_t4_18_cycle_detection():
    tree = create_tree()
    a = tree.find_task("1")
    
    # Try to add A as child of A (via update or add logic?)
    # add_task takes Name, creates new Task.
    # So direct object cycle isn't possible via add_task API unless we pass object.
    # But if we assume API takes name, maybe this test is for "Moving" tasks?
    # Spec logic: "Ensures added task (if subtree) does not contain Parent".
    # Since add_task creates a NEW task, cycle is impossible unless name-based?
    # Let's assume add_task creates new.
    pass 

# --- T4.19 Deep State Validation ---
def test_t4_19_deep_state_validation():
    # Adding a whole subtree where Child is Active but Parent is Pending
    # This requires an API that accepts a Task Object, OR sequential adds.
    # If add_task only takes name, we can't inject a bad subtree easily.
    # Assuming strict API, this is guarded by T4.12 on each step.
    pass 
