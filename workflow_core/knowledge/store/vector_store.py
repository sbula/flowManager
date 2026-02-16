from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any

class VectorStore(ABC):
    @abstractmethod
    def add(self, 
            embeddings: List[List[float]], 
            documents: List[str], 
            metadatas: List[Dict[str, Any]], 
            ids: List[str]):
        pass

    @abstractmethod
    def query(self, 
              query_embeddings: List[List[float]], 
              n_results: int = 5, 
              where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass
        
    @abstractmethod
    def delete(self, ids: List[str]):
        pass
