# Interview Preparation Guide

This document is designed to help you prepare for technical interviews regarding the Enterprise Document Retrieval API (RAG) project.

## 1. Project Explanation

### The "Elevator Pitch" (30 Seconds)
"I built an Enterprise Document Retrieval API, which is an asynchronous RAG backend. It allows users to upload unstructured corporate documents, processes them in the background using Celery, and enables semantic search over the contents using PostgreSQL with pgvector. The system uses OpenAI for embeddings and answer generation, all wrapped in a clean FastAPI REST interface."

### The "Detailed Pitch" (2 Minutes)
"In my RAG project, I focused on building a production-like architecture rather than just a quick script. When a document is uploaded, the FastAPI backend immediately acknowledges the request and offloads the heavy processing—text extraction, chunking, and embedding generation—to a Celery worker backed by Redis. This keeps the API highly responsive. 

For the data layer, I used PostgreSQL. Instead of spinning up a separate vector database like Pinecone, I used the `pgvector` extension. This allowed me to keep document metadata and vector embeddings in the same relational database, simplifying transactions and backups. 

During the query phase, the system vectorizes the user's question, uses pgvector's cosine distance operator to retrieve the most relevant chunks, and injects them into a strict prompt for an LLM to generate an answer. I specifically designed the system to return source citations with the answers to ensure traceability."

## 2. Design Decisions & Trade-offs

### Why FastAPI?
**Reason**: High performance, built-in asynchronous support, automatic validation via Pydantic, and automatic OpenAPI documentation.
**Trade-off**: Smaller ecosystem compared to Django, but for an API-first backend, the speed and typing benefits far outweigh the lack of built-in admin panels.

### Why PostgreSQL + pgvector? (Crucial Question)
**Reason**: Standard vector databases (Pinecone, Milvus) add significant operational overhead (another service to monitor, secure, and sync). By using `pgvector`, we can do a relational join between our document metadata and the vectors in a single query. It is ACID compliant and simplifies the stack.
**Trade-off**: Specialized vector DBs might offer slightly lower latency at massive scale (billions of vectors), but for typical enterprise workloads, `pgvector` with HNSW or IVFFlat indexes is more than sufficient.

### Why Celery + Redis?
**Reason**: Document processing (PDF parsing, API calls to OpenAI for embeddings) is I/O bound and slow. Doing it synchronously in a FastAPI request would cause timeouts and poor UX. Celery handles retries and scales horizontally.
**Trade-off**: Requires running and maintaining a Redis broker and a separate worker process.

### Why Recursive Character Chunking?
**Reason**: We need to keep chunks within the context limit of the LLM while retaining semantic meaning. Splitting by paragraphs/sentences (recursive splitting) is better than naive character splitting which cuts words in half.

## 3. Potential Interview Questions

* **"What happens if the OpenAI API goes down during ingestion?"**
  * *Answer*: Because the ingestion is handled by Celery, the task will fail and can be automatically retried with exponential backoff. The document status in PostgreSQL will reflect `FAILED` if all retries are exhausted, allowing the user to try again later.

* **"How would you scale this system?"**
  * *Answer*: 
    1. **API**: Run multiple FastAPI instances behind a load balancer.
    2. **Workers**: Spin up more Celery worker nodes to process documents in parallel.
    3. **Database**: Add read replicas for the query endpoints, keeping the primary DB for writes (ingestion).

* **"How do you handle security for corporate documents?"**
  * *Answer*: 
    1. **Data at rest**: Encrypt the PostgreSQL volumes and the temporary upload storage.
    2. **Data in transit**: Enforce TLS/HTTPS.
    3. **Access Control**: Implement JWT authentication to ensure users can only query documents they have permission to see (e.g., adding a `tenant_id` column to the Document table).

* **"Why did you use Cosine Similarity instead of Euclidean Distance?"**
  * *Answer*: OpenAI embeddings are normalized. For normalized vectors, cosine similarity and Euclidean distance yield the same ranking. However, cosine similarity is standard for text embeddings because it measures the angle between vectors (semantic meaning) rather than magnitude.
