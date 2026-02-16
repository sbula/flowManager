import pytest
from workflow_core.knowledge.ingestion.splitter import CodeSplitter

@pytest.fixture
def splitter():
    return CodeSplitter()

def test_split_python_simple(splitter):
    code = """
def foo():
    print("bar")

class MyClass:
    def method(self):
        pass
"""
    chunks = splitter.split_text(code, "python")
    assert len(chunks) == 2
    assert "def foo():" in chunks[0]
    assert "class MyClass:" in chunks[1]

def test_split_python_decorated(splitter):
    code = """
@decorator
def foo():
    pass
"""
    chunks = splitter.split_text(code, "python")
    assert len(chunks) == 1
    assert "@decorator" in chunks[0]

def test_split_unsupported(splitter):
    code = "just some text"
    chunks = splitter.split_text(code, "unknown_lang")
    assert len(chunks) == 1
    assert chunks[0] == code
