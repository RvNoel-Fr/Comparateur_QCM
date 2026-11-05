"""
test_csv_generator.py
Vérifie le chargement CSV et la génération de lots de fiches nominatives.
"""

import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("  TEST : GENERATEUR DE FICHES AVEC CSV GROUPE D'ELEVES")
print("=" * 60)

os.makedirs("test_pdfs/csv_test", exist_ok=True)
csv_file = "test_pdfs/csv_test/Terminale_S2.csv"
pdf_output = "test_pdfs/csv_test/QCM_Maths_Terminale_S2_fiches.pdf"

# ── 1. Création d'un fichier CSV de test ───────────────────────────────────────
print("\n[1] Création du fichier CSV groupe...")
csv_content = """Nom;Prénom
DUBOIS;Alexandre
LEFEBVRE;Camille
MOREAU;Lucas
ROUX;Emma
GIRARD;Sophie
"""
with open(csv_file, "w", encoding="utf-8") as f:
    f.write(csv_content)
print(f"  Fichier créé : {csv_file}")

# ── 2. Test du parser CSV ─────────────────────────────────────────────────────
print("\n[2] Test du parser parse_students_csv...")
from app.sheet_generator import parse_students_csv

group_name, students = parse_students_csv(csv_file)
print(f"  Nom du groupe extrait : '{group_name}' (attendu: 'Terminale_S2')")
print(f"  Nombre d'étudiants    : {len(students)} (attendu: 5)")
for idx, s in enumerate(students, 1):
    print(f"    {idx}. {s}")

assert group_name == "Terminale_S2", "Le nom de groupe doit correspondre au nom du fichier CSV"
assert len(students) == 5, "5 étudiants doivent être extraits"
assert students[0] == "DUBOIS Alexandre"
assert students[4] == "GIRARD Sophie"
print("  Validation parser CSV : OK ✓")

# ── 3. Génération du lot de fiches nominatives ────────────────────────────────
print("\n[3] Génération du PDF avec fiches nominatives (20 questions / 4 choix)...")
from app.sheet_generator import generate_answer_sheet

total_pages = generate_answer_sheet(
    output_path=pdf_output,
    num_questions=20,
    num_choices=4,
    title="Contrôle de Mathématiques",
    students=students,
    group_name=group_name
)

print(f"  Fichier généré : {pdf_output}")
print(f"  Nombre total de pages générées : {total_pages} (attendu: 5)")
assert total_pages == 5, "5 fiches d'une page = 5 pages"

# ── 4. Vérification de l'extraction des noms et de l'ordre des places ─────────
print("\n[4] Vérification du classement des fiches par ordre de place (1 à N)...")
from app.pdf_reader import extract_name, pdf_to_images, detect_seat_number
from app.sheet_generator import parse_placement_plan

plan_txt_path = "test_pdfs/csv_test/QCM_Maths_Terminale_S2_fiches_plan_placement.txt"
plan_map = parse_placement_plan(plan_txt_path)
print(f"  Plan de placement chargé : {plan_map}")

imgs = pdf_to_images(pdf_output, dpi=150)
extracted_names = []

for p in range(total_pages):
    seat = detect_seat_number(imgs[p])
    extracted = extract_name(pdf_output, page_num=p)
    expected_name = plan_map[p + 1]
    extracted_names.append(extracted)
    print(f"  Page {p+1} : Place détectée = {seat} (attendu: {p+1}) | Nom = '{extracted}' (attendu: '{expected_name}')")
    assert seat == p + 1, f"Page {p+1}: Place {seat} != {p+1} (doit être classée par numéro croissant)"
    assert extracted == expected_name, f"Page {p+1}: Nom '{extracted}' != '{expected_name}'"

assert sorted(extracted_names) == sorted(students), "Tous les étudiants de la liste doivent être présents"
print("  Vérification de l'ordre des places et des noms : 100% OK ✓")

# ── 5. Test avec QCM sur 2 pages (35 questions = 2 pages/élève x 5 = 10 pages) ─
print("\n[5] Test avec QCM sur 2 pages (35 questions par fiche)...")
pdf_output_2p = "test_pdfs/csv_test/QCM_Grand_Terminale_S2_fiches.pdf"
pages_2p = generate_answer_sheet(
    output_path=pdf_output_2p,
    num_questions=35,
    num_choices=4,
    title="Grand Examen",
    students=students,
    group_name=group_name
)
print(f"  Nombre total de pages pour 35 questions : {pages_2p} (attendu: 10 pages)")
assert pages_2p == 10, "5 étudiants x 2 pages = 10 pages"

plan_2p_path = "test_pdfs/csv_test/QCM_Grand_Terminale_S2_fiches_plan_placement.txt"
plan_2p_map = parse_placement_plan(plan_2p_path)

# Vérifier que le nom et la place sont bien sur les pages impaires (début de chaque fiche)
imgs_2p = pdf_to_images(pdf_output_2p, dpi=150)
for s_idx in range(len(students)):
    p_num = s_idx * 2
    seat = detect_seat_number(imgs_2p[p_num])
    ext = extract_name(pdf_output_2p, page_num=p_num)
    exp_name = plan_2p_map[s_idx + 1]
    print(f"  Fiche {s_idx+1} (Page {p_num+1}) : Place {seat} (attendu: {s_idx+1}) | Nom '{ext}' (attendu: '{exp_name}')")
    assert seat == s_idx + 1, f"Fiche {s_idx+1}: Place {seat} != {s_idx+1}"
    assert ext == exp_name, f"Fiche {s_idx+1}: nom '{ext}' attendu '{exp_name}'"
print("  Vérification fiches multi-pages : 100% OK ✓")

# ── 6. Test du numéro de placement aléatoire et du plan de placement ──────────
print("\n[6] Vérification du numéro de placement et du fichier plan_placement.txt...")
plan_txt_path = "test_pdfs/csv_test/QCM_Maths_Terminale_S2_fiches_plan_placement.txt"
assert os.path.isfile(plan_txt_path), f"Le fichier de plan {plan_txt_path} doit exister"

with open(plan_txt_path, "r", encoding="utf-8") as f:
    plan_content = f.read()

print("  Contenu du plan de placement généré :")
for line in plan_content.strip().split("\n")[:15]:
    print("   ", line)

# Vérifier que toutes les places 1 à 5 sont assignées
import re
seats_found = [int(m) for m in re.findall(r"Place\s+N°\s*(\d+)\s*:", plan_content)]
print(f"  Places trouvées dans le plan : {sorted(seats_found)}")
assert sorted(seats_found) == [1, 2, 3, 4, 5], "Chaque élève doit avoir une place unique de 1 à 5"

# ── 7. Rendu image d'une page pour contrôle visuel ────────────────────────────
print("\n[7] Rendu image de la fiche avec numéro de placement...")
from app.pdf_reader import pdf_to_images
imgs = pdf_to_images(pdf_output, dpi=150)
imgs[0].save("test_pdfs/debug/fiche_nominative_preview.png")
print("  Aperçu sauvegardé : test_pdfs/debug/fiche_nominative_preview.png ✓")

print("\n" + "=" * 60)
print("  TOUS LES TESTS CSV, LOTS ET PLACEMENTS SONT VALIDÉS AVEC SUCCÈS !")
print("=" * 60)
