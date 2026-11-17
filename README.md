# BRD Studio — aligned to the BRD house template

A Flask backend plus a small vanilla-JS wizard, both driven by the same
deterministic Python generator. No Node, no build step, no API key, no
model to train, and nothing leaves the machine it runs on.

The generator now produces the **Business Requirements Document**
exactly as the house template lays it out — cover page, Document
Control, Distribution List, table of contents, and sections 1 to 12 with
their real tables and column headers.

## Run it

```bash
cd brd_studio
python -m venv venv && venv\Scripts\activate      # Windows
# or: python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py                        # localhost dev (http://127.0.0.1:5000)
python app.py --host 0.0.0.0        # LAN server (auto-generates HTTPS cert)
python app.py --host 0.0.0.0 --no-ssl   # behind a TLS-terminating proxy
```

### HTTPS and the mic/dictation feature

Browsers require **HTTPS** (or `localhost`) for microphone access. When
you run with `--host 0.0.0.0` BRD Studio auto-generates a self-signed
certificate under `ssl/cert.pem` (825-day validity, reused on restart).
On first visit you will see a browser security warning — click
**Advanced → Proceed**.

To remove the warning permanently, import the cert into the Windows
**Trusted Root Certification Authorities** store, or ask IT to do so.

If the app sits behind **IIS / nginx** that already terminates TLS with
an internal-CA cert, run Flask with `--no-ssl` on 127.0.0.1 and let the
reverse proxy handle HTTPS.

### Offline speech-to-text (vosk)

For locked-down networks without internet, install the vosk model:

```bash
pip install vosk
# Download the small English model (~50 MB) from:
#   https://alphacephei.com/vosk/models  →  vosk-model-small-en-us-0.15
# Unzip into brd_studio/models/vosk/  (so the folder contains am/ etc.)
```

BRD Studio auto-detects the model directory; if present it uses vosk
offline. Otherwise it falls back to Google's free speech API. Force a
backend with `BRD_STT_BACKEND=vosk` or `BRD_STT_BACKEND=google`.

Try it with the worked example first:

```bash
python demo_kbot.py      # writes outputs/BRD_KBOT_AI_v1_0.docx
```

## What the generated document contains

| Template part | Where it comes from |
|---|---|
| Cover page (violet panel, Confidential, version, date) | Project details step |
| Document Control — details / **Version History** / **Approval Matrix** | Project details, auto-numbered |
| **Distribution List** | Prepared by / Reviewed by / Sponsor, or typed rows |
| Table of Contents | live Word TOC field, refreshed on open |
| 1 Introduction — 1.1 Background, 1.2 Objective, 1.3 Intended Audience | q_problem, q_current, q_trigger, q_existing, q_objective, q_metrics, q_audience |
| 2 Scope — 2.1 In Scope, 2.2 Out of Scope | q_inscope / q_outscope as bullet lists, plus the scope-extension note |
| 3 External Interface Requirements — 3.1 to 3.6 | detail fields d_if_\*, plus q_users / q_systems / q_regs |
| 4 Existing and Proposed System/Solution — 4.1 to 4.4 | q_current, d_challenges, d_to_be, d_proposed, q_features, q_ai |
| 5.1 **Functional Requirements** table (BR#, Module, Business requirement, Requirement Description, Remarks) | derived from q_features / q_outputs / q_users / q_ai, auto-numbered FR-01… |
| 5.2 **Non-Functional Requirements** table | derived from the NFR detail fields and q_regs, auto-numbered NFR-01… |
| 6.1 **Open Item List** + 6.2 **Open Item Declaration** with the house declaration statement | typed in the Template tables step, auto-numbered OI-01… |
| 7 **Change Control Log** + the change-control guidance note | typed rows, auto-numbered CH-01… |
| 8 **Integrations** table (External System, Type, Manufacturer/Agency, Method/Protocol, Security Consideration, Status, Remarks) | seeded from q_systems and q_existing |
| 9 Roles & Responsibilities — A. **Roles table**, AI Stakeholder Role Mapping (AI projects), B. **RACIS legend** + **RACI matrix** | project type picks the right house preset; roles seeded from q_users |
| 10.1 **Assumptions** / 10.2 **Dependencies** / 10.3 **Constraints** | typed rows, else standard engagement rows, auto-numbered A-/D-/C- |
| 11 Prototype | d_prototype |
| 12.1 References, 12.2 Use case model, 12.3.1 **Abbreviations**, 12.3.2 **Glossary** | d_references, d_use_case, plus the template's own BRD/DB/PM/BA and Asset/Control/Guideline entries |
| Annexure — intake diagnostics (optional) | readiness table + prioritised open questions for the client |

Section 9 changes shape with the **Project type** you pick on step 1:
General/Waterfall, Agile (Scrum), AI/GenAI, Infrastructure & security,
or Research. Each gets the roles table and RACI matrix the house
template shows for that project type; AI projects additionally get the
AI Stakeholder Role Mapping table (AI Provider / Producer / Developer /
Customer / User).

## Accuracy discipline

Three mechanisms, all rule-based and all visible to the reviewer:

1. **[VERIFY] tagging.** Every sentence built from a real intake answer
   is plain text. Every sentence falling back to house boilerplate is
   prefixed with a bold amber `[VERIFY]`, so a reviewer can see at a
   glance what still needs confirming. The grounding score in the UI is
   simply the ratio of the two.
2. **Readiness (MVI).** Each section is READY / DRAFT / HEAVY depending
   on how many of its mapped inputs are filled. It is shown live in the
   preview rail and printed in the diagnostics annexure. **Nothing is
   ever blocked from generating** — a draft that starts a conversation
   beats a blank page.
3. **Open questions for the client.** Unanswered fields become a
   prioritised (High/Medium/Low) question list, ready to paste into a
   discovery agenda or an email.

Expect roughly 35–45% grounding from a short intro email, 60–75% once
the core questions are answered, and 80%+ with the detail fields and
tables filled. The lever is the input, not the tool.

## No duplicate questions

Anything asked in **Core questions** is never asked again in **Detail
fields** or the **Template tables** step. The core questions are the ones
a functional team (BA, finance lead, PM) can answer without IT; the
detail fields are the technical follow-ups; the tables are where
row-level content goes.

## Using the real .docx / .dotx house template

Left rail → **Upload BRD template**. When a template is selected the
generator opens *that* file instead of building from scratch, and fills
it in place:

- `{{placeholder}}` tags anywhere in it (any `project`, `answers` or
  `detail` key, plus `{{date_today}}`, `{{timeline}}`, `{{compliance_regs}}`),
  working even when Word has split a tag across runs;
- the **real tables**, found by the heading above them (Version History,
  Functional Requirements, Non-Functional Requirements, Open Item List,
  Change Control Log, Integrations, Assumptions, Dependencies,
  Constraints, Abbreviations, Glossary …), with the leading ID column
  auto-numbered;
- the **In Scope / Out of Scope** instructional paragraphs, replaced by
  bullet lists;
- any remaining `<instructional text>` placeholders, cleared for manual
  completion.

Your letterhead, cover page, numbering and house styles are never
rebuilt. `POST /api/build` returns `template_fill: {filled, missing,
tables_routed, placeholders_cleared}` so the wizard can warn about
anything it could not match.

## Pre-filling from an RFP

Left rail → **Upload RFP to prefill** (.docx, .txt or .xlsx). Each
paragraph is routed to the intake field whose seed phrases it most
resembles, filling **detail** fields as well as core questions.

Three matchers, same interface:

1. **Sentence embeddings** (optional) — if `sentence-transformers` is
   installed, paragraphs are scored with a local BERT-family MiniLM
   model (`all-MiniLM-L6-v2`). Semantic matches beat pure keyword overlap
   on messy client notes. No API key; the model runs on the machine.
2. **FLAN-T5** (optional) — install `transformers`, `torch` and
   `sentencepiece`, then run with `BRD_RFP_MATCHER=flan-t5`. The default
   model is `google/flan-t5-small`. It classifies each paragraph into
   the best intake field IDs, then rewrites the matched source into
   concise BRD-style draft content without adding unsupported facts.
3. **TF-IDF** (default / fallback) — `TfidfVectorizer` is fit on the
   document you give it. Always available; used automatically when the
   selected model backend is missing or fails to load.

PowerShell example:

```powershell
$env:BRD_RFP_MATCHER = "flan-t5"
python app.py
```

There is no training step and no dataset to collect. Improving TF-IDF or
embeddings means editing `SEED_PHRASES` in `rfp_parser.py`; improving the
FLAN-T5 route means adjusting the prompt in `rfp_parser.py`. Force a
backend with `BRD_RFP_MATCHER=tfidf|embeddings|flan-t5|auto` (default
`auto`).

Everything it produces is a **draft**: review it in Core questions and
Detail fields before generating.

## Where things live

```
brd_studio/
  app.py                     Flask routes
  demo_kbot.py               worked example (KBOT AI) -> outputs/
  brd_agent/
    config.py                THE schema: outline, questions, detail fields,
                             table specs, role/RACI presets, readiness rules
    templates.py             deterministic section builders + table row derivation
    kpmg_docx.py             house-style Word writer (cover, TOC, shaded tables
                             headers/footers, numbered headings)
    brd_generator.py         readiness/gap/grounding + orchestration
    template_filler.py       fills an uploaded .docx/.dotx in place
    rfp_parser.py            optional RFP prefill (embeddings or TF-IDF)
  templates/index.html       wizard shell
  static/app.js, style.css   wizard logic (schema comes from /api/config)
  uploads/templates/         drop the real house .docx/.dotx here
  uploads/rfps/              uploaded RFPs
  outputs/                   generated BRDs
```

## Extending it

Everything is `config.py`. Add a question, a detail field, an industry,
a table, a project type or a readiness rule there and it appears in the
wizard and the document with no JS or generator edits — the frontend
renders whatever `GET /api/config` returns.

- New section → add a row to `OUTLINE` and a same-named method on
  `SectionBuilder`.
- New table → add a spec to `TABLE_SPECS` (its `section` is an `OUTLINE`
  id, `anchor` is how to find it in an uploaded template) and, if it
  should auto-populate, a branch in `templates.derive_rows`.
