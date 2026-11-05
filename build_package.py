"""
build_package.py
Assemble le package de distribution pour les collègues et crée l'archive ZIP.
"""

import os
import shutil
import zipfile

pkg_dir = "dist/Package_Test_Comparateur_QCM"
if os.path.exists(pkg_dir):
    shutil.rmtree(pkg_dir)
os.makedirs(pkg_dir, exist_ok=True)

# 1. Copier le standalone executable
shutil.copy2("dist/Comparateur_QCM_Solo.exe", os.path.join(pkg_dir, "Comparateur_QCM.exe"))

# 2. Copier le dossier complet (option portable sans décompression temporaire)
shutil.copytree("dist/Comparateur_QCM", os.path.join(pkg_dir, "Dossier_Complet_Portable"))

# Lanceur .bat pour le dossier portable
with open(os.path.join(pkg_dir, "Dossier_Complet_Portable", "Lancer.bat"), "w", encoding="utf-8") as f:
    f.write('@echo off\nstart "" "%~dp0Comparateur_QCM.exe"\n')

# 3. Dossier Exemples de test
ex_dir = os.path.join(pkg_dir, "Exemples_de_test")
os.makedirs(ex_dir, exist_ok=True)
shutil.copy2("test_pdfs/HN/CorrigeQCM.pdf", os.path.join(ex_dir, "01_Corrige_Modele.pdf"))
shutil.copy2("test_pdfs/multi_test/HnQcm2.pdf", os.path.join(ex_dir, "02_Copies_Eleves_Scannees.pdf"))
shutil.copy2("test_pdfs/csv_test/QCM_Terminale_S2_fiches_HN_plan_placement.txt", os.path.join(ex_dir, "03_Plan_de_placement.txt"))
shutil.copy2("test_pdfs/csv_test/Terminale_S2.csv", os.path.join(ex_dir, "04_Liste_Eleves_Exemple.csv"))

# 4. Guide utilisateur
guide = """========================================================================
   COMPARATEUR QCM PDF — GUIDE DE PRISE EN MAIN RAPIDE
========================================================================

Bonjour et bienvenue dans le Comparateur QCM PDF !
Ce logiciel permet de corriger automatiquement des fiches QCM scannées,
d'attribuer les notes, de générer des statistiques complètes et d'exporter
les résultats aux formats PDF et Excel/CSV.

AUCUNE INSTALLATION REQUISE : Python n'est pas nécessaire sur votre PC.

------------------------------------------------------------------------
  COMMENT LANCER LE LOGICIEL ?
------------------------------------------------------------------------
Double-cliquez simplement sur :
    👉  Comparateur_QCM.exe

(Note : Au premier lancement, Windows SmartScreen peut afficher une alerte
car le programme est un exécutable indépendant récent. Cliquez sur 
"Informations complémentaires" puis "Exécuter quand même").

Si vous préférez une version sans extraction temporaire, vous pouvez aussi
ouvrir le sous-dossier "Dossier_Complet_Portable" et double-cliquer sur Lancer.bat.

------------------------------------------------------------------------
  TEST RAPIDE EN 4 ÉTAPES (avec les fichiers d'exemple fournis) :
------------------------------------------------------------------------
Un dossier "Exemples_de_test" est inclus pour tester immédiatement :

1. CORRECTION (MODÈLE) :
   Cliquez sur "Parcourir..." à côté de "📋 Correction"
   -> Sélectionnez le fichier : Exemples_de_test/01_Corrige_Modele.pdf

2. COPIES ÉTUDIANTS :
   Cliquez sur "Parcourir..." à côté de "📄 QCM Étudiant(s)"
   -> Sélectionnez le fichier : Exemples_de_test/02_Copies_Eleves_Scannees.pdf

3. LANCER L'ANALYSE :
   Cliquez sur le bouton bleu "  ▶  Analyser  "
   -> Le logiciel traite les 5 copies scannées en quelques secondes !

4. CONSULTER ET EXPORTER LES RÉSULTATS :
   - Naviguez entre les copies avec "◀ Copie précédente / Copie suivante ▶"
     ou via la boîte déroulante directe pour voir chaque élève, sa copie annotée
     et sa note.
   - Cliquez sur "📊 Cumul promotion" pour afficher le palmarès de la classe,
     la moyenne, les notes min/max et l'analyse détaillée question par question.
   - Cliquez sur "📊 Exporter le rapport (PDF)" pour générer un bilan PDF complet.
   - Cliquez sur "📥 Exporter les notes (CSV / Excel)" pour obtenir le tableur
     des notes avec le numéro de placement, directement compatible Excel ou Pronote.

------------------------------------------------------------------------
  GÉNÉRATEUR DE FICHES DE RÉPONSES
------------------------------------------------------------------------
Pour créer vos propres sujets de QCM vierges ou nominatifs :
- Cliquez sur "🖨 Générer une fiche de réponses" en haut à droite.
- Choisissez le nombre de questions (jusqu'à 100) et le nombre de choix (3, 4 ou 5).
- Optionnel : Cliquez sur "📁 Charger fichier CSV..." et sélectionnez
  "Exemples_de_test/04_Liste_Eleves_Exemple.csv" pour créer automatiquement
  une fiche par élève avec leur nom et un numéro de placement aléatoire.
- Cliquez sur "Générer le PDF" ou "Imprimer directement".

Merci pour vos tests et vos retours !
"""

with open(os.path.join(pkg_dir, "GUIDE_DE_DEMARRAGE.txt"), "w", encoding="utf-8") as f:
    f.write(guide)

# 5. Créer l'archive ZIP
zip_name = "dist/Comparateur_QCM_Package_Test.zip"
if os.path.exists(zip_name):
    os.remove(zip_name)

print("Compression du package en fichier ZIP...")
with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(pkg_dir):
        for file in files:
            full_path = os.path.join(root, file)
            # Nom relatif dans l'archive commençant par le dossier Package_Test_Comparateur_QCM
            arc_name = os.path.relpath(full_path, "dist")
            z.write(full_path, arc_name)

size_mb = os.path.getsize(zip_name) / (1024 * 1024)
print(f"Archive creee avec succes : {zip_name} ({size_mb:.1f} Mo)")
