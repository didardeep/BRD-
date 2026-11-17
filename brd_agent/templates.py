"""
templates.py -- deterministic content builders, one per section of the
BRD house template.

Every builder returns a list of *blocks*. A block is a small dict the
writer knows how to render:

    {"type": "p",       "text": str, "grounded": bool}
    {"type": "bullets", "items": [str], "grounded": bool}
    {"type": "note",    "text": str}                      italic guidance
    {"type": "subhead", "text": str}                      bold sub-heading
    {"type": "table",   "table_id": str}                  looked up in TABLE_SPECS
    {"type": "raw_table", "cols": [...], "rows": [[...]], "title": str|None}

`grounded=True`  -> sentence built directly from a client answer.
`grounded=False` -> template boilerplate; the writer prefixes it with
                    [VERIFY] so a reviewer knows exactly what to confirm
                    before the document goes to the client.

This is rule-based string templating. There is no model here, trained or
otherwise -- every branch is an if/else over which fields were filled.
"""

import re

from .config import (COMPLIANCE_MAP, RACIS_LEGEND, ROLE_PRESETS, RACI_PRESETS,
                      AI_ROLE_MAPPING, OPEN_ITEM_DECLARATION, SCOPE_NOTE,
                      CHANGE_LOG_NOTE, OPEN_ITEM_NOTE, PROJECT_TYPES)

VERIFY = "[VERIFY]"


def _clean(text):
    return (text or "").strip()


# Leading list marker ("- ", "* ", "• ") -- but not the "**bold**" /
# "*italic*" markers typed with the formatting toolbar.
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-•]+\s*|\*\s+)")


def _strip_bullet(text):
    return _LIST_MARKER_RE.sub("", text).strip()


def split_items(text):
    """Split a free-text answer into list items: newline first, then
    semicolons/numbered markers if the user typed one long line."""
    text = _clean(text)
    if not text:
        return []
    lines = [_strip_bullet(ln) for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        return [ln for ln in lines if ln]
    single = lines[0] if lines else ""
    parts = re.split(r"\s*;\s*|\s*\|\s*|(?:^|\s)\d+[.)]\s+", single)
    parts = [_strip_bullet(p) for p in parts if p and p.strip()]
    return parts if len(parts) > 1 else ([single] if single else [])


def p(text, grounded=False):
    return {"type": "p", "text": text, "grounded": grounded}


def bullets(items, grounded=False):
    return {"type": "bullets", "items": items, "grounded": grounded}


def note(text):
    return {"type": "note", "text": text}


def subhead(text):
    return {"type": "subhead", "text": text}


def table(table_id):
    return {"type": "table", "table_id": table_id}


def raw_table(cols, rows, title=None):
    return {"type": "raw_table", "cols": cols, "rows": rows, "title": title}


def image(path, caption=None):
    return {"type": "image", "path": path, "caption": caption}


class SectionBuilder:
    """Builds the body of every section in the house template."""

    def __init__(self, project, answers, detail, tables_by_id=None, images=None):
        self.p = project or {}
        self.a = answers or {}
        self.d = detail or {}
        self.t = tables_by_id or {}
        self.images = images or []

    # ---- helpers -------------------------------------------------------

    def _a(self, key):
        return _clean(self.a.get(key))

    def _d(self, key):
        return _clean(self.d.get(key))

    def _name(self):
        return self.p.get("project_name") or "this project"

    def _client(self):
        return self.p.get("organization") or "the client"

    def _project_type(self):
        pt = self.p.get("project_type")
        return pt if pt in PROJECT_TYPES else PROJECT_TYPES[0]

    def _user_rows(self):
        return self.t.get("roles_responsibilities") or []

    def _text_or_verify(self, value, lead, fallback):
        if value:
            return p(f"{lead}{value}", True)
        return p(fallback, False)

    def _row_sentence(self, qid, lead):
        """If structured row data exists for qid, return a flowing sentence; else None."""
        rows = _get_row_data(self.d, qid)
        if not rows:
            return None
        parts = []
        for r in rows:
            label = (r.get("label") or "").strip()
            desc = (r.get("desc") or "").strip()
            if label and desc:
                parts.append(f"{label} ({desc})")
            elif label:
                parts.append(label)
        if not parts:
            return None
        return f"{lead}{', '.join(parts)}."

    def _row_blocks(self, qid, lead):
        """If structured row data exists for qid, return a lead paragraph plus
        bullet items joining label and description into proper paragraphs.
        Returns a list of blocks, or None if no row data."""
        rows = _get_row_data(self.d, qid)
        if not rows:
            return None
        items = []
        for r in rows:
            label = (r.get("label") or "").strip()
            desc = (r.get("desc") or "").strip()
            if label and desc:
                items.append(f"{label}: {desc}")
            elif label:
                items.append(label)
        if not items:
            return None
        return [p(lead, True), bullets(items, True)]

    # ---- 1. Introduction ----------------------------------------------

    def project_background(self):
        out = []
        desc = _clean(self.p.get("description"))
        if desc:
            out.append(p(desc, True))
        if self._a("q_problem"):
            out.append(p(f"{self._client()} has initiated {self._name()} to address the following "
                          f"business problem: {self._a('q_problem')}", True))
        else:
            out.append(p(f"{self._name()} has been initiated to improve operational efficiency and "
                          f"control effectiveness in the affected process area.", False))
        return out

    def objective(self):
        out = []
        if self._a("q_objective"):
            out.append(p(f"The primary objective of {self._name()} is: {self._a('q_objective')}",
                          True))
        else:
            out.append(p(f"The primary objective of {self._name()} is to automate and standardise "
                          f"the affected process, improve control coverage, and reduce manual "
                          f"effort.", False))
        row_blocks = self._row_blocks("q_features", "The solution aims to deliver:")
        if row_blocks:
            out.extend(row_blocks)
        else:
            aims = split_items(self._a("q_features"))
            if aims:
                out.append(p("The solution aims to:", True))
                out.append(bullets(aims, True))
        return out

    def intended_audience(self):
        return [p("Business sponsor, process owners, project team, IT and information security "
                   "reviewers, and internal audit / compliance stakeholders.", False)]

    # ---- 2. Scope ------------------------------------------------------

    def in_scope(self):
        out = []
        items = split_items(self._a("q_inscope"))
        if items:
            out.append(p("The following items / functionalities are in scope of the project:", True))
            out.append(bullets(items, True))
        else:
            out.append(p("In-scope modules, entities and locations are to be confirmed with the "
                          "client. Undefined scope boundaries are the single largest cause of BRD "
                          "rework.", False))
        start, end = self.p.get("start_date"), self.p.get("end_date")
        if start or end:
            out.append(p(f"Indicative project window: {start or 'TBD'} to {end or 'TBD'}.", True))
        return out

    def out_scope(self):
        out = []
        items = split_items(self._a("q_outscope"))
        if items:
            out.append(p("The following items / functionalities are explicitly out of scope of the "
                          "project:", True))
            out.append(bullets(items, True))
        else:
            out.append(p("Out-of-scope items are to be confirmed with the client before sign-off.",
                          False))
        out.append(note(SCOPE_NOTE))
        return out

    # ---- 3. External interface requirements ---------------------------

    def _interface(self, detail_key, fallback, extra_answer=None):
        out = []
        if self._d(detail_key):
            out.append(p(self._d(detail_key), True))
        else:
            out.append(p(fallback, False))
        if extra_answer and self._a(extra_answer):
            out.append(p(self._a(extra_answer), True))
        return out

    def if_hardware(self):
        return self._interface(
            "d_if_hardware",
            "No specific hardware interface is anticipated; the solution is expected to run on "
            "standard client end-user devices. To be confirmed with client IT.")

    def if_software(self):
        out = []
        if self._d("d_if_software"):
            out.append(p(self._d("d_if_software"), True))
        row_blocks = self._row_blocks(
            "q_systems",
            "The solution interfaces with the following software components/applications:")
        if row_blocks:
            out.extend(row_blocks)
            out.append(note("Component versions, databases and libraries for each interface are to "
                             "be confirmed with client IT and recorded in section 8."))
        else:
            systems = split_items(self._a("q_systems"))
            if systems:
                out.append(p("The solution interfaces with the following software components / "
                              "applications:", True))
                out.append(bullets(systems, True))
                out.append(note("Component versions, databases and libraries for each interface are to "
                                 "be confirmed with client IT and recorded in section 8."))
            elif not self._d("d_if_software"):
                out.append(p("Software components, versions, databases and libraries to be confirmed "
                              "with client IT.", False))
        return out

    def if_data(self):
        return self._interface(
            "d_if_data",
            "Data exchange mechanism, file formats and encryption standards are to be confirmed. "
            "Example: backup data will be transferred to cloud storage over SFTP and encrypted "
            "using AES-256.")

    def if_security(self):
        out = []
        if self._d("d_if_security"):
            out.append(p(self._d("d_if_security"), True))
        else:
            out.append(p("Authentication, authorization and encryption mechanisms are to be "
                          "confirmed. Example: the system must authenticate users via SAML-based "
                          "Single Sign-On (SSO) with MFA enforced for privileged roles.", False))
        if self._a("q_regs"):
            out.append(p(f"Security and regulatory obligations stated by the client: "
                          f"{self._a('q_regs')}", True))
        else:
            regs = COMPLIANCE_MAP.get(self.p.get("industry", ""), [])
            if regs:
                out.append(p(f"Typical regulatory framework for {self.p.get('industry')}: "
                              f"{', '.join(regs)}. Applicability to be confirmed with the client's "
                              f"compliance team.", False))
        return out

    def if_comm(self):
        return self._interface(
            "d_if_comm",
            "Communication requirements (email notifications, web protocols, network protocols, "
            "electronic forms) are to be confirmed. Standards such as HTTPS/TLS 1.2+ and SMTP for "
            "notifications are assumed.")

    # ---- 4. Existing and proposed system ------------------------------

    def challenges(self):
        out = []
        items = split_items(self._d("d_challenges"))
        if items:
            out.append(p("The following challenges exist in the current process:", True))
            out.append(bullets(items, True))
        elif self._a("q_problem"):
            out.append(p(self._a("q_problem"), True))
        else:
            out.append(p("Existing challenges are to be confirmed: effort-intensive manual steps, "
                          "limited audit trail, delayed exception identification, and dependence on "
                          "individual knowledge.", False))
        return out

    def to_be(self):
        out = []
        if self._d("d_to_be"):
            out.append(p(self._d("d_to_be"), True))
        elif self._a("q_objective"):
            out.append(p(f"After go-live: {self._a('q_objective')}", True))
        else:
            out.append(p("The To-Be process is to be defined with the process owner. It is expected "
                          "to replace manual steps with automated processing, with exceptions routed "
                          "for review.", False))
        return out

    def proposed(self):
        out = []
        if self._d("d_proposed"):
            out.append(p(self._d("d_proposed"), True))
        else:
            out.append(p("The proposed solution architecture is to be confirmed during solution "
                          "design.", False))
        row_blocks = self._row_blocks(
            "q_features",
            "The proposed solution addresses the challenges above through the following capabilities:")
        if row_blocks:
            out.extend(row_blocks)
        else:
            feats = split_items(self._a("q_features"))
            if feats:
                out.append(p("The proposed solution addresses the challenges above through the "
                              "following capabilities:", True))
                out.append(bullets(feats, True))
        return out

    # ---- 5. Requirements ----------------------------------------------

    def functional(self):
        out = [note("Functional requirements describe what the system should do \u2014 the specific "
                     "behaviours, functions and features.")]
        if not self._a("q_features") and not self._a("q_users"):
            out.append(p("Functional requirements are to be elaborated in requirements workshops "
                          "with the business.", False))
        out.append(table("functional_requirements"))
        return out

    def non_functional(self):
        return [table("non_functional_requirements")]

    # ---- 6. Open items -------------------------------------------------

    def open_item_list(self):
        return [p("This section lists the items that are still under discussion and need to be "
                   "resolved.", False),
                table("open_items"),
                note(OPEN_ITEM_NOTE)]

    def open_item_decl(self):
        return [p(OPEN_ITEM_DECLARATION, False),
                table("open_item_declaration"),
                note("Project Lead / Manager are suggested to separately take approval from the "
                      "Sponsor / Owner for the open items and attach the approval mail under "
                      "\u201cAttachment\u201d.")]

    # ---- 7. Change control log ----------------------------------------

    def change_log(self):
        return [table("change_log"), note(CHANGE_LOG_NOTE)]

    # ---- 8. Integrations ----------------------------------------------

    def integrations(self):
        out = [p("This section covers the various integrations, existing and planned, for the "
                  "project / solution / application / system.", False)]
        out.append(table("integrations"))
        return out

    # ---- 9. Roles & responsibilities ----------------------------------

    def roles(self):
        pt = self._project_type()
        out = [p(f"Roles involved in this project and their details are mentioned below "
                  f"(project type: {pt}).", True if self.p.get("project_type") else False)]
        out.append(subhead("A. Role & Responsibilities"))
        out.append(table("roles_responsibilities"))
        if pt == "AI / GenAI project":
            out.append(subhead("AI Stakeholder Role Mapping"))
            out.append(note("To be filled for each AI use case. This table clarifies "
                             "responsibilities, highlights third-party dependencies, and defines "
                             "ownership across the AI lifecycle. Mark \u201cN/A\u201d where a role "
                             "is not applicable."))
            out.append(raw_table(["Role Category", "Role", "Definition", "Entity / Team Responsible"],
                                  [row + [""] for row in AI_ROLE_MAPPING]))
        out.append(subhead("B. RACIS Matrix"))
        out.append(p("The RACIS matrix used in the project is represented as defined below:", False))
        out.append(raw_table(["Abbreviation", "Area", "Details"], RACIS_LEGEND))
        preset = RACI_PRESETS.get(pt) or RACI_PRESETS[next(iter(RACI_PRESETS))]
        out.append(p(f"RACIS matrix for the project ({pt}):", False))
        out.append(raw_table(["Activity"] + preset["roles"], preset["rows"]))
        out.append(note("The matrix above is the house-template reference for this project type. "
                         "Confirm activities and role names with the engagement lead before sign-off."))
        return out

    # ---- 10. Assumptions, dependencies, constraints -------------------

    def assumptions(self):
        return [p("All changes agreed with stakeholders, including the sponsor, are listed here.",
                   False),
                table("assumptions")]

    def dependencies(self):
        return [p("These are external factors or systems that the project depends on for successful "
                   "delivery.", False),
                table("dependencies")]

    def constraints(self):
        return [p("These are limitations or restrictions that the project must operate within.",
                   False),
                table("constraints"),
                note("The section on Assumptions, Dependencies and Constraints helps clarify the "
                      "context and boundaries of the project, so all stakeholders share an "
                      "understanding of what is expected, what the project relies on, and what "
                      "limitations exist.")]

    # ---- 11. Prototype (with system screenshots) ------------------------

    def prototype(self):
        images = self.images or []
        if self._d("d_prototype"):
            out = [p(self._d("d_prototype"), True)]
        elif images:
            out = []
        else:
            out = [p("No prototype has been shared at this stage. This section is to be included "
                      "in case a prototype is presented to the client.", False)]
        if images:
            out.append(subhead("System Screenshots"))
            for img in images:
                out.append(image(img.get("path"), img.get("caption") or ""))
        return out

    def process_flow_diagrams(self):
        from .flowchart import matplotlib_available, steps_from_text, render_flowchart

        blocks = []

        if not matplotlib_available():
            blocks.append(note("matplotlib is not installed. Run  pip install matplotlib  "
                               "to enable process flow diagrams."))
            return blocks

        # --- Custom flowcharts (user-defined in the wizard) ---
        custom_fcs = self.d.get("_custom_flowcharts") or []
        for i, fc in enumerate(custom_fcs):
            fc_title = _clean(fc.get("title")) or f"Custom Flowchart {i + 1}"
            # Structured steps: [{text, type}] or legacy plain text
            fc_steps_raw = fc.get("steps")
            if isinstance(fc_steps_raw, list) and fc_steps_raw:
                fc_steps = [s for s in fc_steps_raw
                            if isinstance(s, dict) and _clean(s.get("text"))]
            else:
                fc_steps = steps_from_text(_clean(fc.get("text")))
            if len(fc_steps) >= 2:
                path = render_flowchart(fc_steps, fc_title, f"custom_{i}")
                if path:
                    blocks.append(image(
                        path,
                        f"Figure: {fc_title} (user-defined flowchart)"))
            else:
                blocks.append(p(f"Custom flowchart \u201c{fc_title}\u201d could not be rendered "
                                 f"(fewer than 2 steps detected).", False))

        if not blocks:
            blocks.append(p("No custom flowcharts have been defined. Use the wizard\u2019s "
                             "flowchart builder to add process flow diagrams.", False))

        blocks.append(note("The diagrams above represent a starting point for the process "
                            "workshop \u2014 not signed-off design. Replace with validated "
                            "Visio / Lucidchart diagrams after the process walkthrough."))
        return blocks

    # ---- dispatch ------------------------------------------------------

    def build(self, section_id):
        fn = getattr(self, section_id, None)
        if fn is None:
            return []
        return fn()


# --------------------------------------------------------------------------
# Table row derivation -- turns intake answers into rows for the house
# template's fixed tables when the user has not typed rows manually.
# Every derived row is flagged so the writer can mark it for verification.
# --------------------------------------------------------------------------

def _dedupe_items(items):
    seen, out = set(), []
    for item in items:
        value = _clean(item)
        if not value:
            continue
        key = re.sub(r"\W+", " ", value).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _items_from_sources(*texts):
    items = []
    for text in texts:
        items.extend(split_items(text))
    return _dedupe_items(items)


def _sentence_from_text(text, keywords=None, strict=False):
    """First sentence matching any keyword. Without a match, the first item
    of the text -- or "" when *strict*."""
    text = _clean(text)
    if not text:
        return ""
    if not keywords:
        return split_items(text)[0] if split_items(text) else text
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        if any(re.search(rf"\b{re.escape(k)}\b", sentence, re.I) for k in keywords):
            return sentence.strip(" -*\u2022")
    if strict:
        return ""
    return split_items(text)[0] if split_items(text) else text


def _module_for_requirement(text):
    lowered = text.lower()
    if any(k in lowered for k in ("report", "dashboard", "mis", "analytics", "extract")):
        return "Reporting & analytics"
    if any(k in lowered for k in ("approval", "workflow", "maker", "checker", "review")):
        return "Workflow"
    if any(k in lowered for k in ("role", "access", "permission", "user")):
        return "Access & roles"
    if any(k in lowered for k in ("integration", "api", "sftp", "interface", "connect")):
        return "Integration"
    if any(k in lowered for k in ("data", "upload", "import", "export", "validation")):
        return "Data management"
    return "Core"


def _integration_type(text):
    lowered = text.lower()
    if any(k in lowered for k in ("api", "rest", "soap", "webhook")):
        return "API"
    if any(k in lowered for k in ("sftp", "file", "csv", "excel", "xml", "json", "batch")):
        return "File / batch"
    if any(k in lowered for k in ("email", "smtp", "notification")):
        return "Notification"
    if any(k in lowered for k in ("database", "sql", "oracle", "db")):
        return "Database"
    return "To be confirmed"


def _integration_protocol(text):
    lowered = text.lower()
    protocols = []
    for label, keys in (
        ("REST API", ("rest", "api")),
        ("SOAP", ("soap",)),
        ("SFTP", ("sftp",)),
        ("CSV", ("csv",)),
        ("XML", ("xml",)),
        ("JSON", ("json",)),
        ("SMTP", ("smtp", "email")),
        ("HTTPS", ("https",)),
    ):
        if any(k in lowered for k in keys) and label not in protocols:
            protocols.append(label)
    return ", ".join(protocols) or "To be confirmed"


def _security_note(text):
    lowered = text.lower()
    notes = []
    for label, keys in (
        ("SSO/MFA", ("sso", "mfa", "saml", "oauth")),
        ("Encryption required", ("encrypt", "aes", "tls", "https")),
        ("Audit logging required", ("audit", "log")),
        ("Role-based access", ("rbac", "role", "permission", "access")),
    ):
        if any(k in lowered for k in keys):
            notes.append(label)
    return ", ".join(_dedupe_items(notes)) or "To be confirmed"

def _get_row_data(detail, qid):
    """Return structured row data [{label, desc}] for a row-based question, or []."""
    rd = (detail or {}).get("_row_data") or {}
    rows = rd.get(qid) or []
    return [r for r in rows if (r.get("label") or "").strip() or (r.get("desc") or "").strip()]


def derive_rows(table_id, project, answers, detail):
    """Return (rows, grounded) where rows is a list of lists matching the
    spec's `cols` (without the leading auto-numbered ID column)."""
    a = {k: _clean(v) for k, v in (answers or {}).items() if isinstance(v, str)}
    d = {k: _clean(v) for k, v in (detail or {}).items() if isinstance(v, str)}
    pj = project or {}

    if table_id == "functional_requirements":
        rows = []
        # Use structured row data for features if available
        feat_rows = _get_row_data(detail, "q_features")
        if feat_rows:
            for fr in feat_rows:
                label = (fr.get("label") or "").strip()
                desc = (fr.get("desc") or "").strip()
                module = _module_for_requirement(f"{label} {desc}")
                req_text = f"{label}: {desc}" if desc else label
                rows.append([module, label or req_text, desc or req_text,
                             "Drafted from intake; validate priority and acceptance criteria"])
        else:
            requirements = _items_from_sources(a.get("q_features"), d.get("d_proposed"), d.get("d_to_be"))
            for req in requirements:
                module = _module_for_requirement(req)
                rows.append([module, req, req, "Drafted from intake; validate priority and acceptance criteria"])
        # Use structured row data for roles if available
        user_rows = _get_row_data(detail, "q_users")
        if user_rows:
            for ur in user_rows:
                label = (ur.get("label") or "").strip()
                desc = (ur.get("desc") or "").strip()
                access = (ur.get("access") or "").strip()
                req = f"Role-based access shall be provided for {label}"
                if access:
                    req += f" with {access} access"
                detail_text = desc or "Validate permissions with process owner"
                rows.append(["Access & roles", req, detail_text, "Validate permissions with process owner"])
        else:
            for role in split_items(a.get("q_users", "")):
                req = f"Role-based access shall be provided for {role}"
                rows.append(["Access & roles", req, req, "Validate permissions with process owner"])
        deduped, seen = [], set()
        for row in rows:
            key = "||".join(row).lower()
            if key not in seen:
                seen.add(key)
                deduped.append(row)
        return deduped, bool(deduped)

    if table_id == "non_functional_requirements":
        pairs = [
            ("d_performance", "Performance", ["response", "latency", "throughput", "sla", "batch", "seconds"]),
            ("d_availability", "Availability", ["uptime", "availability", "disaster", "rto", "rpo", "backup"]),
            ("d_security_nfr", "Security", ["security", "audit", "encryption", "residency", "access"]),
            ("d_scalability", "Scalability", ["volume", "concurrent", "growth", "scale", "transactions"]),
        ]
        # The five business requirements are always listed; the description
        # is filled from the intake where it says something about that type.
        rows = []
        for key, label, keywords in pairs:
            value = d.get(key) or _sentence_from_text(a.get("q_nonfunc", ""), keywords,
                                                      strict=True)
            rows.append([label, value, label,
                         "Drafted from intake; confirm measurable SLA" if value
                         else "To be confirmed with client IT"])
        regs = a.get("q_regs", "")
        rows.append(["Compliance", regs, "Compliance",
                     "Validate with compliance owner" if regs
                     else "To be confirmed with compliance owner"])
        return rows, any(r[1] for r in rows)

    if table_id == "integrations":
        rows = []
        security_source = " ".join([a.get("q_security", ""), a.get("q_regs", ""), d.get("d_if_security", "")])
        context = " ".join([a.get("q_systems", ""), a.get("q_tech", ""), d.get("d_if_software", ""),
                            d.get("d_if_data", ""), d.get("d_if_comm", "")])
        sys_rows = _get_row_data(detail, "q_systems")
        if sys_rows:
            for sr in sys_rows:
                sysname = (sr.get("label") or "").strip()
                desc = (sr.get("desc") or "").strip()
                if not sysname:
                    continue
                row_context = f"{sysname} {desc} {context}"
                rows.append([
                    sysname,
                    _integration_type(row_context),
                    "To be confirmed",
                    _integration_protocol(row_context),
                    _security_note(f"{row_context} {security_source}"),
                    "Planned / to be validated",
                    desc or "Confirm owner, environment, frequency, error handling and data mapping",
                ])
        else:
            for sysname in _items_from_sources(a.get("q_systems"), d.get("d_if_software")):
                row_context = f"{sysname} {context}"
                rows.append([
                    sysname,
                    _integration_type(row_context),
                    "To be confirmed",
                    _integration_protocol(row_context),
                    _security_note(f"{row_context} {security_source}"),
                    "Planned / to be validated",
                    "Confirm owner, environment, frequency, error handling and data mapping",
                ])
        return rows, bool(rows)

    if table_id == "roles_responsibilities":
        rows = []
        user_rows = _get_row_data(detail, "q_users")
        if user_rows:
            for ur in user_rows:
                label = (ur.get("label") or "").strip()
                desc = (ur.get("desc") or "").strip()
                access = (ur.get("access") or "").strip()
                if not label:
                    continue
                details = desc or "Responsibilities to be confirmed with business owner"
                if access:
                    details += f" (Access level: {access})"
                rows.append([label, details])
        else:
            for role in split_items(a.get("q_users", "")):
                details = role if re.search(r"\b(approve|review|create|manage|view|submit|admin|access)\b", role, re.I) else "Responsibilities to be confirmed with business owner"
                rows.append([role, details])
        if rows:
            return rows, True
        pt = pj.get("project_type")
        preset = ROLE_PRESETS.get(pt) or ROLE_PRESETS[PROJECT_TYPES[0]]
        return [list(r) for r in preset], False

    if table_id == "assumptions":
        rows = []
        if a.get("q_inscope"):
            rows.append(["Scope, modules, entities and locations remain limited to the agreed in-scope items.", a["q_inscope"]])
        if a.get("q_tech") or d.get("d_if_data"):
            rows.append(["Required data, environments, connectivity and technical access will be made available by the client.", _clean(a.get("q_tech") or d.get("d_if_data"))])
        if a.get("q_users"):
            rows.append(["Business users and SMEs will be available for requirements walkthroughs, UAT and sign-off.", a["q_users"]])
        if rows:
            return rows, True
        return [
            ["The client will provide timely access to systems, data, test environments and SMEs.", ""],
            ["Source data required for the solution is available and of usable quality.", ""],
            ["Business users will be available for requirement walkthroughs, UAT and sign-off.", ""],
            ["No change in the agreed scope during the phase, unless raised via change control.", ""],
        ], False

    if table_id == "dependencies":
        rows = []
        for s in _items_from_sources(a.get("q_systems"), d.get("d_if_software")):
            rows.append([f"Availability of, and access to, {s}", "Owner, credentials, environments and interface details to be confirmed"])
        if a.get("q_regs"):
            rows.append(["Compliance and security approvals are required before production rollout.", a["q_regs"]])
        if a.get("q_users"):
            rows.append(["Named business users are required for validation, UAT and sign-off.", a["q_users"]])
        if rows:
            return rows, True
        return [["Availability of source systems and their data owners.", ""],
                 ["Timely provisioning of environments and access by client IT.", ""],
                 ["Sign-off on this BRD before solution design commences.", ""]], False

    if table_id == "constraints":
        rows = []
        if a.get("q_regs"):
            rows.append([f"Regulatory deadline / obligation: {a['q_regs']}", "Validate applicability and due date with compliance owner"])
        if a.get("q_outscope"):
            rows.append([f"Excluded from this phase: {a['q_outscope']}", "Track as future phase or change request if required"])
        if d.get("d_availability"):
            rows.append([f"Availability / DR constraint: {d['d_availability']}", "Confirm infrastructure feasibility"])
        if d.get("d_security_nfr") or a.get("q_security"):
            rows.append([f"Security constraint: {_clean(d.get('d_security_nfr') or a.get('q_security'))}", "Validate with information security"])
        if rows:
            return rows, True
        return [["Delivery must be completed within the agreed engagement window.", ""],
                 ["Solution must operate within the client's existing technology standards.", ""]], False

    if table_id == "version_history":
        version = pj.get("version") or "1.0"
        date = pj.get("doc_date") or ""
        author = pj.get("prepared_by") or ""
        reviewer = pj.get("reviewed_by") or ""
        return [[version, date, author, "Initial draft prepared from intake", "All", reviewer]], \
               bool(pj.get("prepared_by"))

    if table_id == "approval_matrix":
        sponsor = pj.get("sponsor") or ""
        if sponsor:
            return [[pj.get("version") or "1.0", sponsor, "Project Sponsor", "", ""]], True
        return [["", "", "Project Sponsor", "", ""],
                 ["", "", "Business Owner", "", ""],
                 ["", "", "IT Owner", "", ""]], False

    if table_id == "distribution_list":
        rows = []
        for label, who in (("Prepared by", pj.get("prepared_by")),
                            ("Reviewed by", pj.get("reviewed_by")),
                            ("Project Sponsor", pj.get("sponsor"))):
            if _clean(who):
                rows.append([who, label, pj.get("organization") or ""])
        return rows, bool(rows)

    return [], False

