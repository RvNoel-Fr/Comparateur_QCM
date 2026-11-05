"""
analysis.py
Analyse statistique cumulative pour un lot de copies (fiches QCM).
"""

from dataclasses import dataclass, field
import statistics
from collections import Counter
from PIL import Image


@dataclass
class StudentSheet:
    """Représente la fiche d'un étudiant au sein du PDF."""
    index: int                                  # Numéro d'ordre (0, 1, 2...)
    name: str                                   # Nom extrait ou saisi ("Dupont Jean")
    name_detected: bool                         # True si extrait du PDF natif
    name_crop: Image.Image | None               # Vignette de la zone nom
    seat_number: int | None = None              # Numéro de placement (1 à N) si présent
    images: list[Image.Image] = field(default_factory=list)        # Pages brutes
    debug_images: list[Image.Image] = field(default_factory=list)  # Pages annotées
    results: list = field(default_factory=list)                    # QuestionResult
    comparison: list = field(default_factory=list)                 # ComparisonRow
    score: dict = field(default_factory=dict)                      # Score dict


@dataclass
class QuestionStat:
    """Statistiques cumulées pour une question donnée."""
    question: int
    correct_answer: str
    total_responses: int
    num_correct: int
    num_incorrect: int
    num_blank: int
    success_rate: float                         # % de réussite (ex: 85.0)
    choice_distribution: dict[str, int]         # {"A": 10, "B": 2, ...}
    difficulty: str                             # "Facile", "Moyen", "Difficile"


@dataclass
class BatchSummary:
    """Synthèse statistique de la promotion / groupe d'étudiants."""
    num_students: int
    total_questions: int
    penalty: float
    average_grade: float
    min_grade: float
    max_grade: float
    median_grade: float
    std_dev_grade: float
    pass_count: int                             # Note >= 10 / 20
    fail_count: int
    pass_rate: float                            # % d'étudiants admis
    avg_correct: float
    avg_incorrect: float
    avg_blank: float
    question_stats: list[QuestionStat] = field(default_factory=list)


def compute_batch_summary(sheets: list[StudentSheet]) -> BatchSummary:
    """
    Calcule toutes les métriques statistiques globales et question par question
    sur l'ensemble des copies fournies.
    """
    if not sheets:
        return BatchSummary(
            num_students=0,
            total_questions=0,
            penalty=0.0,
            average_grade=0.0,
            min_grade=0.0,
            max_grade=0.0,
            median_grade=0.0,
            std_dev_grade=0.0,
            pass_count=0,
            fail_count=0,
            pass_rate=0.0,
            avg_correct=0.0,
            avg_incorrect=0.0,
            avg_blank=0.0,
            question_stats=[]
        )

    n = len(sheets)
    grades = [s.score.get("grade", 0.0) for s in sheets]
    max_possible = sheets[0].score.get("max_grade", 20.0)
    penalty = sheets[0].score.get("penalty", 0.25)
    total_q = sheets[0].score.get("total", 0)

    avg_grade = round(sum(grades) / n, 2)
    min_g = round(min(grades), 2)
    max_g = round(max(grades), 2)
    med_g = round(statistics.median(grades), 2)
    std_g = round(statistics.stdev(grades), 2) if n > 1 else 0.0

    threshold = max_possible / 2.0
    pass_cnt = sum(1 for g in grades if g >= threshold)
    fail_cnt = n - pass_cnt
    pass_pct = round(pass_cnt / n * 100, 1)

    avg_corr = round(sum(s.score.get("correct", 0) for s in sheets) / n, 1)
    avg_inc  = round(sum(s.score.get("incorrect", 0) for s in sheets) / n, 1)
    avg_blk  = round(sum(s.score.get("blank", 0) for s in sheets) / n, 1)

    # ── Analyse question par question ─────────────────────────────────────────
    # Indexer les réponses par question pour chaque étudiant
    q_stats: list[QuestionStat] = []
    # Collecter tous les numéros de questions
    all_q_nums = []
    for s in sheets:
        for r in s.comparison:
            if r.question not in all_q_nums:
                all_q_nums.append(r.question)
    all_q_nums.sort()

    for q in all_q_nums:
        correct_ans = ""
        corr_cnt = 0
        inc_cnt = 0
        blk_cnt = 0
        choices_counter = Counter()

        for s in sheets:
            matching = [r for r in s.comparison if r.question == q]
            if not matching:
                continue
            row = matching[0]
            if not correct_ans and row.correct_answer:
                correct_ans = row.correct_answer

            if row.status == "correct":
                corr_cnt += 1
            elif row.status == "incorrect":
                inc_cnt += 1
            else:
                blk_cnt += 1

            if row.student_answer:
                choices_counter[row.student_answer] += 1

        succ_rate = round(corr_cnt / n * 100, 1) if n > 0 else 0.0

        if succ_rate >= 75.0:
            diff = "Facile"
        elif succ_rate >= 40.0:
            diff = "Moyen"
        else:
            diff = "Difficile"

        q_stats.append(QuestionStat(
            question=q,
            correct_answer=correct_ans,
            total_responses=n,
            num_correct=corr_cnt,
            num_incorrect=inc_cnt,
            num_blank=blk_cnt,
            success_rate=succ_rate,
            choice_distribution=dict(choices_counter),
            difficulty=diff
        ))

    return BatchSummary(
        num_students=n,
        total_questions=total_q,
        penalty=penalty,
        average_grade=avg_grade,
        min_grade=min_g,
        max_grade=max_g,
        median_grade=med_g,
        std_dev_grade=std_g,
        pass_count=pass_cnt,
        fail_count=fail_cnt,
        pass_rate=pass_pct,
        avg_correct=avg_corr,
        avg_incorrect=avg_inc,
        avg_blank=avg_blk,
        question_stats=q_stats
    )
