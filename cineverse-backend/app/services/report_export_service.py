"""
Report export rendering (Phase 5).

Given a `ReportData` (see report_service.py) and a target format, this
service is solely responsible for turning it into bytes -- it never
queries the database or computes anything; all the numbers it renders
were already computed by ReportService (which itself reused
AnalyticsService + existing repositories). Kept deliberately separate
from ReportService so "what goes in a report" and "how a report is
rendered" don't become entangled.
"""
import csv
import io
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.exceptions.custom_exceptions import ValidationException
from app.services.report_service import ReportData

BRAND_RED = colors.HexColor("#E50914")
DARK_SLATE = colors.HexColor("#1e293b")
MUTED = colors.HexColor("#64748b")

SUPPORTED_FORMATS = ("csv", "xlsx", "pdf")

_MEDIA_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


class ReportExportService:
    def export(self, report: ReportData, export_format: str) -> tuple[bytes, str, str]:
        """
        Returns (content_bytes, media_type, file_extension).
        Raises ValidationException for an unsupported format -- surfaced
        by the router as a 422, consistent with how other invalid query
        params are handled elsewhere in this API.
        """
        fmt = export_format.lower()
        if fmt not in SUPPORTED_FORMATS:
            raise ValidationException(
                f"Unsupported export format '{export_format}'. "
                f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
            )

        if fmt == "csv":
            content = self._to_csv(report)
        elif fmt == "xlsx":
            content = self._to_xlsx(report)
        else:
            content = self._to_pdf(report)

        return content, _MEDIA_TYPES[fmt], fmt

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------
    def _to_csv(self, report: ReportData) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([report.title])
        writer.writerow([])
        writer.writerow(["Summary"])
        for label, value in report.summary.items():
            writer.writerow([label, value])
        writer.writerow([])
        writer.writerow(report.columns)
        for row in report.rows:
            writer.writerow([row.get(column, "") for column in report.columns])
        return buffer.getvalue().encode("utf-8")

    # ------------------------------------------------------------------
    # Excel (.xlsx)
    # ------------------------------------------------------------------
    def _to_xlsx(self, report: ReportData) -> bytes:
        workbook = Workbook()

        summary_sheet = workbook.active
        summary_sheet.title = "Summary"
        summary_sheet.append([report.title])
        summary_sheet["A1"].font = Font(bold=True, size=14)
        summary_sheet.append([])
        for label, value in report.summary.items():
            summary_sheet.append([label, value])
        for column_cells in summary_sheet.columns:
            length = max(len(str(cell.value)) for cell in column_cells if cell.value is not None) if any(
                cell.value is not None for cell in column_cells
            ) else 10
            summary_sheet.column_dimensions[column_cells[0].column_letter].width = length + 4

        detail_sheet = workbook.create_sheet("Detail")
        detail_sheet.append(report.columns)
        for cell in detail_sheet[1]:
            cell.font = Font(bold=True)
        for row in report.rows:
            detail_sheet.append([row.get(column, "") for column in report.columns])
        for column_cells in detail_sheet.columns:
            length = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=10)
            detail_sheet.column_dimensions[column_cells[0].column_letter].width = min(length + 2, 40)

        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # PDF (summary report -- distinct from the per-invoice PDF, Phase 4)
    # ------------------------------------------------------------------
    def _to_pdf(self, report: ReportData) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.65 * inch,
            bottomMargin=0.65 * inch,
            leftMargin=0.65 * inch,
            rightMargin=0.65 * inch,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("ReportTitle", parent=styles["Heading1"], textColor=BRAND_RED, fontSize=20)
        company_style = ParagraphStyle("Company", parent=styles["Normal"], textColor=MUTED, fontSize=9)
        heading_style = ParagraphStyle("SectionHeading", parent=styles["Heading3"], textColor=DARK_SLATE, fontSize=12)

        elements = [
            Paragraph("CineVerse", company_style),
            Paragraph(report.title, title_style),
            Spacer(1, 0.25 * inch),
            Paragraph("Summary", heading_style),
            Spacer(1, 0.1 * inch),
        ]

        summary_rows = [[label, str(value)] for label, value in report.summary.items()]
        if summary_rows:
            summary_table = Table(summary_rows, colWidths=[2.5 * inch, 4.15 * inch])
            summary_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
                    ]
                )
            )
            elements.append(summary_table)

        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph("Detail", heading_style))
        elements.append(Spacer(1, 0.1 * inch))

        if report.rows:
            # Cap detail rows on the PDF specifically (unlike CSV/XLSX,
            # which include every row) -- a PDF is meant to be a
            # readable summary report, not a full data dump; very long
            # tables in a paginated PDF render poorly. CSV/XLSX remain
            # the right export choice for complete raw data.
            max_pdf_rows = 200
            table_rows = [report.columns] + [
                [str(row.get(column, "")) for column in report.columns]
                for row in report.rows[:max_pdf_rows]
            ]
            col_width = 6.65 * inch / max(len(report.columns), 1)
            detail_table = Table(table_rows, colWidths=[col_width] * len(report.columns))
            detail_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), DARK_SLATE),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                    ]
                )
            )
            elements.append(detail_table)
            if len(report.rows) > max_pdf_rows:
                note_style = ParagraphStyle("Note", parent=styles["Normal"], textColor=MUTED, fontSize=8)
                elements.append(Spacer(1, 0.1 * inch))
                elements.append(
                    Paragraph(
                        f"Showing the first {max_pdf_rows} of {len(report.rows)} rows. "
                        "Export as CSV or Excel for the complete dataset.",
                        note_style,
                    )
                )
        else:
            elements.append(Paragraph("No data for this report.", styles["Normal"]))

        footer_style = ParagraphStyle("Footer", parent=styles["Normal"], textColor=MUTED, fontSize=8, alignment=TA_RIGHT)
        elements.append(Spacer(1, 0.4 * inch))

        elements.append(
            Paragraph(
                f"Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.",
                footer_style,
            )
        )

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
