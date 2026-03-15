import os
from google import genai

# Common science/math aliases — instant lookup without an API call
ALIASES: dict[str, list[str]] = {
    "oxygen":           ["o2", "o₂", "dioxygen"],
    "carbon dioxide":   ["co2", "co₂"],
    "water":            ["h2o", "h₂o"],
    "hydrogen":         ["h2", "h₂"],
    "nitrogen":         ["n2", "n₂"],
    "sodium chloride":  ["nacl", "salt", "table salt"],
    "glucose":          ["c6h12o6"],
    "photosynthesis":   ["photo synthesis"],
    "herbivore":        ["herbivores", "plant eater", "plant-eater"],
    "carnivore":        ["carnivores", "meat eater", "meat-eater"],
    "omnivore":         ["omnivores"],
    "three":            ["3"],
    "four":             ["4"],
    "yes":              ["true"],
    "no":               ["false"],
}

# Reverse-map so every alias points to its canonical form
_REVERSE: dict[str, str] = {}
for canonical, aliases in ALIASES.items():
    for a in aliases:
        _REVERSE[a.lower()] = canonical
    _REVERSE[canonical.lower()] = canonical


def _normalize(s: str) -> str:
    return s.strip().lower()


def _alias_match(student: str, correct: str) -> bool:
    """Return True if both answers resolve to the same canonical term."""
    return _REVERSE.get(_normalize(student)) == _REVERSE.get(_normalize(correct)) != None


def _gemini_semantic_check(student: str, correct: str) -> bool:
    """Ask Gemini whether the two answers mean the same thing."""
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        prompt = (
            f"You are an answer evaluator for a school quiz.\n"
            f'Correct answer: "{correct}"\n'
            f'Student answer: "{student}"\n\n'
            f"Do these mean the same thing in the context of a school quiz? "
            f"Reply with ONLY 'yes' or 'no'."
        )
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
        )
        return response.text.strip().lower().startswith("yes")
    except Exception as e:
        print(f"[answer_checker] Gemini check failed: {e}")
        return False


def is_correct(student_answer: str, correct_answer: str, question_type: str) -> bool:
    """
    Smart answer comparison:
    1. Exact match (case-insensitive)
    2. Alias / chemical formula lookup
    3. Gemini semantic equivalence check (FillBlank only)
    """
    s = _normalize(student_answer)
    c = _normalize(correct_answer)

    # 1. Exact
    if s == c:
        return True

    # 2. Alias table
    if _alias_match(s, c):
        return True

    # 3. Gemini semantic check — only for fill-in-the-blank
    if question_type == "FillBlank":
        return _gemini_semantic_check(student_answer.strip(), correct_answer.strip())

    return False
