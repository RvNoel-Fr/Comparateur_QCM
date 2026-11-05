"""
test_scanned_analysis.py
Valide l'alignement précis du cadre nom scanné et la reconnaissance des places/noms.
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

print('=' * 60)
print('  TEST : ANALYSE FICHIER MULTIPLE SCANNÉ AVEC NOMS & PLACES')
print('=' * 60)

from app.pdf_reader import pdf_to_images, extract_name, crop_name_zone, detect_seat_number, detect_name_box
from app.sheet_generator import parse_placement_plan

scanned_pdf = 'test_pdfs/multi_test/HnQcm2.pdf'
plan_file = 'test_pdfs/csv_test/QCM_Terminale_S2_fiches_HN_plan_placement.txt'

if not os.path.isfile(scanned_pdf) or not os.path.isfile(plan_file):
    print("Fichiers de test non trouvés, test ignoré.")
    sys.exit(0)

seat_map = parse_placement_plan(plan_file)
print('  Plan de placement chargé :', seat_map)
assert len(seat_map) == 5, '5 places doivent être chargées'

imgs = pdf_to_images(scanned_pdf, dpi=200)
print(f'  Pages converties : {len(imgs)}')

expected_seats = [4, 1, 5, 3, 2]
expected_names = [seat_map[s] for s in expected_seats]

for idx, img in enumerate(imgs):
    # 1. Test du recadrage du cadre nom
    box = detect_name_box(img)
    assert box is not None, f'Page {idx}: Le cadre physique du nom doit être détecté'
    crop = crop_name_zone(img)
    print(f'  Page {idx} : Cadre détecté en {box}, taille vignette {crop.size} ✓')

    # 2. Test détection de la place
    seat = detect_seat_number(img)
    assert seat == expected_seats[idx], f'Page {idx}: Place {seat} != {expected_seats[idx]}'
    print(f'  Page {idx} : Place détectée = {seat} (attendu: {expected_seats[idx]}) ✓')

    # 3. Test résolution du nom
    name = extract_name(scanned_pdf, page_num=idx, pil_image=img, seat_map=seat_map)
    assert name == expected_names[idx], f'Page {idx}: Nom {name} != {expected_names[idx]}'
    print(f'  Page {idx} : Nom résolu = « {name} » ✓')

print('\n' + '=' * 60)
print('  TOUS LES TESTS SUR FICHIER SCANNÉ SONT VALIDÉS AVEC SUCCÈS !')
print('=' * 60)
