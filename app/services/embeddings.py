import openai
from typing import List
from app.core.config import settings
from app.core.logging import logger

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_embedding(text: str) -> List[float]:
    """
    Generates an embedding vector for the given text using OpenAI.
    """
    try:
        response = client.embeddings.create(
            input=text,
            model=settings.EMBEDDING_MODEL
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise ValueError(f"Failed to generate embedding: {e}")

def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generates embedding vectors for a batch of texts.
    """
    try:
        response = client.embeddings.create(
            input=texts,
            model=settings.EMBEDDING_MODEL
        )
        return [data.embedding for data in response.data]
    except Exception as e:
        logger.error(f"Error generating batch embeddings: {e}")
        raise ValueError(f"Failed to generate batch embeddings: {e}")
