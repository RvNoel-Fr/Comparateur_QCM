# -*- coding: utf-8 -*-
"""
debug_contours.py
Diagnostic : affiche tous les contours detectes et sauvegarde les images intermediaires.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import cv2
import numpy as np
from PIL import Image
import os

from app.pdf_reader import pdf_to_images

imgs = pdf_to_images("test_pdfs/test_student.pdf", dpi=200)
img = imgs[0]

# Conversion
bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

# Sauvegarder l'image grise
cv2.imwrite("test_pdfs/debug/01_gray.png", gray)

# Binarisation Otsu
blurred = cv2.GaussianBlur(gray, (3, 3), 0)
_, binary_otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
cv2.imwrite("test_pdfs/debug/02_binary_otsu.png", binary_otsu)

# Binarisation adaptative
binary_adapt = cv2.adaptiveThreshold(blurred, 255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4)
cv2.imwrite("test_pdfs/debug/03_binary_adaptive.png", binary_adapt)

# Chercher les contours sur Otsu
contours, hierarchy = cv2.findContours(binary_otsu, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
print(f"Total contours (Otsu RETR_TREE) : {len(contours)}")

# Afficher les contours quasi-carres de toute taille
debug_img = bgr.copy()
square_count = 0
for cnt in contours:
    x, y, w, h = cv2.boundingRect(cnt)
    if w < 5 or h < 5:
        continue
    ratio = w / h if h > 0 else 0
    if abs(ratio - 1.0) > 0.5:
        continue
    if 10 <= w <= 200 and 10 <= h <= 200:
        cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 0, 255), 1)
        square_count += 1
        if square_count <= 20:
            print(f"  Contour quasi-carre : x={x} y={y} w={w} h={h}")

print(f"Total contours quasi-carres (10-200px) : {square_count}")
cv2.imwrite("test_pdfs/debug/04_all_squares.png", debug_img)

# Chercher specifiquement des rectangles de 20-80 px
print("\nContours dans la plage 20-80px :")
count_range = 0
for cnt in contours:
    x, y, w, h = cv2.boundingRect(cnt)
    if 20 <= w <= 80 and 20 <= h <= 80:
        ratio = w / h
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        count_range += 1
        if count_range <= 30:
            print(f"  x={x} y={y} w={w} h={h} ratio={ratio:.2f} sommets={len(approx)}")

print(f"Total : {count_range}")
print("\nImages sauvegardees dans test_pdfs/debug/")
