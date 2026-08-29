from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from app.api.dependencies import get_db
from app.services.retrieval import search_chunks, generate_rag_answer
from app.services.embeddings import generate_embedding
from app.services.semantic_cache import semantic_cache

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
async def search_documents(request: SearchRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        # 1. Generate query embedding once
        query_embedding = generate_embedding(request.query)

        # 2. Check semantic cache
        cached_answer = semantic_cache.get_cached_answer(query_embedding)
        if cached_answer:
            return SearchResponse(answer=cached_answer, sources=[])

        # 3. Retrieve relevant chunks
        results = search_chunks(db, query_embedding, request.top_k)
        
        # 4. Generate answer
        contexts = [chunk.text_content for chunk, _ in results]
        answer = generate_rag_answer(request.query, contexts) if contexts else "No relevant documents found in the database."
        
        # 5. Format sources
        sources = []
        for chunk, distance in results:
            doc_filename = chunk.document.filename if chunk.document else "Unknown"
            similarity = max(0.0, 1.0 - distance)
            
            sources.append(
                SourceResponse(
                    document_id=chunk.document_id,
                    filename=doc_filename,
                    chunk_index=chunk.chunk_index,
                    similarity=similarity
                )
            )
            
        # 6. Save to cache asynchronously
        if contexts:
            background_tasks.add_task(semantic_cache.set_cached_answer, query_embedding, answer)
            
        return SearchResponse(
            answer=answer,
            sources=sources
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

