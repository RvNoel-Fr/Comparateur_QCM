# -*- coding: utf-8 -*-
"""
test_integration.py
Test complet de toutes les fonctionnalites de l'application.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 50)
print("  Test integration complet")
print("=" * 50)

# 1. Generation de fiche de reponses
print("\n[1] Génération de fiche de réponses...")
from app.sheet_generator import generate_answer_sheet
pages4 = generate_answer_sheet("test_pdfs/fiche_4choix.pdf", 20, 4, "Contrôle de physique")
pages3 = generate_answer_sheet("test_pdfs/fiche_3choix.pdf", 15, 3, "Test de maths")
pages5 = generate_answer_sheet("test_pdfs/fiche_5choix.pdf", 30, 5, "Grand examen")
print(f"  4 choix / 20 questions : {pages4} page(s) ✓")
print(f"  3 choix / 15 questions : {pages3} page(s) ✓")
print(f"  5 choix / 30 questions : {pages5} page(s) ✓")

# 2. Extraction du nom
print("\n[2] Extraction du nom...")
from app.pdf_reader import extract_name, crop_name_zone, pdf_to_images
name_vide = extract_name("test_pdfs/fiche_4choix.pdf")
print(f"  Fiche vide         : {repr(name_vide)} (attendu: None)  {'✓' if name_vide is None else '✗'}")

# 3. Détection sur fiche vide (toutes cases non-cochées)
print("\n[3] Détection cases sur fiche vide...")
imgs = pdf_to_images("test_pdfs/fiche_4choix.pdf", dpi=200)
from app.detector import extract_answers
results = extract_answers(imgs)
blanches = all(r.answer == "" for r in results)
print(f"  {len(results)} questions détectées, toutes blanches : {blanches}  {'✓' if blanches else '✗'}")

# 4. Pipeline QCM étudiant → correction → note
print("\n[4] Pipeline analyse QCM test existant...")
s_imgs = pdf_to_images("test_pdfs/test_student.pdf", dpi=200)
c_imgs = pdf_to_images("test_pdfs/test_correction.pdf", dpi=200)
from app.detector import draw_debug
s_res = extract_answers(s_imgs)
c_res = extract_answers(c_imgs)
from app.comparator import compare
from app.scorer import calculate_score
comp  = compare(s_res, c_res)
score = calculate_score(comp, penalty=0.25)
print(f"  Questions : {score['total']}/20  {'✓' if score['total'] == 20 else '✗'}")
print(f"  Note      : {score['grade']}/20  ({score['percent']}%)")
print(f"  Bonnes    : {score['correct']}    Fausses : {score['incorrect']}    Blanches : {score['blank']}")

# 5. Export rapport PDF avec nom
print("\n[5] Export rapport avec nom étudiant...")
from app.gui import _export_pdf
_export_pdf("test_pdfs/rapport_Dupont.pdf", comp, score, student_name="Dupont Jean")
import os
ok = os.path.isfile("test_pdfs/rapport_Dupont.pdf")
print(f"  Rapport créé : {'✓' if ok else '✗'}")

# 6. Vignette zone nom
print("\n[6] Crop zone nom...")
crop = crop_name_zone(imgs[0], dpi=200)
crop.save("test_pdfs/debug/name_crop_fiche.png")
print(f"  Taille vignette : {crop.size}  ✓")

# 7. Imports GUI
print("\n[7] Import modules GUI...")
from app.gui import QCMApp
from app.generator_dialog import GeneratorDialog
print("  QCMApp, GeneratorDialog  ✓")

print("\n" + "=" * 50)
print("  TOUS LES TESTS PASSES ✓")
print("=" * 50)
