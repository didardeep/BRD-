"""
kpmg_docx.py -- low-level Word helpers that reproduce the BRD house
template look: Times New Roman 11pt body, navy numbered headings, the
violet cover panel, dark-blue table header rows with white bold text,
footer with page numbers, and a real Word table-of-contents field.

Everything here is python-docx plus a little raw OOXML for the things
python-docx doesn't expose (cell shading, repeated header rows, field
codes). No ML, no external services, no network calls.
"""

import datetime
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm, Inches

# --- house palette --------------------------------------------------------
VIOLET = "3F1A5B"        # cover panel
NAVY = "1F3864"          # table header fill / heading colour
NAVY_RGB = RGBColor(0x1F, 0x38, 0x64)
HEAD_BLUE = RGBColor(0x00, 0x33, 0x8D)   # blue for headings
KPMG_BLUE = "00338D"     # table header row fill (always, even in uploaded templates)
GREY = RGBColor(0x59, 0x59, 0x59)
BODY_FONT = "Times New Roman"
BODY_SIZE = Pt(11)


# --------------------------------------------------------------------------
# raw OOXML helpers
# --------------------------------------------------------------------------

def shade_cell(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def repeat_header_row(row):
    """Mark a table row so Word repeats it on every page."""
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_field(paragraph, instruction):
    """Insert a Word field code (PAGE, NUMPAGES, TOC ...)."""
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(fld_end)
    return run


def update_fields_on_open(doc):
    """Tell Word to refresh field results (the TOC, page numbers) when the
    document is opened, so the table of contents is never blank."""
    settings = doc.settings.element
    for existing in settings.findall(qn("w:updateFields")):
        settings.remove(existing)
    el = OxmlElement("w:updateFields")
    el.set(qn("w:val"), "true")
    settings.append(el)


def add_toc(doc, levels="1-3"):
    """Insert a live TOC field. Word populates it on open / F9."""
    para = doc.add_paragraph()
    add_field(para, f' TOC \\o "{levels}" \\h \\z \\u ')
    update_fields_on_open(doc)
    hint = doc.add_paragraph()
    r = hint.add_run("(Word refreshes this on open; if it looks blank, click in it and press F9.)")
    r.font.size = Pt(9)
    r.font.italic = True
    r.font.color.rgb = GREY
    return para


# --------------------------------------------------------------------------
# document scaffolding
# --------------------------------------------------------------------------

def new_document():
    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = BODY_SIZE
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    normal.paragraph_format.space_before = Pt(2)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.25

    for level, (size, sp_before, sp_after) in enumerate(
        [(14, 20, 10), (12.5, 14, 8), (11.5, 12, 6)], start=1
    ):
        st = doc.styles[f"Heading {level}"]
        st.font.name = BODY_FONT
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = HEAD_BLUE
        st.paragraph_format.space_before = Pt(sp_before)
        st.paragraph_format.space_after = Pt(sp_after)
        st.paragraph_format.keep_with_next = True

    # Bullet list spacing
    for bullet_name in ("List Bullet", "List Paragraph"):
        try:
            bs = doc.styles[bullet_name]
            bs.paragraph_format.space_before = Pt(1)
            bs.paragraph_format.space_after = Pt(3)
            bs.paragraph_format.line_spacing = 1.2
        except KeyError:
            pass

    sec = doc.sections[0]
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)
    sec.top_margin = Cm(2.0)
    sec.bottom_margin = Cm(2.0)
    return doc


def apply_header_footer(doc, project_name):
    """Header: '<Business Requirements Document for X>' left, '<BRD Template>'
    right. Footer: 'Confidential' left, page number right."""
    for section in doc.sections:
        section.different_first_page_header_footer = True

        head = section.header.paragraphs[0]
        head.text = ""
        _tabbed(head, f"Business Requirements Document for {project_name}", "BRD", section)
        for run in head.runs:
            run.font.size = Pt(8)
            run.font.italic = True
            run.font.color.rgb = GREY
            run.font.name = BODY_FONT

        foot = section.footer.paragraphs[0]
        foot.text = ""
        foot.paragraph_format.tab_stops.clear_all()
        foot.paragraph_format.tab_stops.add_tab_stop(
            section.page_width - section.left_margin - section.right_margin,
            WD_TAB_ALIGNMENT.RIGHT)
        r = foot.add_run("Confidential\t")
        r.font.size = Pt(8)
        r.font.name = BODY_FONT
        r.font.color.rgb = GREY
        add_field(foot, " PAGE ")
        for run in foot.runs:
            run.font.size = Pt(8)
            run.font.name = BODY_FONT
            run.font.color.rgb = GREY


def _tabbed(paragraph, left_text, right_text, section):
    paragraph.paragraph_format.tab_stops.clear_all()
    paragraph.paragraph_format.tab_stops.add_tab_stop(
        section.page_width - section.left_margin - section.right_margin,
        WD_TAB_ALIGNMENT.RIGHT)
    paragraph.add_run(f"{left_text}\t{right_text}")


def cover_page(doc, project, style_overrides=None):
    """Title panel + document metadata.  When *style_overrides* is provided
    (a dict from sample_template_styles) the panel colour and font are taken
    from the uploaded template instead of the house defaults."""
    so = style_overrides or {}
    panel_color = so.get("panel_fill") or VIOLET
    font_name = so.get("font_name") or "Arial"

    name = project.get("project_name") or "Untitled project"
    version = project.get("version") or "1.0"
    date = project.get("doc_date") or datetime.date.today().strftime("%d %b %Y")

    panel = doc.add_table(rows=1, cols=1)
    panel.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = panel.rows[0].cells[0]
    shade_cell(cell, panel_color)
    cell.width = Inches(6.3)

    logo_p = cell.paragraphs[0]
    org = project.get("organization") or "BRD Studio"
    logo_r = logo_p.add_run(org)
    logo_r.font.size = Pt(20)
    logo_r.font.bold = True
    logo_r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    logo_r.font.name = font_name

    for _ in range(5):
        cell.add_paragraph()

    for line in ("Business Requirements", f"Document for {name}"):
        title_p = cell.add_paragraph()
        title_p.paragraph_format.space_after = Pt(2)
        title_r = title_p.add_run(line)
        title_r.font.size = Pt(24)
        title_r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        title_r.font.name = font_name

    desc = (project.get("description") or "").strip()
    if desc:
        for _ in range(3):
            cell.add_paragraph()
        desc_p = cell.add_paragraph()
        desc_r = desc_p.add_run(desc)
        desc_r.font.size = Pt(10)
        desc_r.font.italic = True
        desc_r.font.color.rgb = RGBColor(0xE0, 0xE0, 0xFF)
        desc_r.font.name = font_name
        for _ in range(5):
            cell.add_paragraph()
    else:
        for _ in range(9):
            cell.add_paragraph()

    for line in ("Confidential", f"Version {version}", date):
        meta_p = cell.add_paragraph()
        meta_r = meta_p.add_run(line)
        meta_r.font.size = Pt(9)
        meta_r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        meta_r.font.name = font_name

    doc.add_paragraph()
    doc.add_page_break()


# --------------------------------------------------------------------------
# content helpers
# --------------------------------------------------------------------------

def _strip_auto_numbering(paragraph):
    """Override any automatic numbering inherited from the heading style
    so the heading displays only the manually inserted number text.
    Setting numId to 0 tells Word 'no numbering for this paragraph' even
    when the style itself defines one."""
    pPr = paragraph._p.get_or_add_pPr()
    for existing in pPr.findall(qn("w:numPr")):
        pPr.remove(existing)
    numPr = OxmlElement("w:numPr")
    numId_el = OxmlElement("w:numId")
    numId_el.set(qn("w:val"), "0")
    numPr.append(numId_el)
    pPr.append(numPr)


def heading(doc, number, title, level=1, inherit_styles=False):
    """Add a numbered heading. When inherit_styles is True the document's
    own Heading N style (font, colour, spacing) is used as-is; otherwise
    the house navy / Times New Roman look is forced on top of the style.

    When inheriting, automatic outline numbering from the template's
    heading styles is stripped so the manual number text is the only
    number visible -- prevents the '4  1  Introduction' double-numbering
    that occurs when both the template and the generator supply numbers."""
    h = doc.add_heading(level=level)
    if inherit_styles:
        run = h.add_run(f"{number}\t{title}" if number else title)
        _strip_auto_numbering(h)
        # Ensure minimum spacing even when inheriting template styles
        fmt = h.paragraph_format
        min_before = {1: 18, 2: 12, 3: 10}.get(level, 10)
        min_after = {1: 8, 2: 6, 3: 5}.get(level, 5)
        if fmt.space_before is None or fmt.space_before < Pt(min_before):
            fmt.space_before = Pt(min_before)
        if fmt.space_after is None or fmt.space_after < Pt(min_after):
            fmt.space_after = Pt(min_after)
    else:
        run = h.add_run(f"{number}\t{title}" if number else title)
        run.font.bold = True
        run.font.name = BODY_FONT
        run.font.color.rgb = HEAD_BLUE
        run.font.size = Pt({1: 14, 2: 12.5, 3: 11.5}.get(level, 11.5))
    return h


# --------------------------------------------------------------------------
# Light formatting typed in the wizard's formatting toolbar:
#   **bold**   *italic*   "- item" bullet line   "## Heading" line
#   blank line = new paragraph
# --------------------------------------------------------------------------

_INLINE_RE = re.compile(r"(\*\*[^*\n]+?\*\*|\*[^*\s](?:[^*\n]*?[^*\s])?\*)")
_BULLET_LINE_RE = re.compile(r"^\s*(?:[-•]|\*(?=\s))\s+")
_HEADING_LINE_RE = re.compile(r"^\s*#{1,3}\s+")
# Sections write "<lead-in>: <answer>"; when the answer opens with a
# heading or bullet line, move it onto its own line.
_LEAD_IN_RE = re.compile(r":[ \t]+(?=(?:#{1,3}|[-•])\s)")


def add_inline_runs(paragraph, text, bold=False, italic=False, size=None, color=None,
                    font_name=None):
    """Add *text* to *paragraph*, turning **bold** / *italic* markers into
    formatted runs. Returns the runs added."""
    runs = []
    for part in _INLINE_RE.split(str(text)):
        if not part:
            continue
        b, i, chunk = bold, italic, part
        if len(part) > 4 and part.startswith("**") and part.endswith("**"):
            b, chunk = True, part[2:-2]
        elif len(part) > 2 and part.startswith("*") and part.endswith("*"):
            i, chunk = True, part[1:-1]
        run = paragraph.add_run(chunk)
        if b:
            run.font.bold = True
        if i:
            run.font.italic = True
        if font_name:
            run.font.name = font_name
        if size is not None:
            run.font.size = size
        if color is not None:
            run.font.color.rgb = color
        runs.append(run)
    return runs


def _has_block_markup(text):
    text = str(text)
    return "\n\n" in text or any(_BULLET_LINE_RE.match(ln) or _HEADING_LINE_RE.match(ln)
                                 for ln in text.splitlines())


def _bullet_para(doc, text, inherit_styles=False):
    try:
        pr = doc.add_paragraph(style="List Bullet")
    except KeyError:
        pr = doc.add_paragraph()
    add_inline_runs(pr, text, font_name=None if inherit_styles else BODY_FONT,
                    size=None if inherit_styles else BODY_SIZE)
    return pr


def _subheading_para(doc, text, inherit_styles=False):
    pr = doc.add_paragraph()
    add_inline_runs(pr, text, bold=True,
                    font_name=None if inherit_styles else BODY_FONT,
                    size=None if inherit_styles else Pt(12),
                    color=None if inherit_styles else HEAD_BLUE)
    return pr


def para(doc, text, italic=False, bold=False, size=None, color=None, style=None,
         inherit_styles=False):
    font_name = None if inherit_styles else BODY_FONT
    run_size = size if (size is not None or inherit_styles) else BODY_SIZE
    text = _LEAD_IN_RE.sub(":\n", str(text))
    if not _has_block_markup(text):
        pr = doc.add_paragraph(style=style) if style else doc.add_paragraph()
        add_inline_runs(pr, text, bold=bold, italic=italic, size=run_size, color=color,
                        font_name=font_name)
        return pr

    # Bullet / heading lines and blank-line paragraph breaks; consecutive
    # plain lines stay in one paragraph (line breaks), as before.
    last, plain = None, []

    def flush():
        nonlocal last
        if plain:
            last = doc.add_paragraph(style=style) if style else doc.add_paragraph()
            add_inline_runs(last, "\n".join(plain), bold=bold, italic=italic, size=run_size,
                            color=color, font_name=font_name)
            plain.clear()

    for line in str(text).splitlines():
        if not line.strip():
            flush()
        elif _HEADING_LINE_RE.match(line):
            flush()
            last = _subheading_para(doc, _HEADING_LINE_RE.sub("", line), inherit_styles)
        elif _BULLET_LINE_RE.match(line):
            flush()
            last = _bullet_para(doc, _BULLET_LINE_RE.sub("", line), inherit_styles)
        else:
            plain.append(line)
    flush()
    return last


def verify_para(doc, text, inherit_styles=False):
    """Boilerplate paragraph, prefixed with a bold [VERIFY] marker."""
    pr = doc.add_paragraph()
    tag = pr.add_run("[VERIFY] ")
    tag.font.bold = True
    tag.font.color.rgb = RGBColor(0xB0, 0x5A, 0x00)
    if not inherit_styles:
        tag.font.name = BODY_FONT
        tag.font.size = BODY_SIZE
    add_inline_runs(pr, text, font_name=None if inherit_styles else BODY_FONT,
                    size=None if inherit_styles else BODY_SIZE)
    return pr


def bullet_list(doc, items, inherit_styles=False):
    for item in items:
        item = str(item)
        if _HEADING_LINE_RE.match(item):
            _subheading_para(doc, _HEADING_LINE_RE.sub("", item), inherit_styles)
        else:
            _bullet_para(doc, _BULLET_LINE_RE.sub("", item), inherit_styles)


def _available_table_width(doc):
    section = doc.sections[-1]
    return section.page_width - section.left_margin - section.right_margin


def _column_weights(cols):
    weights = []
    for col in cols:
        label = str(col).strip().lower()
        if label in {"sr. no", "sr no", "id", "br#", "oi#", "change id"}:
            weights.append(0.55)
        elif "requirement description" in label or label in {"business requirement description", "description"}:
            weights.append(2.3)
        elif "business requirement" in label or "requirement" in label:
            weights.append(1.7)
        elif "remarks" in label or "status" in label or "type" in label or "date" in label:
            weights.append(0.9)
        elif "system" in label or "role" in label or "name" in label or "area" in label:
            weights.append(1.15)
        else:
            weights.append(1.0)
    return weights


def _table_column_widths(doc, cols, widths=None):
    if widths:
        return list(widths)
    total = _available_table_width(doc)
    weights = _column_weights(cols)
    weight_sum = sum(weights) or 1
    return [int(total * weight / weight_sum) for weight in weights]


def _set_table_width(tbl, width):
    tbl_pr = tbl._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:type"), "dxa")
    tbl_w.set(qn("w:w"), str(int(width / 635)))


def _set_cell_margins(cell, margin=45):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.find(qn("w:tcMar"))
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side in ("top", "start", "bottom", "end"):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(margin))
        node.set(qn("w:type"), "dxa")


def _apply_table_widths(tbl, widths):
    for row in tbl.rows:
        for i, cell in enumerate(row.cells[:len(widths)]):
            cell.width = widths[i]
            _set_cell_margins(cell)


def build_table(doc, cols, rows, widths=None, inherit_styles=False,
                header_fill=None):
    """Header row shaded with fixed, readable column widths.

    Word's autofit is especially aggressive when writing into an uploaded
    template and can squeeze multi-column tables into unreadable slivers,
    so every generated table gets explicit widths across the usable page.
    """
    tbl = doc.add_table(rows=1, cols=len(cols))
    try:
        tbl.style = "Table Grid"
    except KeyError:
        pass
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    col_widths = _table_column_widths(doc, cols, widths)
    _set_table_width(tbl, sum(col_widths))
    font_size = Pt(7.2 if len(cols) >= 7 else (8.2 if len(cols) >= 5 else 9.5))

    # header_fill (sampled from an uploaded template) is ignored on purpose:
    # templates often use a light tint, and headers must be solid KPMG blue.
    fill = KPMG_BLUE
    hdr = tbl.rows[0]
    repeat_header_row(hdr)
    for i, label in enumerate(cols):
        cell = hdr.cells[i]
        shade_cell(cell, fill)
        cell.paragraphs[0].text = ""
        run = cell.paragraphs[0].add_run(str(label))
        run.font.bold = True
        run.font.size = font_size
        if not inherit_styles:
            run.font.name = BODY_FONT
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    body = rows if rows else [["" for _ in cols] for _ in range(2)]
    for row_vals in body:
        cells = tbl.add_row().cells
        for i, val in enumerate(row_vals[:len(cols)]):
            cells[i].paragraphs[0].text = ""
            add_inline_runs(cells[i].paragraphs[0], "" if val is None else str(val),
                            size=font_size,
                            color=RGBColor(0x00, 0x00, 0x00),  # always black text
                            font_name=None if inherit_styles else BODY_FONT)

    _apply_table_widths(tbl, col_widths)
    doc.add_paragraph()
    return tbl


def picture(doc, path, caption=None, width=None, inherit_styles=False):
    """Insert an image with an optional italic caption below it. Skips
    silently (with a [VERIFY] note) if the file is missing or unreadable
    so a bad upload never breaks the whole document."""
    from pathlib import Path as _Path
    width = width or Inches(5.5)
    try:
        if not path or not _Path(path).exists():
            raise FileNotFoundError(path)
        pic_p = doc.add_paragraph()
        pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = pic_p.add_run()
        run.add_picture(str(path), width=width)
    except Exception:
        verify_para(doc, f"Image could not be embedded ({path}).",
                    inherit_styles=inherit_styles)
        return None
    if caption:
        cap_p = doc.add_paragraph()
        cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cap_p.add_run(caption)
        r.font.italic = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = GREY
        if not inherit_styles:
            r.font.name = BODY_FONT
    doc.add_paragraph()
    return pic_p


def key_value_table(doc, pairs, inherit_styles=False, header_fill=None):
    """Two-column 'Document details' style table (label shaded, value plain)."""
    tbl = doc.add_table(rows=0, cols=2)
    try:
        tbl.style = "Table Grid"
    except KeyError:
        pass
    label_fill = KPMG_BLUE
    for label, value in pairs:
        cells = tbl.add_row().cells
        shade_cell(cells[0], label_fill)
        for cell, text, bold in ((cells[0], label, True), (cells[1], value or "", False)):
            cell.paragraphs[0].text = ""
            run = cell.paragraphs[0].add_run(str(text))
            run.font.bold = bold
            run.font.size = Pt(9.5)
            # white label text on the blue fill, black value text
            run.font.color.rgb = (RGBColor(0xFF, 0xFF, 0xFF) if bold
                                  else RGBColor(0x00, 0x00, 0x00))
            if not inherit_styles:
                run.font.name = BODY_FONT
        cells[0].width = Inches(2.0)
        cells[1].width = Inches(4.3)
    doc.add_paragraph()
    return tbl


def cover_page_inherited(doc, project):
    """Plain cover that uses the document's own Title / Normal styles
    instead of the house violet panel -- for style-reference uploads
    where forcing the house look would fight the source formatting."""
    name = project.get("project_name") or "Untitled project"
    version = project.get("version") or "1.0"
    date = project.get("doc_date") or datetime.date.today().strftime("%d %b %Y")
    org = project.get("organization") or ""

    try:
        title_p = doc.add_paragraph(style="Title")
    except KeyError:
        title_p = doc.add_paragraph()
    title_p.add_run("Business Requirements Document")

    try:
        sub = doc.add_paragraph(style="Subtitle")
    except KeyError:
        sub = doc.add_paragraph()
    sub.add_run(f"for {name}")

    desc = (project.get("description") or "").strip()
    if desc:
        desc_p = doc.add_paragraph()
        desc_r = desc_p.add_run(desc)
        desc_r.font.italic = True

    meta_lines = [ln for ln in (
        org,
        f"Version {version}",
        date,
        "Confidential",
    ) if ln]
    for line in meta_lines:
        pr = doc.add_paragraph()
        pr.add_run(line)

    doc.add_page_break()
