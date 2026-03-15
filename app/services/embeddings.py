import os
from google import genai
from typing import List
from app.services.cache import embedding_cache, make_key


def get_embedding(text: str) -> List[float]:
    """
    Generate a 768-dim embedding via Gemini text-embedding-004.
    Results are cached in memory for 60 minutes to avoid redundant API calls.
    """
    key = make_key("embed", text)
    cached = embedding_cache.get(key)
    if cached is not None:
        return cached

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    result = client.models.embed_content(
        model="text-embedding-004",
        contents=text,
    )
    vector = result.embeddings[0].values
    embedding_cache.set(key, vector)
    return vector
