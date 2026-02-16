import ollama
from typing import List, Any
from workflow_core.knowledge.llm.provider import LLMProvider

class OllamaAdapter(LLMProvider):
    def __init__(self, base_url: str = None):
        # Ollama python client uses OLLAMA_HOST env var, or defaults to localhost:11434
        if base_url:
            # We can set the client explicitly if the library supports instance-based client
            # The official 'ollama' lib is stateful/module-based mostly, but check recent updates.
            # For simplicity, we assume standard env setup or simplified usage.
            self.client = ollama.Client(host=base_url)
        else:
            self.client = ollama.Client()

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        embeddings = []
        for text in texts:
            response = self.client.embeddings(model=model, prompt=text)
            embeddings.append(response['embedding'])
        return embeddings

    def generate(self, prompt: str, model: str, **kwargs) -> str:
        options = {
            'temperature': kwargs.get('temperature', 0.2),
            'num_predict': kwargs.get('max_tokens', 2048),
        }
        response = self.client.generate(model=model, prompt=prompt, options=options)
        return response['response']
