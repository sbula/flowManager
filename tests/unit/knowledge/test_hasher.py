import pytest
from pathlib import Path
import json
from workflow_core.knowledge.ingestion.hasher import compute_file_hash, ManifestManager

def test_compute_file_hash(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")
    
    h1 = compute_file_hash(f)
    assert len(h1) == 64 # SHA256 length
    
    f.write_text("hello world changed", encoding="utf-8")
    h2 = compute_file_hash(f)
    assert h1 != h2

def test_manifest_manager(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manager = ManifestManager(manifest_path)
    
    # Test update
    manager.update("file1.txt", "hash1")
    manager.save()
    
    assert manifest_path.exists()
    content = json.loads(manifest_path.read_text())
    assert content["file1.txt"] == "hash1"
    
    # Test load
    manager2 = ManifestManager(manifest_path)
    assert manager2.get_hash("file1.txt") == "hash1"
    
    # Test remove
    manager2.remove("file1.txt")
    manager2.save()
    
    content = json.loads(manifest_path.read_text())
    assert "file1.txt" not in content
