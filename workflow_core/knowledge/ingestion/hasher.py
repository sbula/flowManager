import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Optional
import os

def compute_file_hash(path: Path) -> str:
    """Computes SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

class ManifestManager:
    def __init__(self, manifest_path: Path = Path(".flow/rag_manifest.json")):
        self.manifest_path = manifest_path
        self.manifest: Dict[str, str] = self._load()

    def _load(self) -> Dict[str, str]:
        if not self.manifest_path.exists():
            return {}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def save(self):
        # Ensure parent exists
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(self.manifest, indent=2), encoding="utf-8")

    def get_hash(self, file_path: str) -> Optional[str]:
        return self.manifest.get(file_path)

    def update(self, file_path: str, file_hash: str):
        self.manifest[file_path] = file_hash

    def remove(self, file_path: str):
        if file_path in self.manifest:
            del self.manifest[file_path]
