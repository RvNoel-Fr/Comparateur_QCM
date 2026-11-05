"""
comparator.py
Compare les réponses d'un étudiant avec la correction.
"""

from dataclasses import dataclass
from app.detector import QuestionResult


# ──────────────────────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ComparisonRow:
    """Résultat de la comparaison pour une question."""
    question: int
    student_answer: str      # "A", "B", "C", "D", "A, B" ou ""
    correct_answer: str      # "A", "B", "C", "D" ou ""
    status: str              # "correct" | "incorrect" | "blank"
    is_multiple: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Comparaison
# ──────────────────────────────────────────────────────────────────────────────

def compare(student: list[QuestionResult],
            correction: list[QuestionResult]) -> list[ComparisonRow]:
    """
    Compare deux listes de résultats (étudiant vs correction).

    Règle :
      - 0 case cochée : "blank" (non répondu).
      - > 1 case cochée : "incorrect" (mauvaise réponse / invalidée).
      - 1 case cochée == attendu : "correct".
      - 1 case cochée != attendu : "incorrect".

    Returns:
        Liste de ComparisonRow triée par numéro de question.
    """
    # Index par numéro de question
    student_map = {qr.question: qr for qr in student}
    correct_map = {qr.question: qr for qr in correction}

    all_questions = sorted(set(student_map) | set(correct_map))

    rows: list[ComparisonRow] = []
    for q in all_questions:
        sqr = student_map.get(q)
        cqr = correct_map.get(q)

        sa = sqr.answer if sqr else ""
        ca = cqr.answer if cqr else ""
        is_multiple = (sqr.filled_count > 1) if sqr else ("," in sa)

        if sa == "":
            status = "blank"
        elif is_multiple:
            # Plus d'une case cochée : systématiquement traitée comme mauvaise réponse
            status = "incorrect"
        elif sa == ca:
            status = "correct"
        else:
            status = "incorrect"

        rows.append(ComparisonRow(
            question=q,
            student_answer=sa,
            correct_answer=ca,
            status=status,
            is_multiple=is_multiple
        ))

    return rows


def summary(rows: list[ComparisonRow]) -> dict:
    """
    Retourne un dictionnaire de synthèse :
      correct   : nombre de bonnes réponses
      incorrect : nombre de mauvaises réponses
      blank     : nombre de questions sans réponse
      total     : nombre total de questions
    """
    correct = sum(1 for r in rows if r.status == "correct")
    incorrect = sum(1 for r in rows if r.status == "incorrect")
    blank = sum(1 for r in rows if r.status == "blank")
    return {
        "correct": correct,
        "incorrect": incorrect,
        "blank": blank,
        "total": len(rows),
    }
