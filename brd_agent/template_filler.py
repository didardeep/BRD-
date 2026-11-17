"""
template_filler.py -- fills {{placeholder}} tags that already exist inside
a client's uploaded .docx BRD template, in place.

This is deliberately separate from brd_generator.write_docx()'s "append
generated sections after the template" behaviour. That path is still used
for the readiness/gap/section extras. This path is for the actual BRD
template body: the client's own headings, numbering, tables and styling
are untouched -- only the text inside {{tag}} tokens is replaced with the
matching intake value. Nothing else about the template is regenerated.

No ML involved: this is a regex substitution over paragraph/run text.
"""

import re
import datetime

CURLY_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
ANGLE_RE = re.compile(r"<([^<>{}]{1,300})>")
PLACEHOLDER_RE = CURLY_RE  # kept for backwards compatibility with callers


def build_context(project, answers, detail):
    """Merge every intake field into one flat dict keyed by placeholder name,
    plus a few convenience/computed fields. project/answers/detail keys win
    in that order if they ever collide (they don't today, but project wins)."""
    ctx = {}
    ctx.update(detail or {})
    ctx.update(answers or {})
    ctx.update(project or {})

    # Convenience/computed placeholders that don't map 1:1 to a raw field
    ctx.setdefault("date_today", datetime.date.today().strftime("%d %b %Y"))
    start = (project or {}).get("start_date") or "TBD"
    end = (project or {}).get("end_date") or "TBD"
    ctx.setdefault("timeline", f"{start} to {end}")

    from .config import COMPLIANCE_MAP
    regs = COMPLIANCE_MAP.get((project or {}).get("industry", ""), [])
    ctx.setdefault("compliance_regs", ", ".join(regs) if regs else "")

    # Stringify everything; blank out None/missing rather than printing "None"
    return {k: ("" if v is None else str(v)) for k, v in ctx.items()}


VERIFY = "[VERIFY]"


def looks_like_blank_template(doc, known_placeholders=None):
    """True if the upload still carries {{tag}} or <...> placeholder
    markup -- the case the rest of this module was built for.

    False means the upload is a document that's already filled in (a
    reference/example BRD, a client's RFP response, an old project's BRD
    reused as a starting point, etc.) with no substitution markers left in
    it. In that case fill_template()/fill_preset_table() have nothing to
    grab onto and will silently leave the body untouched -- callers should
    check this first and, if False, use the heading-anchored structural
    refill path below (find_section_heading + refill_section_body)
    instead of plain placeholder substitution.

    When known_placeholders is supplied, only {{tag}} markers that map to
    actual intake fields count as fillable placeholders. This avoids
    treating explanatory text like "{{placeholders}}" as a real template
    field and returning an otherwise-unfilled upload unchanged.
    """
    found = find_placeholders(doc)
    if known_placeholders is None:
        if found:
            return True
    elif found.intersection(known_placeholders):
        return True
    for para in _iter_all_paragraphs(doc):
        if ANGLE_RE.search(para.text):
            return True
    return False


def find_placeholders(doc):
    """Scan the whole document (body, tables, headers, footers) and return
    the set of {{tag}} names actually present -- useful for a pre-flight
    'these tags have no matching data' check."""
    found = set()
    for para in _iter_all_paragraphs(doc):
        found.update(PLACEHOLDER_RE.findall(para.text))
    return found


def fill_template(doc, context):
    """Replace every {{tag}} occurrence in the document with context[tag]
    (or leave it untouched if the tag isn't in context, so a typo doesn't
    silently blank out part of the template). Modifies doc in place.

    Returns (filled, missing): filled = tags that were substituted,
    missing = tags found in the template with no matching data.
    """
    filled, missing = set(), set()
    for para in _iter_all_paragraphs(doc):
        _fill_paragraph(para, context, filled, missing)
    return filled, missing


# --------------------------------------------------------------------------
# internals
# --------------------------------------------------------------------------

def _iter_all_paragraphs(doc):
    """Yield every paragraph in the main body, all tables (including
    tables nested inside table cells), and every header/footer."""
    for p in doc.paragraphs:
        yield p
    for t in doc.tables:
        yield from _iter_table_paragraphs(t)
    for section in doc.sections:
        for part in (section.header, section.footer,
                     section.first_page_header, section.first_page_footer,
                     section.even_page_header, section.even_page_footer):
            if part is None:
                continue
            for p in part.paragraphs:
                yield p
            for t in part.tables:
                yield from _iter_table_paragraphs(t)


def _iter_table_paragraphs(table):
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                yield p
            for nested in cell.tables:
                yield from _iter_table_paragraphs(nested)


def _fill_paragraph(para, context, filled, missing):
    """Replace {{tag}} tokens in a single paragraph, even when Word has
    split the token's text across multiple runs (common after any manual
    edit near the tag). Strategy: rebuild the paragraph's runs only if a
    placeholder is actually present, preserving the formatting of the
    run each match started in."""
    full_text = "".join(r.text for r in para.runs)
    if not full_text or "{{" not in full_text:
        return
    if not PLACEHOLDER_RE.search(full_text):
        return

    # Map each character position in full_text to the run index it came from
    run_spans = []  # (start, end, run_index)
    pos = 0
    for i, r in enumerate(para.runs):
        run_spans.append((pos, pos + len(r.text), i))
        pos += len(r.text)

    def run_at(char_pos):
        for start, end, idx in run_spans:
            if start <= char_pos < end:
                return idx
        return len(para.runs) - 1

    # Build the replacement text and figure out which "template" run
    # (for formatting) each stretch of output text should inherit.
    pieces = []  # (text, source_run_index)
    last = 0
    for m in PLACEHOLDER_RE.finditer(full_text):
        if m.start() > last:
            pieces.append((full_text[last:m.start()], run_at(last)))
        tag = m.group(1)
        if tag in context:
            pieces.append((context[tag], run_at(m.start())))
            filled.add(tag)
        else:
            pieces.append((m.group(0), run_at(m.start())))  # leave as-is
            missing.add(tag)
        last = m.end()
    if last < len(full_text):
        pieces.append((full_text[last:], run_at(last)))

    # Rewrite: blank out every original run, then append fresh runs in
    # order, each copying the formatting of the run its text came from.
    # Emptied original runs render nothing, so their leftover position in
    # the paragraph is harmless; only the newly appended runs are visible,
    # and they're appended in the correct left-to-right order.
    template_runs = list(para.runs)
    for r in template_runs:
        r.text = ""

    for text, src_idx in pieces:
        if not text:
            continue
        src_run = template_runs[src_idx]
        new_run = para.add_run(text)
        new_run.bold = src_run.bold
        new_run.italic = src_run.italic
        new_run.underline = src_run.underline
        new_run.font.size = src_run.font.size
        new_run.font.name = src_run.font.name
        if src_run.font.color and src_run.font.color.type is not None:
            new_run.font.color.rgb = src_run.font.color.rgb


# --------------------------------------------------------------------------
# Structured section routing: locate a real table/paragraph in the
# template by the heading text that precedes it, and drop wizard-provided
# rows/bullets straight into it -- instead of only appending a fresh
# "Supporting tables" section at the end of the document.
# --------------------------------------------------------------------------

def _iter_body_items(doc):
    """Yield (kind, obj) for every top-level paragraph and table in the
    document body, in actual document order. python-docx's doc.paragraphs
    and doc.tables are each in order internally but not interleaved with
    each other, so this walks the underlying XML body directly."""
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag.endswith("}p"):
            yield ("p", Paragraph(child, doc))
        elif child.tag.endswith("}tbl"):
            yield ("tbl", Table(child, doc))


def find_paragraph_with_phrase(doc, anchor_phrases, used_ids=None):
    """Find the first paragraph in the body whose own text contains one of
    anchor_phrases (case-insensitive) -- unlike locate_after_heading, the
    match target IS this paragraph, not something after it. Used for
    placeholders like '<...items in scope of the project>' where the
    instructional sentence and the anchor phrase are the same paragraph."""
    used_ids = used_ids if used_ids is not None else set()
    for kind, obj in _iter_body_items(doc):
        if kind != "p":
            continue
        if obj._p in used_ids:
            continue
        text = obj.text.strip().lower()
        if text and any(phrase in text for phrase in anchor_phrases):
            return obj
    return None


def locate_after_heading(doc, anchor_phrases, want="tbl", used_ids=None):
    """Find the first paragraph whose text contains one of anchor_phrases
    (case-insensitive), then return the next table (want='tbl') or next
    non-empty paragraph (want='p') that follows it in document order,
    skipping over any guidance/instructional paragraphs in between. The
    search only gives up early if it reaches another heading-styled
    paragraph first (a sign we've left the intended section without
    finding the target). used_ids (a set of python id()s) lets callers
    mark an element as already claimed so a later, less-specific anchor
    doesn't grab it again.
    """
    used_ids = used_ids if used_ids is not None else set()
    items = list(_iter_body_items(doc))
    for i, (kind, obj) in enumerate(items):
        if kind != "p":
            continue
        text = obj.text.strip().lower()
        if not text:
            continue
        if obj._p in used_ids:
            continue
        if not any(phrase in text for phrase in anchor_phrases):
            continue
        for kind2, obj2 in items[i + 1:]:
            el_id = obj2._p if kind2 == "p" else obj2._tbl
            if el_id in used_ids:
                continue
            if kind2 == want:
                return obj2
            if kind2 == "p" and obj2.text.strip() and _is_heading(obj2):
                break  # this anchor match didn't lead to the target; try the next match, if any
        # fall through: keep scanning for another paragraph matching the anchor
    return None


def _is_heading(paragraph):
    style_name = (paragraph.style.name if paragraph.style else "") or ""
    return style_name.lower().startswith("heading") or style_name.lower().startswith("title")


def _normalize_header(text):
    return re.sub(r"[^a-z0-9#]", "", text.lower())


def _is_auto_number_header(text):
    norm = _normalize_header(text)
    return norm in {"id", "slno", "srno", "sno"} or norm.endswith("no") or "#" in norm


def fill_preset_table(table, column_order, row_dicts, used_ids=None):
    """Populate a located table with rows built from row_dicts (list of
    plain dicts keyed by the wizard's column labels in column_order).
    Columns are matched to the template's real header cells by label text,
    not by position -- the template often has an extra leading ID/Sl.No.
    column the wizard doesn't ask about, which gets auto-numbered instead.
    Any existing body rows (the template's own example/seed rows) are
    replaced outright when real data is supplied; otherwise their
    placeholder text is just cleared so the table keeps its shape."""
    if table is None:
        return False
    used_ids = used_ids if used_ids is not None else set()
    used_ids.add(table._tbl)

    header_cells = [c.text.strip() for c in table.rows[0].cells]
    used_wizard_cols = set()
    col_map = []  # per real column: index into column_order, or None
    for h in header_cells:
        h_norm = h.strip().lower()
        match_idx = None
        for wi, wcol in enumerate(column_order):
            if wi in used_wizard_cols:
                continue
            wcol_norm = wcol.strip().lower()
            if wcol_norm and (wcol_norm in h_norm or h_norm in wcol_norm):
                match_idx = wi
                break
        if match_idx is not None:
            used_wizard_cols.add(match_idx)
        col_map.append(match_idx)

    body_rows = list(table.rows)[1:]  # keep header row

    if row_dicts:
        for row in body_rows:
            row._tr.getparent().remove(row._tr)
        for n, item in enumerate(row_dicts, start=1):
            new_row = table.add_row()
            for ci, mapped in enumerate(col_map):
                if ci >= len(new_row.cells):
                    continue
                if mapped is not None:
                    new_row.cells[ci].text = str(item.get(column_order[mapped], ""))
                elif _is_auto_number_header(header_cells[ci]):
                    new_row.cells[ci].text = str(n)
                else:
                    new_row.cells[ci].text = ""
    else:
        placeholder_rows = []
        for row in body_rows:
            text = "".join(c.text for c in row.cells)
            if ANGLE_RE.search(text) or CURLY_RE.search(text):
                placeholder_rows.append(row)
        for row in placeholder_rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.text = ANGLE_RE.sub("", CURLY_RE.sub("", r.text))
    return True


def insert_bullets_after(anchor_paragraph, items):
    """Clear an instructional placeholder paragraph and insert one bullet
    paragraph per item directly after it, copying the anchor's style."""
    if anchor_paragraph is None:
        return False
    for r in list(anchor_paragraph.runs):
        r.text = ""
    if not items:
        return True
    style = anchor_paragraph.style
    for item in items:
        new_p = anchor_paragraph.insert_paragraph_before(item)
        try:
            new_p.style = "List Bullet"
        except KeyError:
            new_p.style = style
    return True


# --------------------------------------------------------------------------
# Structural refill: for uploads that have no {{tag}}/<...> markers at all
# (an already-filled BRD, an RFP, any doc whose FORMAT we want but whose
# CONTENT we don't) -- locate each house-template section by its heading
# text, discard whatever prose currently sits under that heading, and
# insert freshly generated content in its place, inheriting the paragraph
# style (font, size, spacing, list style) already used in that slot. The
# heading itself, and the document's own numbering/styling, are untouched.
# --------------------------------------------------------------------------

def find_section_heading(doc, number, title, used_ids=None):
    """Locate the heading paragraph in an uploaded document that
    corresponds to a given house-template OUTLINE entry. Uploaded
    documents rarely use our exact numbering, so match primarily on the
    heading's title text (e.g. 'Project Background', 'In Scope'), falling
    back to a leading number token ('1.1', '4.3 ...') if the title text
    isn't found verbatim."""
    used_ids = used_ids if used_ids is not None else set()
    title_norm = re.sub(r"\s+", " ", title.strip().lower())
    num_token = number.strip().lower()
    for kind, obj in _iter_body_items(doc):
        if kind != "p":
            continue
        if obj._p in used_ids:
            continue
        if not _is_heading(obj):
            continue
        text = re.sub(r"\s+", " ", obj.text.strip().lower())
        if not text:
            continue
        if title_norm and title_norm in text:
            return obj
        if num_token and (text == num_token or text.startswith(num_token + " ")
                          or text.startswith(num_token + ".")):
            return obj
    return None


def _section_body_slice(doc, heading_para):
    """Paragraphs between heading_para and the next heading of any level,
    in document order. Stops at the first table encountered -- a table
    belonging to this section is handled by the table-anchor path
    (locate_after_heading + fill_preset_table), not this one."""
    items = list(_iter_body_items(doc))
    start = None
    for i, (kind, obj) in enumerate(items):
        if kind == "p" and obj._p is heading_para._p:
            start = i
            break
    if start is None:
        return []
    body = []
    for kind, obj in items[start + 1:]:
        if kind == "tbl":
            break
        if kind == "p":
            if obj.text.strip() and _is_heading(obj):
                break
            body.append(obj)
    return body


def refill_section_body(doc, heading_para, blocks, used_ids=None):
    """Replace whatever paragraphs currently sit under heading_para with
    freshly generated content (a list of block dicts as produced by
    templates.SectionBuilder -- {"type": "p"/"bullets"/"subhead"/"note"}).
    The existing body paragraphs supply the paragraph style (and, if any
    of them is itself a bullet/list paragraph, the bullet style) that new
    paragraphs are written in, so the result still looks like the
    uploaded document's own formatting. Returns True if anything was
    inserted."""
    used_ids = used_ids if used_ids is not None else set()
    body_paras = _section_body_slice(doc, heading_para)
    if not body_paras:
        return False

    anchor = body_paras[0]
    body_style = anchor.style
    bullet_style = None
    for para in body_paras:
        sname = (para.style.name if para.style else "") or ""
        if "bullet" in sname.lower() or "list" in sname.lower():
            bullet_style = para.style
            break

    inserted_any = False
    for block in blocks:
        kind = block.get("type")
        if kind == "p":
            text = block["text"]
            if block.get("grounded") is False:
                text = f"{VERIFY} {text}"
            new_p = anchor.insert_paragraph_before(text)
            new_p.style = body_style
            inserted_any = True
        elif kind == "bullets":
            items = [i for i in block.get("items", []) if str(i).strip()]
            for item in items:
                new_p = anchor.insert_paragraph_before(item)
                try:
                    new_p.style = bullet_style or "List Bullet"
                except KeyError:
                    new_p.style = body_style
                inserted_any = True
        elif kind == "subhead":
            new_p = anchor.insert_paragraph_before(block["text"])
            new_p.style = body_style
            for r in new_p.runs:
                r.bold = True
            inserted_any = True
        # "note" (internal guidance) and anything else (table/image -- not
        # expected here, those sections aren't routed through this path)
        # are intentionally skipped.

    for para in body_paras:
        used_ids.add(para._p)
        para._p.getparent().remove(para._p)
    return inserted_any


def clear_remaining_angle_placeholders(doc, used_ids=None):
    """Final sweep: blank out any <...> instructional placeholder text
    still left in the document body (paragraphs and table cells) that
    wasn't already claimed by a structured section filler above. Running
    headers/footers are left untouched by default since they typically
    carry the document title, not per-team instructions."""
    used_ids = used_ids if used_ids is not None else set()
    cleared = 0
    for kind, obj in _iter_body_items(doc):
        if kind == "p":
            if obj._p in used_ids:
                continue
            cleared += _clear_angle_in_paragraph(obj)
        elif kind == "tbl":
            if obj._tbl in used_ids:
                continue
            for row in obj.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        cleared += _clear_angle_in_paragraph(p)
    return cleared


def _clear_angle_in_paragraph(para):
    full_text = "".join(r.text for r in para.runs)
    if "<" not in full_text or not ANGLE_RE.search(full_text):
        return 0
    new_text = ANGLE_RE.sub("", full_text)
    for i, r in enumerate(para.runs):
        r.text = new_text if i == 0 else ""
    return 1


# --------------------------------------------------------------------------
# Generic uploaded-template helpers -- for human Word templates that have
# headings and blank lines instead of {{field}} tags.
# --------------------------------------------------------------------------

_LABEL_FIELD_MAP = {
    "project": "project_name",
    "client": "organization",
    "date": "doc_date",
    "version": "version",
    "prepared by": "prepared_by",
    "reviewed by": "reviewed_by",
    "project sponsor": "sponsor",
}


def fill_labeled_fields(doc, context):
    """Fill simple front-matter lines like 'Project: ______'."""
    filled = []
    label_re = re.compile(r"^\s*([A-Za-z][A-Za-z /_-]{1,40})\s*:\s*[_\- .]*\s*$")
    for para in _iter_all_paragraphs(doc):
        text = para.text.strip()
        m = label_re.match(text)
        if not m:
            continue
        label = re.sub(r"\s+", " ", m.group(1).strip().lower())
        key = _LABEL_FIELD_MAP.get(label)
        if not key:
            continue
        value = context.get(key) or (context.get("date_today") if key == "doc_date" else "")
        if not value:
            continue
        _replace_paragraph_text(para, f"{m.group(1).strip()}: {value}")
        filled.append(key)
    return filled


def _replace_paragraph_text(para, text):
    runs = list(para.runs)
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r.text = ""
    else:
        para.add_run(text)


def _looks_like_template_heading(paragraph):
    text = paragraph.text.strip()
    if not text or len(text) > 140:
        return False
    if _is_heading(paragraph):
        return True
    if re.match(r"^\d{1,2}(?:\.\d{1,2})?\.?\s+\S", text):
        return True
    style_name = (paragraph.style.name if paragraph.style else "") or ""
    return "heading" in style_name.lower() or "title" in style_name.lower()


def find_template_heading(doc, anchor_phrases, used_ids=None):
    """Find a short heading-like paragraph containing one of anchor_phrases."""
    used_ids = used_ids if used_ids is not None else set()
    for kind, obj in _iter_body_items(doc):
        if kind != "p" or obj._p in used_ids:
            continue
        if not _looks_like_template_heading(obj):
            continue
        text = re.sub(r"\s+", " ", obj.text.strip().lower())
        if any(phrase in text for phrase in anchor_phrases):
            return obj
    return None


def _template_body_slice(doc, heading_para):
    items = list(_iter_body_items(doc))
    start = None
    for i, (kind, obj) in enumerate(items):
        if kind == "p" and obj._p is heading_para._p:
            start = i
            break
    if start is None:
        return []
    body = []
    for kind, obj in items[start + 1:]:
        if kind == "p" and _looks_like_template_heading(obj):
            break
        body.append((kind, obj))
    return body


def refill_template_section(doc, heading_para, blocks, used_ids=None):
    """Replace the content under a generic uploaded-template heading."""
    used_ids = used_ids if used_ids is not None else set()
    body_items = _template_body_slice(doc, heading_para)
    body_paras = [obj for kind, obj in body_items if kind == "p"]
    if not body_items:
        return False

    anchor = body_paras[0] if body_paras else heading_para
    body_style = (body_paras[0].style if body_paras else heading_para.style)
    bullet_style = None
    for para in body_paras:
        sname = (para.style.name if para.style else "") or ""
        if "bullet" in sname.lower() or "list" in sname.lower():
            bullet_style = para.style
            break

    inserted_any = False
    for block in blocks:
        kind = block.get("type")
        if kind == "p":
            text = block["text"]
            if block.get("grounded") is False:
                text = f"{VERIFY} {text}"
            new_p = anchor.insert_paragraph_before(text)
            new_p.style = body_style
            inserted_any = True
        elif kind == "bullets":
            for item in [i for i in block.get("items", []) if str(i).strip()]:
                new_p = anchor.insert_paragraph_before(str(item))
                try:
                    new_p.style = bullet_style or "List Bullet"
                except KeyError:
                    new_p.style = body_style
                inserted_any = True
        elif kind == "subhead":
            new_p = anchor.insert_paragraph_before(block["text"])
            new_p.style = body_style
            for r in new_p.runs:
                r.bold = True
            inserted_any = True

    for kind, obj in body_items:
        if kind == "p":
            used_ids.add(obj._p)
            obj._p.getparent().remove(obj._p)
        elif kind == "tbl":
            used_ids.add(obj._tbl)
            obj._tbl.getparent().remove(obj._tbl)
    return inserted_any
# --------------------------------------------------------------------------
# Style-reference helpers -- when the upload is not a BRD template at all
# (RFP, proposal, arbitrary Word doc), we keep its styles / theme / page
# setup / headers / footers and clear the body so a full BRD can be written
# into it without carrying over any of the source text.
# --------------------------------------------------------------------------

def clear_document_body(doc, keep_cover=True):
    """Remove the main content from the document body, leaving section
    properties (page size, margins, orientation, headers, footers) intact.
    Styles, numbering definitions and the theme live outside the body and
    are preserved automatically.

    When *keep_cover* is True (the default), everything that appears
    before the first heading-styled paragraph is kept -- this preserves
    the template's own cover page / letterhead / logo block so the
    generated BRD inherits the original first-page look.  Content from
    the first heading onward is removed and will be replaced by the
    generated BRD sections.

    Returns True if a cover preamble was preserved, False otherwise."""
    from docx.text.paragraph import Paragraph

    body = doc.element.body
    children = list(body)

    # Find where the first heading or table starts
    first_heading_idx = None
    if keep_cover:
        for i, child in enumerate(children):
            if child.tag.endswith("}sectPr"):
                continue
            if child.tag.endswith("}tbl"):
                first_heading_idx = i
                break
            if child.tag.endswith("}p"):
                para = Paragraph(child, doc)
                if _is_heading(para):
                    first_heading_idx = i
                    break

    kept_cover = False
    for i, child in enumerate(children):
        if child.tag.endswith("}sectPr"):
            continue
        if keep_cover and first_heading_idx is not None and i < first_heading_idx:
            kept_cover = True
            continue  # preserve cover preamble
        body.remove(child)

    return kept_cover


# Titles that are characteristic of a house BRD and rarely appear in an
# RFP / proposal / notes doc. Generic labels like "Scope", "In Scope",
# "Objective" or "Integrations" are deliberately excluded so an RFP is
# not mis-classified as a BRD structure.
_BRD_SIGNATURE_TITLES = (
    "document control",
    "distribution list",
    "project background",
    "intended audience",
    "external interface requirements",
    "as is process",
    "existing challenges",
    "to be process",
    "functional requirements",
    "non-functional requirements",
    "open item list",
    "open item declaration",
    "change control log",
    "roles & responsibilities",
    "roles and responsibilities",
    "assumptions, dependencies and constraints",
    "current system screenshots",
)


def count_brd_heading_matches(doc):
    """How many distinctive house-BRD section titles appear as headings
    (or short bold section labels) in this document? Used to decide
    whether an upload is a real BRD structure we can refill in place,
    or just a formatting reference."""
    matches = 0
    seen = set()
    for kind, obj in _iter_body_items(doc):
        if kind != "p":
            continue
        text_raw = obj.text.strip()
        if not text_raw:
            continue
        # Prefer true heading styles; also accept short paragraphs that
        # may carry section titles without a Heading style.
        if not _is_heading(obj) and len(text_raw) > 120:
            continue
        text = re.sub(r"\s+", " ", text_raw.lower())
        for t in _BRD_SIGNATURE_TITLES:
            if t in text and t not in seen:
                seen.add(t)
                matches += 1
                break
    return matches


def is_brd_like_document(doc, threshold=3):
    """True when the upload has enough distinctive BRD section titles
    that the structural refill path (find heading → replace body) is
    useful. False for RFPs, proposals and arbitrary Word docs that only
    share visual formatting with the output we want."""
    return count_brd_heading_matches(doc) >= threshold


def sample_table_header_fill(doc):
    """Return the first non-empty cell shading hex found on a table header
    row in the source document, or None. Used so style-reference tables
    can inherit the source's header colour instead of the house navy."""
    from docx.oxml.ns import qn as _qn
    for kind, obj in _iter_body_items(doc):
        if kind != "tbl" or not obj.rows:
            continue
        for cell in obj.rows[0].cells:
            tc_pr = cell._tc.tcPr
            if tc_pr is None:
                continue
            for shd in tc_pr.findall(_qn("w:shd")):
                fill = shd.get(_qn("w:fill"))
                if fill and fill.lower() not in ("auto", "ffffff", "null"):
                    return fill
        break  # only sample the first table
    return None


def has_style(doc, name):
    """True if the document defines a style with this exact name."""
    try:
        doc.styles[name]
        return True
    except KeyError:
        return False


def _resolve_theme_font(doc, theme_attr="minorHAnsi"):
    """Try to resolve a theme font name (e.g. 'minorHAnsi') to an actual
    font family by reading the document's theme XML.  Returns None if the
    theme can't be read or the attribute isn't found."""
    try:
        from docx.oxml.ns import qn as _qn
        theme_part = doc.part.part_related_by("http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme")
        theme_el = theme_part._element
        # a:themeElements / a:fontScheme / a:minorFont or a:majorFont
        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        if "minor" in theme_attr.lower():
            xpath = ".//a:fontScheme/a:minorFont/a:latin"
        else:
            xpath = ".//a:fontScheme/a:majorFont/a:latin"
        nodes = theme_el.findall(xpath, ns)
        if nodes:
            return nodes[0].get("typeface")
    except Exception:
        pass
    return None


def sample_template_styles(doc):
    """Extract cover panel color, font names, and heading color from the
    uploaded template *before* its body is cleared.

    Returns a dict with keys: panel_fill, font_name, heading_color,
    body_size, body_font, heading_font.  body_font and heading_font are
    the separately detected fonts for Normal-style body text and Heading
    styles respectively; font_name is kept as a generic fallback (first
    font found from any source).  Any key may be None."""
    from docx.oxml.ns import qn as _qn

    info = {"panel_fill": None, "font_name": None,
            "heading_color": None, "body_size": None,
            "body_font": None, "heading_font": None}

    # 1. Panel fill -- look for the first single-cell table with shading
    #    (cover pages are typically a 1x1 shaded table)
    for kind, obj in _iter_body_items(doc):
        if kind != "tbl":
            continue
        if len(obj.columns) == 1 and len(obj.rows) == 1:
            cell = obj.rows[0].cells[0]
            tc_pr = cell._tc.tcPr
            if tc_pr is not None:
                for shd in tc_pr.findall(_qn("w:shd")):
                    fill = shd.get(_qn("w:fill"))
                    if fill and fill.lower() not in ("auto", "ffffff", "null"):
                        info["panel_fill"] = fill
                        break
            if info["panel_fill"]:
                for p in cell.paragraphs:
                    for run in p.runs:
                        if run.font.name and not info["font_name"]:
                            info["font_name"] = run.font.name
                break

    # 2. Heading font + color -- from Heading 1/2 style definition
    for style_name in ("Heading 1", "Heading 2"):
        try:
            st = doc.styles[style_name]
            if st.font.color and st.font.color.rgb:
                info["heading_color"] = str(st.font.color.rgb)
            if st.font.name:
                info["heading_font"] = st.font.name
            break
        except KeyError:
            continue

    # 3. Body font + size from Normal style definition
    try:
        normal = doc.styles["Normal"]
        if normal.font.name:
            info["body_font"] = normal.font.name
        if normal.font.size:
            info["body_size"] = normal.font.size
    except KeyError:
        pass

    # 4. Fallback: sample fonts from actual paragraph runs in the body
    #    (handles templates where fonts are set at the run level, not
    #    the style level, or where styles use theme references that
    #    python-docx returns as None)
    if not info["body_font"]:
        for kind, obj in _iter_body_items(doc):
            if kind != "p" or not obj.text.strip() or _is_heading(obj):
                continue
            for run in obj.runs:
                if run.font.name:
                    info["body_font"] = run.font.name
                    break
            if info["body_font"]:
                break

    if not info["heading_font"]:
        for kind, obj in _iter_body_items(doc):
            if kind != "p" or not obj.text.strip() or not _is_heading(obj):
                continue
            for run in obj.runs:
                if run.font.name:
                    info["heading_font"] = run.font.name
                    break
            if info["heading_font"]:
                break

    # 5. Fallback: resolve theme fonts from the document's theme XML
    if not info["body_font"]:
        info["body_font"] = _resolve_theme_font(doc, "minorHAnsi")
    if not info["heading_font"]:
        info["heading_font"] = _resolve_theme_font(doc, "majorHAnsi")

    # 6. Unify the generic font_name (for callers that only check one key)
    if not info["font_name"]:
        info["font_name"] = info["body_font"] or info["heading_font"]
    if not info["body_font"]:
        info["body_font"] = info["font_name"]
    if not info["heading_font"]:
        info["heading_font"] = info["body_font"] or info["font_name"]

    return info
