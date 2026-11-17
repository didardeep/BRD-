"""
generate_user_manual.py
Run this script once to produce BRD_Studio_User_Manual.docx in the same folder.
Usage:  python generate_user_manual.py
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import datetime

# ── Brand colours ──────────────────────────────────────────────────────────
KPMG_BLUE  = RGBColor(0x00, 0x33, 0x8D)   # #00338D
KPMG_TEAL  = RGBColor(0x00, 0x7A, 0x87)   # #007A87
DARK_TEXT  = RGBColor(0x1A, 0x1A, 0x2E)
LIGHT_GRAY = RGBColor(0xF5, 0xF5, 0xF5)
MID_GRAY   = RGBColor(0x66, 0x66, 0x66)

# ── Helpers ─────────────────────────────────────────────────────────────────

def set_cell_bg(cell, hex_color: str):
    """Fill a table cell with a solid background colour."""
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def add_horizontal_rule(doc):
    """Insert a thin blue horizontal rule paragraph."""
    p    = doc.add_paragraph()
    pPr  = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bot  = OxmlElement("w:bottom")
    bot.set(qn("w:val"),   "single")
    bot.set(qn("w:sz"),    "6")
    bot.set(qn("w:space"), "1")
    bot.set(qn("w:color"), "00338D")
    pBdr.append(bot)
    pPr.append(pBdr)
    p.paragraph_format.space_after = Pt(6)
    return p


def heading1(doc, text):
    p = doc.add_heading(text, level=1)
    run = p.runs[0] if p.runs else p.add_run(text)
    run.font.color.rgb = KPMG_BLUE
    run.font.size      = Pt(16)
    run.font.bold      = True
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after  = Pt(6)
    add_horizontal_rule(doc)
    return p


def heading2(doc, text):
    p = doc.add_heading(text, level=2)
    run = p.runs[0] if p.runs else p.add_run(text)
    run.font.color.rgb = KPMG_TEAL
    run.font.size      = Pt(13)
    run.font.bold      = True
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after  = Pt(4)
    return p


def heading3(doc, text):
    p = doc.add_heading(text, level=3)
    run = p.runs[0] if p.runs else p.add_run(text)
    run.font.color.rgb = DARK_TEXT
    run.font.size      = Pt(11)
    run.font.bold      = True
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after  = Pt(2)
    return p


def body(doc, text, bold_prefix=None):
    """Normal body paragraph.  If bold_prefix given, that part is bolded."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    if bold_prefix:
        run = p.add_run(bold_prefix)
        run.bold           = True
        run.font.color.rgb = DARK_TEXT
        run.font.size      = Pt(10.5)
        rest = p.add_run(text)
        rest.font.size     = Pt(10.5)
    else:
        run = p.add_run(text)
        run.font.size      = Pt(10.5)
        run.font.color.rgb = DARK_TEXT
    return p


def bullet(doc, text, level=0, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent  = Inches(0.25 + level * 0.25)
    p.paragraph_format.space_after  = Pt(3)
    if bold_prefix:
        r1 = p.add_run(bold_prefix)
        r1.bold           = True
        r1.font.size      = Pt(10.5)
        r1.font.color.rgb = DARK_TEXT
        r2 = p.add_run(text)
        r2.font.size      = Pt(10.5)
    else:
        run = p.add_run(text)
        run.font.size      = Pt(10.5)
        run.font.color.rgb = DARK_TEXT
    return p


def numbered(doc, text, level=0):
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.left_indent = Inches(0.25 + level * 0.25)
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    run.font.size      = Pt(10.5)
    run.font.color.rgb = DARK_TEXT
    return p


def note_box(doc, text):
    """A shaded callout paragraph."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.style = "Table Grid"
    cell = tbl.cell(0, 0)
    set_cell_bg(cell, "E8F4FD")
    cell.paragraphs[0].clear()
    p   = cell.paragraphs[0]
    run = p.add_run("ℹ  " + text)
    run.font.size      = Pt(10)
    run.font.italic    = True
    run.font.color.rgb = RGBColor(0x00, 0x33, 0x8D)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(4)
    doc.add_paragraph()   # spacer


def two_col_table(doc, rows, header_row=None):
    """
    rows: list of (col1, col2) tuples.
    header_row: optional (h1, h2) for header.
    """
    n = len(rows) + (1 if header_row else 0)
    tbl = doc.add_table(rows=n, cols=2)
    tbl.style = "Table Grid"
    ri = 0
    if header_row:
        for ci, txt in enumerate(header_row):
            cell = tbl.cell(ri, ci)
            set_cell_bg(cell, "00338D")
            cell.paragraphs[0].clear()
            run = cell.paragraphs[0].add_run(txt)
            run.bold           = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            run.font.size      = Pt(10)
        ri += 1
    for i, (c1, c2) in enumerate(rows):
        bg = "F5F5F5" if i % 2 == 0 else "FFFFFF"
        for ci, txt in enumerate((c1, c2)):
            cell = tbl.cell(ri, ci)
            set_cell_bg(cell, bg)
            cell.paragraphs[0].clear()
            run = cell.paragraphs[0].add_run(txt)
            run.font.size      = Pt(10)
            run.font.color.rgb = DARK_TEXT
        ri += 1
    doc.add_paragraph()


# ═══════════════════════════════════════════════════════════════════════════
# DOCUMENT
# ═══════════════════════════════════════════════════════════════════════════

doc = Document()

# ── Page margins ────────────────────────────────────────────────────────────
for section in doc.sections:
    section.top_margin    = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin   = Cm(2.5)
    section.right_margin  = Cm(2.5)

# ── Default font ────────────────────────────────────────────────────────────
style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(10.5)

# ────────────────────────────────────────────────────────────────────────────
# COVER PAGE
# ────────────────────────────────────────────────────────────────────────────
doc.add_paragraph("\n\n\n")

title_p = doc.add_paragraph()
title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title_p.add_run("BRD Creation Platform")
r.font.name  = "Calibri"
r.font.size  = Pt(28)
r.font.bold  = True
r.font.color.rgb = KPMG_BLUE

sub_p = doc.add_paragraph()
sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub_p.add_run("User Manual")
r.font.name  = "Calibri"
r.font.size  = Pt(18)
r.font.color.rgb = KPMG_TEAL

doc.add_paragraph("\n")

info_p = doc.add_paragraph()
info_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = info_p.add_run(f"Version 1.0   ·   {datetime.date.today().strftime('%B %Y')}")
r.font.size      = Pt(11)
r.font.color.rgb = MID_GRAY

doc.add_paragraph("\n\n")

conf_p = doc.add_paragraph()
conf_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = conf_p.add_run("KPMG — Internal Use Only")
r.font.size      = Pt(10)
r.font.italic    = True
r.font.color.rgb = MID_GRAY

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# TABLE OF CONTENTS (static)
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "Table of Contents")

toc = [
    ("1.   Overview",                          "3"),
    ("2.   Getting Started",                   "3"),
    ("3.   Application Layout",                "4"),
    ("4.   Step 0 — Project Details",          "5"),
    ("5.   Step 1 — Core Questions",           "7"),
    ("6.   Step 2 — Detail Fields",            "10"),
    ("7.   Step 3 — Template Tables",          "12"),
    ("8.   Step 4 — Create Document",          "14"),
    ("9.   Top Bar Features",                  "15"),
    ("10.  Save Draft & Projects",             "17"),
    ("11.  Uploading a Custom Template",       "18"),
    ("12.  Flowchart Editor (Annexure 12.2)",  "19"),
    ("13.  Keyboard Shortcuts & Tips",         "20"),
    ("14.  Frequently Asked Questions",        "21"),
]
two_col_table(doc, toc, header_row=("Section", "Page"))

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 1. OVERVIEW
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "1.  Overview")

body(doc, (
    "The BRD Creation Platform is a browser-based wizard that guides you through "
    "the end-to-end creation of a Business Requirements Document (BRD) aligned to "
    "the KPMG house template.  It collects project metadata, functional requirements, "
    "technical specifications, compliance obligations, and supporting tables, then "
    "assembles everything into a professionally formatted Word (.docx) file with one click."
))

body(doc, "Key benefits:")
bullet(doc, "Structured, step-by-step guidance — no blank page to start from.")
bullet(doc, "Auto-fill from an existing RFP or notes document.")
bullet(doc, "Smart people-search for Sponsor, Prepared By, and Reviewed By fields.")
bullet(doc, "Auto-derived detail fields reduce repetitive typing.")
bullet(doc, "Built-in flowchart editor for As-Is / To-Be process diagrams.")
bullet(doc, "Full draft saving and multi-project workspace management.")
bullet(doc, "One-click creation of a fully formatted KPMG-standard .docx file.")

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 2. GETTING STARTED
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "2.  Getting Started")

heading2(doc, "2.1  Starting the Application")
numbered(doc, "Open a terminal / command prompt in the brd_studio folder.")
numbered(doc, "Run:  python app.py")
numbered(doc, "Open a web browser and navigate to:  http://localhost:5050")
note_box(doc, "The application runs entirely on your local machine.  No internet connection is required after the first load.")

heading2(doc, "2.2  First-Time Setup")
body(doc, (
    "On first launch, a blank wizard opens.  You will be prompted with a loading screen "
    "while the application initialises.  If a previously saved draft is found in your browser, "
    "it will be loaded automatically."
))
note_box(doc, (
    "To enable the people-search feature (Sponsor, Prepared By, Reviewed By), place an "
    "employee directory Excel file (.xlsx) containing EmployeeName and EmailId columns "
    "inside the  name_list/  folder, then open:  http://localhost:5050/api/namelist/rebuild"
))

heading2(doc, "2.3  Workflow at a Glance")
two_col_table(doc,
    [
        ("Step 0", "Fill in project cover-page details (name, client, dates, sponsor)."),
        ("Step 1", "Answer the 10 core requirement questions."),
        ("Step 2", "Review and refine the auto-derived detail fields."),
        ("Step 3", "Populate or review the standard template tables."),
        ("Step 4", "Click Create Document to generate your .docx file."),
    ],
    header_row=("Step", "What you do"),
)

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 3. APPLICATION LAYOUT
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "3.  Application Layout")

body(doc, (
    "The application is divided into three main areas: the Top Bar, the Left Rail, "
    "and the Main Content Area."
))

heading2(doc, "3.1  Top Bar")
body(doc, "The dark-blue bar at the top of every page contains:")
two_col_table(doc,
    [
        ("KPMG Logo / Product Name", "Branding — always visible."),
        ("Progress Bar",             "Shows how many fields are filled out of the total.  Turns green as you complete more fields."),
        ("Upload RFP",               "Upload an existing RFP/notes document to auto-fill your answers."),
        ("Sample BRD",               "Preview or download the KPMG in-house BRD sample document as a reference."),
        ("Save Draft",               "Save your current work to browser storage instantly."),
        ("Projects",                 "Open, save, or switch between multiple named BRD projects."),
        ("Clear",                    "Discard all current data and start from scratch (asks for confirmation)."),
    ],
    header_row=("Button", "Purpose"),
)

heading2(doc, "3.2  Left Rail")
body(doc, (
    "The dark sidebar on the left shows the five steps.  Each step has:"
))
bullet(doc, "A numbered circle (turns to a green ✓ when the step is complete).")
bullet(doc, "A step title and short description.")
bullet(doc, "A chevron (›) you can click to expand sub-items and jump directly to a section.")
body(doc, (
    "Sub-items appear when you expand a step: for example, Step 1 shows the question "
    "categories (Background, Scope, Functional, etc.) as clickable links."
))

heading2(doc, "3.3  Main Content Area")
body(doc, (
    "The large white area on the right displays the current step's content.  "
    "Use the Next and Back buttons at the bottom of each step to move through the wizard, "
    "or click any step in the Left Rail to jump directly."
))

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 4. STEP 0 — PROJECT DETAILS
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "4.  Step 0 — Project Details")

body(doc, (
    "This step captures the cover-page and document control information that appears "
    "at the front of your BRD."
))

heading2(doc, "4.1  Project Information")
two_col_table(doc,
    [
        ("Project Name",   "The official name of the project or initiative.  Required."),
        ("Client / Entity","The client organisation or business unit.  Required."),
        ("Industry",       "Select the relevant industry from the drop-down list (e.g., Banking & Financial Services, Healthcare, Telecom).  Required."),
        ("Project Type",   "Choose 'AI project' or 'Non-AI project'.  This affects which sections are included.  Required."),
        ("Project Sponsor","The name of the person sponsoring the project.  Supports people-search (see §4.3).  Required."),
    ],
    header_row=("Field", "Description"),
)

heading2(doc, "4.2  Dates & Version")
two_col_table(doc,
    [
        ("Document Version",   "Version number of this BRD (e.g., 1.0).  Required."),
        ("Document Date",      "Date this version was prepared.  Required."),
        ("Project Start Date", "Planned or actual project start date.  Required."),
        ("Target Go-Live Date","Expected go-live date.  Required."),
        ("Prepared By",        "Name of the person who prepared the document.  Supports people-search."),
        ("Reviewed By",        "Name of the reviewer.  Supports people-search."),
    ],
    header_row=("Field", "Description"),
)

heading2(doc, "4.3  People-Search (Sponsor / Prepared By / Reviewed By)")
body(doc, (
    "These three fields have a smart autocomplete dropdown.  "
    "Start typing a name or email address — after a short pause, a list of matching "
    "employees appears."
))
bullet(doc, "Use the ↑ / ↓ arrow keys to move through the list.")
bullet(doc, "Press Enter or click a name to select it.")
bullet(doc, "Press Escape to close the dropdown without selecting.")
bullet(doc, "For the Sponsor field, the person's designation is appended automatically.")
note_box(doc, (
    "If no dropdown appears, the employee directory may not be loaded.  "
    "Ask your administrator to place the correct Excel file in the name_list/ folder "
    "and visit /api/namelist/rebuild."
))

heading2(doc, "4.4  Project Description")
body(doc, (
    "A free-text area for a high-level description of the project.  "
    "You can use the microphone icon to dictate the text instead of typing."
))

heading2(doc, "4.5  Regulations (Compliance Picker)")
body(doc, (
    "Once you select an Industry, a set of commonly applicable regulations is shown "
    "automatically (for example, selecting Banking shows RBI Master Directions, SOX, Basel III)."
))
bullet(doc, "Tick the checkbox next to each applicable regulation.")
bullet(doc, "Optionally type a note alongside each regulation (e.g., specific clause reference).")
bullet(doc, "Use the 'Other' text box to add regulations not in the pre-populated list.")

heading2(doc, "4.6  Microphone / Voice Input")
body(doc, (
    "Every text field and textarea has a small microphone icon.  "
    "Click it and speak; your speech is converted to text and inserted into the field.  "
    "Click again to stop recording."
))
note_box(doc, "Microphone access requires the browser to have permission to use your device's microphone.  If prompted, click Allow.")

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 5. STEP 1 — CORE QUESTIONS
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "5.  Step 1 — Core Questions")

body(doc, (
    "Step 1 contains ten structured questions that form the backbone of your BRD.  "
    "They are grouped into seven categories visible in the Left Rail."
))

heading2(doc, "5.1  Question Categories")
two_col_table(doc,
    [
        ("Background",   "q_problem — describe the current process and problems.\nq_objective — state the goals and KPIs for success."),
        ("Scope",        "q_inscope — list what is in scope (modules, features, locations).\nq_outscope — list what is out of scope or deferred."),
        ("Functional",   "q_users — roles and responsibilities (table format).\nq_features — features, modules, dashboards, alerts (table format)."),
        ("Integration",  "q_systems — systems to integrate, data flow, real-time vs. batch (table format)."),
        ("Compliance",   "q_regs — regulations, standards, retention rules (uses the Regulation Picker from Step 0)."),
        ("Technical",    "q_tech — deployment model, devices, tech stack, data formats, protocols (table format).\nq_nonfunc — concurrent users, uptime %, response times, RTO/RPO, scalability."),
        ("Custom",       "Any additional questions you add yourself (see §5.4)."),
    ],
    header_row=("Category", "Questions"),
)

heading2(doc, "5.2  Table-Format Questions")
body(doc, (
    "Questions for Roles (q_users), Features (q_features), Integrations (q_systems), "
    "and Technical Components (q_tech) use a two-column table interface:"
))
bullet(doc, "Each row has a Label column and a Description column.")
bullet(doc, "Click the pencil icon to enter edit mode.")
bullet(doc, "Click + Add Row to add more entries.")
bullet(doc, "Click the × icon on any row to delete it.")
bullet(doc, "Click the save/lock icon to confirm your edits.")

heading2(doc, "5.3  Non-Functional Requirements Coverage Checker")
body(doc, (
    "As you type in the q_nonfunc field, the platform tracks how many of the six "
    "standard NFR categories you have covered:"
))
two_col_table(doc,
    [
        ("Uptime %",               "e.g., 99.9% availability"),
        ("Response Time / ms",     "e.g., page load < 2 seconds"),
        ("RPO / RTO / DR",         "Disaster Recovery targets"),
        ("Throughput / TPS",       "Transactions per second"),
        ("Scalability / Concurrency", "User volumes and scaling strategy"),
        ("Data Retention",         "How long data must be kept"),
    ],
    header_row=("NFR Category", "Example"),
)
body(doc, "A counter such as '4 / 6 covered' appears below the field to guide you.")

heading2(doc, "5.4  Adding Custom Questions")
body(doc, (
    "Click the + Add Question button at the bottom of Step 1 (in the Custom category) "
    "to create your own question.  Enter a question label and provide your answer.  "
    "Custom questions are included in the generated document."
))

heading2(doc, "5.5  Markdown Preview")
body(doc, (
    "Each question has a small eye icon in its header.  "
    "Click it to toggle between the raw text editor and a formatted markdown preview.  "
    "This is useful for questions where you have used bullet points or headings."
))

heading2(doc, "5.6  Category Status Indicators")
body(doc, (
    "The Left Rail shows a coloured dot next to each category:"
))
bullet(doc, "Green dot — all questions in this category are answered.")
bullet(doc, "Orange dot — some questions are answered, some are empty.")
bullet(doc, "Grey dot — no questions in this category have been answered yet.")

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 6. STEP 2 — DETAIL FIELDS
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "6.  Step 2 — Detail Fields")

body(doc, (
    "Detail fields are automatically derived from your answers in Step 1.  "
    "You do not need to fill them in manually — the platform infers content for each field "
    "from what you have already typed.  However, you can override any field by typing directly "
    "into it."
))

heading2(doc, "6.1  Field Groups")
two_col_table(doc,
    [
        ("External Interfaces",
         "d_if_user — User interfaces (screens, GUI standards, accessibility).\n"
         "d_if_hardware — Hardware interfaces (devices, scanners, on-prem equipment).\n"
         "d_if_software — Software interfaces (components, databases, libraries).\n"
         "d_if_data — Data interfaces (formats, transfer mechanisms, encryption).\n"
         "d_if_security — Security interfaces (SSO, SAML, MFA, authorisation).\n"
         "d_if_comm — Communication interfaces (email, protocols, network)."),
        ("As-Is / To-Be",
         "d_challenges — Existing process challenges (one per line).\n"
         "d_to_be — Description of the future To-Be process.\n"
         "d_proposed — Proposed solution or system architecture."),
        ("Non-Functional",
         "d_performance — Performance SLAs (page load, batch window, API response).\n"
         "d_availability — Uptime, DR, RTO / RPO, and retention policy.\n"
         "d_security_nfr — Security requirements and audit trail obligations.\n"
         "d_scalability — Volume estimates and scalability expectations."),
        ("Prototype",
         "d_prototype — Description of any prototype or mock-ups shared with the client."),
    ],
    header_row=("Group", "Fields"),
)

heading2(doc, "6.2  Approving a Section")
body(doc, (
    "Each group has an Approve button.  When you are satisfied with the content, "
    "click Approve to lock the section.  Locked sections show a green ✓ Approved badge "
    "and all fields become read-only.  Click the lock icon to unlock and edit again."
))

heading2(doc, "6.3  Flowchart Editor Access")
body(doc, (
    "Inside the As-Is / To-Be section there is an Open Flowchart Editor button.  "
    "Click it to open the side drawer where you can create and edit process flow diagrams "
    "for Annexure 12.2.  See Section 12 of this manual for full details."
))

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 7. STEP 3 — TEMPLATE TABLES
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "7.  Step 3 — Template Tables")

body(doc, (
    "Step 3 contains all the structured tables defined in the KPMG house template.  "
    "Many cells are auto-populated from your earlier answers; you can review and edit them."
))

heading2(doc, "7.1  Standard Tables")
two_col_table(doc,
    [
        ("Version History",           "Records each version, date, author, and summary of changes."),
        ("Approval Matrix",           "Lists approvers by name, designation, and approval date.  People-search is available for Name fields."),
        ("Distribution List",         "Records who receives the document.  People-search is available for Name fields."),
        ("Functional Requirements",   "Structured list of business/functional requirements with BR numbers and module tags."),
        ("Non-Functional Requirements","Structured list of non-functional requirements with type classification."),
        ("Open Item List",            "Tracks open items with owner, expected closure date, and impact."),
        ("Open Item Declaration",     "Signatories who acknowledge the open items."),
        ("Change Control Log",        "Tracks change requests with CR number, description, and approver."),
        ("Integrations",              "Lists external systems, integration type, protocol, and security details."),
        ("Roles & Responsibilities",  "Documents each role and its responsibilities."),
        ("Assumptions",               "Numbered list of project assumptions."),
        ("Dependencies",              "Numbered list of project dependencies."),
        ("Constraints",               "Numbered list of project constraints."),
    ],
    header_row=("Table", "Purpose"),
)

heading2(doc, "7.2  Editing a Table")
numbered(doc, "Click the pencil icon next to a table to unlock it for editing.")
numbered(doc, "Click any cell to type into it.")
numbered(doc, "Click + Add Row to append a new row.")
numbered(doc, "Click the × on a row to delete it.")
numbered(doc, "Click the save icon to lock the table again.")

heading2(doc, "7.3  Adding Custom Tables")
body(doc, (
    "Scroll to the bottom of Step 3 and click + Add Custom Table.  "
    "Enter a table name, define your column headers, and add rows.  "
    "Custom tables are appended to the document after the standard tables."
))

heading2(doc, "7.4  Screenshots (Annexure 12.1)")
body(doc, (
    "Click the Screenshots tab in the Left Rail while on Step 3 to manage screenshots "
    "for Annexure 12.1."
))
bullet(doc, "Click Upload Screenshot to select image files from your computer.")
bullet(doc, "Each uploaded image shows a caption field below it — fill this in to describe the screenshot.")
bullet(doc, "Click the × on an image to remove it.")

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 8. STEP 4 — CREATE DOCUMENT
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "8.  Step 4 — Create Document")

body(doc, (
    "This is the final step.  The platform shows a readiness summary and lets you "
    "generate the formatted Word document."
))

heading2(doc, "8.1  Readiness Checklist")
body(doc, (
    "Before generating, a checklist shows the completion percentage for each step:"
))
bullet(doc, "Project Details — cover-page fields filled.")
bullet(doc, "Core Questions — ten core questions answered.")
bullet(doc, "Detail Fields — optional detail fields reviewed.")
bullet(doc, "Template Tables — standard tables populated.")
body(doc, (
    "A Review → link next to each item takes you directly back to that step "
    "so you can fill in any gaps."
))

heading2(doc, "8.2  Options Before Generating")
two_col_table(doc,
    [
        ("Include diagnostics annexure",
         "Tick this checkbox to append a diagnostics section to the document showing "
         "readiness scores and any unanswered questions.  Useful for internal review."),
    ],
    header_row=("Option", "Description"),
)

heading2(doc, "8.3  Creating the Document")
numbered(doc, "Click the Create Document (.docx) button.")
numbered(doc, "Wait a few seconds while the document is assembled on the server.")
numbered(doc, "A Download .docx link appears.  Click it to save the file to your computer.")
note_box(doc, "The document is generated fresh each time you click the button, incorporating any changes you have made since the last build.")

heading2(doc, "8.4  Preview")
body(doc, (
    "After a successful build, the Preview button becomes active.  "
    "Click it to open an HTML preview of the document inside the browser.  "
    "This is a quick way to review the layout without opening Word."
))

heading2(doc, "8.5  Template Fill Report")
body(doc, (
    "If you uploaded a custom template (see Section 11), a fill report appears after "
    "the build showing:"
))
bullet(doc, "How many template sections were successfully filled.")
bullet(doc, "Which sections were marked VERIFY (matched but need human review).")
bullet(doc, "Which sections were left empty because no matching content was found.")

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 9. TOP BAR FEATURES
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "9.  Top Bar Features")

heading2(doc, "9.1  Upload RFP")
body(doc, (
    "Use this button to upload an existing RFP, notes document, or briefing in "
    ".docx, .txt, or .xlsx format.  The platform reads the file and attempts to "
    "pre-fill your answers automatically."
))
bullet(doc, "Merge mode — if you already have answers filled in, clicking OK on the confirmation dialog fills only empty fields, leaving your existing answers untouched.")
bullet(doc, "Replace mode — clicking Cancel on the confirmation dialog overwrites all existing answers with the parsed content.")
bullet(doc, "After parsing, a summary tells you how many paragraphs were read, how many fields were matched, and which matching method was used.")
note_box(doc, (
    "The auto-fill is a draft only.  Always review every field before generating the final document."
))

heading2(doc, "9.2  Sample BRD")
body(doc, (
    "Click Sample BRD to open the KPMG in-house BRD sample document as a reference.  "
    "You can:"
))
bullet(doc, "Browse the sample directly in the browser.")
bullet(doc, "Click Open in New Tab to view it in a full browser tab.")
bullet(doc, "Click Download .docx to save a copy of the sample to your computer.")

heading2(doc, "9.3  Progress Bar")
body(doc, (
    "The thin bar in the top bar fills from left to right as you complete fields across "
    "all steps.  The label (e.g., '34 / 87 Fields') shows how many fields have been "
    "answered out of the total."
))

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 10. SAVE DRAFT & PROJECTS
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "10.  Save Draft & Projects")

heading2(doc, "10.1  Save Draft")
body(doc, (
    "The Save Draft button saves all your current work — including answers, table data, "
    "flowcharts, and images — to your browser's local storage.  "
    "No sign-in is required and no data is sent anywhere."
))
bullet(doc, "A Draft saved toast notification confirms the save.")
bullet(doc, "The draft is loaded automatically the next time you open the application in the same browser.")
bullet(doc, "Drafts are browser-specific — a draft saved in Chrome will not appear in Firefox.")
note_box(doc, "Clearing your browser's site data will delete the saved draft.  Use the Projects feature for more reliable persistence.")

heading2(doc, "10.2  Projects")
body(doc, (
    "The Projects feature lets you save multiple named workspaces, switch between them, "
    "or share a workspace with a colleague."
))

heading3(doc, "Saving a Project")
numbered(doc, "Click Projects in the top bar.")
numbered(doc, "Type a name in the Project name field (e.g., 'Client ABC – Phase 1').")
numbered(doc, "Click Save as Project.")

heading3(doc, "Loading a Project")
numbered(doc, "Click Projects in the top bar.")
numbered(doc, "Find the project in the list and click Load.")
numbered(doc, "The entire workspace — all steps, answers, and tables — is restored.")

heading3(doc, "Deleting a Project")
numbered(doc, "Click Projects in the top bar.")
numbered(doc, "Click the Delete button next to the project you wish to remove.")

heading2(doc, "10.3  Clear")
body(doc, (
    "The Clear button in the top bar discards all current data and resets the wizard "
    "to a blank state.  You will be asked to confirm before anything is deleted."
))
note_box(doc, "Save your draft or project before clicking Clear if you want to keep your work.")

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 11. UPLOADING A CUSTOM TEMPLATE
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "11.  Uploading a Custom Template")

body(doc, (
    "Instead of the KPMG house template, you can upload your own .docx or .dotx template.  "
    "The platform will fill in the sections of your template that match the questions "
    "collected in the wizard."
))

heading2(doc, "11.1  How to Upload")
numbered(doc, "Click Upload & Auto-Fill Template in the bottom of the Left Rail.")
numbered(doc, "An explainer dialog appears the first time, describing the behaviour.  Click Choose Template.")
numbered(doc, "Select your .docx or .dotx file.")
numbered(doc, "The template is uploaded and stored on the server.  The Left Rail shows the template name once it is ready.")
note_box(doc, "You only need to upload the template once per session.  It is remembered until you clear your draft or upload a different template.")

heading2(doc, "11.2  How Sections Are Matched")
body(doc, "The platform tries to match each section of your template to a question answer.  The result for each section is one of three outcomes:")
two_col_table(doc,
    [
        ("Filled",   "The section was matched and populated with content from your answers."),
        ("VERIFY",   "A match was found but the confidence was low.  The section is marked with a VERIFY label for you to check."),
        ("Empty",    "No matching content was found.  The section is left blank for manual completion."),
    ],
    header_row=("Outcome", "Meaning"),
)

heading2(doc, "11.3  Downloading the KPMG Template")
body(doc, (
    "If you want to start from the KPMG house template and customise it, "
    "click Download KPMG Template at the bottom of the Left Rail to save a copy."
))

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 12. FLOWCHART EDITOR
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "12.  Flowchart Editor (Annexure 12.2)")

body(doc, (
    "The Flowchart Editor lets you create As-Is and To-Be process flow diagrams that "
    "are embedded in Annexure 12.2 of the generated document."
))

heading2(doc, "12.1  Opening the Editor")
numbered(doc, "Go to Step 2 — Detail Fields.")
numbered(doc, "Expand the As-Is / To-Be section.")
numbered(doc, "Click Open Flowchart Editor.  A side drawer slides in from the right.")

heading2(doc, "12.2  Creating a Flowchart")
numbered(doc, "Click + Add Flowchart in the drawer footer.")
numbered(doc, "Enter a title for the flowchart (e.g., 'Customer Onboarding – As-Is').")
numbered(doc, "Click + Add Step to add the first process step.")
numbered(doc, "For each step, select a step type and enter the step text.")

heading2(doc, "12.3  Step Types")
two_col_table(doc,
    [
        ("Process",      "A standard rectangle — represents an action or task."),
        ("Decision",     "A diamond shape — represents a yes/no branch.  Enter text for the Yes branch and No branch separately."),
        ("Data / IO",    "A parallelogram — represents data input or output."),
        ("Subprocess",   "A rectangle with a double border — represents a sub-process or called procedure."),
        ("Start / End",  "A rounded rectangle (stadium shape) — marks the start or end of the flow."),
    ],
    header_row=("Type", "Description"),
)

heading2(doc, "12.4  Swim Lanes")
body(doc, (
    "Tick the Enable swim lanes checkbox to assign each step to a lane "
    "(e.g., a department or role).  A lane field appears on each step card.  "
    "Swim lanes are rendered as vertical columns in the final diagram."
))

heading2(doc, "12.5  Previewing and Downloading")
bullet(doc, "Click Preview to see the flowchart rendered as an image directly in the drawer.")
bullet(doc, "Click Download to save the flowchart as a PNG file.")
bullet(doc, "A minimum of two steps is required before previewing or downloading.")

heading2(doc, "12.6  Saving and Including in the Document")
body(doc, (
    "Click Done in the drawer footer to save your flowcharts to the draft.  "
    "When you generate the document in Step 4, all saved flowcharts are automatically "
    "included in Annexure 12.2."
))

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 13. KEYBOARD SHORTCUTS & TIPS
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "13.  Keyboard Shortcuts & Tips")

heading2(doc, "13.1  People-Search Dropdown")
two_col_table(doc,
    [
        ("↑ / ↓", "Move up or down through the search results."),
        ("Enter",  "Select the highlighted result."),
        ("Escape", "Close the dropdown without selecting."),
    ],
    header_row=("Key", "Action"),
)

heading2(doc, "13.2  General Tips")
bullet(doc, "Save Draft regularly (Ctrl + click is not needed — just click the button).  If your browser crashes, the last saved draft is restored on reload.")
bullet(doc, "Use the Left Rail sub-items to jump to a specific question without scrolling through all of Step 1.")
bullet(doc, "If you want to check a question's answer at any time, click the eye icon to switch to the markdown preview — then click it again to return to editing.")
bullet(doc, "In table-format questions, paste comma-separated or line-separated content and the rows will be split automatically.")
bullet(doc, "The Progress Bar updates in real time — use it as a quick sanity check before generating.")
bullet(doc, "You can generate the document multiple times.  Each time you click Create Document, the latest content is used.")

doc.add_page_break()

# ────────────────────────────────────────────────────────────────────────────
# 14. FREQUENTLY ASKED QUESTIONS
# ────────────────────────────────────────────────────────────────────────────
heading1(doc, "14.  Frequently Asked Questions")

faqs = [
    (
        "Q: The people-search dropdown is not appearing when I type a name.",
        "A: The employee directory may not be loaded.  Ask your administrator to place the "
        "correct Excel file (with EmployeeName and EmailId columns) in the name_list/ folder "
        "and then visit http://localhost:5050/api/namelist/rebuild in the browser.  "
        "You can still type the name manually if the dropdown is unavailable."
    ),
    (
        "Q: My draft disappeared after I cleared my browser data.",
        "A: Browser local storage is cleared when you clear site data.  "
        "Use the Projects feature to save important work — project data is stored "
        "on the server and is not affected by clearing the browser."
    ),
    (
        "Q: The Upload RFP feature filled some fields incorrectly.",
        "A: The auto-fill is a starting draft.  Always review every field before "
        "generating the final document.  You can edit any field directly after the upload."
    ),
    (
        "Q: Can I use my own company's Word template?",
        "A: Yes.  Click Upload & Auto-Fill Template in the Left Rail footer and select "
        "your .docx or .dotx file.  See Section 11 for full details."
    ),
    (
        "Q: How do I add a question that is not in the standard list?",
        "A: Go to Step 1 — Core Questions, scroll to the bottom, and click + Add Question "
        "in the Custom category.  Enter your question and answer."
    ),
    (
        "Q: The Create Document button shows an error.",
        "A: Check that Project Name and Client / Entity are filled in (they are required).  "
        "The error message will list any missing required fields.  "
        "If the server is not running, restart it with python app.py."
    ),
    (
        "Q: Can multiple people work on the same BRD at the same time?",
        "A: Not simultaneously.  Each user's work is stored in their own browser.  "
        "To collaborate, one person should export the project (via the Projects modal) "
        "and share the data with another user who can import it."
    ),
    (
        "Q: Where is the generated .docx file saved on the server?",
        "A: Documents are saved in the  data/output/  folder inside the brd_studio directory."
    ),
]

for q, a in faqs:
    body(doc, q, bold_prefix=None)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.left_indent = Inches(0.3)
    run = p.add_run(a)
    run.font.size = Pt(10.5)
    run.font.color.rgb = DARK_TEXT
    run.font.italic = True
    doc.add_paragraph()

# ────────────────────────────────────────────────────────────────────────────
# SAVE
# ────────────────────────────────────────────────────────────────────────────
out_path = r"C:\Users\didar\Downloads\BRD_Studio_User_Manual.docx"
doc.save(out_path)
print("User manual saved to: " + out_path)
