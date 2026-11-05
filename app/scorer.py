"""
scorer.py
Calcule la note sur 20 à partir des résultats de comparaison.

Formule :
    points = bonnes - (mauvaises × pénalité)
    note   = max(0, points / total) × 20

Par défaut, pénalité = 0.25 (pénalise 1 mauvaise réponse sur 4).
Les questions sans réponse ne sont ni bonifiées ni pénalisées.
"""

from app.comparator import ComparisonRow


def calculate_score(rows: list[ComparisonRow],
                    penalty: float = 0.25,
                    max_grade: float = 20.0) -> dict:
    """
    Calcule la note finale.

    Args:
        rows:      Liste des comparaisons (issue de comparator.compare).
        penalty:   Fraction de point déduite par mauvaise réponse (0 = pas de pénalité).
        max_grade: Note maximale (défaut 20).

    Returns:
        Dictionnaire avec :
          - correct, incorrect, blank, total
          - raw_points : points bruts (avant plafonnage à 0)
          - grade      : note finale arrondie à 2 décimales
          - percent    : pourcentage de réussite (0–100)
    """
    correct = sum(1 for r in rows if r.status == "correct")
    incorrect = sum(1 for r in rows if r.status == "incorrect")
    blank = sum(1 for r in rows if r.status == "blank")
    total = len(rows)

    raw_points = correct - incorrect * penalty
    clamped = max(0.0, raw_points)
    grade = round(clamped / total * max_grade, 2) if total > 0 else 0.0
    percent = round(clamped / total * 100, 1) if total > 0 else 0.0

    return {
        "correct": correct,
        "incorrect": incorrect,
        "blank": blank,
        "total": total,
        "penalty": penalty,
        "raw_points": round(raw_points, 2),
        "grade": grade,
        "max_grade": max_grade,
        "percent": percent,
    }
