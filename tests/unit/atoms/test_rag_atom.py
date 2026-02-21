from unittest.mock import MagicMock, patch

import pytest

from src.flow.engine.atoms import RagRetrievalAtom


def test_rag_atom_run():
    atom = RagRetrievalAtom()

    # Mock config
    mock_config_data = {"knowledge": {"profiles": {"default": {}}}}

    with patch("builtins.open", new_callable=MagicMock), patch(
        "json.load", return_value=mock_config_data
    ), patch("pathlib.Path.exists", return_value=True), patch(
        "workflow_core.knowledge.service.KnowledgeService"
    ) as MockService:

        mock_instance = MockService.return_value
        mock_instance.ask.return_value = "This is the answer"

        # Test Run
        context = {"query": "test query"}
        result = atom.run(context)

        assert result.success
        assert result.exports["answer"] == "This is the answer"
        mock_instance.ask.assert_called_with("test query", profile="default")


def test_rag_atom_missing_query():
    atom = RagRetrievalAtom()
    result = atom.run({})
    assert not result.success
    assert "Query is required" in result.message
