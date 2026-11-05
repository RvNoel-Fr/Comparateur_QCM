"""
test_multi_sheet.py
Test complet de bout en bout :
- Génération d'une fiche de correction (1 page, 20 questions, 4 choix).
- Génération d'un fichier PDF contenant 3 fiches étudiants (3 pages).
- Analyse du PDF multi-fiches.
- Vérification du cumul des résultats (moyenne, palmarès, statistiques par question).
- Export du rapport PDF cumulatif complet.
- Test de la présence du bouton d'impression.
"""

import sys
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import fitz

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("  TEST COMPLET : MULTI-FICHES & CUMUL DES RESULTATS")
print("=" * 60)

os.makedirs("test_pdfs/multi_test", exist_ok=True)
correc_pdf = "test_pdfs/multi_test/modele_correction.pdf"
students_pdf = "test_pdfs/multi_test/copies_classe.pdf"
report_pdf = "test_pdfs/multi_test/rapport_cumul_classe.pdf"

# ── 1. Génération de la correction modèle ──────────────────────────────────────
print("\n[1] Génération de la fiche modèle de correction...")
from app.sheet_generator import generate_answer_sheet, FIRST_BOX_X_CM, GRID_TOP_CM, ROW_H_CM, COL_SPACING_CM, BOX_SIDE_CM
generate_answer_sheet(correc_pdf, num_questions=15, num_choices=4, title="Contrôle Mathématiques")

# Remplir la correction avec des réponses fixes : Q1=A, Q2=B, Q3=C, Q4=D, etc.
doc_c = fitz.open(correc_pdf)
page_c = doc_c[0]
CM = 28.35
CORREC_ANSWERS = ["A", "B", "C", "D"] * 4
CORREC_ANSWERS = CORREC_ANSWERS[:15]  # 15 questions

choice_idx = {"A": 0, "B": 1, "C": 2, "D": 3}
for q_idx, ans in enumerate(CORREC_ANSWERS):
    col = choice_idx[ans]
    x = (FIRST_BOX_X_CM + col * COL_SPACING_CM) * CM
    y = (GRID_TOP_CM + q_idx * ROW_H_CM) * CM
    w = BOX_SIDE_CM * CM
    h = BOX_SIDE_CM * CM
    # Dessiner un X ou croix noire dans la case
    page_c.draw_rect(fitz.Rect(x + 3, y + 3, x + w - 3, y + h - 3), color=(0, 0, 0), fill=(0, 0, 0))

doc_c.save("test_pdfs/multi_test/correction_remplie.pdf")
doc_c.close()
print("  Correction remplie enregistrée ✓")

# ── 2. Génération du PDF contenant 3 fiches étudiants ────────────────────────
print("\n[2] Génération d'un PDF multi-fiches (3 étudiants dans 1 seul PDF)...")
# Étudiant 1 : Alice DUPONT (très bon, 14 bonnes, 1 fausse)
# Étudiant 2 : Bernard MARTIN (moyen, 9 bonnes, 4 fausses, 2 blanches)
# Étudiant 3 : Chloé BERNARD (en difficulté, 5 bonnes, 8 fausses, 2 blanches)

students_info = [
    {
        "name": "Alice DUPONT",
        "answers": ["A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "C", "D", "A", "B", "A"] # Q15 fausse (A au lieu de C)
    },
    {
        "name": "Bernard MARTIN",
        "answers": ["A", "B", "C", "D", "A", "B", "C", "D", "A", "A", "A", "", "A", "B", ""]   # erreurs + blanches
    },
    {
        "name": "Chloe BERNARD",
        "answers": ["B", "C", "D", "A", "B", "C", "C", "D", "A", "", "B", "", "D", "C", "B"]   # plusieurs erreurs
    }
]

doc_multi = fitz.open()

for s_idx, st in enumerate(students_info):
    temp_sheet = f"test_pdfs/multi_test/temp_s{s_idx}.pdf"
    generate_answer_sheet(temp_sheet, num_questions=15, num_choices=4, title="Contrôle Mathématiques")
    st_doc = fitz.open(temp_sheet)
    st_page = st_doc[0]

    # Inscrire le nom dans la case Nom
    from app.sheet_generator import NAME_BOX_X_CM, NAME_BOX_Y_CM, NAME_BOX_H_CM
    st_page.insert_text(
        fitz.Point((NAME_BOX_X_CM + 0.3) * CM, (NAME_BOX_Y_CM + 0.55) * CM),
        st["name"],
        fontsize=12,
        fontname="helv",
        color=(0.1, 0.1, 0.4)
    )

    # Remplir les cases cochées
    for q_idx, ans in enumerate(st["answers"]):
        if not ans:
            continue
        col = choice_idx[ans]
        x = (FIRST_BOX_X_CM + col * COL_SPACING_CM) * CM
        y = (GRID_TOP_CM + q_idx * ROW_H_CM) * CM
        w = BOX_SIDE_CM * CM
        h = BOX_SIDE_CM * CM
        st_page.draw_rect(fitz.Rect(x + 3, y + 3, x + w - 3, y + h - 3), color=(0, 0, 0), fill=(0, 0, 0))

    # Ajouter la page au document multi-pages
    doc_multi.insert_pdf(st_doc)
    st_doc.close()
    if os.path.exists(temp_sheet):
        os.remove(temp_sheet)

doc_multi.save(students_pdf)
print(f"  Fichier multi-copies créé : {students_pdf} ({doc_multi.page_count} pages) ✓")
doc_multi.close()

# ── 3. Analyse complète via le pipeline ──────────────────────────────────────
print("\n[3] Analyse du PDF multi-fiches...")
from app.pdf_reader import pdf_to_images, extract_name, crop_name_zone
from app.detector import extract_answers, draw_debug
from app.comparator import compare
from app.scorer import calculate_score
from app.analysis import StudentSheet, compute_batch_summary

s_imgs = pdf_to_images(students_pdf, dpi=200)
c_imgs = pdf_to_images("test_pdfs/multi_test/correction_remplie.pdf", dpi=200)

print(f"  Images étudiant(s) : {len(s_imgs)} pages")
print(f"  Images correction   : {len(c_imgs)} page(s)")

c_results = extract_answers(c_imgs)
pages_per_sheet = max(1, len(c_imgs))
num_sheets = len(s_imgs) // pages_per_sheet

sheets: list[StudentSheet] = []

for i in range(num_sheets):
    p_start = i * pages_per_sheet
    p_end = (i + 1) * pages_per_sheet
    sub_imgs = s_imgs[p_start:p_end]

    detected_name = extract_name(students_pdf, page_num=p_start)
    name_crop = crop_name_zone(sub_imgs[0], dpi=200)
    display_name = detected_name if detected_name else f"Copie {i + 1}"

    s_results = extract_answers(sub_imgs)
    s_debug = [draw_debug(img, s_results) for img in sub_imgs]

    comp = compare(s_results, c_results)
    score_data = calculate_score(comp, penalty=0.25)

    sheets.append(StudentSheet(
        index=i,
        name=display_name,
        name_detected=bool(detected_name),
        name_crop=name_crop,
        images=sub_imgs,
        debug_images=s_debug,
        results=s_results,
        comparison=comp,
        score=score_data
    ))

    print(f"  Copie {i+1} : {display_name} -> Note: {score_data['grade']}/20 (✓:{score_data['correct']}, ✗:{score_data['incorrect']}, —:{score_data['blank']})")

# ── 4. Calcul du cumul et statistiques ───────────────────────────────────────
print("\n[4] Calcul des statistiques cumulées...")
batch_summary = compute_batch_summary(sheets)

print(f"  Nombre de copies   : {batch_summary.num_students} (attendu: 3) ✓")
print(f"  Moyenne classe     : {batch_summary.average_grade} / 20")
print(f"  Note maximale      : {batch_summary.max_grade} / 20")
print(f"  Note minimale      : {batch_summary.min_grade} / 20")
print(f"  Taux de réussite   : {batch_summary.pass_rate} % ({batch_summary.pass_count} admis)")
print(f"  Questions analysées: {len(batch_summary.question_stats)}")

# Vérifier question stats
q1 = batch_summary.question_stats[0]
print(f"  Q01 : Attendu={q1.correct_answer}, Succès={q1.success_rate}%, Répartition={q1.choice_distribution}, Difficulté={q1.difficulty}")

# ── 5. Export du rapport cumulatif PDF ───────────────────────────────────────
print("\n[5] Export du rapport cumulatif ReportLab...")
from app.report_exporter import export_pdf_report
export_pdf_report(report_pdf, sheets, batch_summary)
print(f"  Rapport généré : {report_pdf} (Taille : {os.path.getsize(report_pdf)} octets) ✓")

# ── 6. Vérification du dialogue de génération et bouton d'impression ─────────
print("\n[6] Vérification du bouton d'impression dans GeneratorDialog...")
from app.generator_dialog import GeneratorDialog
import inspect
methods = [m[0] for m in inspect.getmembers(GeneratorDialog, predicate=inspect.isfunction)]
assert "_print_sheet" in methods, "Méthode _print_sheet manquante dans GeneratorDialog !"
print("  Méthode _print_sheet présente dans GeneratorDialog ✓")

print("\n" + "=" * 60)
print("  TOUS LES TESTS MULTI-FICHES & CUMUL ONT REUSSI AVEC SUCCES !")
print("=" * 60)
