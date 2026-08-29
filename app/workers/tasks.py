import os
from app.workers.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.models import Document, DocumentStatus, DocumentChunk
from app.core.logging import logger
from app.services.document_parser import parse_document
from app.services.chunker import RecursiveCharacterTextSplitter
from app.services.embeddings import generate_embeddings_batch

@celery_app.task(bind=True, name="process_document_task")
def process_document_task(self, document_id: str, file_path: str):
    logger.info(f"Starting processing for document {document_id}")
    db = SessionLocal()
    
    try:
        # Update status to PROCESSING
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found in database.")
            return

        doc.status = DocumentStatus.PROCESSING
        db.commit()

        # 1. Extraction
        logger.info(f"Extracting text from {file_path}")
        text = parse_document(file_path)

        # 2. Chunking
        logger.info("Chunking text")
        chunker = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks_text = chunker.split_text(text)

        # 3. Embeddings
        logger.info(f"Generating embeddings for {len(chunks_text)} chunks")
        if chunks_text:
            embeddings = generate_embeddings_batch(chunks_text)
            
            # 4. Save to Database
            for i, (chunk_text, embedding) in enumerate(zip(chunks_text, embeddings)):
                chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=str(i),
                    text_content=chunk_text,
                    embedding=embedding
                )
                db.add(chunk)

        # Update status to COMPLETED
        doc.status = DocumentStatus.COMPLETED
        db.commit()
        logger.info(f"Document {document_id} processed successfully.")
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        db.rollback()
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(e)
            db.commit()
    finally:
        db.close()
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

