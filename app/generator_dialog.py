"""
generator_dialog.py
Dialogue Tkinter pour paramétrer et générer une fiche de réponses PDF.
Prend en charge :
  - La génération d'une fiche vierge standard.
  - Le chargement d'un fichier CSV de groupe (ex: Terminale_S1.csv)
    pour générer un lot complet de fiches nominatives personnalisées.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from PIL import Image, ImageTk

# Couleurs (reprises de gui.py)
BG      = "#1a1d2e"
PANEL   = "#22253a"
ACCENT  = "#6c63ff"
ACCENT2 = "#a78bfa"
TEXT    = "#e2e8f0"
SUBTEXT = "#94a3b8"
BORDER  = "#2d3154"
SUCCESS = "#22c55e"
ERROR   = "#ef4444"

FONT_HEAD  = ("Segoe UI", 11, "bold")
FONT_BODY  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI", 14, "bold")


class GeneratorDialog(tk.Toplevel):
    """
    Fenêtre modale de génération de fiche(s) de réponses.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Générateur de fiche de réponses")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()   # modal

        self._last_path = tk.StringVar(value="")
        self._csv_path = tk.StringVar(value="")
        self._group_name = tk.StringVar(value="")
        self._students: list[str] = []

        self._build_ui()
        self._center(parent)
        self._update_preview()

    # ──────────────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Titre
        hdr = tk.Frame(self, bg=PANEL, pady=12, padx=20)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🖨️", font=("Segoe UI Emoji", 20),
                 bg=PANEL, fg=ACCENT).pack(side="left")
        tk.Label(hdr, text="  Générer une fiche de réponses",
                 font=FONT_TITLE, bg=PANEL, fg=TEXT).pack(side="left")

        body = tk.Frame(self, bg=BG, padx=24, pady=16)
        body.pack(fill="both")

        # ── Titre du QCM ─────────────────────────────────────────────────────
        self._add_label(body, "Titre du QCM :", row=0)
        self._title_var = tk.StringVar(value="QCM")
        tk.Entry(body, textvariable=self._title_var,
                 font=FONT_BODY, bg=PANEL, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT, width=32
                 ).grid(row=0, column=1, columnspan=2,
                        sticky="ew", padx=(8, 0), pady=4, ipady=5)

        # ── Nombre de questions ───────────────────────────────────────────────
        self._add_label(body, "Nombre de questions :", row=1)
        self._nq_var = tk.IntVar(value=20)
        sb_q = tk.Spinbox(body, from_=1, to=100,
                          textvariable=self._nq_var, width=6,
                          font=FONT_BODY, bg=PANEL, fg=TEXT,
                          buttonbackground=BORDER,
                          insertbackground=TEXT, relief="flat",
                          highlightthickness=1,
                          highlightbackground=BORDER,
                          highlightcolor=ACCENT,
                          command=self._update_preview)
        sb_q.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=4, ipady=4)
        sb_q.bind("<KeyRelease>", lambda e: self._update_preview())

        # ── Nombre de choix ───────────────────────────────────────────────────
        self._add_label(body, "Choix par question :", row=2)
        self._nc_var = tk.IntVar(value=4)
        choice_frame = tk.Frame(body, bg=BG)
        choice_frame.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)
        for v, lbl in [(3, "3 — A/B/C"),
                       (4, "4 — A/B/C/D"),
                       (5, "5 — A/B/C/D/E")]:
            tk.Radiobutton(choice_frame, text=lbl,
                           variable=self._nc_var, value=v,
                           bg=BG, fg=TEXT, selectcolor=ACCENT,
                           activebackground=BG, activeforeground=ACCENT2,
                           font=FONT_SMALL,
                           command=self._update_preview
                           ).pack(side="left", padx=6)

        # ── Fichier CSV du groupe d'étudiants ─────────────────────────────────
        self._add_label(body, "Groupe d'élèves (CSV) :", row=3)
        csv_frame = tk.Frame(body, bg=BG)
        csv_frame.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)

        self._csv_btn = tk.Button(
            csv_frame, text="📁 Charger fichier CSV…",
            font=FONT_SMALL, bg=BORDER, fg=TEXT,
            relief="flat", padx=10, pady=4,
            cursor="hand2", command=self._pick_csv
        )
        self._csv_btn.pack(side="left")

        self._clear_csv_btn = tk.Button(
            csv_frame, text="✖",
            font=FONT_SMALL, bg=BORDER, fg=SUBTEXT,
            relief="flat", padx=6, pady=4,
            cursor="hand2", command=self._clear_csv,
            state="disabled"
        )
        self._clear_csv_btn.pack(side="left", padx=4)

        self._csv_info_lbl = tk.Label(
            csv_frame, text="Aucun (fiche vierge standard)",
            font=FONT_SMALL, bg=BG, fg=SUBTEXT
        )
        self._csv_info_lbl.pack(side="left", padx=6)

        # ── Prévisualisation ──────────────────────────────────────────────────
        prev_frame = tk.Frame(body, bg=PANEL, bd=0,
                              highlightthickness=1,
                              highlightbackground=BORDER)
        prev_frame.grid(row=4, column=0, columnspan=3,
                        sticky="ew", pady=(10, 4))
        self._preview_lbl = tk.Label(prev_frame, text="",
                                     font=FONT_SMALL, bg=PANEL, fg=SUBTEXT,
                                     pady=10, padx=16, justify="left",
                                     anchor="w")
        self._preview_lbl.pack(fill="x")

        # ── Boutons ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(body, bg=BG)
        btn_row.grid(row=5, column=0, columnspan=3,
                     sticky="ew", pady=(8, 0))

        tk.Button(btn_row, text="Fermer",
                  font=FONT_SMALL, bg=BORDER, fg=TEXT,
                  relief="flat", padx=14, pady=6,
                  cursor="hand2", command=self.destroy
                  ).pack(side="right", padx=(4, 0))

        self._print_btn = tk.Button(
            btn_row, text="🖨️  Imprimer",
            font=FONT_SMALL, bg=BORDER, fg=SUBTEXT,
            relief="flat", padx=14, pady=6,
            cursor="hand2", command=self._print_sheet,
            state="disabled"
        )
        self._print_btn.pack(side="right", padx=(4, 0))

        self._gen_btn = tk.Button(
            btn_row, text="  💾  Générer et enregistrer",
            font=FONT_HEAD, bg=ACCENT, fg="white",
            relief="flat", padx=16, pady=6,
            activebackground=ACCENT2, cursor="hand2",
            command=self._generate
        )
        self._gen_btn.pack(side="right")

        # ── Fichier généré ─────────────────────────────────────────────────────
        self._result_lbl = tk.Label(body, text="",
                                    font=FONT_SMALL, bg=BG, fg=SUCCESS,
                                    wraplength=460, justify="left")
        self._result_lbl.grid(row=6, column=0, columnspan=3,
                               sticky="w", pady=(6, 0))

        body.columnconfigure(1, weight=1)

    def _add_label(self, parent, text: str, row: int):
        tk.Label(parent, text=text, font=FONT_SMALL,
                 bg=BG, fg=SUBTEXT, anchor="e"
                 ).grid(row=row, column=0, sticky="e", pady=4)

    # ──────────────────────────────────────────────────────────────────────────
    # Logique CSV
    # ──────────────────────────────────────────────────────────────────────────

    def _pick_csv(self):
        """Ouvre un dialogue pour charger le fichier CSV du groupe."""
        path = filedialog.askopenfilename(
            parent=self,
            title="Sélectionner le fichier CSV du groupe d'étudiants",
            filetypes=[("Fichiers CSV", "*.csv"), ("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")]
        )
        if not path:
            return

        try:
            from app.sheet_generator import parse_students_csv
            group_name, students = parse_students_csv(path)
            if not students:
                messagebox.showwarning(
                    "Aucun étudiant",
                    "Le fichier CSV sélectionné ne semble contenir aucun nom d'étudiant.",
                    parent=self
                )
                return

            self._csv_path.set(path)
            self._group_name.set(group_name)
            self._students = students

            self._csv_info_lbl.config(
                text=f"👥 {group_name} ({len(students)} élèves)",
                fg=SUCCESS
            )
            self._clear_csv_btn.config(state="normal", fg=ERROR)
            self._update_preview()

        except Exception as e:
            messagebox.showerror("Erreur de lecture CSV", str(e), parent=self)

    def _clear_csv(self):
        """Réinitialise la sélection CSV pour revenir au mode fiche vierge."""
        self._csv_path.set("")
        self._group_name.set("")
        self._students = []
        self._csv_info_lbl.config(
            text="Aucun (fiche vierge standard)",
            fg=SUBTEXT
        )
        self._clear_csv_btn.config(state="disabled", fg=SUBTEXT)
        self._update_preview()

    # ──────────────────────────────────────────────────────────────────────────
    # Logique génération & prévisualisation
    # ──────────────────────────────────────────────────────────────────────────

    def _update_preview(self):
        """Met à jour le résumé de prévisualisation."""
        try:
            nq = int(self._nq_var.get())
            nc = int(self._nc_var.get())
        except (tk.TclError, ValueError):
            return

        from app.sheet_generator import QUESTIONS_PER_PAGE
        import math
        pages_per_sheet = math.ceil(nq / QUESTIONS_PER_PAGE)
        cols  = ["A", "B", "C", "D", "E"][:nc]
        sample = "  Q01. □ " + "  □ ".join(cols) + "\n"
        sample += "  Q02. □ " + "  □ ".join(cols) + "\n"
        sample += f"  … ({nq} questions par fiche)"

        if self._students:
            total_pages = len(self._students) * pages_per_sheet
            sample_names = ", ".join(self._students[:3])
            if len(self._students) > 3:
                sample_names += f"… (+{len(self._students) - 3})"

            self._preview_lbl.config(
                text=f"Aperçu lot — Groupe « {self._group_name.get()} » :\n"
                     f"• {len(self._students)} fiches nominatives ({total_pages} page{'s' if total_pages > 1 else ''} au total)\n"
                     f"• Numéro de placement aléatoire (1 à {len(self._students)}) — fiches classées par place (1 à {len(self._students)})\n"
                     f"• {nq} questions, {nc} choix par fiche ({pages_per_sheet} p/fiche)\n"
                     f"• Nom pré-imprimé : {sample_names}\n\n"
                     + sample
            )
            self._gen_btn.config(text=f"  💾  Générer le lot ({len(self._students)} fiches)")
        else:
            self._preview_lbl.config(
                text=f"Aperçu fiche vierge standard ({nq} questions, {nc} choix, {pages_per_sheet} page{'s' if pages_per_sheet > 1 else ''}) :\n\n"
                     + sample
            )
            self._gen_btn.config(text="  💾  Générer et enregistrer")

    def _generate(self):
        title = self._title_var.get().strip() or "QCM"
        try:
            nq = max(1, int(self._nq_var.get()))
            nc = max(3, min(5, int(self._nc_var.get())))
        except (tk.TclError, ValueError):
            messagebox.showerror("Valeur invalide",
                                 "Veuillez entrer des nombres entiers valides.",
                                 parent=self)
            return

        grp = self._group_name.get()
        if grp:
            default_filename = f"{title.replace(' ', '_')}_{grp}_fiches.pdf"
            dlg_title = f"Enregistrer le lot de fiches ({grp})"
        else:
            default_filename = f"{title.replace(' ', '_')}_fiche.pdf"
            dlg_title = "Enregistrer la fiche de réponses"

        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=default_filename,
            title=dlg_title
        )
        if not path:
            return

        try:
            from app.sheet_generator import generate_answer_sheet
            pages = generate_answer_sheet(
                path, nq, nc, title,
                students=self._students if self._students else None,
                group_name=grp
            )
            self._last_path.set(path)

            if self._students:
                plan_file = os.path.basename(os.path.splitext(path)[0] + "_plan_placement.txt")
                self._result_lbl.config(
                    text=f"✓ Lot généré ({len(self._students)} fiches nominatives, {pages} pages) :\n{path}\n"
                         f"📋 Plan de placement (places 1 à {len(self._students)}) : {plan_file}"
                )
                self._gen_btn.config(text="  ✓  Lot généré !")
            else:
                self._result_lbl.config(
                    text=f"✓ Fiche vierge générée ({pages} page{'s' if pages > 1 else ''}) :\n{path}"
                )
                self._gen_btn.config(text="  ✓  Généré !")

            self._print_btn.config(state="normal", bg="#0ea5e9", fg="white", activebackground="#38bdf8")

        except Exception as e:
            messagebox.showerror("Erreur de génération", str(e), parent=self)

    def _print_sheet(self):
        """Lance l'impression de la fiche ou du lot généré."""
        path = self._last_path.get()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Aucun fichier", "Veuillez d'abord générer le fichier PDF.", parent=self)
            return

        import sys
        try:
            if sys.platform == "win32":
                os.startfile(path, "print")
                self._result_lbl.config(
                    text=f"🖨️ Document envoyé vers l'imprimante :\n{path}"
                )
            else:
                import subprocess
                subprocess.run(["lp", path], check=True)
                self._result_lbl.config(
                    text=f"🖨️ Fichier envoyé à l'impression (lp) :\n{path}"
                )
        except Exception as e:
            # Fallback : ouvrir le fichier avec le visualiseur par défaut
            try:
                if sys.platform == "win32":
                    os.startfile(path)
                self._result_lbl.config(
                    text=f"📄 Fichier ouvert dans le lecteur PDF (Ctrl+P pour imprimer) :\n{path}"
                )
            except Exception as err:
                messagebox.showerror(
                    "Erreur d'impression",
                    f"Impossible d'imprimer ou d'ouvrir le fichier :\n{err}",
                    parent=self
                )

    def _center(self, parent):
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w  = self.winfo_width()
        h  = self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")
