import json
import struct
from typing import List, Optional, Tuple
from redis import Redis
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.exceptions import ResponseError
from app.core.config import settings
from app.core.logging import logger

class SemanticCache:
    def __init__(self):
        self.redis_client = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=False)
        self.index_name = "idx:semantic_cache"
        self.vector_dim = 1536 # text-embedding-3-small dimension
        self._init_index()

    def _init_index(self):
        try:
            # Check if index exists
            self.redis_client.ft(self.index_name).info()
        except ResponseError:
            # Create index if it doesn't exist
            logger.info("Creating RediSearch index for semantic caching")
            schema = (
                TextField("answer"),
                VectorField(
                    "embedding",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.vector_dim,
                        "DISTANCE_METRIC": "COSINE",
                    }
                )
            )
            definition = IndexDefinition(prefix=["cache:"], index_type=IndexType.HASH)
            try:
                self.redis_client.ft(self.index_name).create_index(fields=schema, definition=definition)
            except Exception as e:
                logger.error(f"Failed to create Redis semantic cache index: {e}")

    def get_cached_answer(self, query_embedding: List[float], threshold: float = 0.90) -> Optional[str]:
        try:
            # Convert embedding to bytes using struct (float32)
            embedding_bytes = b''.join([struct.pack('f', val) for val in query_embedding])
            
            # We want cosine similarity >= threshold, which means cosine distance <= (1 - threshold)
            max_distance = 1.0 - threshold
            
            # K-Nearest Neighbors query
            q = Query(f"*=>[KNN 1 @embedding $vec AS vector_score]")\
                .sort_by("vector_score")\
                .return_fields("answer", "vector_score")\
                .dialect(2)
            
            res = self.redis_client.ft(self.index_name).search(q, query_params={"vec": embedding_bytes})
            
            if res.docs:
                doc = res.docs[0]
                distance = float(doc.vector_score)
                similarity = 1.0 - distance
                if similarity >= threshold:
                    logger.info(f"Semantic cache hit! Similarity: {similarity:.4f}")
                    return doc.answer.decode('utf-8') if isinstance(doc.answer, bytes) else doc.answer
                
            logger.info("Semantic cache miss.")
            return None
        except Exception as e:
            logger.error(f"Error querying semantic cache: {e}")
            return None

    def set_cached_answer(self, query_embedding: List[float], answer: str):
        try:
            import uuid
            cache_id = f"cache:{uuid.uuid4()}"
            embedding_bytes = b''.join([struct.pack('f', val) for val in query_embedding])
            
            self.redis_client.hset(
                cache_id,
                mapping={
                    "answer": answer,
                    "embedding": embedding_bytes
                }
            )
            # Optional: set TTL for cache entries
            self.redis_client.expire(cache_id, 3600 * 24 * 7) # 7 days
        except Exception as e:
            logger.error(f"Error writing to semantic cache: {e}")

semantic_cache = SemanticCache()
