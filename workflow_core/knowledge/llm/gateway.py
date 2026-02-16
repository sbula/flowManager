from typing import Dict, Any, Optional
import os
from workflow_core.knowledge.llm.provider import LLMProvider
from workflow_core.knowledge.llm.adapters.gemini_adapter import GeminiAdapter
from workflow_core.knowledge.llm.adapters.openai_adapter import OpenAIAdapter
from workflow_core.knowledge.llm.adapters.anthropic_adapter import AnthropicAdapter
from workflow_core.knowledge.llm.adapters.ollama_adapter import OllamaAdapter

class LLMGateway:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.providers: Dict[str, LLMProvider] = {}
        self._init_providers()

    def _init_providers(self):
        """Initialize all providers defined in the configuration profiles."""
        profiles = self.config.get('knowledge', {}).get('profiles', {})
        
        # Collect unique providers required
        required_providers = set()
        for profile in profiles.values():
            if 'provider' in profile:
                required_providers.add(profile['provider'])
        
        # Instantiate them
        # Instantiate them
        if 'gemini' in required_providers:
            # Check for API Key OR Vertex Config
            api_key = os.getenv("GOOGLE_API_KEY")
            
            # Get Vertex config from default profile or specific gemini profile
            # For iteration 1, we look at 'default' profile if it is gemini
            vertex_project = None
            vertex_location = None
            
            # Simple lookup strategy: Check default profile
            default_profile = profiles.get('default', {})
            if default_profile.get('provider') == 'gemini':
                vertex_project = default_profile.get('project_id')
                vertex_location = default_profile.get('location')
            
            if api_key or (vertex_project and vertex_location):
                self.providers['gemini'] = GeminiAdapter(
                    api_key=api_key, 
                    project_id=vertex_project, 
                    location=vertex_location
                )
            else:
                 # Warn or just don't init?
                 # If user has ADC via gcloud auth, SDK handles it but requires project/loc usually for Vertex
                 # If standard Gemini API via ADC? Not common.
                 # Let's try to init without args and let Adapter fail if no auth found.
                 try:
                     self.providers['gemini'] = GeminiAdapter()
                 except ValueError:
                     pass # Failed to init
                
        if 'openai' in required_providers:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.providers['openai'] = OpenAIAdapter(api_key=api_key)
                
        if 'anthropic' in required_providers:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.providers['anthropic'] = AnthropicAdapter(api_key=api_key)

        if 'ollama' in required_providers:
             # Ollama usually needs no key, just base_url if remote
             # We check if there's a specific profile config for base_url
             # For now, default to local
             self.providers['ollama'] = OllamaAdapter()

    def generate(self, prompt: str, profile: str = 'default') -> str:
        """
        Route the generation request to the appropriate provider/model 
        defined in the profile.
        """
        knowledge_config = self.config.get('knowledge', {})
        profiles = knowledge_config.get('profiles', {})
        
        # Fallback to default if profile not found
        target_profile = profiles.get(profile, profiles.get('default'))
        
        if not target_profile:
            raise ValueError(f"No profile found for '{profile}' and no default profile configured.")
            
        provider_name = target_profile['provider']
        model_name = target_profile['model']
        
        provider = self.providers.get(provider_name)
        if not provider:
             raise ValueError(f"Provider '{provider_name}' is not initialized (check API keys).")
             
        # Extract extra args (temperature, etc)
        kwargs = {k: v for k, v in target_profile.items() if k not in ['provider', 'model', 'description']}
        
        return provider.generate(prompt, model=model_name, **kwargs)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Route embedding request. Usually uses a dedicated embedding provider/model 
        globally configured, not per-profile.
        """
        knowledge_config = self.config.get('knowledge', {})
        provider_name = knowledge_config.get('embedding_provider', 'gemini')
        model_name = knowledge_config.get('embedding_model', 'models/embedding-001')
        
        provider = self.providers.get(provider_name)
        if not provider:
            # Try to lazy init if not present (might be embedding-only provider)
            # For iteration 1, assume it must be in profiles or we fail
             raise ValueError(f"Embedding Provider '{provider_name}' is not initialized.")
             
        return provider.embed(texts, model=model_name)
