"""
pdf_generator.py
~~~~~~~~~~~~~~~~
Reusable PDF generation module using ReportLab.
Keeps all PDF logic out of Flask so it can be called from any context.

Usage::

    from pdf_generator import generate_pdf

    data = {
        "name": "Acme Corp",
        "email": "info@acme.com",
        "date": "2026-08-24",
        "details": "Project scope: ...",
    }
    buf = generate_pdf(data)          # returns io.BytesIO
    pdf_bytes = buf.getvalue()
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        HRFlowable,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    _reportlab_available = True
except ImportError:
    _reportlab_available = False

# ---------------------------------------------------------------------------
# Field definitions — edit this list to add / remove / reorder fields.
# Each entry: (field_key, display_label, required)
# ---------------------------------------------------------------------------
FIELDS: list[tuple[str, str, bool]] = [
    ("name",    "Name",             True),
    ("email",   "Email",            False),
    ("date",    "Date",             True),
    ("details", "Details / Notes",  False),
]

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_NAVY   = colors.HexColor("#1F3864")
_BLUE   = colors.HexColor("#2E75B6")
_LGREY  = colors.HexColor("#F2F2F2")
_MGREY  = colors.HexColor("#BFBFBF")
_WHITE  = colors.white
_BLACK  = colors.black


# ---------------------------------------------------------------------------
# Page template with header rule and footer
# ---------------------------------------------------------------------------

def _make_page_template(doc: BaseDocTemplate, title: str) -> PageTemplate:
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id="main",
    )

    def _header_footer(canvas, doc):  # noqa: ANN001
        canvas.saveState()
        w, h = A4

        # ── Header bar ──────────────────────────────────────────────────────
        canvas.setFillColor(_NAVY)
        canvas.rect(0, h - 2.2 * cm, w, 2.2 * cm, fill=1, stroke=0)

        canvas.setFillColor(_WHITE)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(1.5 * cm, h - 1.4 * cm, title)

        # Logo placeholder (right side of header)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#AAAAAA"))
        canvas.drawRightString(w - 1.5 * cm, h - 1.35 * cm, "[ Logo ]")

        # ── Footer ──────────────────────────────────────────────────────────
        canvas.setFillColor(_MGREY)
        canvas.rect(0, 0, w, 1.0 * cm, fill=1, stroke=0)

        canvas.setFillColor(_WHITE)
        canvas.setFont("Helvetica", 8)
        gen_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
        canvas.drawString(1.5 * cm, 0.35 * cm, f"Generated: {gen_dt}")
        canvas.drawRightString(
            w - 1.5 * cm, 0.35 * cm,
            f"Page {doc.page}",
        )

        canvas.restoreState()

    return PageTemplate(id="main", frames=[frame], onPage=_header_footer)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(data: dict[str, Any]) -> list[str]:
    """Return a list of error messages for missing required fields."""
    errors = []
    for key, label, required in FIELDS:
        if required and not str(data.get(key, "")).strip():
            errors.append(f"'{label}' is required.")
    return errors


def generate_pdf(data: dict[str, Any], title: str = "Generated Document") -> io.BytesIO:
    """Build and return a PDF as an in-memory BytesIO buffer.

    Parameters
    ----------
    data:   dict of field values (keys match FIELDS definitions above).
    title:  document title shown in the header.
    """
    if not _reportlab_available:
        raise RuntimeError(
            "reportlab is not installed. Run: pip install reportlab"
        )
    buf = io.BytesIO()

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2.8 * cm,      # room for header bar
        bottomMargin=1.6 * cm,   # room for footer bar
        title=title,
    )
    doc.addPageTemplates([_make_page_template(doc, title)])

    styles = getSampleStyleSheet()

    style_section = ParagraphStyle(
        "section",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=_NAVY,
        spaceBefore=10,
        spaceAfter=4,
    )
    style_body = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=_BLACK,
    )
    style_label = ParagraphStyle(
        "label",
        parent=style_body,
        fontName="Helvetica-Bold",
        textColor=_NAVY,
    )

    story = []

    # ── Section title ────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Document Details", style_section))
    story.append(HRFlowable(width="100%", thickness=1, color=_BLUE, spaceAfter=6))

    # ── Field table ──────────────────────────────────────────────────────────
    table_data = []
    for key, label, _ in FIELDS:
        value = str(data.get(key, "")).strip() or "—"
        # Multi-line values (details etc.) are wrapped in a Paragraph
        if "\n" in value or len(value) > 80:
            value_cell = Paragraph(value.replace("\n", "<br/>"), style_body)
        else:
            value_cell = Paragraph(value, style_body)
        table_data.append([
            Paragraph(label, style_label),
            value_cell,
        ])

    col_widths = [4 * cm, doc.width - 4 * cm]
    tbl = Table(table_data, colWidths=col_widths, repeatRows=0)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, -1), _LGREY),
        ("BACKGROUND",  (1, 0), (1, -1), _WHITE),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_LGREY, _WHITE]),
        ("GRID",        (0, 0), (-1, -1), 0.4, _MGREY),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl)

    # ── Extra space before any overflow pages ────────────────────────────────
    story.append(Spacer(1, 0.5 * cm))

    doc.build(story)
    buf.seek(0)
    return buf
