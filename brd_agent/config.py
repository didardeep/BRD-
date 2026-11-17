"""
config.py -- schema for the BRD intake, aligned 1:1 with the
"Business Requirements Document" house template (sections 1-12, front
matter, and the fixed tables inside them).

This is the single source of truth. The frontend never hardcodes the
question list -- it fetches it from GET /api/config so the form always
matches what the generator actually understands. Add a question here
and it appears in the wizard and the generator with no other changes.

Nothing in this file is a machine learning model. It's plain data.

Document map (matches the house template exactly):

    Cover page
    Document Control          document details / version history / approval matrix
    Distribution List
    Table of Contents
    1  Introduction                    1.1 Project Background
                                       1.2 Objective
                                       1.3 Intended Audience
    2  Scope                           2.1 In Scope
                                       2.2 Out of Scope
    3  External Interface Requirements 3.1 Hardware  3.2 Software   3.3 Data
                                       3.4 Security  3.5 Communication
    4  Existing and Proposed           4.1 Existing Challenges (As-Is)
       System/Solution                 4.2 To-Be Process
                                       4.3 Proposed Solution/System
    5  Functional and Non-Functional   5.1 Functional Requirements     (table)
       Requirements                    5.2 Non-Functional Requirements (table)
    6  Open Items /Pending Decisions   6.1 Open Item List        (table)
                                       6.2 Open Item Declaration (table)
    7  Change Control Log              (table)
    8  Integrations                    (table)
    9  Roles & Responsibilities        A. Role & Responsibilities (table)
                                       B. RACIS Matrix            (tables)
    10 Assumptions, Dependencies       10.1 Assumptions  (table)
       and Constraints                 10.2 Dependencies (table)
                                       10.3 Constraints  (table)
    11 Prototype                       System Screenshots -- uploaded images, with captions
    12 Annexures                       12.1 Process Flow Diagrams
"""

# --------------------------------------------------------------------------
# Document outline: (id, number, title, level, kind)
#   level 1/2/3 -> Heading 1/2/3
#   kind "container" = heading only; "body" = rendered by SectionBuilder
# --------------------------------------------------------------------------

OUTLINE = [
    ("introduction",       "1",      "Introduction",                               1, "container"),
    ("project_background", "1.1",    "Project Background",                         2, "body"),
    ("objective",          "1.2",    "Objective",                                  2, "body"),
    ("intended_audience",  "1.3",    "Intended Audience",                          2, "body"),

    ("scope",              "2",      "Scope",                                      1, "container"),
    ("in_scope",           "2.1",    "In Scope",                                   2, "body"),
    ("out_scope",          "2.2",    "Out of Scope",                               2, "body"),

    ("ext_interfaces",     "3",      "External Interface Requirements",            1, "container"),
    ("if_hardware",        "3.1",    "Hardware Interfaces",                        2, "body"),
    ("if_software",        "3.2",    "Software Interfaces",                        2, "body"),
    ("if_data",            "3.3",    "Data Interfaces",                            2, "body"),
    ("if_security",        "3.4",    "Security Interfaces",                        2, "body"),
    ("if_comm",            "3.5",    "Communication Interfaces",                   2, "body"),

    ("systems",            "4",      "Existing and Proposed System/Solution",      1, "container"),
    ("challenges",         "4.1",    "Existing Challenges (As-Is)",                2, "body"),
    ("to_be",              "4.2",    "To-Be Process",                              2, "body"),
    ("proposed",           "4.3",    "Proposed Solution/System",                   2, "body"),

    ("requirements",       "5",      "Functional and Non-Functional Requirements", 1, "container"),
    ("functional",         "5.1",    "Functional Requirements",                    2, "body"),
    ("non_functional",     "5.2",    "Non-Functional Requirements",                2, "body"),

    ("open_items",         "6",      "Open Items /Pending Decisions",              1, "container"),
    ("open_item_list",     "6.1",    "Open Item List",                             2, "body"),
    ("open_item_decl",     "6.2",    "Open Item Declaration",                      2, "body"),

    ("change_log",         "7",      "Change Control Log",                         1, "body"),
    ("integrations",       "8",      "Integrations",                               1, "body"),
    ("roles",              "9",      "Roles & Responsibilities",                   1, "body"),

    ("adc",                "10",     "Assumptions, Dependencies and Constraints",  1, "container"),
    ("assumptions",        "10.1",   "Assumptions",                                2, "body"),
    ("dependencies",       "10.2",   "Dependencies",                               2, "body"),
    ("constraints",        "10.3",   "Constraints",                                2, "body"),

    ("prototype",          "11",     "Prototype",                                  1, "body"),

    ("annexures",                   "12",   "Annexures",                          1, "container"),
    ("process_flow_diagrams",       "12.1", "Process Flow Diagrams (As-Is / To-Be)", 2, "body"),
]

# Flat list used by the readiness table and the wizard's live preview.
SECTIONS = [(sid, f"{num} {title}") for sid, num, title, _lvl, kind in OUTLINE
            if kind == "body"]

OUTLINE_BY_ID = {row[0]: row for row in OUTLINE}

PROJECT_TYPES = [
    "Non-AI project",
    "AI project",
]

INDUSTRIES = [
    "Banking & Financial Services", "Manufacturing", "Pharma & Life Sciences",
    "Retail & Consumer", "Insurance", "Technology", "Healthcare", "Telecom",
    "Energy & Utilities", "Government & Public Sector", "Other",
]

COMPLIANCE_MAP = {
    "Banking & Financial Services": ["RBI Master Directions", "RBI IT/Cyber Security Framework",
                                      "SEBI LODR", "PMLA / AML-KYC", "DPDP Act 2023",
                                      "PCI-DSS", "SOX", "Basel III"],
    "Insurance": ["IRDAI Information & Cyber Security Guidelines", "DPDP Act 2023",
                   "ISO 27001", "SOC 2 Type II", "PCI-DSS"],
    "Pharma & Life Sciences": ["FDA 21 CFR Part 11", "GxP", "Schedule M", "ICH Guidelines", "GDPR"],
    "Healthcare": ["HIPAA", "HITECH", "DPDP Act 2023", "HL7/FHIR", "NABH"],
    "Retail & Consumer": ["DPDP Act 2023", "GDPR", "PCI-DSS", "Consumer Protection Act"],
    "Technology": ["ISO 27001", "SOC 2", "DPDP Act 2023", "Export Controls (EAR/ITAR)"],
    "Telecom": ["TRAI Regulations", "DoT Licensing Conditions", "DPDP Act 2023",
                "CERT-In Directions", "ISO 27001", "Lawful Interception Rules"],
    "Manufacturing": ["ISO 9001", "ISO 14001", "Factories Act", "Export Controls"],
    "Energy & Utilities": ["CEA Cyber Security Guidelines", "ISO 27001", "NERC CIP"],
    "Government & Public Sector": ["CERT-In Directions", "MeitY Guidelines", "DPDP Act 2023",
                                    "NIST SP 800-53"],
    "Other": ["DPDP Act 2023", "ISO 27001", "SOC 2", "ISO 9001"],
}

# --------------------------------------------------------------------------
# Cover page / document control metadata
# --------------------------------------------------------------------------

PROJECT_FIELDS = [
    {"key": "project_name", "label": "Project name", "type": "text", "required": True},
    {"key": "organization", "label": "Client / entity", "type": "text", "required": True},
    {"key": "industry", "label": "Industry", "type": "select", "options": INDUSTRIES, "required": True},
    {"key": "project_type", "label": "Project type",
     "type": "select", "options": PROJECT_TYPES, "required": True},
    {"key": "sponsor", "label": "Project sponsor", "type": "text", "required": True},
    {"key": "prepared_by", "label": "Prepared by", "type": "text", "required": True},
    {"key": "reviewed_by", "label": "Reviewed by", "type": "text", "required": True},
    {"key": "version", "label": "Document version", "type": "text", "required": True},
    {"key": "doc_date", "label": "Document date", "type": "date", "required": True,
     "default": "today"},
    # Optional -- the implementation timeline is often not known when the BRD is drafted.
    {"key": "start_date", "label": "Project start date", "type": "date", "required": False},
    {"key": "end_date", "label": "Tentative / target go-live date", "type": "date", "required": False},
    {"key": "description", "label": "Project description", "type": "textarea", "required": True},
]

# --------------------------------------------------------------------------
# Core questions -- plain language, answerable by a functional team.
# No duplicates: nothing asked here is asked again in DETAIL_FIELDS.
# `sec` shows the user which template section the answer lands in.
# `maps_to` are OUTLINE ids.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Answer-quality rules -- applied by the wizard (static/app.js) to every
# answer that is filled in, so "N/A", "None", "-", "test" etc. are rejected
# instead of passing a simple "is it non-empty?" check.
# --------------------------------------------------------------------------

PLACEHOLDER_ANSWERS = [
    "na", "n/a", "n.a", "n.a.", "not applicable", "not available", "none", "nil",
    "null", "nothing", "no", "nope", "-", "--", "---", ".", "..", "...", "x", "xx",
    "xxx", "tbd", "tba", "tbc", "to be decided", "to be confirmed", "later",
    "test", "testing", "abc", "asdf", "qwerty", "lorem ipsum", "dummy", "sample",
    "same", "same as above", "as above", "etc", "ok", "yes", "?", "??", "unknown",
    "not sure", "dont know", "don't know", "idk", "blank", "empty",
]

# Answers that ARE meaningful for questions marked "allow_none" (e.g. a
# standalone system with no integrations).
NONE_ANSWERS = ["none", "nil", "no integrations", "no integration", "standalone",
                "not applicable", "n/a", "na"]

# Minimum word counts used by the quality check.
MIN_WORDS_TEXT = 8        # free-text core answers
MIN_WORDS_ROW_DESC = 4    # description column of row-based answers

# Role / user-access guidance for the "user roles" question.
ROLE_SUGGESTIONS = [
    "Administrator", "Super User", "Procurement Head", "Finance Head",
    "Business User", "Reviewer", "Approver", "Requester", "Auditor",
    "Viewer",
]

ACCESS_LEVELS = [
    "Read Only", "Write Only", "Read & Write", "Delete", "Approve",
    "Admin / Full Access",
]

# Structured questionnaire for regulatory & compliance requirements --
# inserted into the Compliance answer with one click so users capture the
# same points every time. Each line is "Heading: <prompt>" -- the user replaces
# the prompt with what applies and deletes what doesn't.
TEMPLATE_FILL_PROMPT = "[mention as per your application]"

COMPLIANCE_TEMPLATE = "\n".join(f"{h}: {TEMPLATE_FILL_PROMPT}" for h in (
    "Industry / security standards (e.g. ISO 27001, SOC 2, NIST)",
    "Data classification (personal, sensitive, financial, health data)",
    "Data residency / localisation requirements",
    "Data retention & deletion rules",
    "Access control & authentication (SSO, MFA, RBAC)",
    "Audit trail & logging requirements",
))

QUESTIONS = [
    {"id": "q_problem", "cat": "Background", "sec": "1.1 / 4.1",
     "q": "What problem does this project solve? Describe the current process, "
          "who does it, what tools are used, and what breaks down.",
     "maps_to": ["project_background", "challenges"], "required": True},

    {"id": "q_objective", "cat": "Background", "sec": "1.2 / 4.2",
     "q": "What should the system achieve after go-live? List goals and the "
          "KPIs or targets that will measure success.",
     "maps_to": ["objective", "to_be"], "required": True},

    {"id": "q_inscope", "cat": "Scope", "sec": "2.1",
     "q": "What will this phase deliver (In Scope)? List all modules, features, "
          "user types, and locations included.",
     "maps_to": ["in_scope"], "required": True},

    {"id": "q_outscope", "cat": "Scope", "sec": "2.2",
     "q": "What is Out of Scope or excluded? List features, integrations, or "
          "capabilities NOT part of this phase.",
     "maps_to": ["out_scope"], "required": True},

    {"id": "q_users", "cat": "Functional", "sec": "5.1 / 9",
     "q": "List each user role, what they do in the system, and what they are "
          "responsible for.",
     "maps_to": ["functional", "roles"], "required": True,
     "input": "rows", "row_fields": ["Role", "Description"],
     "access_field": True},

    {"id": "q_features", "cat": "Functional", "sec": "4.3 / 5.1",
     "q": "List each feature or module, what it does, and its business purpose. "
          "Include dashboards, alerts, reports, and exports.",
     "maps_to": ["proposed", "functional"], "required": True,
     "input": "rows", "row_fields": ["Feature", "Description"]},

    {"id": "q_systems", "cat": "Integration", "sec": "3.2 / 8",
     "q": "List each system to connect to, what data flows in/out, and whether "
          "it is real-time or batch. Write 'None' if standalone.",
     "maps_to": ["if_software", "integrations"], "required": True,
     "input": "rows", "row_fields": ["System", "Description"],
     "allow_none": True},

    {"id": "q_regs", "cat": "Compliance", "sec": "3.4 / 5.2",
     "q": "Describe the regulatory, security and data-protection requirements "
          "that apply to this application.",
     "maps_to": ["if_security", "non_functional"], "required": False,
     "optional_note": "Optional -- leave blank if no regulatory or compliance "
                      "requirements apply. Do not enter N/A.",
     "template": COMPLIANCE_TEMPLATE},

    {"id": "q_tech", "cat": "Technical", "sec": "3.1 / 3.3 / 3.5",
     "q": "List each technical component — deployment model, devices, "
          "tech stack, data formats, and communication channels.",
     "maps_to": ["if_hardware", "if_data", "if_comm"], "required": True,
     "input": "rows", "row_fields": ["Component", "Description"]},

    {"id": "q_nonfunc", "cat": "Technical", "sec": "5.2",
     "q": "Specify concurrent users, uptime %, response times, DR targets "
          "(RTO/RPO), data retention, and scalability expectations.",
     "maps_to": ["non_functional"], "required": True},
]

# --------------------------------------------------------------------------
# Optional detail fields, grouped by the template section they populate.
# These are AUTO-DERIVED from the 11 core questions by inference.py.
# If the user manually provides a detail field, their value overrides
# the inferred value.
# --------------------------------------------------------------------------

DETAIL_FIELDS = {
    "External Interfaces": [
        {"key": "d_if_hardware", "label": "Hardware interfaces (devices, scanners, on-prem kit)"},
        {"key": "d_if_software", "label": "Software interfaces (components, versions, databases, libraries)"},
        {"key": "d_if_data", "label": "Data interfaces (formats, transfer mechanism, encryption)"},
        {"key": "d_if_security", "label": "Security interfaces (SSO/SAML, MFA, authorization model)"},
        {"key": "d_if_comm", "label": "Communication interfaces (email, protocols, network)"},
    ],
    "As-Is / To-Be": [
        {"key": "d_challenges", "label": "Existing challenges (As-Is) — one per line"},
        {"key": "d_to_be", "label": "To-Be process (how it should work after go-live)"},
        {"key": "d_proposed", "label": "Proposed solution / system (architecture in plain words)"},
    ],
    # Edited as a table (see DETAIL_TABLES), not as free-text fields.
    "Non-Functional": [],
    "Prototype": [
        {"key": "d_prototype", "label": "Prototype / mock-ups shared with the client"},
    ],
}

# Detail groups that are edited as a template table instead of text fields.
DETAIL_TABLES = {"Non-Functional": "non_functional_requirements"}

# Detail groups that also take screenshot uploads (rendered under the
# "System Screenshots" subheading of that section).
DETAIL_SCREENSHOTS = {"Prototype"}

# --------------------------------------------------------------------------
# Tables that exist in the house template, with the exact column headers.
#   id_col  : the template's leading auto-numbered column (Sr. No / ID / BR#)
#   prefix  : ID format for that column ("" means plain 1, 2, 3 ...)
#   section : OUTLINE id the table is rendered under
#   anchor  : phrases used to find the same table in an UPLOADED .docx
#             template (matched case-insensitively against the heading
#             before the table). More specific anchors must come first.
#   seed    : rows the house template ships with, kept unless overridden
# --------------------------------------------------------------------------

TABLE_SPECS = [
    {"id": "version_history", "name": "Version History", "section": "_doc_control",
     "id_col": "Sr. No", "prefix": "",
     "cols": ["Version", "Date", "Author", "Description of Change", "Section Changed", "Reviewed By"],
     "anchor": ["version history"], "seed": []},

    {"id": "approval_matrix", "name": "Approval Matrix", "section": "_doc_control",
     "id_col": "Sr. No", "prefix": "",
     "cols": ["Version", "Approver Name", "Designation", "Approval Date", "Remarks if any"],
     "anchor": ["approval matrix"], "seed": []},

    {"id": "distribution_list", "name": "Distribution List", "section": "_distribution",
     "id_col": "Sr. No", "prefix": "",
     "cols": ["Name (First & Last Name)", "Designation", "Function"],
     "anchor": ["distribution list"], "seed": []},

    {"id": "functional_requirements", "name": "Functional Requirements", "section": "functional",
     "id_col": "BR#", "prefix": "FR-",
     "cols": ["Module", "Business requirement", "Requirement Description", "Remarks if any"],
     "anchor": ["functional requirements"], "seed": []},

    {"id": "non_functional_requirements", "name": "Non-Functional Requirements",
     "section": "non_functional", "id_col": "Sr. No", "prefix": "",
     "cols": ["Business Requirement", "Business Requirement Description",
              "Requirement Type", "Remarks if any"],
     "anchor": ["non-functional requirements", "non functional requirements"], "seed": []},

    {"id": "open_items", "name": "Open Item List", "section": "open_item_list",
     "id_col": "OI#", "prefix": "OI-",
     "cols": ["Agenda", "Current Status", "Description", "Owner/Stakeholder Responsible",
              "Expected date of closure", "Impact if not Closed", "Remarks if any"],
     "anchor": ["open item list"], "seed": []},

    {"id": "open_item_declaration", "name": "Open Item Declaration", "section": "open_item_decl",
     "id_col": "Sr. No", "prefix": "",
     "cols": ["Name (First & Second Name)", "Designation", "Attachment", "Remarks If any"],
     "anchor": ["open item declaration"], "seed": []},

    {"id": "change_log", "name": "Change Control Log", "section": "change_log",
     "id_col": "Change ID", "prefix": "CH-",
     "cols": ["CR No. # if any", "Description", "Date", "Approved By", "Remarks if any"],
     "anchor": ["change control log"], "seed": []},

    {"id": "integrations", "name": "Integrations", "section": "integrations",
     "id_col": "Sr. No", "prefix": "",
     "cols": ["External System", "Type of Integration", "Manufacturer/Agency", "Method/Protocol",
              "Security Consideration if any", "Status", "Remarks If any"],
     "anchor": ["integrations"], "seed": []},

    {"id": "roles_responsibilities", "name": "Roles & Responsibilities", "section": "roles",
     "id_col": "Sr. No", "prefix": "",
     "cols": ["Area", "Details"],
     "anchor": ["roles involved in this project", "role & responsibilities"], "seed": []},

    {"id": "assumptions", "name": "Assumptions", "section": "assumptions",
     "id_col": "ID", "prefix": "A-",
     "cols": ["Assumption", "Remarks if any"],
     "anchor": ["assumptions"], "seed": []},

    {"id": "dependencies", "name": "Dependencies", "section": "dependencies",
     "id_col": "ID", "prefix": "D-",
     "cols": ["Dependencies", "Remarks if any"],
     "anchor": ["dependencies"], "seed": []},

    {"id": "constraints", "name": "Constraints", "section": "constraints",
     "id_col": "ID", "prefix": "C-",
     "cols": ["Constraints", "Remarks if any"],
     "anchor": ["constraints"], "seed": []},

]

# The wizard's "add table" presets are the same specs.
TABLE_PRESETS = [{"id": s["id"], "name": s["name"], "cols": s["cols"], "anchor": s["anchor"],
                  "section": s["section"], "id_col": s["id_col"]} for s in TABLE_SPECS]

TABLE_SPEC_BY_ID = {s["id"]: s for s in TABLE_SPECS}
TABLE_SPEC_BY_NAME = {s["name"].strip().lower(): s for s in TABLE_SPECS}

# Anchor phrases for the plain in-scope / out-of-scope placeholder
# paragraphs (not tables) in an uploaded template.
SCOPE_ANCHORS = {
    "q_inscope": ["in scope of the project"],
    "q_outscope": ["out of scope of the project", "not in scope of the project"],
}

# --------------------------------------------------------------------------
# Section 9 reference content, lifted from the house template.
# --------------------------------------------------------------------------

RACIS_LEGEND = [
    ["R", "Responsible", "Person(s) who do the work"],
    ["A", "Accountable", "Person who owns the outcome"],
    ["C", "Consulted", "Subject matter experts"],
    ["I", "Informed", "Kept in the loop"],
    ["S", "Supportive", "Provides resources or help"],
]

ROLE_PRESETS = {
    "Non-AI project": [
        ["Project Manager (PM)", "Oversees project execution, timelines, and budget"],
        ["Business Analyst (BA)", "Gathers and documents requirements"],
        ["Development Team", "Implements features, infrastructure, and deliveries"],
        ["Infrastructure Lead", "Designs and implements infrastructure components"],
        ["Security Lead", "Ensures compliance and security controls"],
        ["QA Lead", "Manages testing and validation"],
        ["Sponsor & Stakeholders", "Sponsors the budget and marks approval of deliverables"],
    ],
    "AI project": [
        ["AI Provider \u2013 Core AI Provider",
         "Supplies the core AI engine or foundational model used as a base for customization "
         "or fine-tuning"],
        ["AI Provider \u2013 Platform Provider",
         "Provides technical infrastructure for model training, hosting, and orchestration "
         "(e.g. cloud platform, ML Ops tooling)"],
        ["AI Provider \u2013 Product Provider",
         "Delivers packaged AI functionality aligned to specific business use cases "
         "(e.g. pre-built model with domain UI/UX)"],
        ["AI Provider \u2013 Service Provider",
         "Supports customization, deployment, monitoring, and managed services related to the "
         "AI solution"],
        ["AI Producer",
         "Accountable for the overall model development lifecycle; defines business needs and "
         "oversees training, validation, and improvements"],
        ["AI Developer",
         "Performs data engineering, feature development, model design, implementation, "
         "validation, and documentation"],
        ["AI Customer",
         "Internal or external function that commissions, procures, or directly benefits from "
         "the AI system"],
        ["AI User",
         "End users of the AI system who interact with it directly or rely on its outputs "
         "(e.g. staff, customers, partners)"],
    ],
}

# AI stakeholder role mapping table (house template, \u00a79 "For AI Project")
AI_ROLE_MAPPING = [
    ["AI Provider", "Core AI Provider",
     "Supplies the core AI engine or foundational model used as a base for customization or fine-tuning"],
    ["AI Provider", "Platform Provider",
     "Provides technical infrastructure for model training, hosting, and orchestration "
     "(e.g. cloud platform, ML Ops tooling)"],
    ["AI Provider", "Product Provider",
     "Delivers packaged AI functionality aligned to specific business use cases "
     "(e.g. pre-built model with domain UI/UX)"],
    ["AI Provider", "Service Provider",
     "Supports customization, deployment, monitoring, and managed services related to the AI solution"],
    ["AI Producer", "AI Producer",
     "Accountable for the overall model development lifecycle; defines business needs and oversees "
     "training, validation, and improvements"],
    ["AI Producer", "AI Developer",
     "Performs data engineering, feature development, model design, implementation, validation, "
     "and documentation"],
    ["AI Customer", "AI Customer",
     "Internal or external function that commissions, procures, or directly benefits from the AI system"],
    ["AI User", "AI User",
     "End users of the AI system who interact with it directly or rely on its outputs "
     "(e.g. staff, customers, partners)"],
]

RACI_PRESETS = {
    "General / Waterfall IT project": {
        "roles": ["Project Manager", "Business Analyst", "Infra Lead", "Security Lead", "Sponsor"],
        "rows": [
            ["Requirements gathering", "A", "R", "I", "C", "I"],
            ["Solution design", "A", "C", "R", "C", "I"],
            ["Build & configuration", "A", "C", "R", "C", "I"],
            ["Testing & UAT", "A", "R", "S", "C", "I"],
            ["Go-live & sign-off", "R", "C", "S", "C", "A"],
        ]},
    "Agile application development (Scrum)": {
        "roles": ["Product Owner", "Scrum Master", "Developers", "QA Lead", "UX Designer"],
        "rows": [
            ["Requirements Gathering", "A", "C", "I", "I", "I"],
            ["UI/UX Design", "I", "I", "I", "I", "R"],
            ["Development", "I", "I", "R", "I", "I"],
            ["Testing", "I", "I", "I", "R", "I"],
            ["Deployment", "I", "I", "R", "I", "I"],
            ["Sprint Review", "R", "A", "I", "I", "I"],
        ]},
    "AI / GenAI project": {
        "roles": ["AI Producer", "AI Developer", "AI Provider", "AI Customer", "AI User"],
        "rows": [
            ["Use case definition", "A", "C", "I", "R", "C"],
            ["Data sourcing & preparation", "A", "R", "S", "C", "I"],
            ["Model development & tuning", "A", "R", "S", "I", "I"],
            ["Validation & bias testing", "A", "R", "C", "C", "I"],
            ["Deployment & monitoring", "A", "R", "S", "I", "I"],
            ["Business acceptance", "C", "I", "I", "A", "R"],
        ]},
    "Infrastructure & security project": {
        "roles": ["Project Manager", "Security Lead", "Infra Lead", "Product Owner/Sponsor", "DevOps"],
        "rows": [
            ["Define Requirements", "R", "C", "C", "A", "I"],
            ["Firewall Setup", "I", "A", "R", "I", "S"],
            ["Cloud Provisioning", "I", "C", "A", "I", "R"],
            ["Security Policy Review", "I", "R", "C", "C", "I"],
            ["Backup Configuration", "I", "C", "R", "I", "A"],
            ["Final Sign-Off", "R", "C", "C", "A", "I"],
        ]},
    "Research project": {
        "roles": ["Principal Investigator", "Research Analyst", "Data Scientist",
                   "Ethics Reviewer", "Project Coordinator"],
        "rows": [
            ["Literature Review", "A", "R", "C", "I", "S"],
            ["Research Design", "A", "R", "C", "C", "S"],
            ["Data Collection", "I", "R", "C", "I", "S"],
            ["Data Analysis", "I", "C", "R", "I", "S"],
            ["Ethics Approval", "I", "C", "I", "A", "S"],
            ["Report Writing", "I", "C", "I", "I", "S"],
        ]},
}

OPEN_ITEM_DECLARATION = (
    "Declaration Statement: This BRD is approved with the understanding that the items listed in "
    "the \u201cOpen Items\u201d section are pending and will be addressed in subsequent revisions or "
    "change requests. These items are not expected to materially impact the overall scope or timeline."
)

SCOPE_NOTE = ("Note: Extension in existing scope, if any, is to be tracked separately with "
              "appropriate approvals.")

CHANGE_LOG_NOTE = (
    "Any changes resulting from the open items should be handled through a formal change request "
    "or addendum to the BRD and will be managed under a change request. Minor updates are recorded "
    "in this log; major changes to scope, budget or timeline are handled via a separate formal "
    "Change Request document, with the CR number referenced here for traceability."
)

OPEN_ITEM_NOTE = ("Note: Open points need to be closed for deriving complete scope and may impact "
                  "overall effort estimates.")

# --------------------------------------------------------------------------
# Readiness rules: which intake keys make each template section "ready".
# Sections driven purely by user-entered tables carry no rule (N/A).
# --------------------------------------------------------------------------

MVI_RULES = {
    "project_background": ["q_problem"],
    "objective": ["q_objective"],
    "intended_audience": [],
    "in_scope": ["q_inscope"],
    "out_scope": ["q_outscope"],
    "if_hardware": ["q_tech", "d_if_hardware"],
    "if_software": ["q_systems", "d_if_software"],
    "if_data": ["q_tech", "d_if_data"],
    "if_security": ["q_regs", "d_if_security"],
    "if_comm": ["q_tech", "d_if_comm"],
    "challenges": ["q_problem", "d_challenges"],
    "to_be": ["q_objective", "d_to_be"],
    "proposed": ["q_features", "d_proposed"],
    "functional": ["q_features", "q_users"],
    "non_functional": ["q_nonfunc"],
    "open_item_list": [],
    "open_item_decl": [],
    "change_log": [],
    "integrations": ["q_systems"],
    "roles": ["q_users"],
    "assumptions": [],
    "dependencies": [],
    "constraints": [],
    "prototype": ["d_prototype"],
    "process_flow_diagrams": [],
}

# rule-based "what to ask the client next" bank, with priority
GAP_QUESTIONS = {
    "q_problem": ("High", "What is the business problem, and how does the process run today?"),
    "q_objective": ("High", "What will be different after go-live, and how will success be measured?"),
    "q_inscope": ("High", "What is explicitly in scope for this phase -- which modules, entities and locations?"),
    "q_outscope": ("High", "What is explicitly out of scope or deferred to a later phase?"),
    "q_users": ("High", "Who are the user roles and what does each need to do in the system?"),
    "q_features": ("High", "What are the must-have features, reports and outputs for this phase?"),
    "q_systems": ("High", "Which systems must this solution integrate with, and who owns each one?"),
    "q_regs": ("High", "Which specific regulations apply, and are there hard compliance deadlines?"),
    "q_tech": ("Medium", "What is the technical setup -- deployment model, devices, data formats, protocols?"),
    "q_nonfunc": ("Medium", "What performance, uptime/DR and scalability expectations should the system meet?"),
}

# --------------------------------------------------------------------------
# Live NFR coverage checklist -- regex patterns matched against q_nonfunc
# text to show the user which NFR topics they have covered.
# --------------------------------------------------------------------------

NFR_CHECKLIST = [
    {"id": "uptime",       "label": "Uptime / Availability %",
     "pattern": r"uptime|\d{2,3}\s*%|availability|nine.?nine"},
    {"id": "response_time","label": "Response time / Latency",
     "pattern": r"response\s*time|latency|page\s*load|\d+\s*ms|\d+\s*seconds?"},
    {"id": "rpo_rto",      "label": "RPO / RTO / DR",
     "pattern": r"rpo|rto|disaster\s*recover|failover|backup|business\s*continuity"},
    {"id": "throughput",   "label": "Throughput / TPS",
     "pattern": r"throughput|tps|transactions?\s*per|batch\s*window|processing\s*time"},
    {"id": "scalability",  "label": "Scalability / Concurrency",
     "pattern": r"scal|concurrent|concurrency|peak\s*load|auto.?scale|capacity|elastic"},
    {"id": "data_retention","label": "Data retention / Archival",
     "pattern": r"retention|archiv|purge|data\s*lifecycle|storage\s*period"},
]
