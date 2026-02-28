import pytest

from workflow_core.knowledge.store.chroma_store import ChromaStore


@pytest.fixture
def chroma_store(tmp_path):
    # Setup
    persist_path = str(tmp_path / "test_db")
    store = ChromaStore(persist_path=persist_path, collection_name="test_collection")
    yield store

    # Teardown
    del store
    import gc

    gc.collect()


def test_add_and_query(chroma_store):
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    documents = ["doc1", "doc2"]
    metadatas = [{"source": "src"}, {"source": "docs"}]
    ids = ["id1", "id2"]

    chroma_store.add(embeddings, documents, metadatas, ids)

    # Query
    results = chroma_store.query(query_embeddings=[[0.1, 0.2]], n_results=1)

    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "id1"
    assert results["documents"][0][0] == "doc1"


def test_delete(chroma_store):
    embeddings = [[0.1, 0.2]]
    documents = ["doc1"]
    metadatas = [{"source": "src"}]
    ids = ["id1"]

    chroma_store.add(embeddings, documents, metadatas, ids)
    chroma_store.delete(ids=["id1"])

    results = chroma_store.query(query_embeddings=[[0.1, 0.2]], n_results=1)
    assert len(results["ids"][0]) == 0
