import pytest
from flow.domain.models import StatusTree, Task, StateError

# T5.xx: Domain Policy (Auto-Propagation / Protocol V2)
# Goal: Verify Auto-Activation and Auto-Completion.

@pytest.fixture
def policy_tree():
    """Setup a basic Parent -> 2 Children tree."""
    tree = StatusTree()
    tree.add_task(parent_id="root", name="Parent", status="pending") 
    tree._reindex() 
    
    tree.add_task(parent_id="1", name="Child 1", status="pending") 
    tree._reindex()
    
    tree.add_task(parent_id="1", name="Child 2", status="pending") 
    tree._reindex() 
    return tree

def test_t5_01_activation_bubble(policy_tree):
    # Input: Parent [ ], Child 1 [ ], Child 2 [ ]
    tree = policy_tree
    
    # Action: Update Child 1 -> Done
    tree.update_task("1.1", status="done")
    
    # Expectation: Parent becomes Active (Working on child implies Parent is open)
    parent = tree.find_task("1")
    assert parent.status == "active", "Parent MUST become active when child is done"
    
def test_t5_02_completion_bubble(policy_tree):
    # Input: Parent [/], Child 1 [ ], Child 2 [ ]
    tree = policy_tree
    
    # Setup: Parent Active, Child 1 Done
    tree.update_task("1.1", status="done") 
    assert tree.find_task("1").status == "active" # Check Activation bubble worked
    
    # Action: Update Child 2 -> Done
    tree.update_task("1.2", status="done")
    
    # Expectation: Parent becomes Done (All children done)
    parent = tree.find_task("1")
    assert parent.status == "done", "Parent MUST become done when ALL children done"

def test_t5_03_deep_completion_bubble():
    """Verify recursive completion bubble up 5 levels."""
    tree = StatusTree()
    tree.add_task(parent_id="root", name="Root", status="pending") 
    tree._reindex()
    tree.add_task(parent_id="1", name="A", status="pending")
    tree._reindex()
    tree.add_task(parent_id="1.1", name="B", status="pending")
    tree._reindex()
    
    # Action: Mark Leaf (B) as Done
    tree.update_task("1.1.1", status="done")
    
    # Expectation:
    # 1. B [x] -> A checks siblings (none), update A [x]
    # 2. A [x] -> Root checks siblings (none), update Root [x]
    assert tree.find_task("1.1.1").status == "done"
    assert tree.find_task("1.1").status == "done"
    assert tree.find_task("1").status == "done"

def test_t5_04_deep_activation_bubble():
    """Verify recursive activation bubble up 3 levels."""
    tree = StatusTree()
    # Root -> 1 (Pending)
    tree.add_task(parent_id="root", name="Root", status="pending")
    tree._reindex()
    
    # 1 -> 1.1 (Pending)
    tree.add_task(parent_id="1", name="A", status="pending")
    tree._reindex()
    
    # 1 -> 1.2 (Pending) (Another branch preventing full completion)
    tree.add_task(parent_id="1", name="Sibling", status="pending")
    tree._reindex()
    
    # 1.1 -> 1.1.1 (Pending)
    tree.add_task(parent_id="1.1", name="B", status="pending")
    tree._reindex()

    # Action: Work on Leaf (B) -> Done/Active
    tree.update_task("1.1.1", status="done")
    
    # Expectation:
    # B [x] -> A checks siblings (none), A becomes [x] (Completion Bubble)
    # A [x] -> Root checks siblings (Sibling is pending). Root becomes [/] (Activation Bubble)
    
    assert tree.find_task("1.1.1").status == "done"
    assert tree.find_task("1.1").status == "done" # Only child, so it completes
    assert tree.find_task("1.2").status == "pending" # Sibling untouched
    
    # Root Check:
    # Root was Pending. Child A became Done.
    # Logic: If child status in [active, done], parent becomes active?
    # Yes. "1. Activation Bubble".
    assert tree.find_task("1").status == "active"
