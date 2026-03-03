"""LLM adapters package.

Adapter modules live here. Each is lazily loaded by the Factory.
Do NOT import adapter classes here to maintain dependency isolation.
"""

# Adapters are imported lazily by LLMFactory._load_adapter_class().
__all__ = ["GeminiProvider", "AnthropicProvider"]
