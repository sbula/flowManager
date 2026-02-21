from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from workflow_core.knowledge.ingestion.engine import IngestionEngine


@pytest.fixture
def mock_service():
    service = MagicMock()
    return service


@pytest.fixture
def mock_manifest():
    manifest = MagicMock()
    manifest.get_hash.return_value = None  # Always new
    return manifest


def test_index_directory(tmp_path, mock_service):
    # Setup files
    (tmp_path / "src").mkdir()
    f = tmp_path / "src" / "app.py"
    f.write_text("def foo(): pass", encoding="utf-8")

    # Manifest in tmp
    manifest_path = tmp_path / "manifest.json"

    with patch(
        "workflow_core.knowledge.ingestion.engine.ManifestManager"
    ) as MockManifestCls:
        # Instance mock
        mock_man_inst = MockManifestCls.return_value
        mock_man_inst.get_hash.return_value = None
        mock_man_inst.manifest = {}

        engine = IngestionEngine(mock_service, manifest_path)

        engine.index_directory(tmp_path)

        # Check call
        assert mock_service.embed_and_store.called
        # Verify it processed app.py
        args = mock_service.embed_and_store.call_args
        assert len(args[0][0]) > 0  # Chunks
