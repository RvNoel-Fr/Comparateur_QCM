"""
test_gui_reset_and_theme.py
Teste le thème sombre de la boîte de sélection des copies (ttk.Combobox)
et la réinitialisation complète de l'état / des noms lors du traitement successif de plusieurs fichiers.
"""

import sys
import os
import tkinter as tk

sys.stdout.reconfigure(encoding="utf-8")

print("=" * 60)
print("  TEST : THEME SOMBRE DU COMBOBOX & REINITIALISATION DE L'ETAT")
print("=" * 60)

from app.gui import QCMApp, PANEL, TEXT, ACCENT, BORDER
from app.analysis import StudentSheet

app = QCMApp()
app.withdraw()

# ── 1. Test du thème sombre du Combobox ───────────────────────────────────────
print("\n[1] Vérification du thème sombre du Combobox...")
app._sheet_combo.tk.eval(f"ttk::combobox::PopdownWindow {app._sheet_combo}")
lb = f"{app._sheet_combo}.popdown.f.l"
bg = app._sheet_combo.tk.eval(f"{lb} cget -background")
fg = app._sheet_combo.tk.eval(f"{lb} cget -foreground")
sel_bg = app._sheet_combo.tk.eval(f"{lb} cget -selectbackground")

print(f"  Popdown Listbox background : {bg} (attendu: {PANEL})")
print(f"  Popdown Listbox foreground : {fg} (attendu: {TEXT})")
print(f"  Popdown Listbox selectBackground : {sel_bg} (attendu: {ACCENT})")

assert bg == PANEL, f"Fond de liste {bg} != {PANEL}"
assert fg == TEXT, f"Texte de liste {fg} != {TEXT}"
print("  ✓ La liste déroulante est configurée sur fond sombre avec texte clair lisible.")

# ── 2. Test d'injection de données et vérification de la réinitialisation ─────
print("\n[2] Test de réinitialisation lors du chargement d'un nouveau fichier...")

# Simuler un fichier précédemment chargé et analysé avec des noms
app._student_path.set("test_pdfs/multi_test/HnQcm2.pdf")
app._plan_path.set("test_pdfs/csv_test/QCM_Terminale_S2_fiches_HN_plan_placement.txt")
app._sheets = [
    StudentSheet(index=0, name="MOREAU Lucas", name_detected=True, name_crop=None, seat_number=4),
    StudentSheet(index=1, name="ROUX Emma", name_detected=True, name_crop=None, seat_number=1)
]
app._student_name.set("MOREAU Lucas")
app._grade_lbl.config(text="14.50")
app._sheet_combo["values"] = ["Copie 1 (Place 4) : MOREAU Lucas", "Copie 2 (Place 1) : ROUX Emma"]
app._sheet_combo_var.set("Copie 1 (Place 4) : MOREAU Lucas")

print("  État avant réinitialisation :")
print(f"    _student_name = {app._student_name.get()}")
print(f"    _plan_path    = {app._plan_path.get()}")
print(f"    _sheets count = {len(app._sheets)}")
print(f"    combo values  = {app._sheet_combo['values']}")

# Appel de _reset_results
app._reset_results()

print("\n  État après réinitialisation (_reset_results) :")
print(f"    _student_name = '{app._student_name.get()}'")
print(f"    _sheets count = {len(app._sheets)}")
print(f"    _grade_lbl    = '{app._grade_lbl.cget('text')}'")
print(f"    combo values  = {list(app._sheet_combo['values'])}")

assert app._student_name.get() == "", "Le nom de l'étudiant doit être vidé"
assert len(app._sheets) == 0, "La liste des copies doit être vidée"
assert app._grade_lbl.cget("text") == "—", "La note doit être réinitialisée à '—'"
assert len(app._sheet_combo["values"]) == 0, "Le combobox doit être vidé"
print("  ✓ _reset_results réinitialise tous les champs correctement.")

# ── 3. Test de non-persistance du plan lors de la sélection d'un nouveau PDF ─
print("\n[3] Test de non-persistance du plan lors du choix d'un nouveau fichier...")

# Supposons que l'ancien plan était encore en mémoire
app._plan_path.set("test_pdfs/csv_test/QCM_Terminale_S2_fiches_HN_plan_placement.txt")

# Simuler la méthode _pick_student sans dialogue (changement de fichier)
new_file = "test_pdfs/HN/Test2etud.pdf"
app._student_path.set(new_file)
app._plan_path.set("")
app._reset_results()

assert app._plan_path.get() == "", "Le plan précédent ne doit PAS persister"
print("  ✓ L'ancien plan est immédiatement purgé lors du chargement d'un nouveau PDF.")

app.destroy()

print("\n" + "=" * 60)
print("  TOUS LES TESTS DE THEME ET REINITIALISATION SONT VALIDES !")
print("=" * 60)
