from typing import Dict, Any, List, Optional
from workflow_core.knowledge.llm.gateway import LLMGateway
from workflow_core.knowledge.store.chroma_store import ChromaStore
import json
import os

class KnowledgeService:
    _instance = None

    def __new__(cls, config: Dict[str, Any]):
        if cls._instance is None:
            cls._instance = super(KnowledgeService, cls).__new__(cls)
            cls._instance.gateway = LLMGateway(config)
            cls._instance.store = ChromaStore(
                persist_path=config.get('knowledge', {}).get('store_path', '.flow/knowledge/db'),
                collection_name=config.get('knowledge', {}).get('collection_name', 'codebase_v1')
            )
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError("KnowledgeService not initialized. Call constructor with config first.")
        return cls._instance

    def embed_and_store(self, 
                        texts: List[str], 
                        metadatas: List[Dict[str, Any]], 
                        ids: List[str]):
        """
        Embeds texts using the configured embedding provider and stores them in Chroma.
        """
        embeddings = self.gateway.embed(texts)
        self.store.add(embeddings, texts, metadatas, ids)

    def query(self, 
              query_text: str, 
              n_results: int = 5, 
              filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Semantic search.
        """
        embedding = self.gateway.embed([query_text])
        return self.store.query(
            query_embeddings=embedding,
            n_results=n_results,
            where=filters
        )

    def ask(self, 
            question: str, 
            profile: str = 'default', 
            include_decisions: bool = True) -> str:
        """
        RAG Q&A. 
        1. Retrieve context.
        2. Filter decisions if needed.
        3. Construct prompt.
        4. Generate answer.
        """
        # 1. Retrieve
        filters = {}
        if not include_decisions:
           # Filter out decision types? Chroma filtering is limited to exact matches usually
           # Better to retrieve and then post-filter if complex logic needed
           pass
           
        context_results = self.query(question, n_results=10, filters=filters)
        
        # 2. Construct Context
        docs = context_results['documents'][0]
        metas = context_results['metadatas'][0]
        
        context_str = ""
        for doc, meta in zip(docs, metas):
            # If strictly filtering decisions out 
            if not include_decisions and meta.get('type') == 'decision':
                continue
            
            source = meta.get('document_id', 'unknown')
            context_str += f"--- Source: {source} ---\n{doc}\n\n"
            
        # 3. Prompt
        prompt = f"""
        Context from Codebase:
        {context_str}
        
        Question: {question}
        
        Answer based on the context above.
        """
        
        # 4. Generate
        return self.gateway.generate(prompt, profile=profile)
