"""
sheet_generator.py
Génère des fiches de réponses PDF vierges ou pré-remplies par étudiant avec ReportLab.

Prend en charge :
  - La génération d'une fiche vierge standard.
  - La génération d'un lot de fiches personnalisées à partir d'un fichier CSV de groupe :
    une fiche par étudiant avec son nom inscrit dans l'emplacement réservé,
    et un numéro de placement aléatoire (1 à N) en haut à droite dans un cadre épais.
  - La génération automatique d'un plan de placement (fichier compagnon .txt)
    indiquant la place attribuée à chaque étudiant.

Les constantes de position de la zone "Nom" sont exportées pour permettre
à pdf_reader.extract_name() de localiser et extraire le nom lors de l'analyse.
"""

import os
import csv
import io
import re
import random
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors

# ──────────────────────────────────────────────────────────────────────────────
# Constantes de mise en page (en cm depuis le coin HAUT-GAUCHE de la page)
# Partagées avec pdf_reader.extract_name() pour localiser la zone nom.
# ──────────────────────────────────────────────────────────────────────────────

PAGE_W_CM, PAGE_H_CM = 21.0, 29.7          # A4

# Zone "Nom" — boîte rectangulaire encadrée
NAME_BOX_X_CM   = 3.0      # bord gauche
NAME_BOX_Y_CM   = 3.6      # bord supérieur (depuis haut de page)
NAME_BOX_W_CM   = 13.5     # largeur
NAME_BOX_H_CM   = 0.75     # hauteur

# Zone "Date"
DATE_BOX_X_CM   = 16.8
DATE_BOX_Y_CM   = 3.6
DATE_BOX_W_CM   = 3.5
DATE_BOX_H_CM   = 0.75

# Grille de cases
GRID_TOP_CM     = 5.5      # y du haut de la première ligne de question
ROW_H_CM        = 0.85     # hauteur d'une ligne de question
COL0_X_CM       = 2.5      # x du numéro de question
FIRST_BOX_X_CM  = 4.2      # x de la première case (choix A)
COL_SPACING_CM  = 1.5      # espacement horizontal entre cases
BOX_SIDE_CM     = 0.5      # taille d'une case carrée

QUESTIONS_PER_PAGE = 25    # max questions par page

CHOICE_LABELS = ["A", "B", "C", "D", "E"]


# ──────────────────────────────────────────────────────────────────────────────
# Lecture de fichier CSV groupe d'étudiants
# ──────────────────────────────────────────────────────────────────────────────

def parse_students_csv(csv_path: str) -> tuple[str, list[str]]:
    """
    Lit un fichier CSV contenant une liste d'étudiants.
    Le nom du fichier (sans extension) est utilisé comme nom du groupe.

    Prend en charge :
      - Séparateurs ';' ou ',' ou '\t'.
      - Encodages UTF-8, UTF-8-BOM, CP1252/Windows, Latin-1.
      - Colonnes uniques (Nom complet) ou doubles (Nom;Prénom ou Prénom;Nom).
      - Détection et élimination automatique de la ligne d'en-tête.

    Returns:
        tuple (group_name, list_of_student_names)
    """
    group_name = os.path.splitext(os.path.basename(csv_path))[0]

    content = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(csv_path, "r", encoding=enc) as f:
                content = f.read()
            break
        except Exception:
            continue

    if content is None:
        raise ValueError(f"Impossible de lire le fichier {csv_path} (encodage non reconnu)")

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return group_name, []

    first_line = lines[0]
    if ";" in first_line:
        sep = ";"
    elif "\t" in first_line:
        sep = "\t"
    elif "," in first_line:
        sep = ","
    else:
        sep = None

    reader = csv.reader(io.StringIO(content), delimiter=sep) if sep else [[l] for l in lines]
    rows = [r for r in reader if r and any(c.strip() for c in r)]
    if not rows:
        return group_name, []

    header = [c.strip().lower() for c in rows[0]]
    nom_idx = None
    prenom_idx = None
    has_header = False

    for idx, col in enumerate(header):
        if col in ("nom", "last name", "lastname", "family name", "nom de famille"):
            nom_idx = idx
            has_header = True
        elif col in ("prenom", "prénom", "first name", "firstname", "given name"):
            prenom_idx = idx
            has_header = True
        elif col in ("etudiant", "étudiant", "student", "eleve", "élève", "nom complet", "name"):
            nom_idx = idx
            has_header = True

    start_row = 1 if has_header else 0
    students = []

    for row in rows[start_row:]:
        clean_row = [c.strip() for c in row if c.strip()]
        if not clean_row:
            continue

        if nom_idx is not None and prenom_idx is not None:
            n = row[nom_idx].strip() if nom_idx < len(row) else ""
            p = row[prenom_idx].strip() if prenom_idx < len(row) else ""
            full_name = f"{n} {p}".strip() if (n and p) else (n or p)
        elif nom_idx is not None:
            full_name = row[nom_idx].strip() if nom_idx < len(row) else ""
        elif len(clean_row) >= 2:
            full_name = f"{clean_row[0]} {clean_row[1]}"
        else:
            full_name = clean_row[0]

        if full_name:
            students.append(full_name)

    return group_name, students


# ──────────────────────────────────────────────────────────────────────────────
# Génération PDF & Plan de placement
# ──────────────────────────────────────────────────────────────────────────────

def _save_placement_plan(plan_path: str, group_name: str, assignments: list[tuple[str, int]]):
    """
    Enregistre le plan de placement compagnon sous forme de fichier texte lisible.
    assignments: liste de tuples (nom_etudiant, numero_place).
    """
    now = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")
    grp_title = group_name if group_name else "Groupe d'examen"

    # Tri par numéro de place (croissant)
    by_seat = sorted(assignments, key=lambda a: a[1])
    # Tri par ordre alphabétique
    by_name = sorted(assignments, key=lambda a: a[0].lower())

    lines = [
        "=" * 60,
        f"  PLAN DE PLACEMENT ALÉATOIRE — {grp_title}",
        f"  Généré le {now}  •  Effectif : {len(assignments)} étudiants",
        "=" * 60,
        "",
        "── 1. PLAN DE SALLE (Trié par numéro de place) ───────────────",
    ]
    for name, seat in by_seat:
        lines.append(f"  Place N° {seat:02d}  :  {name}")

    lines.extend([
        "",
        "── 2. RECHERCHE RAPIDE (Trié par ordre alphabétique) ─────────",
    ])
    for name, seat in by_name:
        lines.append(f"  {name:<30}  -->  Place N° {seat:02d}")

    lines.append("")
    lines.append("=" * 60)

    try:
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass


def parse_placement_plan(plan_path: str) -> dict[int, str]:
    """
    Lit un fichier plan de placement (*_plan_placement.txt)
    et retourne un dictionnaire {numero_place: nom_etudiant}.
    """
    if not os.path.isfile(plan_path):
        return {}

    mapping: dict[int, str] = {}
    try:
        with open(plan_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                # Format 1 : '  Place N° 01  :  DUBOIS Alexandre' ou 'Place 1 : ...'
                m = re.search(r"Place\s+.*?(\d+)\s*:\s*(.+)", line, re.IGNORECASE)
                if m:
                    seat_num = int(m.group(1))
                    name = m.group(2).strip()
                    if name:
                        mapping[seat_num] = name
                else:
                    # Format 2 : '  DUBOIS Alexandre                -->  Place N° 01'
                    m2 = re.search(r"^\s*(.+?)\s+-->\s+Place\s+.*?(\d+)", line, re.IGNORECASE)
                    if m2:
                        name = m2.group(1).strip()
                        seat_num = int(m2.group(2))
                        if name:
                            mapping[seat_num] = name
    except Exception:
        pass
    return mapping


def generate_answer_sheet(output_path: str,
                           num_questions: int,
                           num_choices: int,
                           title: str = "QCM",
                           students: list[str] | None = None,
                           group_name: str = "",
                           seat_numbers: list[int] | None = None) -> int:
    """
    Génère la fiche de réponses PDF.

    Args:
        output_path:   Chemin de sortie du PDF.
        num_questions: Nombre de questions (1–100).
        num_choices:   Nombre de choix par question (3, 4 ou 5).
        title:         Titre affiché en en-tête.
        students:      Liste des noms d'étudiants (optionnel). Si renseigné,
                       génère une fiche par étudiant avec son nom inscrit,
                       et un numéro de placement aléatoire (1 à N) en haut à droite.
        group_name:    Nom du groupe d'étudiants (optionnel, issu du CSV).
        seat_numbers:  Numéros de places pré-définis (optionnel). Si omis et
                       students fourni, une permutation aléatoire 1..N est générée.

    Returns:
        Nombre total de pages générées.
    """
    num_choices = max(3, min(5, num_choices))
    c = rl_canvas.Canvas(output_path, pagesize=A4)
    w, h = A4  # points

    pages_per_sheet = max(1, -(-num_questions // QUESTIONS_PER_PAGE))  # ceil division

    display_title = title

    # Mode 1 : Génération d'un lot personnalisé par étudiant
    if students:
        total_students = len(students)

        # Générer l'attribution aléatoire des numéros de placement de 1 à N
        if seat_numbers is None or len(seat_numbers) != total_students:
            seats = list(range(1, total_students + 1))
            random.shuffle(seats)
        else:
            seats = list(seat_numbers)

        assignments = list(zip(students, seats))

        # Classer les fiches suivant les numéros de place attribués (Place 1, 2, 3...)
        # pour faciliter la distribution et la mise en place physique en salle
        assignments.sort(key=lambda a: a[1])

        # Enregistrer le fichier compagnon plan de placement (.txt)
        plan_path = os.path.splitext(output_path)[0] + "_plan_placement.txt"
        _save_placement_plan(plan_path, group_name, assignments)

        total_pages = 0
        for student_name, seat_num in assignments:
            q_start = 1
            for page_num in range(1, pages_per_sheet + 1):
                q_end = min(q_start + QUESTIONS_PER_PAGE - 1, num_questions)
                _draw_page(c, display_title, page_num, pages_per_sheet,
                           q_start, q_end, num_choices, w, h,
                           student_name=student_name if page_num == 1 else "",
                           seat_number=seat_num)
                q_start = q_end + 1
                total_pages += 1
        c.save()
        return total_pages

    # Mode 2 : Fiche vierge unique standard
    else:
        q_start = 1
        for page_num in range(1, pages_per_sheet + 1):
            q_end = min(q_start + QUESTIONS_PER_PAGE - 1, num_questions)
            _draw_page(c, display_title, page_num, pages_per_sheet,
                       q_start, q_end, num_choices, w, h,
                       student_name="",
                       seat_number=None)
            q_start = q_end + 1
        c.save()
        return pages_per_sheet


def _draw_placement_badge(c, page_w: float, page_h: float, seat_number: int | str):
    """
    Dessine le numéro de placement aléatoire en haut à droite de la feuille,
    inscrit dans un rectangle épais avec une police de grande taille.
    """
    rw = 2.1 * cm
    rh = 1.45 * cm
    rx = page_w - 1.8 * cm - rw
    ry = page_h - 0.75 * cm - rh

    # Cadre épais avec coins arrondis
    c.setLineWidth(2.5)
    c.setStrokeColorRGB(0.12, 0.12, 0.4)
    c.setFillColorRGB(0.96, 0.96, 1.0)
    c.roundRect(rx, ry, rw, rh, 3, fill=1, stroke=1)

    # Intitulé 'PLACE N°'
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColorRGB(0.25, 0.25, 0.55)
    c.drawCentredString(rx + rw / 2.0, ry + rh - 9, "PLACE N°")

    # Numéro en grande taille
    val_str = str(seat_number)
    font_size = 22 if len(val_str) <= 2 else 17
    c.setFont("Helvetica-Bold", font_size)
    c.setFillColorRGB(0.1, 0.1, 0.4)
    c.drawCentredString(rx + rw / 2.0, ry + 6, val_str)


def _draw_page(c, title: str, page_num: int, total_pages: int,
               q_start: int, q_end: int, num_choices: int,
               w: float, h: float,
               student_name: str = "",
               seat_number: int | None = None):
    """Dessine une page complète de la fiche de réponses."""

    # ── En-tête ──────────────────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(0.1, 0.1, 0.5)
    c.drawString(2.5 * cm, h - 1.45 * cm, title)

    # Pagination (affichée uniquement si la fiche comporte plusieurs pages, pas de "Page 1 / 1")
    if total_pages > 1:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        pagin_right = (w - 4.4 * cm) if seat_number is not None else (w - 2.0 * cm)
        c.drawRightString(pagin_right, h - 1.45 * cm,
                          f"Page {page_num} / {total_pages}")

    # Numéro de placement aléatoire en haut à droite
    if seat_number is not None:
        _draw_placement_badge(c, w, h, seat_number)

    # Ligne séparatrice
    c.setStrokeColorRGB(0.6, 0.6, 0.8)
    c.setLineWidth(0.8)
    c.line(2.5 * cm, h - 2.3 * cm, w - 1.8 * cm, h - 2.3 * cm)

    # ── Zone Nom (page 1 seulement) ────────────────────────────────────────
    if page_num == 1:
        _draw_label_box(c, "Nom :", h,
                        NAME_BOX_X_CM, NAME_BOX_Y_CM,
                        NAME_BOX_W_CM, NAME_BOX_H_CM,
                        text=student_name)
        _draw_label_box(c, "Date :", h,
                        DATE_BOX_X_CM, DATE_BOX_Y_CM,
                        DATE_BOX_W_CM, DATE_BOX_H_CM)

    # ── En-têtes colonnes (A B C D E) ────────────────────────────────────────
    labels = CHOICE_LABELS[:num_choices]
    header_y = h - GRID_TOP_CM * cm + 0.35 * cm

    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(0.2, 0.2, 0.6)
    for i, lbl in enumerate(labels):
        cx = (FIRST_BOX_X_CM + i * COL_SPACING_CM + BOX_SIDE_CM / 2) * cm
        c.drawCentredString(cx, header_y, lbl)

    # Ligne de séparation sous les en-têtes
    c.setStrokeColorRGB(0.7, 0.7, 0.9)
    c.setLineWidth(0.5)
    line_y = h - GRID_TOP_CM * cm + 0.05 * cm
    c.line(2.0 * cm, line_y, w - 2.0 * cm, line_y)

    # ── Lignes de questions ───────────────────────────────────────────────────
    for idx, q_num in enumerate(range(q_start, q_end + 1)):
        row_y_top = h - (GRID_TOP_CM + idx * ROW_H_CM) * cm
        row_center = row_y_top - (BOX_SIDE_CM * cm) / 2 - 0.05 * cm

        # Fond alterné léger
        if idx % 2 == 0:
            c.setFillColorRGB(0.96, 0.96, 1.0)
            c.rect(2.0 * cm, row_y_top - ROW_H_CM * cm,
                   w - 4.0 * cm, ROW_H_CM * cm, fill=1, stroke=0)

        # Numéro de question
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.drawString(COL0_X_CM * cm, row_center,
                     f"Q{q_num:02d}.")

        # Cases à cocher
        for i in range(num_choices):
            bx = (FIRST_BOX_X_CM + i * COL_SPACING_CM) * cm
            by = row_y_top - (0.1 + BOX_SIDE_CM) * cm
            bside = BOX_SIDE_CM * cm
            c.setStrokeColorRGB(0.15, 0.15, 0.15)
            c.setFillColorRGB(1.0, 1.0, 1.0)
            c.setLineWidth(0.8)
            c.rect(bx, by, bside, bside, fill=1, stroke=1)

    c.showPage()


def _draw_label_box(c, label: str, page_h: float,
                    bx_cm: float, by_cm: float, bw_cm: float, bh_cm: float,
                    text: str = ""):
    """Dessine un label + boîte rectangulaire, avec texte pré-rempli optionnel."""
    # Label à gauche de la boîte
    lbl_x = (bx_cm - 1.5) * cm
    lbl_y = page_h - by_cm * cm - bh_cm * cm / 2 - 0.1 * cm
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(lbl_x, lbl_y, label)

    # Rectangle encadré
    c.setStrokeColorRGB(0.2, 0.2, 0.5)
    c.setFillColorRGB(0.97, 0.97, 1.0)
    c.setLineWidth(0.8)
    box_bottom = page_h - (by_cm + bh_cm) * cm
    c.rect(bx_cm * cm, box_bottom, bw_cm * cm, bh_cm * cm, fill=1, stroke=1)

    # Nom pré-imprimé dans le cadre si fourni
    if text:
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColorRGB(0.1, 0.1, 0.4)
        c.drawString((bx_cm + 0.35) * cm,
                     box_bottom + 0.22 * cm,
                     text)
