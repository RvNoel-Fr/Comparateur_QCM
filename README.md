# Comparateur QCM PDF 🎓

Application de bureau complète pour la création, la numérisation, la correction automatique et l'analyse statistique de questionnaires à choix multiples (QCM) au format PDF.

---

## ✨ Fonctionnalités principales

1. **Correction automatique et instantanée par vision par ordinateur (OpenCV)** :
   * Détection précise des cases cochées (croix, noircissement, symboles).
   * Gestion des copies uniques ou de lots multi-fiches réunis dans un seul fichier PDF.
   * Détection et découpage automatique du cadre nom de l'étudiant.
   * Traitement automatique des réponses multiples comme mauvaises réponses.

2. **Placement aléatoire & fiches nominatives** :
   * Attribution automatique d'un numéro de placement aléatoire (1 à N) par étudiant pour éviter la triche.
   * **Classement automatique des fiches par ordre de place (1 → N)** à la génération pour faciliter la distribution en salle.
   * Génération automatique d'un plan de placement compagnon (`_plan_placement.txt`) avec tri par place et tri alphabétique.
   * Reconnaissance automatique de la place et du nom lors du scan (même sur PDF scanné).

3. **Générateur de fiches de réponses intégré** :
   * Création de fiches personnalisées de 1 à 100 questions (3, 4 ou 5 choix).
   * Import possible d'une liste d'élèves au format CSV.
   * Bouton d'impression directe ou sauvegarde en PDF.

4. **Statistiques cumulées de la promotion** :
   * Palmarès complet des étudiants (rang, note sur 20, pourcentage, statut admis/ajourné).
   * Analyse détaillée question par question (taux de réussite, répartition des réponses choisies, niveau de difficulté).
   * Métriques globales : moyenne générale, note minimale/maximale, médiane, écart-type, taux de réussite.

5. **Exports complets** :
   * **Rapport d'analyse PDF** détaillé avec copies annotées en vert/rouge.
   * **Export des notes au format CSV** (séparateur point-virgule `;`, encodage UTF-8 BOM) pour une ouverture directe sous Microsoft Excel, LibreOffice ou import dans Pronote/ENT.
   * **Export Excel natif XLS** avec mise en forme des notes et statuts.

---

## 🚀 Démarrage rapide

### Option 1 : Exécutable portable (sans installation de Python)
Téléchargez l'archive prête à l'emploi `Comparateur_QCM_Package_Test.zip` depuis les Releases, décompressez-la et lancez directement `Comparateur_QCM.exe`.

### Option 2 : Lancement avec Python (Windows)
Double-cliquez sur **`run.bat`** : il crée automatiquement l'environnement virtuel `.venv`, installe les dépendances et démarre l'application.

Ou manuellement en ligne de commande :
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## 📦 Structure du projet

```text
AMC/
├── main.py                  # Point d'entrée de l'application
├── run.bat                  # Lanceur Windows automatique
├── build_package.py         # Script de création du package autonome
├── requirements.txt         # Dépendances Python
├── app/
│   ├── gui.py               # Interface graphique Tkinter complète
│   ├── pdf_reader.py        # Conversion PDF/images & reconnaissance places/noms
│   ├── detector.py          # Détection des cases cochées (OpenCV)
│   ├── comparator.py        # Comparaison des réponses vs correction
│   ├── scorer.py            # Calcul des notes et pénalités
│   ├── analysis.py          # Statistiques cumulées de la promotion
│   ├── sheet_generator.py   # Générateur de fiches QCM et plans de placement
│   ├── generator_dialog.py  # Boîte de dialogue du générateur
│   ├── report_exporter.py   # Exportateur de rapports PDF (ReportLab)
│   └── csv_exporter.py      # Exportateur de notes CSV (;) et Excel XLS
└── test_pdfs/               # Jeux de données et tests
```

---

## ⚖️ Barème de notation

$$\text{Points} = \text{Bonnes} - (\text{Fausses} \times \text{Pénalité})$$
$$\text{Note} = \max\left(0, \frac{\text{Points}}{\text{Total}}\right) \times 20$$

Pénalités configurables au choix : Aucune, ¼, ⅓ ou ½ point par mauvaise réponse. Les réponses blanches ne pénalisent pas.
