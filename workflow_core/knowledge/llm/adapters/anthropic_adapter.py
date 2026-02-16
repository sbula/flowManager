import anthropic
from typing import List, Any
from workflow_core.knowledge.llm.provider import LLMProvider

class AnthropicAdapter(LLMProvider):
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        # Only supported if Anthropic releases embeddings, otherwise raise error
        # Currently Claude does not have a public embedding API generally available as OpenAI/Gemini
        # We might use VoyageAI or similar if needed, but for now raising NotImplemented
        raise NotImplementedError("Anthropic does not offer a public Embedding API yet. Use Gemini or OpenAI/Ollama for embeddings.")

    def generate(self, prompt: str, model: str, **kwargs) -> str:
        response = self.client.messages.create(
            model=model,
            max_tokens=kwargs.get('max_tokens', 2048),
            temperature=kwargs.get('temperature', 0.2),
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text
