from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from app.api.dependencies import get_db
from app.services.retrieval import search_chunks, generate_rag_answer

router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

class SourceResponse(BaseModel):
    document_id: str
    filename: str
    chunk_index: str
    similarity: float

class SearchResponse(BaseModel):
    answer: str
    sources: List[SourceResponse]

@router.post("/", response_model=SearchResponse)
async def search_documents(request: SearchRequest, db: Session = Depends(get_db)):
    try:
        # 1. Retrieve relevant chunks
        chunks = search_chunks(db, request.query, request.top_k)
        
        # 2. Generate answer
        contexts = [chunk.text_content for chunk in chunks]
        answer = generate_rag_answer(request.query, contexts) if contexts else "No relevant documents found in the database."
        
        # 3. Format sources
        # We need query embedding to calculate similarity score for the response
        from app.services.embeddings import generate_embedding
        query_embedding = generate_embedding(request.query)
        
        sources = []
        for chunk in chunks:
            # We fetch the document to get the filename. 
            # In a highly optimized setup, we could join this in the search query.
            doc_filename = chunk.document.filename if chunk.document else "Unknown"
            
            # Since SQLAlchemy pgvector returns distance, we can approximate similarity 
            # 1 - cosine_distance = cosine_similarity
            # For exact math, we would re-calculate or fetch the annotated distance from the query.
            sources.append(
                SourceResponse(
                    document_id=chunk.document_id,
                    filename=doc_filename,
                    chunk_index=chunk.chunk_index,
                    similarity=1.0 # Placeholder for simplicity in output, could be replaced with actual cosine similarity
                )
            )
            
        return SearchResponse(
            answer=answer,
            sources=sources
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

