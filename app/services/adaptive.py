import uuid
from sqlalchemy.orm import Session
from app.models import StudentProfile

DIFFICULTY_LEVELS = ["easy", "medium", "hard"]
STREAK_TO_UPGRADE = 3   # 3 correct in a row → harder


def get_or_create_profile(db: Session, student_id: str) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
    if not profile:
        profile = StudentProfile(
            id=str(uuid.uuid4()),
            student_id=student_id,
            current_difficulty="easy",
            correct_streak=0,
            total_answered=0,
            total_correct=0,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_difficulty(profile: StudentProfile, is_correct: bool, db: Session) -> str:
    """
    Adaptive logic:
      - Correct answer: increment streak; upgrade difficulty after STREAK_TO_UPGRADE consecutive correct answers.
      - Wrong answer:   reset streak; downgrade difficulty by one level (if not already at 'easy').
    """
    current_idx = DIFFICULTY_LEVELS.index(profile.current_difficulty)

    profile.total_answered += 1

    if is_correct:
        profile.total_correct += 1
        profile.correct_streak += 1
        if profile.correct_streak >= STREAK_TO_UPGRADE and current_idx < len(DIFFICULTY_LEVELS) - 1:
            profile.current_difficulty = DIFFICULTY_LEVELS[current_idx + 1]
            profile.correct_streak = 0
    else:
        profile.correct_streak = 0
        if current_idx > 0:
            profile.current_difficulty = DIFFICULTY_LEVELS[current_idx - 1]

    db.commit()
    db.refresh(profile)
    return profile.current_difficulty
