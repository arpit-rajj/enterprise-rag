# Architecture: Enterprise Document Retrieval API

## Overview
This system is an asynchronous Retrieval-Augmented Generation (RAG) backend designed to process enterprise documents, extract their text, and answer user queries using semantic search against the document contents.

## Components
### 1. FastAPI REST API
Handles client requests for document uploads and query searches. It acts as the gateway to the system and is strictly stateless.

### 2. Celery + Redis Task Queue
Handles the heavy lifting of processing documents. By decoupling ingestion from the API, the system remains responsive.

### 3. PostgreSQL + pgvector
The central database. It stores:
- Document metadata (status, timestamps, source).
- Document chunks.
- Vector embeddings of the chunks using `pgvector` for efficient similarity search.

### 4. OpenAI
Provides the intelligence layer:
- **Embeddings API**: Converts document chunks into high-dimensional vectors (e.g. 1536 dimensions for `text-embedding-3-small`).
- **Chat API**: Synthesizes the final answer given the retrieved context chunks.

## Data Flow
### Ingestion Flow
1. **Upload**: Client uploads a PDF/TXT.
2. **API**: Saves the file temporarily, creates a `PENDING` DB record, and dispatches a Celery task.
3. **Worker (Celery)**:
   - Changes status to `PROCESSING`.
   - Extracts text (`app/services/document_parser.py`).
   - Chunks text (`app/services/chunker.py`).
   - Generates embeddings via OpenAI (`app/services/embeddings.py`).
   - Saves chunks and embeddings to PostgreSQL.
   - Changes status to `COMPLETED`.

### Query Flow
1. **Search**: Client sends a query string to the `/search` endpoint.
2. **API**: Generates an embedding for the query string via OpenAI.
3. **Database**: Performs a cosine similarity search in `pgvector` to find the top-K chunks.
4. **LLM**: The retrieved chunks are formatted into a prompt and sent to the OpenAI Chat API.
5. **Response**: The LLM's answer and the sources (document ID, chunk index) are returned to the client.
