"""
csv_exporter.py
Export des résultats et notes des étudiants au format CSV (séparateur point-virgule)
ou Microsoft Excel XLS (SpreadsheetML).
"""

from __future__ import annotations

import csv
import html
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.analysis import StudentSheet, BatchSummary


def _format_float_fr(val: float, decimals: int = 2) -> str:
    """Formate un nombre décimal avec la virgule française pour Excel."""
    fmt = f"{{:.{decimals}f}}"
    return fmt.format(val).replace(".", ",")


def export_grades_csv(path: str,
                      sheets: list[StudentSheet],
                      batch_summary: BatchSummary | None = None) -> str:
    """
    Exporte les notes des étudiants au format CSV avec séparateur ';'
    et encodage utf-8-sig (BOM UTF-8 pour ouverture automatique sans dialogue
    dans Microsoft Excel sous Windows).

    Colonnes :
      Place ; Nom de l'étudiant ; Note / 20 ; Pourcentage ; Bonnes réponses ;
      Fausses réponses ; Réponses blanches ; Total questions ; Statut ; Q01 ; Q02...
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    # Déterminer les colonnes de questions (ex: Q01, Q02, ...)
    max_questions = 0
    reference_comparison = None
    for s in sheets:
        if s.comparison and len(s.comparison) > max_questions:
            max_questions = len(s.comparison)
            reference_comparison = s.comparison

    headers = [
        "Place",
        "Nom de l'étudiant",
        "Note / 20",
        "Pourcentage",
        "Bonnes réponses",
        "Fausses réponses",
        "Réponses blanches",
        "Total questions",
        "Statut",
    ]
    if reference_comparison:
        headers.extend([f"Q{r.question:02d}" for r in reference_comparison])
    elif max_questions > 0:
        headers.extend([f"Q{i:02d}" for i in range(1, max_questions + 1)])

    with open(path, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)

        # Ligne de correction attendue (s'il y a des questions de référence)
        if reference_comparison:
            corr_row = [
                "—",
                "CORRECTION ATTENDUE",
                "20,00",
                "100,0 %",
                str(max_questions),
                "0",
                "0",
                str(max_questions),
                "—",
            ]
            corr_row.extend([r.correct_answer if r.correct_answer else "—" for r in reference_comparison])
            writer.writerow(corr_row)

        for sheet in sheets:
            sc = sheet.score or {}
            grade = sc.get("grade", 0.0)
            percent = sc.get("percent", 0.0)
            correct = sc.get("correct", 0)
            incorrect = sc.get("incorrect", 0)
            blank = sc.get("blank", 0)
            total = sc.get("total", len(sheet.comparison))
            statut = "Admis" if grade >= 10.0 else "Ajourné"

            seat_str = str(sheet.seat_number) if sheet.seat_number is not None else ""
            grade_str = _format_float_fr(grade, 2)
            pct_str = _format_float_fr(percent, 1) + " %"

            row = [
                seat_str,
                sheet.name,
                grade_str,
                pct_str,
                str(correct),
                str(incorrect),
                str(blank),
                str(total),
                statut,
            ]
            if sheet.comparison:
                for r in sheet.comparison:
                    row.append(r.student_answer if r.student_answer else "—")
            writer.writerow(row)

        # Synthèse globale si plusieurs étudiants
        if batch_summary and len(sheets) > 1:
            writer.writerow([])  # Ligne vide de séparation
            writer.writerow(["", "SYNTHÈSE DE LA PROMOTION", "", "", "", "", "", "", ""])
            writer.writerow([
                "",
                "Moyenne de la classe",
                _format_float_fr(batch_summary.average_grade, 2),
                _format_float_fr(batch_summary.average_grade / 20.0 * 100.0, 1) + " %" if batch_summary.total_questions else "—",
                _format_float_fr(batch_summary.avg_correct, 1),
                _format_float_fr(batch_summary.avg_incorrect, 1),
                _format_float_fr(batch_summary.avg_blank, 1),
                str(batch_summary.total_questions),
                f"Taux admis : {_format_float_fr(batch_summary.pass_rate, 1)} %",
            ])
            writer.writerow(["", "Note minimale", _format_float_fr(batch_summary.min_grade, 2)])
            writer.writerow(["", "Note maximale", _format_float_fr(batch_summary.max_grade, 2)])
            writer.writerow(["", "Note médiane", _format_float_fr(batch_summary.median_grade, 2)])
            writer.writerow(["", "Écart-type", _format_float_fr(batch_summary.std_dev_grade, 2)])
            writer.writerow([
                "",
                "Étudiants admis (≥ 10/20)",
                f"{batch_summary.pass_count} / {batch_summary.num_students}",
                f"{_format_float_fr(batch_summary.pass_rate, 1)} %"
            ])

    return path


def export_grades_xls(path: str,
                      sheets: list[StudentSheet],
                      batch_summary: BatchSummary | None = None) -> str:
    """
    Exporte les notes au format Microsoft Excel SpreadsheetML 2003 (.xls).
    Permet une ouverture native dans Excel avec en-têtes stylisés et colonnes typées.
    """
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    max_questions = 0
    reference_comparison = None
    for s in sheets:
        if s.comparison and len(s.comparison) > max_questions:
            max_questions = len(s.comparison)
            reference_comparison = s.comparison

    headers = [
        "Place",
        "Nom de l'étudiant",
        "Note / 20",
        "Pourcentage",
        "Bonnes réponses",
        "Fausses réponses",
        "Réponses blanches",
        "Total questions",
        "Statut",
    ]
    if reference_comparison:
        headers.extend([f"Q{r.question:02d}" for r in reference_comparison])
    elif max_questions > 0:
        headers.extend([f"Q{i:02d}" for i in range(1, max_questions + 1)])

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:o="urn:schemas-microsoft-com:office:office"',
        ' xmlns:x="urn:schemas-microsoft-com:office:excel"',
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:html="http://www.w3.org/TR/REC-html40">',
        ' <Styles>',
        '  <Style ss:ID="Default" ss:Name="Normal">',
        '   <Alignment ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Color="#000000"/>',
        '  </Style>',
        '  <Style ss:ID="Header">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>',
        '   <Borders>',
        '    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#4F81BD"/>',
        '   </Borders>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Color="#FFFFFF" ss:Bold="1"/>',
        '   <Interior ss:Color="#1F497D" ss:Pattern="Solid"/>',
        '  </Style>',
        '  <Style ss:ID="CorrHeader">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="10" ss:Color="#276A3C" ss:Bold="1" ss:Italic="1"/>',
        '   <Interior ss:Color="#E2EFDA" ss:Pattern="Solid"/>',
        '  </Style>',
        '  <Style ss:ID="GradeCell">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Bold="1" ss:Color="#1F497D"/>',
        '   <NumberFormat ss:Format="0.00"/>',
        '  </Style>',
        '  <Style ss:ID="Center">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>',
        '  </Style>',
        '  <Style ss:ID="Admis">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Color="#276A3C" ss:Bold="1"/>',
        '  </Style>',
        '  <Style ss:ID="Ajourne">',
        '   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Color="#C00000" ss:Bold="1"/>',
        '  </Style>',
        '  <Style ss:ID="SummaryLabel">',
        '   <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>',
        '   <Font ss:FontName="Calibri" ss:Size="11" ss:Bold="1" ss:Color="#1F497D"/>',
        '  </Style>',
        ' </Styles>',
        ' <Worksheet ss:Name="Notes QCM">',
        '  <Table>',
        '   <Column ss:Width="50"/>',   # Place
        '   <Column ss:Width="160"/>',  # Nom
        '   <Column ss:Width="70"/>',   # Note / 20
        '   <Column ss:Width="75"/>',   # Pourcentage
        '   <Column ss:Width="65"/>',   # Bonnes
        '   <Column ss:Width="65"/>',   # Fausses
        '   <Column ss:Width="65"/>',   # Blanches
        '   <Column ss:Width="65"/>',   # Total
        '   <Column ss:Width="75"/>',   # Statut
    ]

    for _ in range(max_questions):
        xml_lines.append('   <Column ss:Width="40"/>')

    # Ligne d'en-tête
    xml_lines.append('   <Row ss:Height="24">')
    for h in headers:
        esc_h = html.escape(h)
        xml_lines.append(f'    <Cell ss:StyleID="Header"><Data ss:Type="String">{esc_h}</Data></Cell>')
    xml_lines.append('   </Row>')

    # Ligne correction attendue
    if reference_comparison:
        xml_lines.append('   <Row ss:Height="20">')
        corr_vals = [
            ("—", "String", "CorrHeader"),
            ("CORRECTION ATTENDUE", "String", "CorrHeader"),
            (20.0, "Number", "CorrHeader"),
            ("100.0 %", "String", "CorrHeader"),
            (max_questions, "Number", "CorrHeader"),
            (0, "Number", "CorrHeader"),
            (0, "Number", "CorrHeader"),
            (max_questions, "Number", "CorrHeader"),
            ("—", "String", "CorrHeader"),
        ]
        for val, t, style in corr_vals:
            xml_lines.append(f'    <Cell ss:StyleID="{style}"><Data ss:Type="{t}">{html.escape(str(val))}</Data></Cell>')
        for r in reference_comparison:
            ans = html.escape(r.correct_answer if r.correct_answer else "—")
            xml_lines.append(f'    <Cell ss:StyleID="CorrHeader"><Data ss:Type="String">{ans}</Data></Cell>')
        xml_lines.append('   </Row>')

    # Lignes étudiants
    for sheet in sheets:
        sc = sheet.score or {}
        grade = sc.get("grade", 0.0)
        percent = sc.get("percent", 0.0)
        correct = sc.get("correct", 0)
        incorrect = sc.get("incorrect", 0)
        blank = sc.get("blank", 0)
        total = sc.get("total", len(sheet.comparison))
        is_pass = grade >= 10.0
        statut_style = "Admis" if is_pass else "Ajourne"
        statut_text = "Admis" if is_pass else "Ajourné"

        xml_lines.append('   <Row ss:Height="20">')

        # Place
        if sheet.seat_number is not None:
            xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="Number">{sheet.seat_number}</Data></Cell>')
        else:
            xml_lines.append('    <Cell ss:StyleID="Center"><Data ss:Type="String"></Data></Cell>')

        # Nom
        xml_lines.append(f'    <Cell><Data ss:Type="String">{html.escape(sheet.name)}</Data></Cell>')
        # Note
        xml_lines.append(f'    <Cell ss:StyleID="GradeCell"><Data ss:Type="Number">{grade:.2f}</Data></Cell>')
        # Pourcentage
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="String">{percent:.1f} %</Data></Cell>')
        # Bonnes / Fausses / Blanches / Total
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="Number">{correct}</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="Number">{incorrect}</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="Number">{blank}</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="Number">{total}</Data></Cell>')
        # Statut
        xml_lines.append(f'    <Cell ss:StyleID="{statut_style}"><Data ss:Type="String">{statut_text}</Data></Cell>')

        # Questions
        if sheet.comparison:
            for r in sheet.comparison:
                ans = html.escape(r.student_answer if r.student_answer else "—")
                xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="String">{ans}</Data></Cell>')

        xml_lines.append('   </Row>')

    # Synthèse globale si plusieurs étudiants
    if batch_summary and len(sheets) > 1:
        xml_lines.append('   <Row></Row>')  # Ligne vide
        xml_lines.append('   <Row ss:Height="22">')
        xml_lines.append('    <Cell></Cell>')
        xml_lines.append('    <Cell ss:StyleID="SummaryLabel"><Data ss:Type="String">SYNTHÈSE DE LA PROMOTION</Data></Cell>')
        xml_lines.append('   </Row>')

        # Moyenne
        xml_lines.append('   <Row ss:Height="20">')
        xml_lines.append('    <Cell></Cell>')
        xml_lines.append('    <Cell ss:StyleID="SummaryLabel"><Data ss:Type="String">Moyenne de la classe</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="GradeCell"><Data ss:Type="Number">{batch_summary.average_grade:.2f}</Data></Cell>')
        pct_avg = f"{(batch_summary.average_grade / 20.0 * 100.0):.1f} %" if batch_summary.total_questions else "—"
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="String">{pct_avg}</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="Number">{batch_summary.avg_correct:.1f}</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="Number">{batch_summary.avg_incorrect:.1f}</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="Number">{batch_summary.avg_blank:.1f}</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="Number">{batch_summary.total_questions}</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Admis"><Data ss:Type="String">Taux admis : {batch_summary.pass_rate:.1f} %</Data></Cell>')
        xml_lines.append('   </Row>')

        # Min / Max / Médiane
        for label, val in [
            ("Note minimale", batch_summary.min_grade),
            ("Note maximale", batch_summary.max_grade),
            ("Note médiane", batch_summary.median_grade),
            ("Écart-type", batch_summary.std_dev_grade),
        ]:
            xml_lines.append('   <Row ss:Height="19">')
            xml_lines.append('    <Cell></Cell>')
            xml_lines.append(f'    <Cell><Data ss:Type="String">{label}</Data></Cell>')
            xml_lines.append(f'    <Cell ss:StyleID="GradeCell"><Data ss:Type="Number">{val:.2f}</Data></Cell>')
            xml_lines.append('   </Row>')

        # Étudiants admis
        xml_lines.append('   <Row ss:Height="19">')
        xml_lines.append('    <Cell></Cell>')
        xml_lines.append('    <Cell><Data ss:Type="String">Étudiants admis (≥ 10/20)</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Center"><Data ss:Type="String">{batch_summary.pass_count} / {batch_summary.num_students}</Data></Cell>')
        xml_lines.append(f'    <Cell ss:StyleID="Admis"><Data ss:Type="String">{batch_summary.pass_rate:.1f} %</Data></Cell>')
        xml_lines.append('   </Row>')

    xml_lines.extend([
        '  </Table>',
        ' </Worksheet>',
        '</Workbook>',
    ])

    with open(path, mode="w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))

    return path


def export_grades(path: str,
                  sheets: list[StudentSheet],
                  batch_summary: BatchSummary | None = None) -> str:
    """
    Exporte les notes vers le chemin spécifié selon son extension :
    - .xls -> classeur Microsoft Excel XML SpreadsheetML 2003
    - .csv (ou autre) -> CSV séparateur point-virgule avec encodage utf-8-sig
    """
    if path.lower().endswith(".xls"):
        return export_grades_xls(path, sheets, batch_summary)
    return export_grades_csv(path, sheets, batch_summary)
