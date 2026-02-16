try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None
from typing import List, Any, Optional
import os
from workflow_core.knowledge.llm.provider import LLMProvider

class GeminiAdapter(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, project_id: Optional[str] = None, location: Optional[str] = None):
        """
        Initialize Gemini Adapter.
        prioritizes API Key. If not present, tries Vertex AI (ADC) if project_id/location are provided.
        """
        if genai is None:
            raise ImportError("Google GenAI SDK not installed. Run 'poetry install -E google'")

        if api_key:
            self.client = genai.Client(api_key=api_key)
            self.mode = "gemini" 
        elif project_id and location:
            self.client = genai.Client(vertexai=True, project=project_id, location=location)
            self.mode = "vertex"
        else:
             # Try environment variable fallback for API Key handled by SDK or fail
             # SDK automatically checks GOOGLE_API_KEY
             if os.environ.get("GOOGLE_API_KEY"):
                 self.client = genai.Client()
                 self.mode = "gemini"
             else:
                 raise ValueError("GeminiAdapter requires either an API Key or (Project ID + Location) for Vertex AI.")

    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        # Map old model names if necessary, or assume config is updated.
        # google-genai uses 'models/embedding-001' or 'text-embedding-004'
        
        result = self.client.models.embed_content(
            model=model,
            contents=texts,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        
        # Result has .embeddings attribute which is a list of objects with .values
        return [e.values for e in result.embeddings]

    def generate(self, prompt: str, model: str, **kwargs) -> str:
        config = types.GenerateContentConfig(
            temperature=kwargs.get('temperature', 0.2),
            top_p=kwargs.get('top_p', 0.95),
            top_k=kwargs.get('top_k', 40),
            max_output_tokens=kwargs.get('max_tokens', 8192 if "flash" in model else 2048),
        )
        
        response = self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=config
        )
        
        return response.text
