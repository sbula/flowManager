import chromadb
from typing import List, Dict, Optional, Any
from workflow_core.knowledge.store.vector_store import VectorStore
import os

class ChromaStore(VectorStore):
    def __init__(self, persist_path: str = ".flow/knowledge/db", collection_name: str = "codebase_v1"):
        # Ensure directory exists
        os.makedirs(persist_path, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add(self, 
            embeddings: List[List[float]], 
            documents: List[str], 
            metadatas: List[Dict[str, Any]], 
            ids: List[str]):
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def query(self, 
              query_embeddings: List[List[float]], 
              n_results: int = 5, 
              where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where
        )

    def delete(self, ids: List[str]):
        self.collection.delete(ids=ids)
