"""
detector.py
Détecte les cases à cocher dans une image PIL et détermine lesquelles sont cochées.

Stratégie (robuste pour PDFs dessinés/scannés) :
  1. Conversion en niveaux de gris.
  2. Détection des contours avec RETR_TREE pour capturer toute la hiérarchie.
  3. Filtrage des contours quasi-carrés de la bonne taille.
  4. Déduplication (NMS) pour éviter les doublons.
  5. Mesure du taux de remplissage INTÉRIEUR pour décider si cochée.
  6. Regroupement en lignes → labels A, B, C, D.
"""

import cv2
import numpy as np
from PIL import Image
from dataclasses import dataclass, field


# ──────────────────────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CheckBox:
    """Représente une case à cocher détectée."""
    x: int
    y: int
    w: int
    h: int
    filled: bool
    fill_ratio: float
    label: str = ""
    question: int = 0


@dataclass
class QuestionResult:
    """Résultat de détection pour une question."""
    question: int
    answer: str
    boxes: list = field(default_factory=list)
    filled_count: int = 0


# ──────────────────────────────────────────────────────────────────────────────
# Paramètres (ajustables si la qualité du PDF varie)
# ──────────────────────────────────────────────────────────────────────────────

BOX_MIN_SIZE      = 28     # px @ 200 dpi — taille minimale d'une case
BOX_MAX_SIZE      = 70     # px @ 200 dpi — taille maximale
ASPECT_RATIO_TOL  = 0.35   # tolérance aspect ratio (1 = carré parfait)
FILL_THRESHOLD    = 0.08   # ratio min de pixels noirs pour "cochée"
ROW_Y_TOLERANCE   = 20     # px — marge verticale pour regrouper en ligne
NMS_OVERLAP       = 0.5    # seuil IoU pour suppression des doublons (garder le plus grand)


# ──────────────────────────────────────────────────────────────────────────────
# Utilitaires image
# ──────────────────────────────────────────────────────────────────────────────

def _pil_to_cv(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _preprocess(gray: np.ndarray) -> np.ndarray:
    """
    Prépare l'image pour la détection de contours :
    léger flou + binarisation globale (Otsu) + morphologie pour renforcer les bords.
    """
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    # Binarisation globale inversée (fond blanc → fond noir)
    _, binary = cv2.threshold(blurred, 0, 255,
                               cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Fermeture légère pour relier les bords discontinus
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    return binary


def _fill_ratio(binary: np.ndarray, x: int, y: int, w: int, h: int,
                margin: int = 4) -> float:
    """Ratio de pixels 'cochés' à l'intérieur de la case (en ignorant les bords)."""
    x1 = max(0, x + margin)
    y1 = max(0, y + margin)
    x2 = min(binary.shape[1], x + w - margin)
    y2 = min(binary.shape[0], y + h - margin)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    roi = binary[y1:y2, x1:x2]
    total = roi.size
    return float(np.count_nonzero(roi)) / total if total > 0 else 0.0


def _iou(a: tuple, b: tuple) -> float:
    """Intersection over Union pour deux boîtes (x, y, w, h)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(ax, bx)
    iy = max(ay, by)
    iw = min(ax + aw, bx + bw) - ix
    ih = min(ay + ah, by + bh) - iy
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _is_duplicate(b1: tuple, b2: tuple) -> bool:
    """Vérifie si b1 et b2 représentent la même case (inclusion ou fort recouvrement)."""
    ax, ay, aw, ah = b1
    bx, by, bw, bh = b2
    ix = max(ax, bx)
    iy = max(ay, by)
    iw = min(ax + aw, bx + bw) - ix
    ih = min(ay + ah, by + bh) - iy
    if iw > 0 and ih > 0:
        inter = iw * ih
        min_area = min(aw * ah, bw * bh)
        if inter / min_area > 0.4:
            return True
        union = aw * ah + bw * bh - inter
        if union > 0 and (inter / union) > 0.35:
            return True
    # Distance entre les centres
    cax = ax + aw / 2.0
    cay = ay + ah / 2.0
    cbx = bx + bw / 2.0
    cby = by + bh / 2.0
    if abs(cax - cbx) < 22 and abs(cay - cby) < 22:
        return True
    return False


def _nms(boxes: list[tuple]) -> list[tuple]:
    """Suppression des boîtes dupliquées par NMS enrichi (IoU + inclusion + centre)."""
    if not boxes:
        return []
    kept = []
    # Trier par surface décroissante pour privilégier le contour externe complet de la case
    for box in sorted(boxes, key=lambda b: b[2] * b[3], reverse=True):
        if not any(_is_duplicate(box, k) for k in kept):
            kept.append(box)
    return kept


# ──────────────────────────────────────────────────────────────────────────────
# Détection principale
# ──────────────────────────────────────────────────────────────────────────────

def detect_checkboxes(image: Image.Image) -> list[CheckBox]:
    """
    Détecte toutes les cases à cocher dans une image PIL.
    Utilise RETR_TREE pour capturer les rectangles à tout niveau hiérarchique.
    """
    bgr = _pil_to_cv(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    binary = _preprocess(gray)

    # Détection de tous les contours (hiérarchie complète)
    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    candidates: list[tuple] = []  # (x, y, w, h)

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)

        # Filtre de taille
        if not (BOX_MIN_SIZE <= w <= BOX_MAX_SIZE and
                BOX_MIN_SIZE <= h <= BOX_MAX_SIZE):
            continue

        # Filtre d'aspect ratio (quasi-carré)
        ratio = w / h if h > 0 else 0
        if abs(ratio - 1.0) > ASPECT_RATIO_TOL:
            continue

        # Filtre de rectangularité : le contour doit approcher un rectangle
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        if len(approx) < 4 or len(approx) > 8:
            continue

        candidates.append((x, y, w, h))

    # Déduplication
    unique = _nms(candidates)

    # Création des CheckBox avec mesure de remplissage
    boxes: list[CheckBox] = []
    for (x, y, w, h) in unique:
        fr = _fill_ratio(binary, x, y, w, h)
        filled = fr > FILL_THRESHOLD
        boxes.append(CheckBox(x=x, y=y, w=w, h=h,
                               filled=filled, fill_ratio=fr))

    return boxes


# ──────────────────────────────────────────────────────────────────────────────
# Regroupement en questions
# ──────────────────────────────────────────────────────────────────────────────

def group_into_questions(boxes: list[CheckBox],
                          page_offset: int = 0) -> list[QuestionResult]:
    """
    Regroupe les cases par lignes horizontales et attribue A, B, C, D.
    """
    if not boxes:
        return []

    boxes_sorted = sorted(boxes, key=lambda b: (b.y, b.x))

    # Regroupement par ligne (même y ± ROW_Y_TOLERANCE)
    rows: list[list[CheckBox]] = []
    current_row: list[CheckBox] = [boxes_sorted[0]]

    for box in boxes_sorted[1:]:
        # Compare au centroïde Y de la ligne courante
        row_y = sum(b.y + b.h // 2 for b in current_row) / len(current_row)
        if abs((box.y + box.h // 2) - row_y) <= ROW_Y_TOLERANCE:
            current_row.append(box)
        else:
            rows.append(sorted(current_row, key=lambda b: b.x))
            current_row = [box]
    rows.append(sorted(current_row, key=lambda b: b.x))

    results: list[QuestionResult] = []
    labels = ["A", "B", "C", "D", "E"]
    q_idx = 0

    for r in rows:
        # Élimination des doublons horizontaux au sein d'une même ligne
        clean_r: list[CheckBox] = []
        for b in sorted(r, key=lambda b: b.x):
            if not clean_r or (b.x - clean_r[-1].x) >= 40:
                clean_r.append(b)
            else:
                # Deux cases sur la même colonne : conserver la plus grande
                if b.w * b.h > clean_r[-1].w * clean_r[-1].h:
                    clean_r[-1] = b

        # Ne garder que les lignes de 3 à 5 choix
        if not (3 <= len(clean_r) <= 5):
            continue

        # Vérifier la régularité d'espacement des choix
        # Les cases d'un QCM sont régulièrement espacées ; les lettres manuscrites ou artéfacts ne le sont pas
        dx = [clean_r[i + 1].x - clean_r[i].x for i in range(len(clean_r) - 1)]
        if min(dx) < 55 or (max(dx) / min(dx) > 1.6):
            continue

        q_num = page_offset + q_idx + 1
        q_idx += 1
        for i, box in enumerate(clean_r):
            box.label = labels[i] if i < len(labels) else str(i + 1)
            box.question = q_num

        filled_boxes = [box for box in clean_r if box.filled]
        filled_count = len(filled_boxes)

        if filled_count == 0:
            answer = ""
        elif filled_count == 1:
            answer = filled_boxes[0].label
        else:
            # Plus d'une case cochée (ex: "A, B") -> réponse multiple traitée comme invalide
            answer = ", ".join(b.label for b in filled_boxes)

        results.append(QuestionResult(
            question=q_num,
            answer=answer,
            boxes=clean_r,
            filled_count=filled_count
        ))

    return results


def extract_answers(images: list[Image.Image],
                    questions_per_page=None) -> list[QuestionResult]:
    """
    Traite toutes les pages et retourne les réponses détectées.
    """
    all_results: list[QuestionResult] = []
    q_offset = 0

    for image in images:
        boxes = detect_checkboxes(image)
        results = group_into_questions(boxes, page_offset=q_offset)
        q_offset += len(results)
        all_results.extend(results)

    return all_results


# ──────────────────────────────────────────────────────────────────────────────
# Rendu de débogage
# ──────────────────────────────────────────────────────────────────────────────

def draw_debug(image: Image.Image,
               results: list[QuestionResult]) -> Image.Image:
    """
    Retourne l'image annotée :
      - Vert épais    : case cochée unique
      - Orange épais  : plusieurs cases cochées sur la même question (invalide)
      - Gris fin      : case vide
    """
    bgr = _pil_to_cv(image).copy()

    for qr in results:
        is_multiple = qr.filled_count > 1
        for box in qr.boxes:
            if box.filled:
                color = (0, 140, 255) if is_multiple else (0, 200, 0)
                thick = 3
            else:
                color = (150, 150, 150)
                thick = 1
            cv2.rectangle(bgr,
                           (box.x, box.y),
                           (box.x + box.w, box.y + box.h),
                           color, thick)
            cv2.putText(bgr, box.label,
                        (box.x, max(0, box.y - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1,
                        cv2.LINE_AA)

    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
