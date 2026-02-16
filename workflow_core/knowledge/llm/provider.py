from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class LLMProvider(ABC):
    """
    Abstract Base Class defining the contract for all LLM Provider implementations.
    Ensures that the Knowledge System is agnostic to the underlying model source.
    """

    @abstractmethod
    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of strings to embed.
            model: Model identifier string.
            
        Returns:
            List of embedding vectors (list of floats).
        """
        pass

    @abstractmethod
    def generate(self, prompt: str, model: str, **kwargs) -> str:
        """
        Generate a text completion for a given prompt.
        
        Args:
            prompt: The input prompt.
            model: Model identifier string.
            **kwargs: Additional generation parameters (temperature, max_tokens, etc.)
            
        Returns:
            Generated text string.
        """
        pass
