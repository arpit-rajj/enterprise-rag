from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.api.dependencies import get_db
from app.db.models import Document, DocumentStatus
from app.core.logging import logger
from app.workers.tasks import process_document_task
import uuid
import os

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(('.pdf', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload .pdf or .txt files."
        )

    # 1. Create a unique ID for the document
    doc_id = str(uuid.uuid4())
    
    # 2. Save the file temporarily
    file_extension = os.path.splitext(file.filename)[1]
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{file_extension}")
    
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file")

    # 3. Create DB Record
    new_doc = Document(
        id=doc_id,
        filename=file.filename,
        content_type=file.content_type,
        status=DocumentStatus.PENDING
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # 4. Dispatch Celery Task
    process_document_task.delay(doc_id, file_path)

    return {
        "message": "Document uploaded successfully and is pending processing.",
        "document_id": doc_id,
        "status": DocumentStatus.PENDING
    }

@router.get("/{document_id}")
def get_document_status(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "error_message": doc.error_message
    }
