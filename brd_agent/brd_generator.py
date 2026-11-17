"""
brd_generator.py -- turns an intake payload into a .docx Business
Requirements Document laid out exactly like the house template
(cover, document control, distribution list, TOC, sections 1-12 with
their fixed tables).

Three output paths:

  1. No uploaded template (default): the document is built from scratch
     by kpmg_docx.py in house style. Structure, numbering and tables come
     from config.OUTLINE / config.TABLE_SPECS, so the output matches the
     template section for section.

  2. An uploaded .docx/.dotx BRD house template (blank with {{tags}} /
     <...> markers, or an already-filled B8yRD with matching section
     headings): that file is opened as-is and filled / refilled in place.
     The client's own styling and numbering are never regenerated.

  3. An uploaded non-BRD Word document (RFP, proposal, notes, …): treated
     as a formatting reference only. Body text is discarded; styles,
     theme, page setup, headers and footers are kept. A full BRD is then
     written into that shell so the result looks like it belongs to the
     uploaded document while containing only generated BRD content.

No ML model is involved in this file. Readiness and gap detection are
lookups against config.MVI_RULES / config.GAP_QUESTIONS; document
assembly is templates.SectionBuilder plus python-docx formatting calls.
"""

import datetime
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor

from .config import (OUTLINE, SECTIONS, MVI_RULES, GAP_QUESTIONS, COMPLIANCE_MAP,
                      TABLE_SPECS, TABLE_SPEC_BY_ID, TABLE_SPEC_BY_NAME)
from .templates import SectionBuilder, derive_rows
from . import kpmg_docx as K
from .template_filler import build_context, fill_template
from .inference import infer_details

# OUTLINE sections whose content is plain prose/bullets (built by
# SectionBuilder as p/bullets/subhead blocks only -- no table, no image).
# These are the ones the structural (heading-anchored) refill path in
# write_into_template() knows how to handle; table- and image-driven
# sections (functional requirements, roles, annex screenshots, ...) are
# always routed through the table-anchor / image path instead, in both
# upload modes.
PROSE_SECTION_IDS = {
    "project_background", "objective", "intended_audience",
    "in_scope", "out_scope",
    "if_hardware", "if_software", "if_data", "if_security", "if_comm",
    "challenges", "to_be", "proposed",
    "prototype",
}


# --------------------------------------------------------------------------
# Readiness + gaps -- rule lookups, not predictions
# --------------------------------------------------------------------------

def mvi_status(answers, detail):
    """Per-section readiness: READY / DRAFT / HEAVY. Never blocks generation."""
    merged = {**(answers or {}), **(detail or {})}
    result = {}
    for sid, keys in MVI_RULES.items():
        if not keys:
            result[sid] = "N/A"
            continue
        answered = [k for k in keys if str(merged.get(k, "")).strip()]
        if len(answered) == len(keys):
            result[sid] = "READY"
        elif answered:
            result[sid] = "DRAFT"
        else:
            result[sid] = "HEAVY"
    return result


def gap_report(answers, detail=None):
    """Rule-based 'what to ask the client next' -- unanswered items only."""
    merged = {**(answers or {}), **(detail or {})}
    gaps = []
    for key, (priority, question) in GAP_QUESTIONS.items():
        if not str(merged.get(key, "")).strip():
            gaps.append({"priority": priority, "question": question, "field": key})
    order = {"High": 0, "Medium": 1, "Low": 2}
    gaps.sort(key=lambda g: order.get(g["priority"], 3))
    return gaps


class Grounding:
    """Counts grounded vs boilerplate content as the document is written."""

    def __init__(self):
        self.total = 0
        self.grounded = 0
        self.per_section = {}

    def add(self, section_id, grounded, n=1):
        self.total += n
        if grounded:
            self.grounded += n
        g, t = self.per_section.get(section_id, (0, 0))
        self.per_section[section_id] = (g + (n if grounded else 0), t + n)

    @property
    def pct(self):
        return round(100 * self.grounded / self.total) if self.total else 0

    def as_dict(self):
        return {sid: f"{g}/{t}" for sid, (g, t) in self.per_section.items()}


# --------------------------------------------------------------------------
# Table resolution: user rows win, otherwise rows derived from the intake
# --------------------------------------------------------------------------

def _clean_rows(rows):
    return [list(r) for r in (rows or []) if any(str(c).strip() for c in r)]


def index_user_tables(tables):
    """Map the wizard's table payload to TABLE_SPECS ids where possible.
    Returns (by_spec_id, leftovers) -- leftovers are custom tables the
    template has no home for, rendered in an appendix."""
    by_id, leftovers = {}, []
    for t in (tables or []):
        spec = None
        if t.get("id") and t["id"] in TABLE_SPEC_BY_ID:
            spec = TABLE_SPEC_BY_ID[t["id"]]
        else:
            spec = TABLE_SPEC_BY_NAME.get((t.get("name") or "").strip().lower())
        rows = _clean_rows(t.get("rows"))
        if spec and rows:
            by_id[spec["id"]] = rows
        elif spec:
            by_id.setdefault(spec["id"], [])
        elif rows:
            leftovers.append(t)
    return by_id, leftovers


def resolve_table(spec, user_rows, project, answers, detail):
    """Return (rows, grounded). User-entered rows are always grounded."""
    rows = _clean_rows(user_rows)
    if rows:
        return rows, True
    derived, grounded = derive_rows(spec["id"], project, answers, detail)
    derived = _clean_rows(derived)
    if derived:
        return derived, grounded
    return list(spec.get("seed") or []), False


def number_rows(spec, rows):
    """Prepend the template's auto-numbered ID column (FR-01, OI-01, 1, 2 ...)."""
    prefix = spec.get("prefix", "")
    out = []
    for n, row in enumerate(rows, start=1):
        ident = f"{prefix}{n:02d}" if prefix else str(n)
        out.append([ident] + [("" if c is None else str(c)) for c in row])
    return out


# --------------------------------------------------------------------------
# Native house-template writer
# --------------------------------------------------------------------------

def _write_block(doc, block, section_id, ground, inherit_styles=False, header_fill=None):
    kind = block.get("type")

    if kind == "p":
        if block.get("grounded"):
            K.para(doc, block["text"], inherit_styles=inherit_styles)
        else:
            K.verify_para(doc, block["text"], inherit_styles=inherit_styles)
        ground.add(section_id, bool(block.get("grounded")))

    elif kind == "bullets":
        items = [i for i in block.get("items", []) if str(i).strip()]
        if items:
            K.bullet_list(doc, items, inherit_styles=inherit_styles)
            ground.add(section_id, bool(block.get("grounded")), n=len(items))

    elif kind == "note":
        K.para(doc, block["text"], italic=True, size=Pt(9.5), color=K.GREY,
               inherit_styles=inherit_styles)

    elif kind == "subhead":
        K.para(doc, block["text"], bold=True, inherit_styles=inherit_styles)

    elif kind == "raw_table":
        if block.get("title"):
            K.para(doc, block["title"], bold=True, inherit_styles=inherit_styles)
        K.build_table(doc, block["cols"], block["rows"],
                      inherit_styles=inherit_styles, header_fill=header_fill)

    elif kind == "image":
        K.picture(doc, block.get("path"), block.get("caption"),
                  inherit_styles=inherit_styles)
        ground.add(section_id, True)

    return block


def _write_spec_table(doc, spec, ctx, ground, section_id,
                      inherit_styles=False, header_fill=None):
    rows, grounded = resolve_table(spec, ctx["user_tables"].get(spec["id"]),
                                   ctx["project"], ctx["answers"], ctx["detail"])
    numbered = number_rows(spec, rows)
    K.build_table(doc, [spec["id_col"]] + spec["cols"], numbered,
                  inherit_styles=inherit_styles, header_fill=header_fill)
    if rows:
        ground.add(section_id, grounded, n=len(rows))
    else:
        ground.add(section_id, False)
    return len(rows), grounded


def write_native(project, answers, detail, tables, gaps, mvi, out_path,
                  include_diagnostics=True, images=None, doc=None,
                  inherit_styles=False, header_fill=None,
                  style_overrides=None):
    """Build a full house-template BRD.

    When *doc* is supplied the BRD is written into that existing document
    (styles, theme, section properties, headers and footers already on
    *doc* are kept). When *inherit_styles* is True the writer does not
    force house fonts/colours on top of the document's own styles — used
    for the style-reference path where the upload is an RFP or other
    non-BRD Word file.
    """
    project_name = project.get("project_name") or "Untitled project"

    so = style_overrides or {}
    if doc is None:
        doc = K.new_document()
        K.apply_header_footer(doc, project_name)
        K.cover_page(doc, project)
    elif so.get("skip_cover"):
        # Template's own cover page was preserved — insert a page break
        # after the preamble so BRD sections start on a fresh page
        doc.add_page_break()
    else:
        # Template had no cover preamble — generate one with its colors/font
        K.cover_page(doc, project, style_overrides=style_overrides)

    user_tables, leftovers = index_user_tables(tables)
    ctx = {"project": project, "answers": answers, "detail": detail,
           "user_tables": user_tables}
    ground = Grounding()
    inh = inherit_styles
    fill = header_fill

    # ---------------- Document control ----------------
    K.heading(doc, "", "Document Control", level=1, inherit_styles=inh)
    K.para(doc, "Document details", bold=True, inherit_styles=inh)
    K.key_value_table(doc, [
        ("Document Name", f"Business Requirements Document \u2013 {project_name}"),
        ("Client / Entity", project.get("organization", "")),
        ("Industry", project.get("industry_other", "").strip() or project.get("industry", "")),
        ("Project Type", project.get("project_type", "")),
        ("Version", project.get("version") or "1.0"),
        ("Date", project.get("doc_date") or datetime.date.today().strftime("%d %b %Y")),
        ("Prepared By", project.get("prepared_by", "")),
        ("Reviewed By", project.get("reviewed_by", "")),
        ("Project Sponsor", project.get("sponsor", "")),
        ("Classification", "Confidential"),
    ], inherit_styles=inh, header_fill=fill)

    K.para(doc, "Version History", bold=True, inherit_styles=inh)
    _write_spec_table(doc, TABLE_SPEC_BY_ID["version_history"], ctx, ground, "_doc_control",
                      inherit_styles=inh, header_fill=fill)

    K.para(doc, "Approval Matrix", bold=True, inherit_styles=inh)
    _write_spec_table(doc, TABLE_SPEC_BY_ID["approval_matrix"], ctx, ground, "_doc_control",
                      inherit_styles=inh, header_fill=fill)
    doc.add_page_break()

    # ---------------- Distribution list ----------------
    K.heading(doc, "", "Distribution List", level=1, inherit_styles=inh)
    K.para(doc, "The following individuals have been identified as the distribution list for this "
                 "document.", inherit_styles=inh)
    _write_spec_table(doc, TABLE_SPEC_BY_ID["distribution_list"], ctx, ground, "_distribution",
                      inherit_styles=inh, header_fill=fill)
    doc.add_page_break()

    # ---------------- Table of contents ----------------
    K.heading(doc, "", "Table of Contents", level=1, inherit_styles=inh)
    K.add_toc(doc)
    doc.add_page_break()

    # ---------------- Sections 1-12 ----------------
    builder = SectionBuilder(project, answers, detail, user_tables, images)

    for sid, number, title, level, kind in OUTLINE:
        K.heading(doc, number, title, level=level, inherit_styles=inh)
        if kind == "container":
            continue
        for block in builder.build(sid):
            if block.get("type") == "table":
                spec = TABLE_SPEC_BY_ID.get(block["table_id"])
                if spec:
                    _write_spec_table(doc, spec, ctx, ground, sid,
                                      inherit_styles=inh, header_fill=fill)
            else:
                _write_block(doc, block, sid, ground,
                             inherit_styles=inh, header_fill=fill)

    # ---------------- Custom tables the template has no slot for --------
    if leftovers:
        doc.add_page_break()
        K.heading(doc, "", "Annexure \u2013 Supporting Tables", level=1, inherit_styles=inh)
        for t in leftovers:
            K.para(doc, t.get("name") or "Table", bold=True, inherit_styles=inh)
            cols = [c or f"Column {i+1}" for i, c in enumerate(t.get("cols") or [])]
            if cols:
                K.build_table(doc, cols, _clean_rows(t.get("rows")),
                              inherit_styles=inh, header_fill=fill)

    # ---------------- Intake diagnostics (internal) ---------------------
    if include_diagnostics:
        doc.add_page_break()
        K.heading(doc, "", "Annexure \u2013 Intake Diagnostics (internal, remove before issue)",
                   level=1, inherit_styles=inh)
        K.para(doc, "Plain text = grounded directly in the intake answers provided by the team or "
                     "client. [VERIFY] = house-template boilerplate that must be validated with the "
                     "client before sign-off.", italic=True, size=Pt(9.5), color=K.GREY,
               inherit_styles=inh)

        K.para(doc, "Input readiness by section", bold=True, inherit_styles=inh)
        readiness_rows = [[label, mvi.get(sid, "N/A")] for sid, label in SECTIONS]
        K.build_table(doc, ["Section", "Readiness"], readiness_rows,
                      inherit_styles=inh, header_fill=fill)

        K.para(doc, "Open questions for the client", bold=True, inherit_styles=inh)
        K.para(doc, "Prioritised information gaps identified from the intake. Copy into the "
                     "discovery agenda or client email.", italic=True, size=Pt(9.5), color=K.GREY,
               inherit_styles=inh)
        if gaps:
            K.build_table(doc, ["Priority", "Question"],
                           [[g["priority"], g["question"]] for g in gaps],
                           inherit_styles=inh, header_fill=fill)
        else:
            K.para(doc, "No open gaps \u2014 every tracked field was answered.",
                   inherit_styles=inh)

    doc.save(out_path)
    return ground


def build_blank_template():
    """Blank house-format BRD template: cover, document control, every
    outline heading, and each template table with its header row and
    empty rows -- no intake content. Returns a python-docx Document."""
    placeholder = {
        "project_name": "<Project Name>",
        "organization": "<Client / Entity>",
        "version": "<Version>",
        "doc_date": "<Date>",
    }
    doc = K.new_document()
    K.apply_header_footer(doc, "<Project Name>")
    K.cover_page(doc, placeholder)

    def empty_table(table_id):
        spec = TABLE_SPEC_BY_ID[table_id]
        K.build_table(doc, [spec["id_col"]] + spec["cols"], [])

    K.heading(doc, "", "Document Control", level=1)
    K.para(doc, "Document details", bold=True)
    K.key_value_table(doc, [(label, "") for label in (
        "Document Name", "Client / Entity", "Industry", "Project Type", "Version", "Date",
        "Prepared By", "Reviewed By", "Project Sponsor", "Classification")])
    K.para(doc, "Version History", bold=True)
    empty_table("version_history")
    K.para(doc, "Approval Matrix", bold=True)
    empty_table("approval_matrix")
    doc.add_page_break()

    K.heading(doc, "", "Distribution List", level=1)
    empty_table("distribution_list")
    doc.add_page_break()

    K.heading(doc, "", "Table of Contents", level=1)
    K.add_toc(doc)
    doc.add_page_break()

    # Run the builder with no intake only to learn which tables sit in
    # which section; prose blocks are dropped so the body stays blank.
    builder = SectionBuilder({}, {}, {}, {}, [])
    for sid, number, title, level, kind in OUTLINE:
        K.heading(doc, number, title, level=level)
        if kind == "container":
            continue
        for block in builder.build(sid):
            if block.get("type") == "table" and block["table_id"] in TABLE_SPEC_BY_ID:
                empty_table(block["table_id"])
            elif block.get("type") == "subhead":
                K.para(doc, block["text"], bold=True)
    return doc


# --------------------------------------------------------------------------
# Uploaded-template writer (fills the client's own .docx in place)
# --------------------------------------------------------------------------

def _reinforce_template_fonts(doc, style_overrides):
    """Set the template's detected fonts explicitly on the document styles
    so every paragraph and heading created by write_native() inherits
    them reliably.

    body_font  → Normal, List Bullet (body text)
    heading_font → Heading 1 / 2 / 3 (section headings)

    Some templates define fonts via theme references (asciiTheme /
    minorHAnsi) which python-docx returns as None and doesn't cascade
    to newly added runs.  Setting the font name explicitly on each style
    resolves this."""
    from docx.oxml.ns import qn as _qn

    body_font = style_overrides.get("body_font") or style_overrides.get("font_name")
    heading_font = style_overrides.get("heading_font") or style_overrides.get("font_name")
    body_size = style_overrides.get("body_size")

    def _set_font(style, font_name):
        """Set font name on a style, including the eastAsia slot."""
        style.font.name = font_name
        rpr = style.element.get_or_add_rPr()
        rfonts = rpr.find(_qn("w:rFonts"))
        if rfonts is not None:
            rfonts.set(_qn("w:eastAsia"), font_name)

    # Body styles
    if body_font:
        try:
            _set_font(doc.styles["Normal"], body_font)
        except KeyError:
            pass
        for bullet_style in ("List Bullet", "List Paragraph"):
            try:
                _set_font(doc.styles[bullet_style], body_font)
            except KeyError:
                pass

    if body_size:
        try:
            doc.styles["Normal"].font.size = body_size
        except KeyError:
            pass

    # Heading styles
    if heading_font:
        for level in (1, 2, 3):
            try:
                _set_font(doc.styles[f"Heading {level}"], heading_font)
            except KeyError:
                pass


def write_into_template(project, answers, detail, tables, gaps, mvi, out_path,
                         template_path, include_diagnostics=True, images=None):
    from .template_filler import (clear_document_body, sample_table_header_fill,
                                   sample_template_styles)

    doc = Document(template_path)

    # The BRD/BRS template upload is the output shell. Do not return its
    # original body unchanged. Keep the uploaded document's look (styles,
    # page setup, theme, headers and footers), remove its sample/guidance
    # body, and write the generated BRD details into that same document.
    header_fill = sample_table_header_fill(doc)
    style_overrides = sample_template_styles(doc)
    kept_cover = clear_document_body(doc, keep_cover=True)
    if kept_cover:
        style_overrides["skip_cover"] = True

    # Make the template's font explicit on the Normal style so body text
    # added by write_native() inherits it even when the original template
    # used theme-font references.
    _reinforce_template_fonts(doc, style_overrides)

    ground = write_native(
        project, answers, detail, tables, gaps, mvi, out_path,
        include_diagnostics=include_diagnostics, images=images,
        doc=doc, inherit_styles=True, header_fill=header_fill,
        style_overrides=style_overrides)

    report = {
        "filled": ["generated_brd_body"],
        "missing": [],
        "tables_routed": [],
        "placeholders_cleared": 0,
        "unmatched_custom_tables": [],
        "upload_type": "uploaded_template_shell",
        "sections_refilled": [sid for sid, _num, _title, _lvl, kind in OUTLINE if kind == "body"],
    }
    return ground, report

# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def build(project, answers, detail, tables, out_dir, template_path=None,
          include_diagnostics=True, images=None):
    project = project or {}
    answers = answers or {}
    detail = detail or {}
    if not project.get("project_name"):
        raise ValueError("Project name is required")

    # Derive detail fields from answers; user-provided detail always wins.
    inferred = infer_details(answers)
    for key, value in inferred.items():
        if key not in detail or not str(detail.get(key, "")).strip():
            detail[key] = value

    mvi = mvi_status(answers, detail)
    gaps = gap_report(answers, detail)

    safe = "".join(ch if ch.isalnum() else "_" for ch in project["project_name"])[:60]
    version = (project.get("version") or "1.0").replace(".", "_")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_path = Path(out_dir) / f"BRD_{safe}_v{version}_{stamp}.docx"

    template_fill_report = None
    if template_path and Path(template_path).exists():
        ground, template_fill_report = write_into_template(
            project, answers, detail, tables, gaps, mvi, str(out_path), template_path,
            include_diagnostics, images)
    else:
        ground = write_native(project, answers, detail, tables, gaps, mvi, str(out_path),
                               include_diagnostics, images)

    ready = sum(1 for v in mvi.values() if v == "READY")
    draft = sum(1 for v in mvi.values() if v == "DRAFT")
    heavy = sum(1 for v in mvi.values() if v == "HEAVY")
    high_gaps = sum(1 for g in gaps if g["priority"] == "High")

    return {
        "file": str(out_path),
        "filename": out_path.name,
        "grounding_pct": ground.pct,
        "grounding_by_section": ground.as_dict(),
        "readiness": {"ready": ready, "draft": draft, "heavy": heavy},
        "open_gaps": len(gaps),
        "high_priority_gaps": high_gaps,
        "gaps": gaps,
        "mvi": mvi,
        "template_fill": template_fill_report,
        "engine_version": "uploaded-template-shell-v2",
        # Frontend treats anything other than 'uploaded_template' as the
        # house format; the precise subtype (blank_template / structural /
        # style_reference) lives under template_fill.upload_type.
        "mode": "uploaded_template" if template_fill_report else "house_template",
    }
