import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase
from app.models import CHUNKS, QUESTIONS
from app.services.quiz_generator import generate_quiz_from_chunks
from app.services.cache import quiz_cache, make_key

router = APIRouter()


@router.post("/generate-quiz", summary="Generate quiz questions (with validation, dedup & embeddings)")
def generate_quiz(
    source_id:  Optional[str] = Query(None),
    subject:    Optional[str] = Query(None),
    max_chunks: Optional[int] = Query(None),
    validate:   bool          = Query(True, description="Run Gemini quality validation"),
):
    sb = get_supabase()

    # ── Fetch chunks ───────────────────────────────────────────────────────
    q = sb.table(CHUNKS).select("*")
    if source_id:
        q = q.eq("source_id", source_id)
    if subject:
        q = q.ilike("subject", f"%{subject}%")
    chunks = q.execute().data

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No chunks found. Ingest PDFs first via POST /ingest.",
        )

    # ── Fetch existing questions for duplicate detection ───────────────────
    existing_rows = sb.table(QUESTIONS).select("question, embedding").execute().data
    existing_texts     = [r["question"] for r in existing_rows]
    existing_embeddings = [
        r["embedding"] for r in existing_rows if r.get("embedding")
    ]

    # ── Run full pipeline ──────────────────────────────────────────────────
    result = generate_quiz_from_chunks(
        chunks,
        max_chunks=max_chunks,
        existing_question_texts=existing_texts,
        existing_embeddings=existing_embeddings,
        validate=validate,
    )

    # ── Persist accepted questions ─────────────────────────────────────────
    stored = []
    for q_data in result["accepted"]:
        embedding = q_data.pop("embedding", None)
        row = {
            "id":           str(uuid.uuid4()),
            "question_id":  q_data["question_id"],
            "chunk_id":     q_data["chunk_id"],
            "question":     q_data["question"],
            "type":         q_data["type"],
            "options":      q_data["options"],
            "answer":       q_data["answer"],
            "difficulty":   q_data["difficulty"],
            "subject":      q_data["subject"],
            "topic":        q_data["topic"],
            "grade":        q_data["grade"],
            "quality_score": q_data.get("quality_score", 0.7),
            "embedding":    embedding,
        }
        sb.table(QUESTIONS).insert(row).execute()
        stored.append(q_data)

    # Invalidate quiz cache when new questions are added
    if stored:
        quiz_cache.clear()

    return {
        "message": f"Stored {len(stored)} new questions.",
        "pipeline_stats": result["stats"],
        "rejected_questions": [
            {"question": r["question"], "reason": r["reject_reason"]}
            for r in result["rejected"]
        ],
        "sample": stored[:3],
    }


@router.get("/quiz", summary="Retrieve quiz questions (cached, with filters)")
def get_quiz(
    topic:         Optional[str] = Query(None),
    difficulty:    Optional[str] = Query(None),
    subject:       Optional[str] = Query(None),
    grade:         Optional[int] = Query(None),
    question_type: Optional[str] = Query(None),
    limit:         int           = Query(10, ge=1, le=100),
    min_quality:   float         = Query(0.0, description="Minimum quality score filter"),
):
    # ── Cache lookup ───────────────────────────────────────────────────────
    cache_key = make_key(topic, difficulty, subject, grade, question_type, limit, min_quality)
    cached = quiz_cache.get(cache_key)
    if cached:
        return {**cached, "cached": True}

    sb = get_supabase()
    q = sb.table(QUESTIONS).select("*")

    if topic:
        q = q.ilike("topic", f"%{topic}%")
    if difficulty:
        q = q.eq("difficulty", difficulty)
    if subject:
        q = q.ilike("subject", f"%{subject}%")
    if grade:
        q = q.eq("grade", grade)
    if question_type:
        q = q.eq("type", question_type)
    if min_quality > 0:
        q = q.gte("quality_score", min_quality)

    questions = q.limit(limit).execute().data

    if not questions:
        raise HTTPException(status_code=404, detail="No questions found for the given filters.")

    response = {
        "total":   len(questions),
        "cached":  False,
        "filters": {
            "topic": topic, "difficulty": difficulty, "subject": subject,
            "grade": grade, "question_type": question_type, "min_quality": min_quality,
        },
        "questions": [
            {
                "question_id":   q["question_id"],
                "question":      q["question"],
                "type":          q["type"],
                "options":       q["options"],
                "difficulty":    q["difficulty"],
                "subject":       q["subject"],
                "topic":         q["topic"],
                "grade":         q["grade"],
                "quality_score": q.get("quality_score"),
                "chunk_id":      q["chunk_id"],
            }
            for q in questions
        ],
    }

    quiz_cache.set(cache_key, response)
    return response


@router.get("/cache/stats", summary="View cache statistics")
def cache_stats():
    return {
        "quiz_cache":      quiz_cache.stats(),
        "embedding_cache": quiz_cache.stats(),
    }


@router.delete("/cache", summary="Clear all caches")
def clear_cache():
    quiz_cache.clear()
    return {"message": "All caches cleared."}
