"""
report_exporter.py
Génération de rapports PDF d'analyse QCM avec ReportLab.
Prend en charge :
  1. Rapport individuel (1 étudiant).
  2. Rapport cumulatif de promotion (plusieurs fiches / multi-copies).
"""

import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.analysis import BatchSummary, StudentSheet


def export_single_report(path: str, comparison: list, score_data: dict, student_name: str | None = None):
    """Génère le rapport PDF pour un étudiant unique."""
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm
    )
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "title", fontSize=18, leading=22,
        alignment=TA_CENTER, spaceAfter=4,
        textColor=colors.HexColor("#6c63ff"),
        fontName="Helvetica-Bold"
    )
    style_sub = ParagraphStyle(
        "sub", fontSize=9, leading=12,
        alignment=TA_CENTER, textColor=colors.HexColor("#64748b"),
        spaceAfter=14
    )

    story = []
    story.append(Paragraph("Rapport de correction QCM", style_title))
    now = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")
    story.append(Paragraph(f"Généré le {now}", style_sub))

    # Synthèse
    sd = score_data
    name_row = [["Étudiant / Copie", student_name or "—"]] if student_name is not None else []
    summary_data = name_row + [
        ["Note finale", f"{sd['grade']} / {sd['max_grade']}"],
        ["Pourcentage de réussite", f"{sd['percent']} %"],
        ["Bonnes réponses (✓)", str(sd["correct"])],
        ["Mauvaises réponses (✗)", str(sd["incorrect"])],
        ["Sans réponse (—)", str(sd["blank"])],
        ["Total questions", str(sd["total"])],
        ["Pénalité par erreur", f"{sd['penalty']} pt"],
    ]
    tbl_summary = Table(summary_data, colWidths=[8 * cm, 7 * cm])
    tbl_summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6c63ff")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl_summary)
    story.append(Spacer(1, 0.6 * cm))

    # Détail par question
    detail_data = [["Q#", "Réponse étudiant", "Réponse attendue", "Résultat"]]
    icons = {"correct": "✓ Correct", "incorrect": "✗ Incorrect", "blank": "— Sans réponse"}
    for row in comparison:
        status_text = icons.get(row.status, "—")
        if getattr(row, "is_multiple", False):
            status_text = "✗ Multiple (Invalide)"
        detail_data.append([
            f"Q{row.question:02d}",
            row.student_answer or "—",
            row.correct_answer or "—",
            status_text
        ])

    tbl_detail = Table(detail_data, colWidths=[2.5 * cm, 4.5 * cm, 4.5 * cm, 4 * cm])
    row_colors = []
    for i, row in enumerate(comparison, start=1):
        if row.status == "correct":
            c = colors.HexColor("#d1fae5")
        elif row.status == "incorrect":
            c = colors.HexColor("#fee2e2")
        else:
            c = colors.HexColor("#fef3c7")
        row_colors.append(("BACKGROUND", (0, i), (-1, i), c))

    tbl_detail.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6c63ff")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ] + row_colors))
    story.append(tbl_detail)

    doc.build(story)


def export_cumulative_report(path: str, sheets: list[StudentSheet], batch_summary: BatchSummary):
    """
    Génère le rapport d'analyse statistique complet et cumulatif pour un lot de copies.
    """
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm
    )
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "title", fontSize=18, leading=22,
        alignment=TA_CENTER, spaceAfter=4,
        textColor=colors.HexColor("#6c63ff"),
        fontName="Helvetica-Bold"
    )
    style_sub = ParagraphStyle(
        "sub", fontSize=9, leading=12,
        alignment=TA_CENTER, textColor=colors.HexColor("#64748b"),
        spaceAfter=12
    )
    style_h2 = ParagraphStyle(
        "h2", fontSize=12, leading=16,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold", spaceBefore=10, spaceAfter=6
    )
    style_desc = ParagraphStyle(
        "desc", fontSize=8.5, leading=11,
        textColor=colors.HexColor("#64748b"), spaceAfter=6
    )

    story = []
    now = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1 : SYNTHÈSE GLOBALE & PALMARÈS DES ÉTUDIANTS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Rapport d'analyse et cumul QCM", style_title))
    story.append(Paragraph(
        f"Généré le {now}  •  Effectif : {batch_summary.num_students} copies  •  "
        f"Pénalité : {batch_summary.penalty} pt/fausse",
        style_sub
    ))

    # ── Tableau de synthèse globale ──
    story.append(Paragraph("1. Synthèse globale de la promotion", style_h2))
    bs = batch_summary
    synth_data = [
        ["Métrique", "Valeur", "Métrique", "Valeur"],
        ["Nombre de copies", str(bs.num_students), "Taux de réussite (≥10/20)", f"{bs.pass_rate} %"],
        ["Moyenne de la classe", f"{bs.average_grade} / 20", "Admis / Ajournés", f"{bs.pass_count} / {bs.fail_count}"],
        ["Note maximale", f"{bs.max_grade} / 20", "Moy. Bonnes réponses (✓)", f"{bs.avg_correct}"],
        ["Note minimale", f"{bs.min_grade} / 20", "Moy. Mauvaises rép. (✗)", f"{bs.avg_incorrect}"],
        ["Médiane", f"{bs.median_grade} / 20", "Moy. Sans réponse (—)", f"{bs.avg_blank}"],
        ["Écart-type", f"{bs.std_dev_grade}", "Nombre de questions", str(bs.total_questions)],
    ]
    tbl_synth = Table(synth_data, colWidths=[4.5 * cm, 4 * cm, 4.8 * cm, 4.5 * cm])
    tbl_synth.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6c63ff")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl_synth)
    story.append(Spacer(1, 0.4 * cm))

    # ── Tableau Palmarès des étudiants ──
    story.append(Paragraph("2. Palmarès et classement des étudiants", style_h2))
    story.append(Paragraph("Classement de l'ensemble des copies par ordre de note décroissante :", style_desc))

    # Trier les copies par note décroissante
    sorted_sheets = sorted(sheets, key=lambda s: s.score.get("grade", 0.0), reverse=True)

    ranks_data = [["Rang", "Étudiant / Copie", "Note /20", "% Réussite", "Bonnes", "Fausses", "Blanches", "Statut"]]
    row_styles = []

    for rank, s in enumerate(sorted_sheets, start=1):
        sc = s.score
        is_pass = sc.get("grade", 0.0) >= 10.0
        status_text = "Admis" if is_pass else "Ajourné"

        ranks_data.append([
            str(rank),
            s.name,
            f"{sc.get('grade', 0.0):.2f}",
            f"{sc.get('percent', 0.0):.1f} %",
            str(sc.get("correct", 0)),
            str(sc.get("incorrect", 0)),
            str(sc.get("blank", 0)),
            status_text
        ])

        bg_col = colors.HexColor("#ecfdf5") if is_pass else colors.HexColor("#fef2f2")
        txt_col = colors.HexColor("#065f46") if is_pass else colors.HexColor("#991b1b")
        row_styles.append(("BACKGROUND", (0, rank), (-1, rank), bg_col))
        row_styles.append(("TEXTCOLOR", (7, rank), (7, rank), txt_col))
        row_styles.append(("FONTNAME", (7, rank), (7, rank), "Helvetica-Bold"))

    tbl_ranks = Table(
        ranks_data,
        colWidths=[1.5 * cm, 5.5 * cm, 2.2 * cm, 2.3 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 2.0 * cm]
    )
    tbl_ranks.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",      (1, 1), (1, -1), "LEFT"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ] + row_styles))
    story.append(tbl_ranks)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 : ANALYSE CUMULÉE PAR QUESTION (ITEM ANALYSIS)
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("3. Analyse statistique cumulée par question", style_h2))
    story.append(Paragraph(
        "Ce tableau détaille le comportement de chaque question : taux de réussite, "
        "répartition des choix choisis par les étudiants et niveau de difficulté.",
        style_desc
    ))

    q_data = [["Q#", "Attendu", "Taux réussite", "Bonnes", "Fausses", "Blanches", "Choix choisis", "Difficulté"]]
    q_styles = []

    for idx, qs in enumerate(bs.question_stats, start=1):
        # Format distribution des choix ex: "A:15, B:2"
        distrib_str = ", ".join(f"{k}:{v}" for k, v in sorted(qs.choice_distribution.items())) or "—"

        q_data.append([
            f"Q{qs.question:02d}",
            qs.correct_answer or "—",
            f"{qs.success_rate:.1f} %",
            str(qs.num_correct),
            str(qs.num_incorrect),
            str(qs.num_blank),
            distrib_str,
            qs.difficulty
        ])

        if qs.difficulty == "Facile":
            bg = colors.HexColor("#ecfdf5")
            fg = colors.HexColor("#065f46")
        elif qs.difficulty == "Moyen":
            bg = colors.HexColor("#fefce8")
            fg = colors.HexColor("#854d0e")
        else:
            bg = colors.HexColor("#fef2f2")
            fg = colors.HexColor("#991b1b")

        q_styles.append(("BACKGROUND", (0, idx), (-1, idx), bg))
        q_styles.append(("TEXTCOLOR", (7, idx), (7, idx), fg))
        q_styles.append(("FONTNAME", (7, idx), (7, idx), "Helvetica-Bold"))

    tbl_q = Table(
        q_data,
        colWidths=[1.4 * cm, 1.8 * cm, 2.6 * cm, 1.8 * cm, 1.8 * cm, 1.8 * cm, 5.0 * cm, 2.2 * cm]
    )
    tbl_q.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6c63ff")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ] + q_styles))
    story.append(tbl_q)
    story.append(Spacer(1, 0.5 * cm))

    # Diagnostic questions sensibles
    hard_questions = [qs for qs in bs.question_stats if qs.difficulty == "Difficile"]
    if hard_questions:
        diag_title = Paragraph("Points d'attention — Questions discriminantes / fort taux d'échec :", style_h2)
        diag_items = []
        for hq in hard_questions:
            dist = ", ".join(f"{k}:{v}" for k, v in hq.choice_distribution.items())
            diag_items.append(Paragraph(
                f"• <b>Q{hq.question:02d}</b> : seulement {hq.success_rate}% de réussite "
                f"(Attendu: {hq.correct_answer} ; Réponses : {dist})",
                style_desc
            ))
        story.append(KeepTogether([diag_title] + diag_items))

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 3 : GRILLE RÉCAPITULATIVE DES RÉPONSES
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("4. Grille synthétique des réponses par étudiant", style_h2))
    story.append(Paragraph(
        "Vue matricielle des réponses données par chaque étudiant (vert = correct, rouge = incorrect, blanc = non répondu) :",
        style_desc
    ))

    # Limiter à 25 questions par tableau pour la largeur de page
    all_qs = [qs.question for qs in bs.question_stats]
    max_cols = 15
    q_chunks = [all_qs[i:i + max_cols] for i in range(0, len(all_qs), max_cols)]

    for chunk_idx, chunk in enumerate(q_chunks):
        if chunk_idx > 0:
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph(f"Suite de la grille (Questions {chunk[0]} à {chunk[-1]}) :", style_desc))

        header_row = ["Étudiant"] + [f"Q{q:02d}" for q in chunk] + ["Note"]
        matrix_data = [header_row]
        cell_styles = []

        # Ligne de la correction
        corr_row = ["CORRIGÉ"]
        for q in chunk:
            matching = [qs.correct_answer for qs in bs.question_stats if qs.question == q]
            corr_row.append(matching[0] if matching else "—")
        corr_row.append("20.0")
        matrix_data.append(corr_row)

        cell_styles.append(("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#e0e7ff")))
        cell_styles.append(("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"))

        for s_idx, s in enumerate(sorted_sheets, start=2):
            s_row = [s.name[:18]]
            comp_map = {r.question: r for r in s.comparison}
            for col_idx, q in enumerate(chunk, start=1):
                r = comp_map.get(q)
                ans = r.student_answer if r and r.student_answer else "—"
                s_row.append(ans)
                if r:
                    if r.status == "correct":
                        c = colors.HexColor("#d1fae5")
                    elif r.status == "incorrect":
                        c = colors.HexColor("#fee2e2")
                    else:
                        c = colors.HexColor("#fef3c7")
                    cell_styles.append(("BACKGROUND", (col_idx, s_idx), (col_idx, s_idx), c))

            s_row.append(f"{s.score.get('grade', 0.0):.1f}")
            matrix_data.append(s_row)

        col_w = [4.2 * cm] + [0.85 * cm] * len(chunk) + [1.5 * cm]
        tbl_mat = Table(matrix_data, colWidths=col_w)
        tbl_mat.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6c63ff")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 7.5),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("ALIGN",      (0, 1), (0, -1), "LEFT"),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING",    (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ] + cell_styles))
        story.append(tbl_mat)

    doc.build(story)


def export_pdf_report(path: str, sheets: list[StudentSheet], batch_summary: BatchSummary | None = None):
    """
    Point d'entrée pour l'export PDF :
    - Si 1 seule copie : exporte le rapport individuel.
    - Si plusieurs copies : exporte le rapport cumulatif de promotion.
    """
    if len(sheets) == 1:
        s = sheets[0]
        export_single_report(path, s.comparison, s.score, student_name=s.name)
    else:
        if batch_summary is None:
            from app.analysis import compute_batch_summary
            batch_summary = compute_batch_summary(sheets)
        export_cumulative_report(path, sheets, batch_summary)
