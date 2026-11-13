"""
pdf_reader.py
Convertit les pages d'un PDF en images PIL via PyMuPDF.
Gère l'extraction des noms (numérique ou scanné par vision) et le recadrage du nom.
"""

import sys
sys.modules.setdefault('pymupdf.layout', None)
try:
    import pymupdf as fitz  # pymupdf >= 1.24
except ImportError:
    import fitz  # ancienne API
from PIL import Image, ImageFont, ImageDraw
import io
import os
import re
import cv2
import numpy as np


def pdf_to_images(pdf_path: str, dpi: int = 200) -> list[Image.Image]:
    """
    Ouvre un fichier PDF et retourne une liste d'images PIL,
    une par page, au DPI demandé.

    Args:
        pdf_path: Chemin absolu vers le fichier PDF.
        dpi:      Résolution de rendu (200 dpi = bon compromis vitesse/précision).

    Returns:
        Liste d'objets PIL.Image (mode RGB), indexée par numéro de page.
    """
    doc = fitz.open(pdf_path)
    images: list[Image.Image] = []

    zoom = dpi / 72.0          # PyMuPDF travaille en 72 dpi par défaut
    mat = fitz.Matrix(zoom, zoom)

    for page in doc:
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img.convert("RGB"))

    doc.close()
    return images


def page_count(pdf_path: str) -> int:
    """Retourne le nombre de pages du PDF."""
    doc = fitz.open(pdf_path)
    n = doc.page_count
    doc.close()
    return n


# ──────────────────────────────────────────────────────────────────────────────
# Vision par ordinateur : détection de l'encadré du nom & du numéro de place
# ──────────────────────────────────────────────────────────────────────────────

_DIGIT_TEMPLATES: dict[int, np.ndarray] | None = None
_NAME_TEMPLATES_CACHE: dict[str, np.ndarray] = {}


def _get_digit_templates() -> dict[int, np.ndarray]:
    """
    Génère et met en cache les gabarits exacts des chiffres 0 à 9
    au format vectoriel ReportLab Helvetica-Bold (la même police que les fiches).
    """
    global _DIGIT_TEMPLATES
    if _DIGIT_TEMPLATES is None:
        try:
            import io
            import reportlab.lib.pagesizes as pagesizes
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import cm

            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(12 * cm, 3 * cm))
            c.setFont("Helvetica-Bold", 22)
            for d in range(10):
                c.drawString((0.8 + d * 1.0) * cm, 1.0 * cm, str(d))
            c.save()
            buf.seek(0)

            doc = fitz.open(stream=buf.read(), filetype="pdf")
            pix = doc[0].get_pixmap(dpi=200)
            doc.close()

            img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            _, bin_img = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
            cnts, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            boxes = sorted([cv2.boundingRect(c) for c in cnts], key=lambda b: b[0])
            templates = {}
            for d, (x, y, w, h) in enumerate(boxes):
                templates[d] = bin_img[y:y+h, x:x+w]
            _DIGIT_TEMPLATES = templates
        except Exception:
            _DIGIT_TEMPLATES = {}
    return _DIGIT_TEMPLATES


def detect_seat_number(pil_image: Image.Image) -> int | None:
    """
    Détecte par vision par ordinateur le numéro de placement (1 à N)
    inscrit dans le badge épais en haut à droite de la feuille.
    Retourne l'entier du numéro de place ou None si non trouvé.
    """
    try:
        img = np.array(pil_image)
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img

        h_img, w_img = gray.shape
        roi_x = int(w_img * 0.60)
        roi_h = int(h_img * 0.30)
        gray_roi = gray[:roi_h, roi_x:]

        _, binary = cv2.threshold(gray_roi, 190, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        badge_candidates = [
            cv2.boundingRect(c) for c in contours
            if 90 <= cv2.boundingRect(c)[2] <= 250 and 55 <= cv2.boundingRect(c)[3] <= 170
        ]
        if not badge_candidates:
            return None

        # Sélectionne le badge extérieur (le plus haut / plus large)
        bx, by, bw, bh = min(badge_candidates, key=lambda b: (b[1], -b[2]))

        # Zone interne inférieure contenant le numéro (évite les bordures)
        dy1 = int(by + 0.35 * bh)
        dy2 = int(by + 0.90 * bh)
        dx1 = int(roi_x + bx + 0.10 * bw)
        dx2 = int(roi_x + bx + 0.90 * bw)
        digit_crop = gray[dy1:dy2, dx1:dx2]

        _, bin_d = cv2.threshold(digit_crop, 185, 255, cv2.THRESH_BINARY_INV)
        cnts, _ = cv2.findContours(bin_d, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = sorted([
            cv2.boundingRect(c) for c in cnts
            if 6 <= cv2.boundingRect(c)[2] <= 60 and 20 <= cv2.boundingRect(c)[3] <= 60
        ], key=lambda b: b[0])

        if not boxes:
            return None

        templates = _get_digit_templates()
        if not templates:
            return None

        digits = []
        for (gx, gy, gw, gh) in boxes:
            crop_single = bin_d[gy:gy+gh, gx:gx+gw]
            scores = {}
            for d, tpl in templates.items():
                th_target = gh
                tw_target = max(4, int(tpl.shape[1] * (th_target / tpl.shape[0])))
                cur_tpl = cv2.resize(tpl, (tw_target, th_target), interpolation=cv2.INTER_AREA)

                pw = max(crop_single.shape[1], cur_tpl.shape[1])
                ph = max(crop_single.shape[0], cur_tpl.shape[0])
                p_c = np.zeros((ph, pw), dtype=np.uint8)
                p_c[:crop_single.shape[0], :crop_single.shape[1]] = crop_single
                p_t = np.zeros((ph, pw), dtype=np.uint8)
                p_t[:cur_tpl.shape[0], :cur_tpl.shape[1]] = cur_tpl

                res = cv2.matchTemplate(p_c, p_t, cv2.TM_CCOEFF_NORMED)
                scores[d] = res[0, 0]

            best_d = max(scores, key=scores.get)
            if scores[best_d] >= 0.45:
                digits.append(str(best_d))

        if digits:
            return int("".join(digits))
        return None
    except Exception:
        return None


def detect_name_box(pil_image: Image.Image) -> tuple[int, int, int, int] | None:
    """
    Localise par vision par ordinateur le cadre rectangulaire du 'Nom'
    dans la partie supérieure de la feuille.
    Retourne (x, y, w, h) en pixels de l'image, ou None.
    """
    try:
        img = np.array(pil_image)
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img

        h_img, w_img = gray.shape
        roi_h = int(h_img * 0.35)
        gray_roi = gray[:roi_h, :]

        _, binary = cv2.threshold(gray_roi, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Le cadre de nom est large (>= 25% de la page) et de hauteur modérée (20 à 150 px)
            if w >= 0.25 * w_img and 20 <= h <= 150:
                candidates.append((x, y, w, h))

        if candidates:
            # Retient le plus large (qui correspond au grand cadre Nom, pas la Date)
            return max(candidates, key=lambda b: b[2])
        return None
    except Exception:
        return None


def crop_name_zone(pil_image: Image.Image, dpi: int = 200) -> Image.Image:
    """
    Extrait et retourne la vignette de la zone "Nom".
    Utilise la détection de contour pour s'aligner exactement sur le cadre scanné,
    résolvant ainsi tout décalage d'impression ou de numérisation.
    Si le cadre physique n'est pas détecté, utilise les coordonnées théoriques avec marges élargies.

    Args:
        pil_image: Image PIL de la première page du PDF (rendue à `dpi`).
        dpi:       DPI auquel l'image a été rendue.

    Returns:
        Image PIL recadrée et centrée de la zone nom.
    """
    scale = dpi / 2.54  # px par cm
    box = detect_name_box(pil_image)

    if box is not None:
        bx, by, bw, bh = box
        # Inclut le label 'Nom :' à gauche (~1.6 cm) et des marges de respiration
        lbl_margin_px = int(1.6 * scale)
        pad_y = int(0.20 * scale)
        pad_x = int(0.25 * scale)

        x1 = max(0, bx - lbl_margin_px)
        y1 = max(0, by - pad_y)
        x2 = min(pil_image.width, bx + bw + pad_x)
        y2 = min(pil_image.height, by + bh + pad_y)
        return pil_image.crop((x1, y1, x2, y2))

    # Repli avec coordonnées théoriques
    from app.sheet_generator import (
        NAME_BOX_X_CM, NAME_BOX_Y_CM,
        NAME_BOX_W_CM, NAME_BOX_H_CM
    )
    margin_px = int(0.5 * scale)
    x1 = max(0, int((NAME_BOX_X_CM - 1.6) * scale) - margin_px)
    y1 = max(0, int((NAME_BOX_Y_CM - 0.2) * scale) - margin_px)
    x2 = min(pil_image.width, int((NAME_BOX_X_CM + NAME_BOX_W_CM) * scale) + margin_px)
    y2 = min(pil_image.height, int((NAME_BOX_Y_CM + NAME_BOX_H_CM + 0.3) * scale) + margin_px * 2)

    return pil_image.crop((x1, y1, x2, y2))


def get_name_template(name: str) -> np.ndarray | None:
    """Génère le gabarit binaire exact du nom en Helvetica-Bold 10.5 pt."""
    if name in _NAME_TEMPLATES_CACHE:
        return _NAME_TEMPLATES_CACHE[name]
    try:
        import io
        import reportlab.lib.pagesizes as pagesizes
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(16 * cm, 2.5 * cm))
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(0.5 * cm, 0.5 * cm, name)
        c.save()
        buf.seek(0)
        doc = fitz.open(stream=buf.read(), filetype="pdf")
        pix = doc[0].get_pixmap(dpi=200)
        doc.close()
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        _, bin_tpl = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        cnts, _ = cv2.findContours(bin_tpl, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        x, y, w, h = cv2.boundingRect(np.vstack(cnts))
        tpl = bin_tpl[y:y+h, x:x+w]
        _NAME_TEMPLATES_CACHE[name] = tpl
        return tpl
    except Exception:
        return None


def match_printed_name(pil_image: Image.Image, candidates: list[str]) -> tuple[str | None, float]:
    """
    Compare l'image de la zone nom avec une liste de noms d'étudiants candidats
    par corrélation multi-échelle de gabarits vectoriels (ReportLab Helvetica-Bold 10.5 pt).
    Utilise la boîte englobante de l'encre détectée et une pénalité de longueur
    pour une discrimination parfaite entre noms courts et longs.
    """
    if not candidates:
        return None, 0.0

    box = detect_name_box(pil_image)
    if not box:
        return None, 0.0
    bx, by, bw, bh = box
    img_np = np.array(pil_image)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if img_np.ndim == 3 else img_np

    # Rogner l'intérieur du cadre nom (jusqu'à 92% de la largeur pour couvrir les noms longs)
    crop = gray[by + 3 : by + bh - 3, bx + 10 : bx + int(bw * 0.92)]
    if crop.shape[0] < 10 or crop.shape[1] < 20:
        return None, 0.0

    # Binarisation avec seuil d'Otsu
    _, bin_crop = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Détection des contours de l'encre
    cnts, _ = cv2.findContours(bin_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    text_cnts = [c for c in cnts if cv2.boundingRect(c)[3] >= 8 and cv2.boundingRect(c)[2] >= 3]
    if not text_cnts:
        return None, 0.0

    tx, ty, tw, th = cv2.boundingRect(np.vstack(text_cnts))
    if tw < 15 or th < 10:
        return None, 0.0

    text_crop = bin_crop[max(0, ty - 2) : min(bin_crop.shape[0], ty + th + 2),
                         max(0, tx - 2) : min(bin_crop.shape[1], tx + tw + 2)]

    scores = {}
    for name in candidates:
        tpl = get_name_template(name)
        if tpl is None:
            continue
        best_sc = 0.0
        # Tester plusieurs échelles pour compenser les petites variations de DPI de numérisation
        for scale in (0.91, 0.93, 0.95, 0.96, 0.98, 1.0, 1.02):
            sw = max(4, int(tpl.shape[1] * scale))
            sh = max(4, int(tpl.shape[0] * scale))
            if text_crop.shape[0] < sh or text_crop.shape[1] < sw:
                continue
            stpl = cv2.resize(tpl, (sw, sh), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(text_crop, stpl, cv2.TM_CCOEFF_NORMED)
            width_penalty = abs(tw - sw) / max(tw, sw)
            sc = float(res.max()) * (1.0 - 0.45 * width_penalty)
            if sc > best_sc:
                best_sc = sc
        scores[name] = best_sc

    if not scores:
        return None, 0.0
    best_name = max(scores, key=scores.get)
    return best_name, scores[best_name]


def find_candidate_plans(pdf_path: str) -> list[str]:
    """Recherche tous les fichiers plan de placement (*.txt) dans le dossier du PDF et l'espace de travail."""
    plans: list[str] = []
    seen = set()

    def add_plan(filepath: str):
        full = os.path.abspath(filepath)
        if full not in seen and os.path.isfile(full):
            seen.add(full)
            plans.append(full)

    def scan_dir(directory: str, max_depth: int = 2):
        if not directory or not os.path.isdir(directory):
            return
        for root, dirs, files in os.walk(directory):
            rel = os.path.relpath(root, directory)
            if rel != "." and rel.count(os.sep) >= max_depth:
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "build", ".venv", ".git")]
            for f in files:
                fl = f.lower()
                if fl.endswith(".txt") and ("plan" in fl or "placement" in fl):
                    add_plan(os.path.join(root, f))

    try:
        p_dir = os.path.dirname(os.path.abspath(pdf_path)) if pdf_path else ""
        if p_dir:
            scan_dir(p_dir, max_depth=1)
            scan_dir(os.path.dirname(p_dir), max_depth=1)
        scan_dir(os.getcwd(), max_depth=2)
        plans.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    except Exception:
        pass
    return plans


def find_best_matching_plan(pdf_path: str, pages_imgs: list[Image.Image]) -> tuple[dict[int, str], str | None]:
    """
    Parcourt tous les plans de placement disponibles dans le projet et
    sélectionne celui qui correspond aux numéros de place et
    aux noms imprimés sur les premières pages.
    Ne retient un plan QUE s'il correspond au nom du fichier ou si la vérification
    optique des noms imprimés est positive.
    """
    plans = find_candidate_plans(pdf_path)
    if not plans:
        return {}, None

    from app.sheet_generator import parse_placement_plan

    # 1. Correspondance directe par nom de fichier
    pdf_base = os.path.splitext(os.path.basename(pdf_path))[0].lower()
    for p in plans:
        p_base = os.path.splitext(os.path.basename(p))[0].lower()
        if pdf_base in p_base or p_base.replace("_plan_placement", "") in pdf_base:
            p_map = parse_placement_plan(p)
            if p_map:
                return p_map, p

    # 2. Détecter la place sur les 3 premières pages
    checks = []
    for im in pages_imgs[:3]:
        st = detect_seat_number(im)
        if st is not None:
            checks.append((im, st))

    if not checks:
        return {}, None

    best_plan = None
    best_score = 0.0
    best_map = {}

    for p in plans:
        p_map = parse_placement_plan(p)
        matched_count = 0
        score_sum = 0.0
        for im, st in checks:
            expected_name = p_map.get(st)
            if expected_name:
                _, sc = match_printed_name(im, [expected_name])
                if sc >= 0.38:
                    matched_count += 1
                    score_sum += sc

        # Exige qu'au moins 2 pages (ou toutes les pages vérifiées) correspondent avec certitude
        min_required = min(2, len(checks))
        if matched_count >= min_required and score_sum > best_score:
            best_score = score_sum
            best_plan = p
            best_map = p_map

    if best_plan is not None:
        return best_map, best_plan

    return {}, None


def find_candidate_csvs(pdf_path: str) -> list[str]:
    """Recherche tous les fichiers CSV d'étudiants dans le dossier et l'espace de travail."""
    csvs: list[str] = []
    seen = set()

    def add_csv(filepath: str):
        full = os.path.abspath(filepath)
        if full not in seen and os.path.isfile(full):
            seen.add(full)
            csvs.append(full)

    def scan_dir(directory: str, max_depth: int = 2):
        if not directory or not os.path.isdir(directory):
            return
        for root, dirs, files in os.walk(directory):
            rel = os.path.relpath(root, directory)
            if rel != "." and rel.count(os.sep) >= max_depth:
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "build", ".venv", ".git")]
            for f in files:
                fl = f.lower()
                if fl.endswith(".csv") and not fl.startswith("notes_"):
                    add_csv(os.path.join(root, f))

    try:
        p_dir = os.path.dirname(os.path.abspath(pdf_path)) if pdf_path else ""
        if p_dir:
            scan_dir(p_dir, max_depth=1)
            scan_dir(os.path.dirname(p_dir), max_depth=1)
        scan_dir(os.getcwd(), max_depth=2)
        csvs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    except Exception:
        pass
    return csvs


def extract_name(pdf_path: str, page_num: int = 0,
                 pil_image: Image.Image | None = None,
                 seat_map: dict[int, str] | None = None,
                 candidates: list[str] | None = None) -> str | None:
    """
    Tente d'extraire le nom de l'étudiant depuis la fiche à la page `page_num`.

    Stratégie hybride intelligente :
    1. Si le PDF est numérique : lit le texte vectoriel PyMuPDF.
    2. Si le PDF est scanné (aucun texte vectoriel) :
       a. Détecte le numéro de placement aléatoire (badge en haut à droite).
       b. Résout le nom via le seat_map fourni ou trouvé dans les plans de l'espace de travail.
       c. Reconnaissance optique directe du nom imprimé parmi la liste des candidats.
       d. Repli sur 'Place N° X' si aucune correspondance trouvée.

    Returns:
        Le nom de l'étudiant sous forme de chaîne nettoyée, ou None.
    """
    # ── Étape 1 : Lecture du texte vectoriel PyMuPDF ─────────────────────────
    try:
        from app.sheet_generator import (
            NAME_BOX_X_CM, NAME_BOX_Y_CM,
            NAME_BOX_W_CM, NAME_BOX_H_CM
        )
        doc = fitz.open(pdf_path)
        if page_num < doc.page_count:
            page = doc[page_num]
            CM = 28.35
            effective_w = min(NAME_BOX_W_CM, 12.0)
            rect = fitz.Rect(
                NAME_BOX_X_CM * CM,
                NAME_BOX_Y_CM * CM,
                (NAME_BOX_X_CM + effective_w) * CM,
                (NAME_BOX_Y_CM + NAME_BOX_H_CM) * CM,
            )
            text = page.get_text("text", clip=rect).strip()

            # Filtrer les artéfacts connus (labels imprimés)
            IGNORED = {"date :", "nom :", "nom:", "date:", "page"}
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            filtered = [
                l for l in lines
                if l.lower() not in IGNORED and not l.lower().startswith("date") and not l.lower().startswith("nom")
            ]
            clean_name = " ".join(filtered).strip()
            if clean_name and len(clean_name) >= 2:
                doc.close()
                return clean_name
        doc.close()
    except Exception:
        pass

    # ── Étape 2 : PDF scanné ────────────────────────────────────────────────
    if pil_image is not None:
        seat = detect_seat_number(pil_image)

        # 1. Utiliser le seat_map explicitement fourni
        if seat_map and seat is not None and seat in seat_map:
            return seat_map[seat]

        # 2. Liste de candidats globale
        all_candidates = list(candidates) if candidates else []

        # 3. Recherche automatique dans les plans de placement du projet
        active_map = dict(seat_map) if seat_map else {}
        if not active_map:
            from app.sheet_generator import parse_placement_plan
            plans = find_candidate_plans(pdf_path)
            pdf_base = os.path.splitext(os.path.basename(pdf_path))[0].lower()
            for p in plans:
                p_base = os.path.splitext(os.path.basename(p))[0].lower()
                is_name_match = (pdf_base in p_base or p_base.replace("_plan_placement", "") in pdf_base)
                p_map = parse_placement_plan(p)
                if not p_map:
                    continue
                for s_name in p_map.values():
                    if s_name not in all_candidates:
                        all_candidates.append(s_name)

                if seat is not None and seat in p_map:
                    if is_name_match:
                        active_map.update(p_map)
                        break
                    else:
                        # Validation optique indispensable pour éviter d'attribuer un plan arbitraire
                        cand_name = p_map[seat]
                        m_name, sc = match_printed_name(pil_image, [cand_name])
                        if m_name and sc >= 0.38:
                            active_map.update(p_map)
                            break

        # 4. Reconnaissance optique directe du nom imprimé en priorité si des candidats sont connus
        if all_candidates:
            matched_name, score = match_printed_name(pil_image, all_candidates)
            if matched_name and score >= 0.38:
                return matched_name

        # 5. Si la place correspond dans un plan validé
        if seat is not None and seat in active_map:
            return active_map[seat]

        # 6. Si pas encore de nom, enrichir les candidats avec les CSVs disponibles
        if not all_candidates:
            from app.sheet_generator import parse_students_csv
            csv_files = find_candidate_csvs(pdf_path)
            for c_path in csv_files:
                _, c_students = parse_students_csv(c_path)
                for s in c_students:
                    if s not in all_candidates:
                        all_candidates.append(s)
            if all_candidates:
                matched_name, score = match_printed_name(pil_image, all_candidates)
                if matched_name and score >= 0.38:
                    return matched_name

        # 7. Repli sur le numéro de place si détecté
        if seat is not None:
            return f"Place N° {seat}"

    return None
