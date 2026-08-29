from typing import List
import openai
from sqlalchemy.orm import Session
from app.db.models import DocumentChunk, Document
from app.services.embeddings import generate_embedding
from app.core.config import settings
from app.core.logging import logger

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

def search_chunks(db: Session, query: str, top_k: int = 5) -> List[DocumentChunk]:
    """
    Performs vector similarity search on document chunks using pgvector.
    We use cosine similarity/distance for text embeddings.
    pgvector uses the <=> operator for cosine distance.
    """
    query_embedding = generate_embedding(query)
    
    # We order by cosine distance (embedding <=> query_embedding)
    results = db.query(DocumentChunk).order_by(
        DocumentChunk.embedding.cosine_distance(query_embedding)
    ).limit(top_k).all()
    
    return results

def generate_rag_answer(query: str, contexts: List[str]) -> str:
    """
    Constructs a prompt with the retrieved contexts and generates an answer using an LLM.
    """
    context_str = "\n\n---\n\n".join(contexts)
    
    prompt = f"""You are a helpful enterprise assistant. Answer the question based ONLY on the provided context. 
If the context does not contain enough information to answer the question, say "I don't have enough information to answer that based on the provided documents."
Do not invent information.

Context:
{context_str}

Question: {query}
"""
    
    try:
        response = client.chat.completions.create(
            model=settings.CHAT_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful and precise document retrieval assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0 # Keep it deterministic and factual
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generating RAG answer: {e}")
        raise ValueError(f"Failed to generate answer from LLM: {e}")
