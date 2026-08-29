# Engineering Decisions & Trade-offs

This document outlines the core architectural and engineering decisions made in the Enterprise Document Retrieval API (RAG), including the rationale behind them and the explicit trade-offs accepted.

## 1. Web Framework: FastAPI

**Decision**: Build the REST API using FastAPI.
**Why**: We need high concurrency for API endpoints and native asynchronous support to integrate smoothly with the async ecosystem. FastAPI provides automatic OpenAPI docs, built-in validation via Pydantic, and extremely high performance.
**Alternative considered**: Django / Django REST Framework.
**Trade-off**: While Django provides a massive ecosystem and a built-in admin panel, its synchronous nature (historically) and heavier footprint make it less ideal for a lean, I/O-heavy microservice. We trade the batteries-included ecosystem for raw async performance.
**Current limitation**: No built-in admin panel to manage documents or users.
**Future improvement**: Implement a custom admin dashboard using a modern frontend framework like React or Vue.

## 2. Database & Vector Search: PostgreSQL + pgvector

**Decision**: Use PostgreSQL with the `pgvector` extension for both metadata and vector storage.
**Why**: RAG applications require querying both structured data (document ownership, upload status) and unstructured data (vector embeddings). Using a single database guarantees ACID compliance, simplifies backups, and avoids the "split-brain" problem of syncing a relational database with a dedicated vector database.
**Alternative considered**: PostgreSQL + Pinecone (or Milvus).
**Trade-off**: Specialized vector databases like Pinecone might offer slightly lower latency at massive scale (billions of vectors) and out-of-the-box SaaS convenience. We trade extreme scale performance for operational simplicity and data consistency.
**Current limitation**: `pgvector` requires manual tuning of indexes (like `m` and `ef_construction` for HNSW) as the dataset grows.
**Future improvement**: Implement partitioning on the `document_chunks` table to keep index sizes manageable as the system scales to hundreds of millions of chunks.

## 3. Asynchronous Processing: Celery + Redis

**Decision**: Offload document ingestion (PDF parsing, chunking, and embedding generation) to Celery background workers.
**Why**: Document processing is I/O-bound and slow. Doing it synchronously in a FastAPI route would block the event loop, cause HTTP timeouts, and lead to a poor user experience. Celery allows us to return a `202 Accepted` immediately, process the file asynchronously, and automatically retry on transient OpenAI API failures using exponential backoff.
**Alternative considered**: FastAPI `BackgroundTasks`.
**Trade-off**: Celery requires running a separate message broker (Redis) and worker processes, increasing infrastructure complexity. `BackgroundTasks` are simpler but lack persistence; if the FastAPI server restarts, pending tasks are lost. We trade simplicity for durability and scalability.
**Current limitation**: RabbitMQ might be a more robust message broker for Celery than Redis for complex routing, but Redis was chosen to double as our semantic cache.
**Future improvement**: Implement Celery task routing to dedicate specific workers to heavy PDF parsing vs. lightweight text processing.

## 4. Chunking Strategy: Character Chunking

**Decision**: Split text into chunks using a simple character-based approach.
**Why**: To prevent exceeding the LLM's context window, we must break large documents into smaller pieces. A basic character splitter is simple to implement and understand as a baseline.
**Alternative considered**: Semantic chunking (e.g., splitting by markdown headers, sentences, or logical sections).
**Trade-off**: Character splitting is fast and predictable but often splits concepts or sentences in half, reducing the quality of the retrieved context.
**Current limitation**: Retrieved chunks may lack necessary surrounding context if a concept spans a chunk boundary.
**Future improvement**: Implement a true recursive semantic chunker that respects document structure (paragraphs, sentences) to improve retrieval relevance.

## 5. Semantic Caching (Redis)

**Decision**: Implement a semantic cache using Redis Vector Search (RediSearch).
**Why**: To reduce OpenAI API costs and response latency. When a user asks a question, we embed it and search Redis for previously asked queries with a similarity ≥ 0.90. If a match is found, we return the cached LLM answer instantly, bypassing pgvector and the OpenAI chat completion call.
**Alternative considered**: Exact string matching caching (e.g., standard Redis `GET`).
**Trade-off**: Higher similarity thresholds reduce incorrect cache reuse but lower the hit rate; lower thresholds improve hit rate at the risk of returning an answer generated for a meaningfully different query. We trade deterministic exact-match accuracy for broader cache utility, requiring empirical tuning of the threshold (currently 0.90).
**Current limitation**: The cache does not currently invalidate if the underlying documents are updated or deleted.
**Future improvement**: Implement cache invalidation logic based on document updates to ensure stale answers are not served.
