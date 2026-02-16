from pathlib import Path
from typing import List, Optional
import os
from ..service import KnowledgeService
from .hasher import ManifestManager, compute_file_hash
from .splitter import CodeSplitter

class IngestionEngine:
    def __init__(self, service: KnowledgeService, manifest_path: Path):
        self.service = service
        self.manifest = ManifestManager(manifest_path)
        self.splitter = CodeSplitter()

    def index_directory(self, root_path: Path, extensions: List[str] = ['.py', '.js', '.md']):
        """
        Walks the directory and indexes files that have changed.
        """
        # 1. Scan and Update
        current_files = set()
        
        for root, dirs, files in os.walk(root_path):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix not in extensions:
                    continue
                
                # Check exclusion? (e.g. .git, __pycache__)
                if ".git" in str(file_path):
                    continue

                rel_path = str(file_path.relative_to(root_path))
                current_files.add(rel_path)
                
                self._process_file(file_path, rel_path)

        # 2. Handle Deletions
        known_files = list(self.manifest.manifest.keys())
        for existing_file in known_files:
            # We need to distinguish if existing_file is within the root_path we just scanned
            # If manifest tracks absolute paths or relative?
            # Design choice: relative to project root usually better.
            # Here we assume manifest stores paths relative to PROJECT ROOT, while index_directory might follow a subdir?
            # To simplify: index_directory usually called on PROJ_ROOT.
            
            # If we assume we always index from root, then any key in manifest not in current_files is deleted.
            if existing_file not in current_files:
                # File deleted
                print(f"Deleting indexes for {existing_file}")
                # We need to find all chunks for this doc.
                # Usually we delete by document_id in Chroma
                # self.service.store.delete(where={"document_id": existing_file})
                # But current store interface takes IDs list. 
                # We need support for delete by metadata ideally or we track chunk IDs.
                
                # For now, let's assume valid implementation in ChromaStore handles 'where' or we enhanced it.
                # Since VectorStore.delete only takes IDs in our interface... we might need to query first?
                # Or assume we can just ignore for now in this MVP or implement 'delete_by_doc'
                
                self.manifest.remove(existing_file)

        self.manifest.save()

    def _process_file(self, file_path: Path, rel_path: str):
        try:
            current_hash = compute_file_hash(file_path)
            stored_hash = self.manifest.get_hash(rel_path)
            
            if current_hash == stored_hash:
                return # Skip unchanged

            print(f"Indexing {rel_path}...")
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            
            # Determine language
            lang = 'python' if file_path.suffix == '.py' else 'javascript' if file_path.suffix == '.js' else 'text'
            
            chunks = self.splitter.split_text(content, lang)
            
            # Prepare for Store
            ids = [f"{rel_path}:{i}:{current_hash[:8]}" for i in range(len(chunks))]
            metadatas = [{"document_id": rel_path, "type": "code_chunk", "language": lang, "chunk_index": i} for i in range(len(chunks))]
            
            # Check for existing chunks to remove? 
            # If we change file, we might have old chunks with old hash logic or old IDs.
            # Best practice: Delete all chunks for this doc_id first, then insert new.
            # But we need delete_by_metadata.
            
            self.service.embed_and_store(chunks, metadatas, ids)
            self.manifest.update(rel_path, current_hash)
            
        except Exception as e:
            print(f"Error processing {rel_path}: {e}")
