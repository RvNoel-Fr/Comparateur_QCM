"""
make_test_pdfs.py
Génère deux PDFs de test (QCM étudiant + correction) avec des cases à cocher
dessinées, pour valider la détection OpenCV.

Usage :
    python make_test_pdfs.py

Produit :
    test_student.pdf   — QCM avec les réponses d'un étudiant fictif
    test_correction.pdf — Correction officielle
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


# ──────────────────────────────────────────────────────────────────────────────
# Données de test : 20 questions, 4 choix chacune
# ──────────────────────────────────────────────────────────────────────────────

# Clé de correction (index 0–3 = A–D)
CORRECT_KEY = [
    0, 1, 2, 3, 0, 1, 2, 0, 1, 3,   # Q1–Q10
    2, 0, 1, 3, 2, 1, 0, 3, 2, 1,   # Q11–Q20
]

# Réponses étudiant (quelques erreurs et blancs)
STUDENT_ANSWERS = [
    0, 1, 2, 3, 0, 1, 2, 0, 1, 3,   # Q1–Q10 : toutes correctes
    2, 0, 1, 2, 2, 1, 0, 3, 2, 0,   # Q11–Q20 : Q14, Q20 incorrectes
]
# -1 = pas de réponse
# On met Q7 sans réponse pour tester le cas "blank"
STUDENT_ANSWERS[6] = -1


CHOICES = ["A", "B", "C", "D"]
PAGE_H, PAGE_W = A4   # hauteur, largeur en points

# ──────────────────────────────────────────────────────────────────────────────
# Paramètres de mise en page
# ──────────────────────────────────────────────────────────────────────────────

MARGIN_LEFT   = 3 * cm
MARGIN_TOP    = 2.5 * cm
BOX_SIZE      = 0.45 * cm     # taille d'une case (doit être ~12-55 px @ 200dpi)
CHOICE_SPACING = 1.8 * cm     # espacement horizontal entre choix
ROW_HEIGHT    = 0.9 * cm      # espacement vertical entre questions
QUESTIONS_PER_PAGE = 10


def _draw_page(c: canvas.Canvas, questions: list[tuple[int, int, int]],
               page_num: int, total_pages: int, title: str):
    """
    Dessine une page du QCM.

    questions : liste de (q_num, correct_idx, student_idx)  1-based q_num
    """
    w, h = A4

    # En-tête
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN_LEFT, h - MARGIN_TOP, title)
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 2*cm, h - MARGIN_TOP,
                       f"Page {page_num}/{total_pages}")

    # Ligne de séparation
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.5)
    c.line(MARGIN_LEFT, h - MARGIN_TOP - 0.3*cm,
            w - 2*cm, h - MARGIN_TOP - 0.3*cm)

    # Légende choix
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    label_y = h - MARGIN_TOP - 0.9*cm
    for i, lbl in enumerate(CHOICES):
        cx = MARGIN_LEFT + 3*cm + i * CHOICE_SPACING
        c.drawCentredString(cx, label_y, lbl)

    # Questions
    for idx, (q_num, correct_idx, student_idx) in enumerate(questions):
        y = h - MARGIN_TOP - 1.6*cm - idx * ROW_HEIGHT

        # Numéro de question
        c.setFont("Helvetica", 10)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(MARGIN_LEFT, y, f"Q{q_num:02d}.")

        # Cases à cocher
        for i in range(len(CHOICES)):
            cx = MARGIN_LEFT + 3*cm + i * CHOICE_SPACING - BOX_SIZE / 2
            # Dessin de la case (rectangle)
            c.setStrokeColorRGB(0.2, 0.2, 0.2)
            c.setFillColorRGB(1, 1, 1)
            c.setLineWidth(1)
            c.rect(cx, y - 1, BOX_SIZE, BOX_SIZE, fill=1)

            # Remplissage si case cochée
            if student_idx == i:
                # Croix ou remplissage sombre
                c.setStrokeColorRGB(0.1, 0.1, 0.8)
                c.setFillColorRGB(0.1, 0.1, 0.8)
                c.setLineWidth(1.5)
                # Diagonales (symbole ✕)
                m = 2  # marge intérieure
                c.line(cx + m, y - 1 + m,
                        cx + BOX_SIZE - m, y - 1 + BOX_SIZE - m)
                c.line(cx + BOX_SIZE - m, y - 1 + m,
                        cx + m, y - 1 + BOX_SIZE - m)

    c.showPage()


def make_student_pdf(path: str):
    """Génère le PDF étudiant (avec les réponses choisies)."""
    c = canvas.Canvas(path, pagesize=A4)
    pages = [
        STUDENT_ANSWERS[:QUESTIONS_PER_PAGE],
        STUDENT_ANSWERS[QUESTIONS_PER_PAGE:],
    ]
    for pg_idx, pg_answers in enumerate(pages):
        offset = pg_idx * QUESTIONS_PER_PAGE
        questions = [
            (offset + i + 1, CORRECT_KEY[offset + i], ans)
            for i, ans in enumerate(pg_answers)
        ]
        _draw_page(c, questions, pg_idx + 1, 2, "QCM — Copie étudiant")
    c.save()
    print(f"✓ Créé : {path}")


def make_correction_pdf(path: str):
    """Génère le PDF correction (cases cochées = bonnes réponses)."""
    c = canvas.Canvas(path, pagesize=A4)
    pages = [
        CORRECT_KEY[:QUESTIONS_PER_PAGE],
        CORRECT_KEY[QUESTIONS_PER_PAGE:],
    ]
    for pg_idx, pg_answers in enumerate(pages):
        offset = pg_idx * QUESTIONS_PER_PAGE
        questions = [
            (offset + i + 1, ans, ans)   # student_idx == correct_idx
            for i, ans in enumerate(pg_answers)
        ]
        _draw_page(c, questions, pg_idx + 1, 2, "QCM — Correction officielle")
    c.save()
    print(f"✓ Créé : {path}")


if __name__ == "__main__":
    import os, sys
    out_dir = os.path.join(os.path.dirname(__file__), "test_pdfs")
    os.makedirs(out_dir, exist_ok=True)
    make_student_pdf(os.path.join(out_dir, "test_student.pdf"))
    make_correction_pdf(os.path.join(out_dir, "test_correction.pdf"))
    print("PDFs de test generes dans ./test_pdfs/")
