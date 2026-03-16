import os
import requests
from typing import List
from app.services.cache import embedding_cache, make_key


def get_embedding(text: str) -> List[float]:
    """
    Generate a 768-dim embedding via Gemini text-embedding-004 REST API.
    Results are cached in memory for 60 minutes to avoid redundant API calls.
    """
    key = make_key("embed", text)
    cached = embedding_cache.get(key)
    if cached is not None:
        return cached

    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"
    response = requests.post(url, json={
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": 768
    })
    if response.status_code != 200:
        raise RuntimeError(f"Embedding generation failed: {response.status_code} {response.text}")

    vector = response.json()["embedding"]["values"]
    embedding_cache.set(key, vector)
    return vector
