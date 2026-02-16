import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow_core.knowledge.service import KnowledgeService

def test_knowledge_stack():
    print("Initializing Knowledge Stack...")
    
    # Mock Config
    config = {
        "knowledge": {
            "embedding_provider": "ollama", # Use local for test if possible, or mock
            "embedding_model": "nomic-embed-text",
            "store_path": ".flow/knowledge/test_db",
            "profiles": {
                "default": {
                    "provider": "ollama",
                    "model": "llama3"
                }
            }
        }
    }
    
    # Ensure Ollama is running or swap to Mock if this is CI
    # For this script we assume manual run on the user machine
    
    try:
        service = KnowledgeService(config)
        print("Service Initialized.")
        
        # 1. Embed & Store
        print("Embedding data...")
        texts = ["The sky is blue.", "Python is a programming language.", "ChromaDB is a vector store."]
        metas = [{"source": "nature"}, {"source": "tech"}, {"source": "tech"}]
        ids = ["1", "2", "3"]
        
        service.embed_and_store(texts, metas, ids)
        print("Data Stored.")
        
        # 2. Query
        print("Querying: 'programming'...")
        results = service.query("programming", n_results=1)
        print(f"Results: {results['documents']}")
        
        # 3. RAG Ask
        print("Asking: 'What is python?'...")
        # Note: This requires a running Ollama instance
        # answer = service.ask("What is python?")
        # print(f"Answer: {answer}")
        print("Skipping LLM generation in this quick test script to avoid timeouts if Ollama not ready")

    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_knowledge_stack()
