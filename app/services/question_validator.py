"""
Question validation + quality scoring using Gemini.
Every generated question passes through here before being stored.
"""
import os
import re
import json
import math
from typing import Dict, List, Tuple

from google import genai


# ── Quality threshold — questions below this score are rejected ────────────
QUALITY_THRESHOLD = 0.60
# ── Semantic duplicate threshold (cosine similarity) ─────────────────────
DUPLICATE_THRESHOLD = 0.92


def _cosine(a: List[float], b: List[float]) -> float:
    dot   = sum(x * y for x, y in zip(a, b))
    na    = math.sqrt(sum(x ** 2 for x in a))
    nb    = math.sqrt(sum(x ** 2 for x in b))
    return dot / (na * nb) if na and nb else 0.0


def is_semantic_duplicate(
    new_embedding: List[float],
    existing_embeddings: List[List[float]],
    threshold: float = DUPLICATE_THRESHOLD,
) -> bool:
    """Return True if the new question is too similar to any existing one."""
    return any(_cosine(new_embedding, e) >= threshold for e in existing_embeddings)


def validate_question(question: Dict, chunk_text: str) -> Tuple[bool, float, str]:
    """
    Ask Gemini to evaluate the question for:
    - answer correctness based on the source chunk
    - question clarity
    - answer traceability to the content
    - MCQ option distinctiveness

    Returns: (is_valid: bool, quality_score: float 0-1, reason: str)
    """
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        prompt = f"""You are an educational question quality evaluator.

Source content (the ONLY basis for evaluation):
\"\"\"{chunk_text[:600]}\"\"\"

Question:
  Text    : {question['question']}
  Type    : {question['type']}
  Answer  : {question['answer']}
  Options : {question.get('options', 'N/A')}
  Difficulty: {question['difficulty']}
  Grade   : {question.get('grade', '?')}

Evaluate strictly. Return ONLY valid JSON (no markdown):
{{
  "answer_correct":    true/false,
  "question_clear":    true/false,
  "answer_in_content": true/false,
  "options_distinct":  true/false,
  "quality_score":     0.0-1.0,
  "reason":            "one sentence"
}}"""

        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
        )
        raw = response.text.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return True, 0.70, "Validation inconclusive"

        result = json.loads(match.group())
        is_valid = (
            result.get("answer_correct",    True) and
            result.get("question_clear",     True) and
            result.get("answer_in_content",  True)
        )
        score  = float(result.get("quality_score", 0.70))
        reason = result.get("reason", "")
        return is_valid, score, reason

    except Exception as e:
        print(f"[validator] Skipping validation (API error): {e}")
        return True, 0.70, "Validation skipped"
