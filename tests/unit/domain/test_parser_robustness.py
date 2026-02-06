import pytest

from flow.domain.models import StatusTree
from flow.domain.parser import StatusParser, StatusParsingError

FLOW_DIR_NAME = ".flow"


@pytest.fixture
def flow_env(tmp_path):
    flow_dir = tmp_path / FLOW_DIR_NAME
    flow_dir.mkdir()
    return tmp_path


def test_repro_crash_on_comment(flow_env):
    """Reproduces the crash when Parser encounters HTML comments."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    content = """
- [ ] Task A
<!-- This is a comment that should be skipped -->
- [ ] Task B
""".strip()
    p.write_text(content, encoding="utf-8")

    # Currently crashes with StatusParsingError: Invalid format
    parser = StatusParser(flow_env)
    tree = parser.load("status.md")

    assert len(tree.root_tasks) == 2
    assert tree.root_tasks[0].name == "Task A"
    assert tree.root_tasks[1].name == "Task B"


def test_repro_crash_on_text_line(flow_env):
    """Reproduces crash/error on non-task lines starting with hyphen."""
    p = flow_env / FLOW_DIR_NAME / "status.md"
    content = """
- [ ] Task A
- Just a note
- [ ] Task B
""".strip()
    p.write_text(content, encoding="utf-8")

    parser = StatusParser(flow_env)

    try:
        tree = parser.load("status.md")
        assert len(tree.root_tasks) == 2
    except StatusParsingError:
        pytest.fail("Should not crash on plain text line")
