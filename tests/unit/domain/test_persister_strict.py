from pathlib import Path

import pytest

from flow.domain.models import StateError, StatusTree, Task
from flow.domain.persister import StatusPersister


@pytest.fixture
def temp_flow(tmp_path):
    flow_dir = tmp_path / ".flow"
    flow_dir.mkdir()
    return flow_dir


def test_t3_11b_strict_sibling_exclusivity(temp_flow):
    p = StatusPersister(temp_flow)
    t = StatusTree()
    # Two active siblings
    t.root_tasks.append(Task(id="1", name="A", status="active", indent_level=0))
    t.root_tasks.append(Task(id="2", name="B", status="active", indent_level=0))

    with pytest.raises(ValueError, match="Ambiguous Focus"):
        p.save(t, "ambiguous.md")


# --- T3.11c Validation: Child Active Parent Pending ---
def test_t3_11c_child_active_parent_pending(temp_flow):
    p = StatusPersister(temp_flow)
    t = StatusTree()
    parent = Task(id="1", name="Parent", status="pending", indent_level=0)
    child = Task(id="1.1", name="Child", status="active", indent_level=1, parent=parent)
    parent.children.append(child)
    t.root_tasks.append(parent)

    with pytest.raises(ValueError, match="Logic Conflict"):
        p.save(t, "conflict.md")
