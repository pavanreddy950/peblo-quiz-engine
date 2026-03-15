import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_supabase
from app.models import QUESTIONS, STUDENT_ANSWERS, STUDENT_PROFILES
from app.services.answer_checker import is_correct as smart_is_correct

router = APIRouter()


class AnswerSubmission(BaseModel):
    student_id: str
    question_id: str
    selected_answer: str


def _get_or_create_profile(sb, student_id: str) -> dict:
    result = sb.table(STUDENT_PROFILES).select("*").eq("student_id", student_id).execute()
    if result.data:
        return result.data[0]
    profile = {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "current_difficulty": "easy",
        "correct_streak": 0,
        "total_answered": 0,
        "total_correct": 0,
    }
    sb.table(STUDENT_PROFILES).insert(profile).execute()
    return profile


def _update_difficulty(sb, profile: dict, is_correct: bool) -> dict:
    levels = ["easy", "medium", "hard"]
    idx = levels.index(profile["current_difficulty"])

    profile["total_answered"] += 1

    if is_correct:
        profile["total_correct"] += 1
        profile["correct_streak"] += 1
        if profile["correct_streak"] >= 3 and idx < 2:
            profile["current_difficulty"] = levels[idx + 1]
            profile["correct_streak"] = 0
    else:
        profile["correct_streak"] = 0
        if idx > 0:
            profile["current_difficulty"] = levels[idx - 1]

    sb.table(STUDENT_PROFILES).update({
        "current_difficulty": profile["current_difficulty"],
        "correct_streak": profile["correct_streak"],
        "total_answered": profile["total_answered"],
        "total_correct": profile["total_correct"],
    }).eq("student_id", profile["student_id"]).execute()

    return profile


@router.post("/submit-answer", summary="Submit a student answer and receive adaptive feedback")
def submit_answer(body: AnswerSubmission):
    sb = get_supabase()

    q_result = sb.table(QUESTIONS).select("*").eq("question_id", body.question_id).execute()
    if not q_result.data:
        raise HTTPException(status_code=404, detail=f"Question '{body.question_id}' not found.")

    question = q_result.data[0]
    is_correct = smart_is_correct(body.selected_answer, question["answer"], question["type"])

    sb.table(STUDENT_ANSWERS).insert({
        "id": str(uuid.uuid4()),
        "student_id": body.student_id,
        "question_id": body.question_id,
        "selected_answer": body.selected_answer,
        "is_correct": is_correct,
    }).execute()

    profile = _get_or_create_profile(sb, body.student_id)
    profile = _update_difficulty(sb, profile, is_correct)

    total = profile["total_answered"]
    correct = profile["total_correct"]

    return {
        "student_id": body.student_id,
        "question_id": body.question_id,
        "selected_answer": body.selected_answer,
        "correct_answer": question["answer"],
        "is_correct": is_correct,
        "feedback": "Correct! Great job!" if is_correct else f"Incorrect. The correct answer is: {question['answer']}",
        "adaptive_difficulty": {
            "current_difficulty": profile["current_difficulty"],
            "correct_streak": profile["correct_streak"],
            "total_answered": total,
            "total_correct": correct,
            "accuracy_percent": round(correct / total * 100, 1) if total > 0 else 0.0,
        },
    }


@router.get("/student/{student_id}/profile", summary="Get a student's adaptive learning profile")
def get_student_profile(student_id: str):
    sb = get_supabase()
    profile = _get_or_create_profile(sb, student_id)
    total = profile["total_answered"]
    correct = profile["total_correct"]
    return {
        "student_id": profile["student_id"],
        "current_difficulty": profile["current_difficulty"],
        "correct_streak": profile["correct_streak"],
        "total_answered": total,
        "total_correct": correct,
        "accuracy_percent": round(correct / total * 100, 1) if total > 0 else 0.0,
    }
