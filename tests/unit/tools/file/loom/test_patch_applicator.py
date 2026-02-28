import pytest

from flow.tools.base import ToolError
from flow.tools.file.loom.patch_applicator import PatchApplicator


@pytest.fixture
def patcher():
    return PatchApplicator()


def test_replace_exact(patcher):
    content = "hello world"
    edits = [
        {"operation": "replace", "spec": "world", "content": "universe", "count": 1}
    ]
    result = patcher.apply(content, edits)
    assert result == "hello universe"


def test_delete_text(patcher):
    content = "foo bar baz"
    edits = [{"operation": "delete", "spec": " bar", "count": 1}]
    result = patcher.apply(content, edits)
    assert result == "foo baz"


def test_append_after(patcher):
    content = "func main() {}"
    edits = [
        {
            "operation": "append_after",
            "spec": "func main() {}",
            "content": "// comment",
            "count": 1,
        }
    ]
    result = patcher.apply(content, edits)
    assert result == "func main() {}\n// comment"


def test_prepend_before(patcher):
    content = "class A:"
    edits = [
        {
            "operation": "prepend_before",
            "spec": "class A:",
            "content": "@decorator",
            "count": 1,
        }
    ]
    result = patcher.apply(content, edits)
    assert result == "@decorator\nclass A:"


def test_count_mismatch_error(patcher):
    content = "a a a"
    edits = [{"operation": "replace", "spec": "a", "content": "b", "count": 2}]

    # Found 3, expected 2 -> Error
    with pytest.raises(ToolError) as exc:
        patcher.apply(content, edits)
    assert "Expected 2, Found 3" in str(exc.value) or "Match count mismatch" in str(
        exc.value
    )


def test_idempotency_success(patcher):
    """Refactoring already done."""
    content = "new_value"
    edits = [
        {
            "operation": "replace",
            "spec": "old_value",  # Not found
            "content": "new_value",  # Found
            "count": 1,
        }
    ]
    # Should succeed without change
    result = patcher.apply(content, edits)
    assert result == "new_value"


def test_not_found_error(patcher):
    content = "hello"
    edits = [{"operation": "replace", "spec": "world", "content": "!", "count": 1}]

    with pytest.raises(ToolError) as exc:
        patcher.apply(content, edits)
    assert "Target text not found" in str(exc.value) or "Match count mismatch" in str(
        exc.value
    )
