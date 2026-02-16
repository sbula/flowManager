try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
from typing import List, Any
from workflow_core.knowledge.llm.provider import LLMProvider

class OpenAIAdapter(LLMProvider):
    def __init__(self, api_key: str, base_url: str = None):
        if OpenAI is None:
            raise ImportError("OpenAI SDK not installed. Run 'poetry install -E openai'")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        # OpenAI embedding
        # Ensure texts are not empty
        clean_texts = [t.replace("\n", " ") for t in texts]
        response = self.client.embeddings.create(input=clean_texts, model=model)
        return [data.embedding for data in response.data]

    def generate(self, prompt: str, model: str, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get('temperature', 0.2),
            max_tokens=kwargs.get('max_tokens', 2048)
        )
        return response.choices[0].message.content
