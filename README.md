# Enterprise Document Retrieval API

## Problem
Modern enterprises possess massive amounts of unstructured data locked in PDFs, policy documents, and manuals. Employees spend hours searching for specific answers, often relying on keyword searches that fail to understand the semantic intent of the query. 

This project solves that problem by implementing an asynchronous **Retrieval-Augmented Generation (RAG)** pipeline. It allows users to upload documents, which are automatically parsed, embedded, and stored. Users can then ask natural language questions, and the system will retrieve the most relevant information and synthesize a precise answer using an LLM, complete with source citations.

## Architecture
The system is designed with a production-ready mindset, separating the fast, stateless API from the slow, I/O-bound document processing pipeline.

```text
                    ┌──────────────────┐
                    │      Client      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │     FastAPI      │
                    │    REST API      │
                    └────────┬─────────┘
                             │
               ┌─────────────┴──────────────┐
               │                            │
               ▼                            ▼
       Document Upload                 Query Endpoint
               │                            │
               ▼                            ▼
        Create Ingestion              Generate Query
             Task                       Embedding
               │                            │
               ▼                            ▼
            Celery                   pgvector Search
               │                            │
               ▼                            ▼
        Worker Process                Top-K Chunks
               │                            │
               ▼                            │
       Extract Document                     │
               │                            │
               ▼                            │
           Chunking                         │
               │                            │
               ▼                            │
         Generate Embeddings                │
               │                            │
               ▼                            │
       PostgreSQL + pgvector ◄──────────────┘
               │
               ▼
        Retrieved Context
               │
               ▼
          OpenAI API
               │
               ▼
             Answer
```

## Tech Stack
* **Python**: Core programming language.
* **FastAPI**: High-performance, asynchronous web framework for building the REST API.
* **PostgreSQL + pgvector**: Relational database used to store both structured document metadata and high-dimensional vector embeddings, eliminating the need for a separate vector database.
* **Celery & Redis**: Distributed task queue for handling asynchronous document processing (parsing, chunking, and calling OpenAI).
* **OpenAI API**: Provides the intelligence layer (`text-embedding-3-small` for embeddings and `gpt-4o-mini` for generation).
* **PyPDF2**: Pure Python library for extracting text from PDF documents.
* **SQLAlchemy & Alembic**: ORM and database migration tools.

## Project Structure
```text
enterprise-rag-api/
├── app/
│   ├── api/          # FastAPI routes (upload, search)
│   ├── core/         # Configuration and logging
│   ├── db/           # SQLAlchemy models and database setup
│   ├── services/     # Core logic (chunking, embedding, parsing, retrieval)
│   └── workers/      # Celery task definitions and app setup
├── docs/             # Architecture and interview prep documentation
├── tests/            # Unit and API tests
├── docker-compose.yml# Local infrastructure (Postgres, Redis)
└── requirements.txt  # Python dependencies
```

## Data Flow
### Document Ingestion
1. A user uploads a `.pdf` or `.txt` file via `POST /api/v1/documents/upload`.
2. The API creates a `PENDING` record in PostgreSQL and saves the file temporarily.
3. A Celery task is dispatched to process the file in the background. The API immediately returns a success response to the client.
4. The Celery worker picks up the task:
   - Parses the text from the file.
   - Chunks the text into smaller segments (1000 characters) to fit LLM context windows.
   - Calls the OpenAI API to generate embeddings for each chunk.
   - Stores the chunks and embeddings in the `document_chunks` table in PostgreSQL.
5. The document status is updated to `COMPLETED`.

### Query / Retrieval
1. A user submits a question via `POST /api/v1/search/`.
2. The system generates an embedding for the user's question using OpenAI.
3. Using `pgvector` and the `<=>` (cosine distance) operator, the system queries the database for the top 5 most semantically similar chunks.
4. The retrieved chunks are injected into a strict prompt.
5. The OpenAI Chat API is called to synthesize a final answer based *only* on the provided context.
6. The answer and the source citations are returned to the user.

## Setup
### 1. Infrastructure
Run PostgreSQL and Redis using Docker:
```bash
docker-compose up -d
```

### 2. Environment
Copy the `.env.example` file to `.env` and fill in your OpenAI API key.
```bash
cp .env.example .env
```

### 3. Installation
Set up a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Database Migrations
Initialize the database schema using Alembic:
```bash
alembic upgrade head
```

### 5. Running the Application
Start the Celery worker (in one terminal):
```bash
celery -A app.workers.celery_app worker --loglevel=info
```

Start the FastAPI server (in another terminal):
```bash
uvicorn app.main:app --reload
```

## Database
We use **PostgreSQL** with the **pgvector** extension. 
* `documents`: Tracks the file metadata and ingestion status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`).
* `document_chunks`: Stores the actual extracted text chunks, a foreign key to the parent document, and a `Vector(1536)` column for the OpenAI embeddings.

## Celery
Document processing involves reading large files and making external HTTP requests to OpenAI. If done synchronously in the FastAPI route, it would block the event loop and lead to poor performance or timeouts. **Celery** offloads this work to a separate process, using **Redis** as the message broker.

## API Endpoints
* `POST /api/v1/documents/upload`: Upload a document for asynchronous processing.
* `GET /api/v1/documents/{id}`: Check the status of a document.
* `POST /api/v1/search/`: Query the knowledge base.

## Testing
Run the test suite using `pytest`:
```bash
pytest tests/
```

## Design Decisions
See `docs/architecture.md` and `docs/interview-preparation.md` for in-depth explanations of why specific technologies (FastAPI, pgvector, Celery) were chosen over alternatives.

## Limitations
* **Basic Chunking**: The current chunking strategy splits by character length. A semantic chunker (e.g., splitting by markdown headers or logical sections) would improve retrieval quality.
* **Basic Retrieval**: The system uses naive Top-K cosine similarity. 

## Future Improvements
* **Hybrid Search**: Combine vector search with full-text keyword search (BM25) using PostgreSQL's native text search features.
* **Reranking**: Implement a cross-encoder model (like Cohere Rerank) to re-order the retrieved chunks before passing them to the LLM.
* **Authentication**: Add JWT-based authentication and multi-tenancy so users can only search their own documents.
* **Caching**: Cache identical semantic queries using Redis to save OpenAI API costs.
