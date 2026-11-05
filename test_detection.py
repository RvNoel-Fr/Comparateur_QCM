# -*- coding: utf-8 -*-
"""
test_detection.py
Teste la pipeline complète de détection sur les PDFs de test.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.pdf_reader import pdf_to_images
from app.detector import extract_answers, draw_debug
from app.comparator import compare
from app.scorer import calculate_score

print("=" * 50)
print("  Test de detection QCM PDF")
print("=" * 50)

# --- Chargement ---
s_imgs = pdf_to_images("test_pdfs/test_student.pdf", dpi=200)
c_imgs = pdf_to_images("test_pdfs/test_correction.pdf", dpi=200)
print(f"\nPages etudiant   : {len(s_imgs)}")
print(f"Pages correction : {len(c_imgs)}")

# --- Detection ---
s_results = extract_answers(s_imgs)
c_results = extract_answers(c_imgs)

print(f"\nQuestions detectees (etudiant)   : {len(s_results)}")
print(f"Questions detectees (correction) : {len(c_results)}")

# --- Affichage des reponses etudiant ---
print("\n  Reponses etudiant detectees :")
for qr in s_results:
    print(f"    Q{qr.question:02d} -> {qr.answer if qr.answer else '(blanc)'}")

print("\n  Reponses correction detectees :")
for qr in c_results:
    print(f"    Q{qr.question:02d} -> {qr.answer if qr.answer else '(blanc)'}")

# --- Comparaison ---
comparison = compare(s_results, c_results)
score_data = calculate_score(comparison, penalty=0.25)

print("\n" + "=" * 50)
print(f"  NOTE : {score_data['grade']} / {score_data['max_grade']}")
print(f"  Bonnes   : {score_data['correct']}")
print(f"  Fausses  : {score_data['incorrect']}")
print(f"  Blanches : {score_data['blank']}")
print(f"  Pourcentage : {score_data['percent']} %")
print("=" * 50)

# --- Sauvegarde images annotees ---
import os
os.makedirs("test_pdfs/debug", exist_ok=True)
for i, img in enumerate(s_imgs):
    page_results = [qr for qr in s_results
                    if qr.question > i * 10 and qr.question <= (i + 1) * 10]
    debug_img = draw_debug(img, page_results)
    debug_img.save(f"test_pdfs/debug/student_page{i+1}_annotated.png")
    print(f"Image annotee sauvegardee : test_pdfs/debug/student_page{i+1}_annotated.png")
