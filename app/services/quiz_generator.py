"""
Quiz generation pipeline with:
  1. Gemini LLM question generation
  2. Question validation + quality scoring
  3. Semantic duplicate detection via embeddings
  4. Embedding cache to avoid redundant API calls
"""
import os
import re
import json
import uuid
from google import genai
from google.genai import types
from typing import List, Dict

from app.services.embeddings import get_embedding
from app.services.question_validator import (
    validate_question,
    is_semantic_duplicate,
    QUALITY_THRESHOLD,
)


def _get_client() -> genai.Client:
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _extract_json(text: str) -> list:
    text = re.sub(r"```(?:json)?", "", text).strip()
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)


def _build_prompt(chunk: Dict) -> str:
    grade = chunk.get("grade", 1)
    subject = chunk.get("subject", "General")
    topic = chunk.get("topic", "General")
    text = chunk["text"]

    if grade and grade <= 2:
        difficulty_guide = "Use only 'easy' difficulty."
    elif grade and grade <= 4:
        difficulty_guide = "Use 'easy' for MCQ, 'easy' for TrueFalse, 'medium' for FillBlank."
    else:
        difficulty_guide = "Use 'medium' for MCQ, 'easy' for TrueFalse, 'hard' for FillBlank."

    return f"""You are an educational quiz generator for school students.

Based ONLY on the content below, generate exactly 3 quiz questions:
1. One MCQ with 4 options
2. One True/False
3. One Fill-in-the-blank

Content:
\"\"\"{text}\"\"\"

Subject: {subject} | Topic: {topic} | Grade: {grade}
{difficulty_guide}

Return ONLY a valid JSON array — no markdown, no explanation.

[
  {{"question":"...","type":"MCQ","options":["A","B","C","D"],"answer":"A","difficulty":"easy"}},
  {{"question":"True or False: ...","type":"TrueFalse","options":["True","False"],"answer":"True","difficulty":"easy"}},
  {{"question":"The ___ has three sides.","type":"FillBlank","options":null,"answer":"triangle","difficulty":"medium"}}
]

Rules:
- All questions must be answerable from the content above.
- MCQ must have exactly 4 distinct options; answer must exactly match one option.
- difficulty ∈ {{easy, medium, hard}}.
"""


def generate_questions_for_chunk(chunk: Dict, client: genai.Client) -> List[Dict]:
    prompt = _build_prompt(chunk)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.4),
    )
    questions_data = _extract_json(response.text.strip())
    questions = []
    for q in questions_data:
        questions.append({
            "question_id": f"Q_{uuid.uuid4().hex[:8].upper()}",
            "chunk_id":    chunk["chunk_id"],
            "question":    q["question"],
            "type":        q["type"],
            "options":     q.get("options"),
            "answer":      q["answer"],
            "difficulty":  q.get("difficulty", "easy"),
            "subject":     chunk.get("subject"),
            "topic":       chunk.get("topic"),
            "grade":       chunk.get("grade"),
        })
    return questions


def generate_quiz_from_chunks(
    chunks: List[Dict],
    max_chunks: int = None,
    existing_question_texts: List[str] = None,
    existing_embeddings: List[List[float]] = None,
    validate: bool = True,
) -> Dict:
    """
    Full pipeline:
      - Generate questions via Gemini
      - Validate quality (Gemini evaluator)
      - Detect semantic duplicates (embedding cosine similarity)
      - Return accepted + rejected questions with reasons

    Args:
        existing_question_texts : list of question strings already in DB
        existing_embeddings     : pre-fetched embeddings for duplicate check
        validate                : set False to skip validation (faster, for testing)
    """
    client = _get_client()
    target = chunks[:max_chunks] if max_chunks else chunks

    accepted:  List[Dict] = []
    rejected:  List[Dict] = []
    seen_embeddings: List[List[float]] = list(existing_embeddings or [])
    existing_texts_lower = {t.lower() for t in (existing_question_texts or [])}

    for chunk in target:
        raw_questions = []
        try:
            raw_questions = generate_questions_for_chunk(chunk, client)
        except Exception as e:
            print(f"[quiz_generator] Generation failed for {chunk['chunk_id']}: {e}")
            continue

        for q in raw_questions:
            reject_reason = None

            # ── 1. Exact text duplicate ────────────────────────────────────
            if q["question"].lower() in existing_texts_lower:
                reject_reason = "exact duplicate"

            # ── 2. Semantic duplicate via embedding ────────────────────────
            q_embedding = None
            if not reject_reason:
                try:
                    q_embedding = get_embedding(q["question"])
                    if is_semantic_duplicate(q_embedding, seen_embeddings):
                        reject_reason = "semantic duplicate (similarity > 0.92)"
                except Exception as e:
                    print(f"[quiz_generator] Embedding failed: {e}")

            # ── 3. Quality validation via Gemini ───────────────────────────
            quality_score = 0.70
            if not reject_reason and validate:
                try:
                    is_valid, quality_score, reason = validate_question(q, chunk["text"])
                    if not is_valid:
                        reject_reason = f"validation failed: {reason}"
                    elif quality_score < QUALITY_THRESHOLD:
                        reject_reason = f"low quality score ({quality_score:.2f} < {QUALITY_THRESHOLD})"
                except Exception as e:
                    print(f"[quiz_generator] Validation error: {e}")

            if reject_reason:
                rejected.append({**q, "reject_reason": reject_reason})
            else:
                q["quality_score"] = round(quality_score, 3)
                q["embedding"] = q_embedding
                accepted.append(q)
                if q_embedding:
                    seen_embeddings.append(q_embedding)
                existing_texts_lower.add(q["question"].lower())

    return {
        "accepted": accepted,
        "rejected": rejected,
        "stats": {
            "total_generated": len(accepted) + len(rejected),
            "accepted":        len(accepted),
            "rejected":        len(rejected),
            "rejection_rate":  f"{len(rejected) / max(len(accepted)+len(rejected),1)*100:.1f}%",
        },
    }
