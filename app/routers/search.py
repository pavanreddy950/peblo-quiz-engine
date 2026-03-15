from fastapi import APIRouter, Query, HTTPException
from app.database import get_supabase
from app.services.embeddings import get_embedding

router = APIRouter()


@router.get("/search", summary="Semantic search over ingested content using RAG")
def semantic_search(
    query: str = Query(..., description="Natural language query, e.g. 'photosynthesis in plants'"),
    limit: int = Query(5, ge=1, le=20),
):
    """
    Converts the query to a Gemini embedding and retrieves the most
    semantically similar content chunks via pgvector cosine similarity.
    """
    sb = get_supabase()

    try:
        query_embedding = get_embedding(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")

    try:
        result = sb.rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "match_count": limit,
            },
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector search failed: {e}")

    if not result.data:
        raise HTTPException(status_code=404, detail="No similar content found.")

    return {
        "query": query,
        "results": [
            {
                "chunk_id": r["chunk_id"],
                "subject": r["subject"],
                "topic": r["topic"],
                "grade": r["grade"],
                "similarity": round(r["similarity"], 4),
                "text": r["text"][:300] + ("..." if len(r["text"]) > 300 else ""),
            }
            for r in result.data
        ],
    }
