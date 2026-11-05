"""
gui.py
Interface graphique Tkinter pour le Comparateur QCM PDF.
Prend en charge les fiches uniques et les fichiers multi-fiches (lot de copies),
avec navigation entre copies, vue cumulée de la promotion, et export PDF complet.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import math
from PIL import Image, ImageTk

from app.pdf_reader import pdf_to_images, extract_name, crop_name_zone, detect_seat_number
from app.detector import extract_answers, draw_debug
from app.comparator import compare
from app.scorer import calculate_score
from app.analysis import StudentSheet, BatchSummary, compute_batch_summary
from app.report_exporter import export_pdf_report
from app.csv_exporter import export_grades


# ──────────────────────────────────────────────────────────────────────────────
# Palette & constantes visuelles
# ──────────────────────────────────────────────────────────────────────────────

BG         = "#1a1d2e"       # fond principal
PANEL      = "#22253a"       # panneaux secondaires
ACCENT     = "#6c63ff"       # violet principal
ACCENT2    = "#a78bfa"       # violet clair
SUCCESS    = "#22c55e"       # vert correct
ERROR      = "#ef4444"       # rouge incorrect
WARN       = "#f59e0b"       # jaune non-répondu
TEXT       = "#e2e8f0"       # texte principal
SUBTEXT    = "#94a3b8"       # texte secondaire
BORDER     = "#2d3154"       # bordures

FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_HEAD   = ("Segoe UI", 11, "bold")
FONT_BODY   = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_GRADE  = ("Segoe UI", 34, "bold")
FONT_MONO   = ("Consolas", 10)


# ──────────────────────────────────────────────────────────────────────────────
# Classe principale
# ──────────────────────────────────────────────────────────────────────────────

class QCMApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Comparateur QCM PDF — Auto Multiple Choice")
        self.configure(bg=BG)
        self.minsize(1150, 750)
        self.geometry("1240x800")

        # Configuration de la base d'options Tk pour le thème sombre des Combobox (listes déroulantes)
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "white")
        self.option_add("*TCombobox*Listbox.font", FONT_BODY)

        # État interne
        self._student_path = tk.StringVar(value="")
        self._correc_path  = tk.StringVar(value="")
        self._plan_path    = tk.StringVar(value="")
        self._penalty      = tk.DoubleVar(value=0.25)

        self._sheets: list[StudentSheet] = []
        self._current_sheet_idx: int = 0
        self._batch_summary: BatchSummary | None = None
        self._c_debug: list[Image.Image] = []

        self._preview_imgs = []   # list[(PIL student, PIL correction)]
        self._page_index   = 0
        self._student_name = tk.StringVar(value="")
        self._name_thumb   = None
        self._view_mode    = tk.StringVar(value="single")  # "single" ou "cumul"

        self._build_ui()
        self._apply_styles()

    # ──────────────────────────────────────────────────────────────────────────
    # Construction de l'UI
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Barre supérieure ──────────────────────────────────────────────────
        top = tk.Frame(self, bg=PANEL, pady=10, padx=20)
        top.pack(fill="x", side="top")

        tk.Label(top, text="🎓", font=("Segoe UI Emoji", 22),
                 bg=PANEL, fg=ACCENT).pack(side="left")
        tk.Label(top, text="Comparateur QCM PDF",
                 font=FONT_TITLE, bg=PANEL, fg=TEXT).pack(side="left", padx=8)

        # ── Zone de sélection fichiers ────────────────────────────────────────
        file_bar = tk.Frame(self, bg=BG, pady=10, padx=20)
        file_bar.pack(fill="x")

        self._student_btn = self._file_picker(
            file_bar, "📄 QCM Étudiant(s)", self._student_path,
            self._pick_student, side="left", width=22
        )
        self._correc_btn = self._file_picker(
            file_bar, "📋 Correction", self._correc_path,
            self._pick_correction, side="left", padx=10, width=18
        )
        self._plan_btn = self._file_picker(
            file_bar, "👥 Plan / CSV (optionnel)", self._plan_path,
            self._pick_plan, side="left", padx=10, width=18
        )

        # Pénalité
        pen_frame = tk.Frame(file_bar, bg=BG)
        pen_frame.pack(side="left", padx=8)
        tk.Label(pen_frame, text="Pénalité /mauvaise réponse :",
                 font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack(anchor="w")
        pen_row = tk.Frame(pen_frame, bg=BG)
        pen_row.pack()
        for v, label in [(0.0, "Aucune"), (0.25, "¼"), (0.33, "⅓"), (0.5, "½")]:
            rb = tk.Radiobutton(pen_row, text=label, variable=self._penalty,
                                value=v, bg=BG, fg=TEXT, selectcolor=ACCENT,
                                activebackground=BG, activeforeground=ACCENT2,
                                font=FONT_SMALL, command=self._refresh_score)
            rb.pack(side="left", padx=3)

        # Bouton Générer fiche
        self._sheet_btn = tk.Button(
            file_bar, text="🖨️ Fiche de réponse",
            font=FONT_SMALL, bg=BORDER, fg=TEXT,
            relief="flat", padx=12, pady=6,
            activebackground=ACCENT2, activeforeground="white",
            cursor="hand2",
            command=self._open_generator
        )
        self._sheet_btn.pack(side="right", padx=(0, 6))

        # Bouton Analyser
        self._run_btn = tk.Button(
            file_bar, text="  ▶  Analyser",
            font=FONT_HEAD, bg=ACCENT, fg="white",
            relief="flat", padx=16, pady=6,
            activebackground=ACCENT2, cursor="hand2",
            command=self._run_analysis
        )
        self._run_btn.pack(side="right", padx=10)

        # ── Corps principal ───────────────────────────────────────────────────
        body = tk.PanedWindow(self, orient="horizontal",
                              bg=BG, sashwidth=6, sashrelief="flat")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Panneau gauche : prévisualisation
        left_panel = tk.Frame(body, bg=PANEL, bd=0)
        body.add(left_panel, minsize=420)
        self._build_preview(left_panel)

        # Panneau droit : résultats
        right_panel = tk.Frame(body, bg=PANEL, bd=0)
        body.add(right_panel, minsize=440)
        self._build_results(right_panel)

        # ── Barre de statut ───────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Chargez un QCM étudiant et sa correction pour commencer.")
        status_bar = tk.Label(self, textvariable=self._status_var,
                              font=FONT_SMALL, bg=BORDER, fg=SUBTEXT,
                              anchor="w", padx=12, pady=4)
        status_bar.pack(fill="x", side="bottom")

    def _file_picker(self, parent, label, var, cmd, side="left", padx=0, width=22):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(side=side, padx=padx)
        tk.Label(frame, text=label, font=FONT_SMALL,
                 bg=BG, fg=SUBTEXT).pack(anchor="w")
        row = tk.Frame(frame, bg=BG)
        row.pack()
        entry = tk.Entry(row, textvariable=var, width=width,
                         font=FONT_SMALL, bg=PANEL, fg=TEXT,
                         insertbackground=TEXT, relief="flat",
                         bd=0, highlightthickness=1,
                         highlightbackground=BORDER,
                         highlightcolor=ACCENT)
        entry.pack(side="left", ipady=5, padx=(0, 4))
        btn = tk.Button(row, text="Parcourir…", font=FONT_SMALL,
                        bg=BORDER, fg=TEXT, relief="flat", padx=8, pady=4,
                        activebackground=ACCENT, activeforeground="white",
                        cursor="hand2", command=cmd)
        btn.pack(side="left")
        return btn

    # ──────────────────────────────────────────────────────────────────────────
    # Panneau de gauche : Prévisualisation
    # ──────────────────────────────────────────────────────────────────────────

    def _build_preview(self, parent):
        tk.Label(parent, text="Prévisualisation", font=FONT_HEAD,
                 bg=PANEL, fg=ACCENT2, pady=8).pack(anchor="w", padx=12)

        # Onglets Étudiant / Correction
        self._tab_var = tk.StringVar(value="student")
        tab_bar = tk.Frame(parent, bg=PANEL)
        tab_bar.pack(fill="x", padx=12)
        for val, lbl in [("student", "Étudiant / Copie"), ("correction", "Correction")]:
            rb = tk.Radiobutton(tab_bar, text=lbl, variable=self._tab_var,
                                value=val, bg=PANEL, fg=TEXT,
                                selectcolor=ACCENT, font=FONT_SMALL,
                                activebackground=PANEL, activeforeground=ACCENT2,
                                indicatoron=False, relief="flat",
                                padx=12, pady=4, cursor="hand2",
                                command=self._show_preview)
            rb.pack(side="left", padx=2)

        # Canvas image
        canvas_frame = tk.Frame(parent, bg=BG, bd=0,
                                highlightthickness=1,
                                highlightbackground=BORDER)
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self._canvas = tk.Canvas(canvas_frame, bg=BG, bd=0,
                                 highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        # Navigation pages
        nav = tk.Frame(parent, bg=PANEL)
        nav.pack(pady=(0, 8))
        tk.Button(nav, text="◀ Page précédente", font=FONT_SMALL,
                  bg=BORDER, fg=TEXT, relief="flat", padx=8,
                  cursor="hand2",
                  command=lambda: self._change_page(-1)).pack(side="left", padx=4)
        self._page_lbl = tk.Label(nav, text="—", font=FONT_SMALL,
                                  bg=PANEL, fg=SUBTEXT)
        self._page_lbl.pack(side="left", padx=8)
        tk.Button(nav, text="Page suivante ▶", font=FONT_SMALL,
                  bg=BORDER, fg=TEXT, relief="flat", padx=8,
                  cursor="hand2",
                  command=lambda: self._change_page(1)).pack(side="left", padx=4)

    # ──────────────────────────────────────────────────────────────────────────
    # Panneau de droite : Résultats & Cumul
    # ──────────────────────────────────────────────────────────────────────────

    def _build_results(self, parent):
        # ── En-tête des résultats avec bascule de mode ────────────────────────
        hdr_bar = tk.Frame(parent, bg=PANEL, pady=6, padx=12)
        hdr_bar.pack(fill="x")

        tk.Label(hdr_bar, text="Résultats", font=FONT_HEAD,
                 bg=PANEL, fg=ACCENT2).pack(side="left")

        # Sélecteur de vue : Individuelle vs Cumul
        mode_frame = tk.Frame(hdr_bar, bg=PANEL)
        mode_frame.pack(side="right")

        self._btn_mode_single = tk.Radiobutton(
            mode_frame, text="👤 Copie individuelle",
            variable=self._view_mode, value="single",
            bg=PANEL, fg=TEXT, selectcolor=ACCENT,
            indicatoron=False, relief="flat",
            font=FONT_SMALL, padx=8, pady=3,
            cursor="hand2", command=self._on_view_mode_changed
        )
        self._btn_mode_single.pack(side="left", padx=2)

        self._btn_mode_cumul = tk.Radiobutton(
            mode_frame, text="📊 Cumul promotion",
            variable=self._view_mode, value="cumul",
            bg=PANEL, fg=TEXT, selectcolor=ACCENT,
            indicatoron=False, relief="flat",
            font=FONT_SMALL, padx=8, pady=3,
            cursor="hand2", command=self._on_view_mode_changed
        )
        self._btn_mode_cumul.pack(side="left", padx=2)

        # ── Barre de navigation entre les copies (visible si multi-fiches) ───
        self._sheet_nav_frame = tk.Frame(parent, bg=BORDER, pady=5, padx=8)
        # pack() dynamiquement quand > 1 copie

        tk.Button(self._sheet_nav_frame, text="◀ Copie précédente",
                  font=FONT_SMALL, bg=PANEL, fg=TEXT, relief="flat", padx=8,
                  cursor="hand2", command=self._prev_sheet).pack(side="left", padx=2)

        self._sheet_combo_var = tk.StringVar(value="")
        self._sheet_combo = ttk.Combobox(
            self._sheet_nav_frame, textvariable=self._sheet_combo_var,
            state="readonly", width=30, font=FONT_SMALL
        )
        self._sheet_combo.pack(side="left", padx=8, ipady=3)
        self._sheet_combo.bind("<<ComboboxSelected>>", self._on_sheet_combo_select)

        tk.Button(self._sheet_nav_frame, text="Copie suivante ▶",
                  font=FONT_SMALL, bg=PANEL, fg=TEXT, relief="flat", padx=8,
                  cursor="hand2", command=self._next_sheet).pack(side="left", padx=2)

        self._sheet_badge_lbl = tk.Label(self._sheet_nav_frame, text="1 copie",
                                         font=FONT_SMALL, bg=BORDER, fg=ACCENT2)
        self._sheet_badge_lbl.pack(side="right", padx=6)

        # ── Conteneur 1 : VUE INDIVIDUELLE ───────────────────────────────────
        self._single_frame = tk.Frame(parent, bg=PANEL)
        self._single_frame.pack(fill="both", expand=True)

        # Carte Nom de l'étudiant
        name_card = tk.Frame(self._single_frame, bg=BG, bd=0,
                             highlightthickness=1, highlightbackground=BORDER)
        name_card.pack(fill="x", padx=12, pady=(0, 6))

        name_inner = tk.Frame(name_card, bg=BG)
        name_inner.pack(fill="x", padx=10, pady=6)

        tk.Label(name_inner, text="👤 Nom :", font=FONT_SMALL,
                 bg=BG, fg=SUBTEXT).pack(side="left")
        self._name_entry = tk.Entry(
            name_inner, textvariable=self._student_name,
            font=("Segoe UI", 10, "bold"), bg=PANEL, fg=TEXT,
            insertbackground=TEXT, relief="flat", width=22,
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT
        )
        self._name_entry.pack(side="left", padx=(6, 8), ipady=4)
        self._name_entry.bind("<KeyRelease>", lambda e: self._on_name_edited())
        self._name_entry.bind("<FocusOut>", lambda e: self._on_name_edited())

        self._name_thumb_lbl = tk.Label(name_inner, bg=BG)
        self._name_thumb_lbl.pack(side="left")
        self._name_hint = tk.Label(name_inner,
                                   text="(chargez un QCM pour détecter le nom)",
                                   font=FONT_SMALL, bg=BG, fg=SUBTEXT)
        self._name_hint.pack(side="left")

        self._link_plan_btn = tk.Button(
            name_inner, text="👥 Associer CSV / Plan…",
            font=FONT_SMALL, bg=BORDER, fg=ACCENT2,
            relief="flat", padx=8, pady=2, cursor="hand2",
            command=self._on_link_plan_clicked
        )

        # Note principale
        grade_card = tk.Frame(self._single_frame, bg=BG, bd=0,
                              highlightthickness=1, highlightbackground=BORDER)
        grade_card.pack(fill="x", padx=12, pady=(0, 8))

        self._grade_lbl = tk.Label(grade_card, text="—",
                                   font=FONT_GRADE, bg=BG, fg=ACCENT)
        self._grade_lbl.pack(pady=(8, 0))
        self._grade_sub = tk.Label(grade_card, text="Analysez un QCM pour obtenir la note",
                                   font=FONT_SMALL, bg=BG, fg=SUBTEXT)
        self._grade_sub.pack(pady=(0, 6))

        stats_row = tk.Frame(grade_card, bg=BG)
        stats_row.pack(fill="x", padx=16, pady=(0, 10))
        self._stat_correct   = self._stat_badge(stats_row, "✓ Bonnes",  SUCCESS)
        self._stat_incorrect = self._stat_badge(stats_row, "✗ Fausses", ERROR)
        self._stat_blank     = self._stat_badge(stats_row, "— Blanches", WARN)

        # Tableau individuel par question
        tbl_frame = tk.Frame(self._single_frame, bg=PANEL)
        tbl_frame.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        cols = ("q", "student", "correct", "status")
        self._tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=10)
        self._tree.heading("q",       text="Q#")
        self._tree.heading("student", text="Réponse")
        self._tree.heading("correct", text="Attendu")
        self._tree.heading("status",  text="Résultat")
        self._tree.column("q",       width=45,  anchor="center")
        self._tree.column("student", width=85,  anchor="center")
        self._tree.column("correct", width=85,  anchor="center")
        self._tree.column("status",  width=115, anchor="center")

        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # ── Conteneur 2 : VUE CUMUL PROMOTION ────────────────────────────────
        self._cumul_frame = tk.Frame(parent, bg=PANEL)
        # pack() uniquement en mode "cumul"

        # Carte Synthèse globale
        cumul_card = tk.Frame(self._cumul_frame, bg=BG, bd=0,
                              highlightthickness=1, highlightbackground=BORDER)
        cumul_card.pack(fill="x", padx=12, pady=(0, 8))

        c_top = tk.Frame(cumul_card, bg=BG, padx=12, pady=8)
        c_top.pack(fill="x")

        # Métriques clés
        self._cumul_avg_lbl = tk.Label(c_top, text="—", font=("Segoe UI", 24, "bold"),
                                       bg=BG, fg=ACCENT)
        self._cumul_avg_lbl.pack(side="left", padx=8)

        c_top_sub = tk.Frame(c_top, bg=BG)
        c_top_sub.pack(side="left", padx=12)
        self._cumul_title_lbl = tk.Label(c_top_sub, text="Moyenne de la promotion",
                                         font=FONT_HEAD, bg=BG, fg=TEXT)
        self._cumul_title_lbl.pack(anchor="w")
        self._cumul_meta_lbl = tk.Label(c_top_sub, text="0 copies traitées",
                                        font=FONT_SMALL, bg=BG, fg=SUBTEXT)
        self._cumul_meta_lbl.pack(anchor="w")

        # Grille de stats secondaires
        c_grid = tk.Frame(cumul_card, bg=BG, padx=12, pady=4)
        c_grid.pack(fill="x", pady=(0, 6))
        self._c_stat_pass = self._cumul_badge(c_grid, "Taux réussite", "—", SUCCESS, 0, 0)
        self._c_stat_max  = self._cumul_badge(c_grid, "Note max", "—", ACCENT2, 0, 1)
        self._c_stat_min  = self._cumul_badge(c_grid, "Note min", "—", WARN, 0, 2)
        self._c_stat_med  = self._cumul_badge(c_grid, "Médiane", "—", TEXT, 1, 0)
        self._c_stat_std  = self._cumul_badge(c_grid, "Écart-type", "—", SUBTEXT, 1, 1)
        self._c_stat_corr = self._cumul_badge(c_grid, "Moy. Bonnes", "—", SUCCESS, 1, 2)

        # Onglets sous-jacents : Palmarès vs Analyse par question
        sub_nb = ttk.Notebook(self._cumul_frame)
        sub_nb.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        # Onglet 1 : Palmarès des copies
        tab_palmares = tk.Frame(sub_nb, bg=PANEL)
        sub_nb.add(tab_palmares, text="🏆 Palmarès des copies")

        cols_p = ("rank", "name", "grade", "pct", "correct", "incorrect", "blank", "status")
        self._batch_tree = ttk.Treeview(tab_palmares, columns=cols_p, show="headings", height=8)
        self._batch_tree.heading("rank",      text="Rang")
        self._batch_tree.heading("name",      text="Étudiant / Copie")
        self._batch_tree.heading("grade",     text="Note /20")
        self._batch_tree.heading("pct",       text="%")
        self._batch_tree.heading("correct",   text="✓")
        self._batch_tree.heading("incorrect", text="✗")
        self._batch_tree.heading("blank",     text="—")
        self._batch_tree.heading("status",    text="Statut")

        self._batch_tree.column("rank",      width=45,  anchor="center")
        self._batch_tree.column("name",      width=140, anchor="w")
        self._batch_tree.column("grade",     width=75,  anchor="center")
        self._batch_tree.column("pct",       width=65,  anchor="center")
        self._batch_tree.column("correct",   width=45,  anchor="center")
        self._batch_tree.column("incorrect", width=45,  anchor="center")
        self._batch_tree.column("blank",     width=45,  anchor="center")
        self._batch_tree.column("status",    width=80,  anchor="center")

        vsb_p = ttk.Scrollbar(tab_palmares, orient="vertical", command=self._batch_tree.yview)
        self._batch_tree.configure(yscrollcommand=vsb_p.set)
        self._batch_tree.pack(side="left", fill="both", expand=True)
        vsb_p.pack(side="right", fill="y")
        self._batch_tree.bind("<Double-1>", self._on_batch_tree_double_click)

        # Onglet 2 : Cumul par question
        tab_questions = tk.Frame(sub_nb, bg=PANEL)
        sub_nb.add(tab_questions, text="🔍 Analyse par question")

        cols_q = ("q", "correct", "rate", "num_c", "num_i", "num_b", "distrib", "diff")
        self._qstat_tree = ttk.Treeview(tab_questions, columns=cols_q, show="headings", height=8)
        self._qstat_tree.heading("q",       text="Q#")
        self._qstat_tree.heading("correct", text="Attendu")
        self._qstat_tree.heading("rate",    text="Taux Réussite")
        self._qstat_tree.heading("num_c",   text="Bonnes")
        self._qstat_tree.heading("num_i",   text="Fausses")
        self._qstat_tree.heading("num_b",   text="Blanches")
        self._qstat_tree.heading("distrib", text="Choix choisis")
        self._qstat_tree.heading("diff",    text="Difficulté")

        self._qstat_tree.column("q",       width=45,  anchor="center")
        self._qstat_tree.column("correct", width=65,  anchor="center")
        self._qstat_tree.column("rate",    width=90,  anchor="center")
        self._qstat_tree.column("num_c",   width=55,  anchor="center")
        self._qstat_tree.column("num_i",   width=55,  anchor="center")
        self._qstat_tree.column("num_b",   width=55,  anchor="center")
        self._qstat_tree.column("distrib", width=120, anchor="w")
        self._qstat_tree.column("diff",    width=75,  anchor="center")

        vsb_q = ttk.Scrollbar(tab_questions, orient="vertical", command=self._qstat_tree.yview)
        self._qstat_tree.configure(yscrollcommand=vsb_q.set)
        self._qstat_tree.pack(side="left", fill="both", expand=True)
        vsb_q.pack(side="right", fill="y")

        # ── Boutons d'export (PDF et CSV/Excel) ────────────────────────────────
        export_frame = tk.Frame(parent, bg=BG)
        export_frame.pack(pady=(0, 8))

        self._export_btn = tk.Button(
            export_frame, text="📊 Exporter le rapport (PDF)",
            font=FONT_SMALL, bg=BORDER, fg=TEXT, relief="flat",
            padx=12, pady=6, cursor="hand2",
            command=self._export_report, state="disabled"
        )
        self._export_btn.pack(side="left", padx=4)

        self._export_csv_btn = tk.Button(
            export_frame, text="📥 Exporter les notes (CSV / Excel)",
            font=FONT_SMALL, bg=BORDER, fg=TEXT, relief="flat",
            padx=12, pady=6, cursor="hand2",
            command=self._export_csv, state="disabled"
        )
        self._export_csv_btn.pack(side="left", padx=4)

    def _stat_badge(self, parent, label, color):
        f = tk.Frame(parent, bg=BG)
        f.pack(side="left", expand=True)
        num = tk.Label(f, text="—", font=("Segoe UI", 18, "bold"), bg=BG, fg=color)
        num.pack()
        tk.Label(f, text=label, font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack()
        return num

    def _cumul_badge(self, parent, label, val, color, row, col):
        f = tk.Frame(parent, bg=BG)
        f.grid(row=row, column=col, sticky="ew", padx=8, pady=2)
        parent.columnconfigure(col, weight=1)
        tk.Label(f, text=label + " :", font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack(side="left")
        lbl = tk.Label(f, text=val, font=("Segoe UI", 10, "bold"), bg=BG, fg=color)
        lbl.pack(side="left", padx=4)
        return lbl

    # ──────────────────────────────────────────────────────────────────────────
    # Styles ttk
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
                        background=BG, foreground=TEXT,
                        fieldbackground=BG, rowheight=24,
                        font=FONT_BODY, borderwidth=0)
        style.configure("Treeview.Heading",
                        background=BORDER, foreground=ACCENT2,
                        font=FONT_SMALL, relief="flat")
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])
        style.configure("Vertical.TScrollbar",
                        background=BORDER, troughcolor=PANEL,
                        borderwidth=0, arrowsize=12)
        style.configure("TNotebook", background=PANEL, borderwidth=0)
        style.configure("TNotebook.Tab", background=BORDER, foreground=TEXT,
                        font=FONT_SMALL, padding=[10, 4])
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])
        style.configure("TCombobox",
                        fieldbackground=PANEL,
                        background=BORDER,
                        foreground=TEXT,
                        darkcolor=BORDER,
                        lightcolor=BORDER,
                        bordercolor=BORDER,
                        arrowcolor=TEXT,
                        insertcolor=TEXT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", PANEL), ("disabled", BG), ("!disabled", PANEL)],
                  foreground=[("readonly", TEXT), ("disabled", SUBTEXT), ("!disabled", TEXT)],
                  selectbackground=[("readonly", ACCENT), ("!disabled", ACCENT)],
                  selectforeground=[("readonly", "white"), ("!disabled", "white")],
                  background=[("readonly", BORDER), ("!disabled", BORDER)])

    # ──────────────────────────────────────────────────────────────────────────
    # Réinitialisation de l'état
    # ──────────────────────────────────────────────────────────────────────────

    def _reset_results(self):
        """Réinitialise intégralement l'état et l'affichage des résultats."""
        self._sheets = []
        self._current_sheet_idx = 0
        self._batch_summary = None
        self._c_debug = []
        self._preview_imgs = []
        self._page_index = 0

        # Réinitialisation de l'affichage du nom
        self._student_name.set("")
        self._name_thumb = None
        self._name_thumb_lbl.config(image="")
        self._name_hint.config(text="(cliquez sur Analyser pour lancer le traitement)", fg=SUBTEXT)
        self._link_plan_btn.pack_forget()

        # Réinitialisation de la note individuelle
        self._grade_lbl.config(text="—", fg=ACCENT)
        self._grade_sub.config(text="Analysez un QCM pour obtenir la note", fg=SUBTEXT)
        self._stat_correct.config(text="—")
        self._stat_incorrect.config(text="—")
        self._stat_blank.config(text="—")

        # Vidage des tableaux
        for item in self._tree.get_children():
            self._tree.delete(item)
        for item in self._batch_tree.get_children():
            self._batch_tree.delete(item)
        for item in self._qstat_tree.get_children():
            self._qstat_tree.delete(item)

        # Réinitialisation des métriques de cumul
        self._cumul_avg_lbl.config(text="—")
        self._cumul_meta_lbl.config(text="0 copies traitées")
        self._c_stat_pass.config(text="—")
        self._c_stat_max.config(text="—")
        self._c_stat_min.config(text="—")
        self._c_stat_med.config(text="—")
        self._c_stat_std.config(text="—")
        self._c_stat_corr.config(text="—")

        # Masquer la barre de navigation multi-copies
        self._sheet_nav_frame.pack_forget()
        self._sheet_combo["values"] = []
        self._sheet_combo_var.set("")
        self._sheet_badge_lbl.config(text="1 copie")

        # Désactiver les boutons d'export
        self._export_btn.config(state="disabled", text="📊 Exporter le rapport (PDF)")
        self._export_csv_btn.config(state="disabled", text="📥 Exporter les notes (CSV / Excel)")

        # Réinitialiser la vue et la prévisualisation
        self._view_mode.set("single")
        self._btn_mode_single.select()
        self._single_frame.pack(fill="both", expand=True)
        self._cumul_frame.pack_forget()
        self._canvas.delete("all")
        self._page_lbl.config(text="—")

    # ──────────────────────────────────────────────────────────────────────────
    # Sélection des fichiers
    # ──────────────────────────────────────────────────────────────────────────

    def _pick_student(self):
        path = filedialog.askopenfilename(
            title="Sélectionner le QCM étudiant (1 ou plusieurs copies)",
            filetypes=[("PDF", "*.pdf"), ("Tous", "*.*")]
        )
        if path:
            self._student_path.set(path)
            # Réinitialisation systématique du plan précédent et des résultats
            self._plan_path.set("")
            self._reset_results()
            self._status_var.set(f"Fichier chargé : {os.path.basename(path)} — Prêt pour l'analyse.")

            # Auto-détection uniquement si un plan avec nom correspondant au PDF existe
            try:
                from app.pdf_reader import find_candidate_plans
                pdf_base = os.path.splitext(os.path.basename(path))[0].lower()
                plans = find_candidate_plans(path)
                for p in plans:
                    p_base = os.path.splitext(os.path.basename(p))[0].lower()
                    if pdf_base in p_base or p_base.replace("_plan_placement", "") in pdf_base:
                        self._plan_path.set(p)
                        break
            except Exception:
                pass

    def _pick_correction(self):
        path = filedialog.askopenfilename(
            title="Sélectionner la correction (modèle)",
            filetypes=[("PDF", "*.pdf"), ("Tous", "*.*")]
        )
        if path:
            self._correc_path.set(path)
            if self._sheets:
                self._reset_results()
                self._status_var.set(f"Correction chargée : {os.path.basename(path)} — Prêt pour l'analyse.")

    def _pick_plan(self):
        path = filedialog.askopenfilename(
            title="Sélectionner le plan de placement (.txt) ou groupe (.csv)",
            filetypes=[
                ("Plan de placement ou CSV", "*.txt;*.csv"),
                ("Plan de placement (.txt)", "*.txt"),
                ("Groupe d'élèves (.csv)", "*.csv"),
                ("Tous les fichiers", "*.*")
            ]
        )
        if path:
            self._plan_path.set(path)

    # ──────────────────────────────────────────────────────────────────────────
    # Analyse principale (thread)
    # ──────────────────────────────────────────────────────────────────────────

    def _run_analysis(self):
        sp = self._student_path.get()
        cp = self._correc_path.get()
        if not sp or not os.path.isfile(sp):
            messagebox.showerror("Fichier manquant",
                                 "Veuillez sélectionner le QCM étudiant (PDF).")
            return
        if not cp or not os.path.isfile(cp):
            messagebox.showerror("Fichier manquant",
                                 "Veuillez sélectionner la correction (PDF).")
            return

        self._run_btn.config(state="disabled", text="  ⏳  Analyse en cours…")
        self._export_btn.config(state="disabled")
        self._export_csv_btn.config(state="disabled")
        self._reset_results()
        self._status_var.set("Analyse en cours — chargement des PDFs…")
        threading.Thread(target=self._analysis_thread,
                         args=(sp, cp), daemon=True).start()

    def _analysis_thread(self, student_path, correc_path):
        try:
            self._status_var.set("Conversion PDF → images…")
            s_imgs = pdf_to_images(student_path, dpi=200)
            c_imgs = pdf_to_images(correc_path,  dpi=200)

            if not s_imgs:
                raise ValueError("Le fichier étudiant ne contient aucune page lisible.")
            if not c_imgs:
                raise ValueError("Le fichier correction ne contient aucune page lisible.")

            self._status_var.set("Détection des cases (correction)…")
            c_results = extract_answers(c_imgs)
            c_debug = [draw_debug(img, c_results) for img in c_imgs]

            # Chargement du plan de placement ou CSV si spécifié ou auto-détecté
            seat_map: dict[int, str] = {}
            group_students: list[str] = []
            plan_file = self._plan_path.get().strip()

            if plan_file and os.path.isfile(plan_file):
                if plan_file.lower().endswith(".txt"):
                    from app.sheet_generator import parse_placement_plan
                    seat_map = parse_placement_plan(plan_file)
                elif plan_file.lower().endswith(".csv"):
                    from app.sheet_generator import parse_students_csv
                    _, group_students = parse_students_csv(plan_file)
            else:
                # Recherche et sélection intelligente parmi tous les plans du projet
                from app.pdf_reader import find_best_matching_plan
                seat_map, detected_plan = find_best_matching_plan(student_path, s_imgs)
                if detected_plan:
                    self._plan_path.set(detected_plan)

            # Détermination du nombre de pages par fiche (basé sur la correction)
            pages_per_sheet = max(1, len(c_imgs))
            total_s_pages = len(s_imgs)
            num_sheets = max(1, math.ceil(total_s_pages / pages_per_sheet))

            sheets: list[StudentSheet] = []

            for i in range(num_sheets):
                p_start = i * pages_per_sheet
                p_end = min((i + 1) * pages_per_sheet, total_s_pages)
                sub_imgs = s_imgs[p_start : p_end]
                if not sub_imgs:
                    continue

                self._status_var.set(f"Analyse copie {i + 1} / {num_sheets}…")
                first_img = sub_imgs[0]
                detected_seat = detect_seat_number(first_img)
                candidates_list = group_students if group_students else list(seat_map.values())
                detected_name = extract_name(
                    student_path, page_num=p_start,
                    pil_image=first_img,
                    seat_map=seat_map,
                    candidates=candidates_list
                )
                # Repli sur l'ordre de la liste CSV si aucun numéro/texte trouvé
                if not detected_name and group_students and i < len(group_students):
                    detected_name = group_students[i]

                if detected_seat is None and seat_map and detected_name:
                    inv_map = {v: k for k, v in seat_map.items()}
                    detected_seat = inv_map.get(detected_name)

                name_crop = crop_name_zone(first_img, dpi=200)
                display_name = detected_name if detected_name else f"Copie {i + 1}"

                s_results = extract_answers(sub_imgs)
                s_debug = [draw_debug(img, s_results) for img in sub_imgs]

                comp = compare(s_results, c_results)
                score_data = calculate_score(comp, penalty=self._penalty.get())

                sheets.append(StudentSheet(
                    index=i,
                    name=display_name,
                    name_detected=bool(detected_name and not detected_name.startswith("Place N°")),
                    name_crop=name_crop,
                    seat_number=detected_seat,
                    images=sub_imgs,
                    debug_images=s_debug,
                    results=s_results,
                    comparison=comp,
                    score=score_data
                ))

            self._status_var.set("Calcul du cumul et des statistiques…")
            batch_summary = compute_batch_summary(sheets)

            # Mise à jour UI dans le thread principal
            self.after(0, self._update_ui_batch, sheets, c_debug, batch_summary)

        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _update_ui_batch(self, sheets: list[StudentSheet], c_debug: list[Image.Image], batch_summary: BatchSummary):
        self._sheets = sheets
        self._c_debug = c_debug
        self._batch_summary = batch_summary
        self._current_sheet_idx = 0

        num = len(sheets)
        if num > 1:
            self._sheet_nav_frame.pack(fill="x", padx=12, pady=(0, 6), before=self._single_frame)
            self._refresh_sheet_combo_list()
            self._sheet_badge_lbl.config(text=f"{num} copies détectées")
            self._export_btn.config(text="📊 Exporter le rapport cumulé (PDF)")
            self._status_var.set(
                f"Analyse terminée — {num} copies traitées. "
                f"Moyenne : {batch_summary.average_grade}/20 (Taux réussite : {batch_summary.pass_rate} %)"
            )
        else:
            self._sheet_nav_frame.pack_forget()
            self._export_btn.config(text="📊 Exporter le rapport (PDF)")
            sc = sheets[0].score if sheets else {}
            self._status_var.set(f"Analyse terminée — 1 copie traitée ({sc.get('total', 0)} questions).")

        self._run_btn.config(state="normal", text="  ▶  Analyser")
        self._export_btn.config(state="normal")
        self._export_csv_btn.config(state="normal")

        # Afficher la première copie
        self._select_sheet(0)
        self._update_cumul_display()

    def _on_error(self, msg):
        self._run_btn.config(state="normal", text="  ▶  Analyser")
        self._status_var.set("Erreur lors de l'analyse.")
        messagebox.showerror("Erreur d'analyse", msg)

    # ──────────────────────────────────────────────────────────────────────────
    # Navigation entre les copies
    # ──────────────────────────────────────────────────────────────────────────

    def _refresh_sheet_combo_list(self):
        vals = [
            f"Copie {s.index + 1}{f' (Place {s.seat_number})' if s.seat_number is not None else ''} : {s.name}"
            for s in self._sheets
        ]
        self._sheet_combo["values"] = vals
        if 0 <= self._current_sheet_idx < len(vals):
            self._sheet_combo.current(self._current_sheet_idx)

    def _select_sheet(self, idx: int):
        if not self._sheets or idx < 0 or idx >= len(self._sheets):
            return
        self._current_sheet_idx = idx
        sheet = self._sheets[idx]

        self._refresh_sheet_combo_list()

        # Nom
        self._student_name.set(sheet.name)
        seat_prefix = f"Place {sheet.seat_number} — " if sheet.seat_number is not None else ""
        if sheet.name_detected:
            self._name_hint.config(text=f"✓ {seat_prefix}Nom détecté", fg=SUCCESS)
            self._link_plan_btn.pack_forget()
        elif sheet.name.startswith("Place N°"):
            self._name_hint.config(text=f"✓ Place détectée ({sheet.name})", fg=ACCENT2)
            self._link_plan_btn.pack(side="left", padx=8)
        else:
            self._name_hint.config(text=f"{seat_prefix}PDF scanné — vérifiez ou associez le groupe :", fg=SUBTEXT)
            self._link_plan_btn.pack(side="left", padx=8)

        if sheet.name_crop is not None:
            thumb = sheet.name_crop.copy()
            thumb.thumbnail((220, 36), Image.LANCZOS)
            photo = ImageTk.PhotoImage(thumb)
            self._name_thumb = photo
            self._name_thumb_lbl.config(image=photo)
        else:
            self._name_thumb_lbl.config(image="")

        # Prévisualisation
        # Associer les images de la copie et de la correction
        c_count = len(self._c_debug)
        s_count = len(sheet.debug_images)
        pairs = []
        max_p = max(s_count, c_count)
        for p in range(max_p):
            s_im = sheet.debug_images[p] if p < s_count else sheet.debug_images[-1]
            c_im = self._c_debug[p] if p < c_count else self._c_debug[-1]
            pairs.append((s_im, c_im))

        self._preview_imgs = pairs
        self._page_index = 0
        self._show_preview()

        # Résultats individuels
        self._update_individual_results(sheet)

    def _on_link_plan_clicked(self):
        path = filedialog.askopenfilename(
            title="Sélectionner le fichier CSV du groupe ou le plan de placement (.txt)",
            filetypes=[
                ("Plan de placement ou CSV", "*.txt;*.csv"),
                ("Groupe d'élèves (.csv)", "*.csv"),
                ("Plan de placement (.txt)", "*.txt"),
                ("Tous les fichiers", "*.*")
            ]
        )
        if path:
            self._apply_plan_to_sheets(path)

    def _apply_plan_to_sheets(self, path: str):
        """Applique un plan de placement ou CSV à l'ensemble des copies chargées."""
        if not path or not os.path.isfile(path) or not self._sheets:
            return
        self._plan_path.set(path)

        seat_map = {}
        group_students = []
        if path.lower().endswith(".txt"):
            from app.sheet_generator import parse_placement_plan
            seat_map = parse_placement_plan(path)
        elif path.lower().endswith(".csv"):
            from app.sheet_generator import parse_students_csv
            _, group_students = parse_students_csv(path)

        from app.pdf_reader import match_printed_name, detect_seat_number

        candidates = group_students if group_students else list(seat_map.values())

        for sheet in self._sheets:
            first_img = sheet.images[0] if sheet.images else None
            new_name = None
            if first_img:
                seat = detect_seat_number(first_img)
                if seat is not None:
                    sheet.seat_number = seat
                if seat is not None and seat in seat_map:
                    new_name = seat_map[seat]
                elif candidates:
                    m_name, sc = match_printed_name(first_img, candidates)
                    if m_name and sc >= 0.28:
                        new_name = m_name
                    elif group_students and sheet.index < len(group_students):
                        new_name = group_students[sheet.index]
                elif seat is not None:
                    new_name = f"Place N° {seat}"

            if new_name:
                sheet.name = new_name
                sheet.name_detected = not new_name.startswith("Place N°")
            if sheet.seat_number is None and seat_map and sheet.name in {v: k for k, v in seat_map.items()}:
                sheet.seat_number = {v: k for k, v in seat_map.items()}[sheet.name]

        self._refresh_sheet_combo_list()
        self._select_sheet(self._current_sheet_idx)
        self._status_var.set(f"Plan associé : {os.path.basename(path)} — Noms des élèves actualisés.")

    def _prev_sheet(self):
        if not self._sheets:
            return
        idx = (self._current_sheet_idx - 1) % len(self._sheets)
        self._select_sheet(idx)

    def _next_sheet(self):
        if not self._sheets:
            return
        idx = (self._current_sheet_idx + 1) % len(self._sheets)
        self._select_sheet(idx)

    def _on_sheet_combo_select(self, event=None):
        idx = self._sheet_combo.current()
        if idx >= 0:
            self._select_sheet(idx)

    def _on_name_edited(self):
        """Met à jour le nom de la copie active lors de la frappe."""
        if not self._sheets or not (0 <= self._current_sheet_idx < len(self._sheets)):
            return
        new_name = self._student_name.get().strip() or f"Copie {self._current_sheet_idx + 1}"
        self._sheets[self._current_sheet_idx].name = new_name
        self._refresh_sheet_combo_list()
        self._update_cumul_display()

    # ──────────────────────────────────────────────────────────────────────────
    # Bascule de mode : Copie individuelle vs Cumul promotion
    # ──────────────────────────────────────────────────────────────────────────

    def _on_view_mode_changed(self):
        mode = self._view_mode.get()
        if mode == "cumul":
            self._single_frame.pack_forget()
            self._cumul_frame.pack(fill="both", expand=True)
            self._update_cumul_display()
        else:
            self._cumul_frame.pack_forget()
            self._single_frame.pack(fill="both", expand=True)
            if self._sheets:
                self._select_sheet(self._current_sheet_idx)

    def _on_batch_tree_double_click(self, event=None):
        """Double-clic sur un étudiant dans le palmarès -> ouvre sa copie."""
        sel = self._batch_tree.selection()
        if not sel:
            return
        item = self._batch_tree.item(sel[0])
        vals = item.get("values", [])
        if vals:
            try:
                rank = int(vals[0]) - 1
                # Trouver la copie correspondante par son nom
                name = vals[1]
                for idx, s in enumerate(self._sheets):
                    if s.name == name:
                        self._view_mode.set("single")
                        self._on_view_mode_changed()
                        self._select_sheet(idx)
                        break
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────────────
    # Prévisualisation
    # ──────────────────────────────────────────────────────────────────────────

    def _show_preview(self):
        if not self._preview_imgs:
            return
        idx = self._page_index
        s_img, c_img = self._preview_imgs[idx]
        img = s_img.copy() if self._tab_var.get() == "student" else c_img.copy()

        cw = max(self._canvas.winfo_width(), 360)
        ch = max(self._canvas.winfo_height(), 420)
        img.thumbnail((cw, ch), Image.LANCZOS)

        photo = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, anchor="center", image=photo)
        self._canvas.image = photo

        total = len(self._preview_imgs)
        self._page_lbl.config(text=f"Page {idx + 1} / {total}")

    def _change_page(self, delta):
        if not self._preview_imgs:
            return
        n = len(self._preview_imgs)
        self._page_index = (self._page_index + delta) % n
        self._show_preview()

    # ──────────────────────────────────────────────────────────────────────────
    # Affichage des résultats individuels
    # ──────────────────────────────────────────────────────────────────────────

    def _update_individual_results(self, sheet: StudentSheet):
        score_data = sheet.score
        grade = score_data.get("grade", 0.0)
        mx    = score_data.get("max_grade", 20.0)
        self._grade_lbl.config(text=f"{grade} / {mx}")
        pct = score_data.get("percent", 0.0)
        color = SUCCESS if pct >= 50 else (WARN if pct >= 30 else ERROR)
        self._grade_lbl.config(fg=color)
        self._grade_sub.config(
            text=f"{pct} %   •   pénalité {score_data.get('penalty', 0.25)} pt / mauvaise réponse"
        )

        self._stat_correct.config(text=str(score_data.get("correct", 0)))
        self._stat_incorrect.config(text=str(score_data.get("incorrect", 0)))
        self._stat_blank.config(text=str(score_data.get("blank", 0)))

        for row in self._tree.get_children():
            self._tree.delete(row)

        icons   = {"correct": "✓", "incorrect": "✗", "blank": "—"}
        tag_map = {"correct": "ok", "incorrect": "ko", "blank": "na"}

        self._tree.tag_configure("ok", foreground=SUCCESS)
        self._tree.tag_configure("ko", foreground=ERROR)
        self._tree.tag_configure("na", foreground=WARN)

        for row in sheet.comparison:
            tag = tag_map.get(row.status, "na")
            status_text = icons.get(row.status, " ") + " " + row.status.capitalize()
            if getattr(row, "is_multiple", False):
                status_text = "✗ Multiple (Invalide)"
            self._tree.insert("", "end", values=(
                f"Q{row.question:02d}",
                row.student_answer or "—",
                row.correct_answer or "—",
                status_text
            ), tags=(tag,))

    # ──────────────────────────────────────────────────────────────────────────
    # Affichage du cumul de la promotion
    # ──────────────────────────────────────────────────────────────────────────

    def _update_cumul_display(self):
        if not self._sheets:
            return
        self._batch_summary = compute_batch_summary(self._sheets)
        bs = self._batch_summary

        # Cartouche de note
        self._cumul_avg_lbl.config(text=f"{bs.average_grade} / 20")
        color = SUCCESS if bs.average_grade >= 10.0 else (WARN if bs.average_grade >= 8.0 else ERROR)
        self._cumul_avg_lbl.config(fg=color)
        self._cumul_meta_lbl.config(
            text=f"{bs.num_students} copie{'s' if bs.num_students > 1 else ''}  •  "
                 f"{bs.total_questions} questions  •  Pénalité {bs.penalty} pt"
        )

        # Badges
        self._c_stat_pass.config(text=f"{bs.pass_rate} % ({bs.pass_count}/{bs.num_students})")
        self._c_stat_max.config(text=f"{bs.max_grade} / 20")
        self._c_stat_min.config(text=f"{bs.min_grade} / 20")
        self._c_stat_med.config(text=f"{bs.median_grade} / 20")
        self._c_stat_std.config(text=f"{bs.std_dev_grade}")
        self._c_stat_corr.config(text=f"{bs.avg_correct}")

        # Remplir le tableau du Palmarès
        for row in self._batch_tree.get_children():
            self._batch_tree.delete(row)

        sorted_s = sorted(self._sheets, key=lambda s: s.score.get("grade", 0.0), reverse=True)
        self._batch_tree.tag_configure("admis", foreground=SUCCESS)
        self._batch_tree.tag_configure("ajourne", foreground=ERROR)

        for rank, s in enumerate(sorted_s, start=1):
            sc = s.score
            is_pass = sc.get("grade", 0.0) >= 10.0
            tag = "admis" if is_pass else "ajourne"
            self._batch_tree.insert("", "end", values=(
                f"{rank}",
                s.name,
                f"{sc.get('grade', 0.0):.2f}",
                f"{sc.get('percent', 0.0):.1f}%",
                sc.get("correct", 0),
                sc.get("incorrect", 0),
                sc.get("blank", 0),
                "✓ Admis" if is_pass else "✗ Ajourné"
            ), tags=(tag,))

        # Remplir le tableau d'analyse par question
        for row in self._qstat_tree.get_children():
            self._qstat_tree.delete(row)

        self._qstat_tree.tag_configure("facile", foreground=SUCCESS)
        self._qstat_tree.tag_configure("moyen", foreground=WARN)
        self._qstat_tree.tag_configure("difficile", foreground=ERROR)

        for qs in bs.question_stats:
            dist = ", ".join(f"{k}:{v}" for k, v in sorted(qs.choice_distribution.items())) or "—"
            tag = qs.difficulty.lower()
            self._qstat_tree.insert("", "end", values=(
                f"Q{qs.question:02d}",
                qs.correct_answer or "—",
                f"{qs.success_rate:.1f} %",
                qs.num_correct,
                qs.num_incorrect,
                qs.num_blank,
                dist,
                qs.difficulty
            ), tags=(tag,))

    def _refresh_score(self):
        """Recalcule les notes si l'utilisateur change la pénalité."""
        if not self._sheets:
            return
        pen = self._penalty.get()
        for s in self._sheets:
            s.score = calculate_score(s.comparison, penalty=pen)
        self._batch_summary = compute_batch_summary(self._sheets)
        if 0 <= self._current_sheet_idx < len(self._sheets):
            self._update_individual_results(self._sheets[self._current_sheet_idx])
        self._update_cumul_display()

    # ──────────────────────────────────────────────────────────────────────────
    # Export rapport PDF
    # ──────────────────────────────────────────────────────────────────────────

    def _export_report(self):
        if not self._sheets:
            return
        is_multi = len(self._sheets) > 1
        default_name = "Rapport_Cumule_QCM.pdf" if is_multi else f"Rapport_{self._sheets[0].name.replace(' ', '_')}.pdf"

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=default_name,
            title="Enregistrer le rapport d'analyse"
        )
        if not path:
            return
        try:
            export_pdf_report(path, self._sheets, self._batch_summary)
            self._status_var.set(f"Rapport exporté : {path}")
            messagebox.showinfo("Export réussi", f"Rapport enregistré avec succès :\n{path}")
        except Exception as e:
            messagebox.showerror("Erreur d'export", str(e))

    def _export_csv(self):
        """Exporte les notes des étudiants au format CSV ou Excel."""
        if not self._sheets:
            return
        is_multi = len(self._sheets) > 1
        default_name = "Notes_QCM_Cumul.csv" if is_multi else f"Notes_{self._sheets[0].name.replace(' ', '_')}.csv"

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("Fichier CSV Excel (*.csv)", "*.csv"),
                ("Classeur Excel 97-2003 (*.xls)", "*.xls"),
                ("Tous les fichiers", "*.*")
            ],
            initialfile=default_name,
            title="Enregistrer les notes des étudiants (CSV / Excel)"
        )
        if not path:
            return
        try:
            export_grades(path, self._sheets, self._batch_summary)
            self._status_var.set(f"Notes exportées : {path}")
            messagebox.showinfo("Export réussi", f"Notes enregistrées avec succès :\n{path}")
        except Exception as e:
            messagebox.showerror("Erreur d'export", str(e))

    def _open_generator(self):
        """Ouvre le dialogue de génération de fiche de réponses."""
        from app.generator_dialog import GeneratorDialog
        GeneratorDialog(self)


# ──────────────────────────────────────────────────────────────────────────────
# Rétro-compatibilité
# ──────────────────────────────────────────────────────────────────────────────

def _export_pdf(path, comparison, score_data, student_name=None):
    """Alias rétro-compatible pour l'export d'un rapport individuel."""
    from app.report_exporter import export_single_report
    export_single_report(path, comparison, score_data, student_name=student_name)

