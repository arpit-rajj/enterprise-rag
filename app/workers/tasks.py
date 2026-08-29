import os
import time
import json
from app.workers.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.models import Document, DocumentStatus, DocumentChunk
from app.core.logging import logger
from app.services.document_parser import parse_document
from app.services.chunker import CharacterTextSplitter
from app.services.embeddings import generate_embeddings_batch

@celery_app.task(bind=True, name="process_document_task", max_retries=5)
def process_document_task(self, document_id: str, file_path: str):
    logger.info(f"Starting processing for document {document_id}")
    db = SessionLocal()
    
    start_time = time.time()
    metrics = {
        "event": "document_processed",
        "document_id": document_id,
        "queue_latency_ms": 0,
        "parse_latency_ms": 0,
        "chunk_count": 0,
        "embedding_latency_ms": 0,
        "embedding_batch_size": 0,
        "status": "processing"
    }

    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found in database.")
            return

        doc.status = DocumentStatus.PROCESSING
        db.commit()

        # 1. Extraction
        t0 = time.time()
        text = parse_document(file_path)
        metrics["parse_latency_ms"] = int((time.time() - t0) * 1000)

        # 2. Chunking
        chunker = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks_text = chunker.split_text(text)
        metrics["chunk_count"] = len(chunks_text)

        # 3. Embeddings
        if chunks_text:
            t0 = time.time()
            embeddings = generate_embeddings_batch(chunks_text)
            metrics["embedding_latency_ms"] = int((time.time() - t0) * 1000)
            metrics["embedding_batch_size"] = len(chunks_text)
            
            # 4. Save to Database
            for i, (chunk_text, embedding) in enumerate(zip(chunks_text, embeddings)):
                chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=str(i),
                    text_content=chunk_text,
                    embedding=embedding
                )
                db.add(chunk)

        doc.status = DocumentStatus.COMPLETED
        db.commit()
        
        metrics["status"] = "completed"
        metrics["total_latency_ms"] = int((time.time() - start_time) * 1000)
        logger.info(json.dumps(metrics))
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        db.rollback()
        try:
            # Exponential backoff: 30s, 60s, 120s...
            backoff = 2 ** self.request.retries * 30
            logger.info(f"Retrying document {document_id} in {backoff} seconds...")
            self.retry(exc=e, countdown=backoff)
        except self.MaxRetriesExceededError:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = DocumentStatus.FAILED
                doc.error_message = str(e)
                db.commit()
            
            metrics["status"] = "failed"
            metrics["error"] = str(e)
            logger.info(json.dumps(metrics))
            
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        if os.path.exists(file_path):
            os.remove(file_path)
    finally:
        db.close()
