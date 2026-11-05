"""
test_csv_export.py
Valide l'export des notes au format CSV (séparateur ';') et XLS (Excel 2003)
avec intégration du numéro de placement.
"""

import os
import sys
import csv
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

print("=" * 60)
print("  TEST : EXPORT DES NOTES (CSV SÉPARATEUR ';' & XLS)")
print("=" * 60)

from app.pdf_reader import pdf_to_images, extract_name, crop_name_zone, detect_seat_number
from app.detector import extract_answers
from app.comparator import compare
from app.scorer import calculate_score
from app.analysis import StudentSheet, compute_batch_summary
from app.sheet_generator import parse_placement_plan
from app.csv_exporter import export_grades_csv, export_grades_xls, export_grades

scanned_pdf = "test_pdfs/multi_test/HnQcm2.pdf"
correc_pdf = "test_pdfs/HN/CorrigeQCM.pdf"
plan_file = "test_pdfs/csv_test/QCM_Terminale_S2_fiches_HN_plan_placement.txt"

assert os.path.isfile(scanned_pdf), f"Fichier introuvable: {scanned_pdf}"
assert os.path.isfile(correc_pdf), f"Fichier introuvable: {correc_pdf}"
assert os.path.isfile(plan_file), f"Fichier introuvable: {plan_file}"

seat_map = parse_placement_plan(plan_file)
print(f"  Plan de placement chargé ({len(seat_map)} places) : {seat_map}")

s_imgs = pdf_to_images(scanned_pdf, dpi=200)
c_imgs = pdf_to_images(correc_pdf, dpi=200)
c_results = extract_answers(c_imgs)

sheets: list[StudentSheet] = []
expected_seats = [4, 1, 5, 3, 2]

for i in range(len(s_imgs)):
    first_img = s_imgs[i]
    seat = detect_seat_number(first_img)
    name = extract_name(scanned_pdf, page_num=i, pil_image=first_img, seat_map=seat_map)
    sub_imgs = [first_img]
    s_results = extract_answers(sub_imgs)
    comp = compare(s_results, c_results)
    score_data = calculate_score(comp, penalty=0.25)

    sheets.append(StudentSheet(
        index=i,
        name=name or f"Copie {i + 1}",
        name_detected=True,
        name_crop=crop_name_zone(first_img),
        seat_number=seat,
        images=sub_imgs,
        results=s_results,
        comparison=comp,
        score=score_data
    ))

assert len(sheets) == 5
for idx, s in enumerate(sheets):
    assert s.seat_number == expected_seats[idx], f"Place {s.seat_number} != {expected_seats[idx]}"
    print(f"  Copie {idx + 1} : Place={s.seat_number}, Nom={s.name}, Note={s.score['grade']}/20")

batch_summary = compute_batch_summary(sheets)
print(f"  Moyenne promo : {batch_summary.average_grade}/20")

# ── Test 1 : Export CSV avec séparateur ';' ──────────────────────────────────
csv_out = "test_pdfs/csv_test/test_notes_export.csv"
export_grades_csv(csv_out, sheets, batch_summary)
assert os.path.isfile(csv_out), "Le fichier CSV doit avoir été généré."
print(f"\n  ✓ Fichier CSV généré : {csv_out}")

# Vérification du contenu CSV
with open(csv_out, mode="r", encoding="utf-8-sig") as f:
    reader = list(csv.reader(f, delimiter=";"))

assert len(reader) >= 7, f"Trop peu de lignes : {len(reader)}"
header = reader[0]
print("  En-têtes CSV :", header[:9])
assert header[0] == "Place"
assert header[1] == "Nom de l'étudiant"
assert header[2] == "Note / 20"
assert "Q01" in header

# Ligne correction attendue
corr_line = reader[1]
assert corr_line[1] == "CORRECTION ATTENDUE"
print("  Ligne correction :", corr_line[:5])

# Lignes étudiants
student_lines = reader[2:7]
for idx, line in enumerate(student_lines):
    place_str = line[0]
    nom = line[1]
    note_str = line[2]
    statut = line[8]
    assert int(place_str) == expected_seats[idx], f"Place dans CSV {place_str} != {expected_seats[idx]}"
    assert nom == sheets[idx].name
    assert "," in note_str or "." in note_str  # nombre formaté
    print(f"  Vérifié ligne étudiant {idx + 1} : Place {place_str} | {nom} | Note: {note_str} | {statut}")

# Vérification présence de la synthèse de fin
found_summary = any("Moyenne de la classe" in line for line in reader[7:])
assert found_summary, "La synthèse de la promotion doit être présente dans le CSV"
print("  ✓ Synthèse de la classe présente dans le CSV")

# ── Test 2 : Export XLS (XML Spreadsheet 2003) ───────────────────────────────
xls_out = "test_pdfs/csv_test/test_notes_export.xls"
export_grades_xls(xls_out, sheets, batch_summary)
assert os.path.isfile(xls_out), "Le fichier XLS doit avoir été généré."
print(f"\n  ✓ Fichier XLS généré : {xls_out}")

with open(xls_out, mode="r", encoding="utf-8") as f:
    xls_content = f.read()

assert '<?xml version="1.0"' in xls_content
assert 'ss:Name="Notes QCM"' in xls_content
assert "MOREAU Lucas" in xls_content
assert "ROUX Emma" in xls_content
assert "<Data ss:Type=\"Number\">4</Data>" in xls_content
print("  ✓ Format XML Spreadsheet 2003 validé pour Excel")

# ── Test 3 : Dispatcher export_grades ────────────────────────────────────────
out_disp_csv = export_grades(csv_out, sheets, batch_summary)
assert out_disp_csv.endswith(".csv")
out_disp_xls = export_grades(xls_out, sheets, batch_summary)
assert out_disp_xls.endswith(".xls")
print("  ✓ Dispatcher export_grades validé")

print("\n" + "=" * 60)
print("  TOUS LES TESTS D'EXPORT CSV & XLS ONT RÉUSSI !")
print("=" * 60)
