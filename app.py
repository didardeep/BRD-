"""
app.py -- Flask backend for the BRD studio.

Usage:
    pip install -r requirements.txt
    python app.py                          # localhost dev
    python app.py --host 0.0.0.0           # LAN server (HTTPS auto-enabled)
    python app.py --host 0.0.0.0 --no-ssl  # behind a reverse-proxy that terminates TLS
"""

import sys
import os
import re
import socket
import webbrowser
import threading
import argparse
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, render_template, send_file
from werkzeug.utils import secure_filename

from brd_agent.config import (PROJECT_FIELDS, QUESTIONS, DETAIL_FIELDS, DETAIL_TABLES,
                              DETAIL_SCREENSHOTS, INDUSTRIES,
                              SECTIONS, OUTLINE, TABLE_PRESETS, TABLE_SPECS, PROJECT_TYPES,
                              COMPLIANCE_MAP, ROLE_PRESETS, NFR_CHECKLIST,
                              MVI_RULES, GAP_QUESTIONS, PLACEHOLDER_ANSWERS,
                              NONE_ANSWERS, MIN_WORDS_TEXT, MIN_WORDS_ROW_DESC,
                              ROLE_SUGGESTIONS, ACCESS_LEVELS, TEMPLATE_FILL_PROMPT)
from brd_agent import brd_generator, rfp_parser
from brd_agent.inference import infer_details
from brd_agent.flowchart import OBJECT_TYPES as FLOWCHART_OBJECT_TYPES, render_swimlane_flowchart

# When frozen by PyInstaller, static/template files live in sys._MEIPASS
# but writable folders (uploads, outputs) go next to the .exe
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS) / "brd_studio"
    DATA_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR

UPLOAD_TEMPLATES = DATA_DIR / "uploads" / "templates"
UPLOAD_RFPS      = DATA_DIR / "uploads" / "rfps"
UPLOAD_IMAGES    = DATA_DIR / "uploads" / "images"
OUTPUT_DIR       = DATA_DIR / "outputs"
PROJECTS_DIR     = DATA_DIR / "projects"
NAME_LIST_DIR    = DATA_DIR / "name_list"
for d in (UPLOAD_TEMPLATES, UPLOAD_RFPS, UPLOAD_IMAGES, OUTPUT_DIR, PROJECTS_DIR, NAME_LIST_DIR):
    d.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
ALLOWED_NOTES_EXT = (".docx", ".txt", ".xlsx", ".xls")

# Organisation defaults -- optional file that pre-fills new project fields
import json as _json
_DEFAULTS_PATH = DATA_DIR / "defaults.json"
ORG_DEFAULTS = {}
if _DEFAULTS_PATH.is_file():
    try:
        ORG_DEFAULTS = _json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass


app = Flask(__name__,
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"))
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB uploads
app.config["TEMPLATES_AUTO_RELOAD"] = True           # always read templates from disk
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0          # disable static file caching during dev



@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/config")
def api_config():
    """Single source of truth for the wizard -- the frontend renders
    whatever schema this returns, so config.py changes need no JS edits."""
    return jsonify({
        "project_fields": PROJECT_FIELDS,
        "questions": QUESTIONS,
        "detail_fields": DETAIL_FIELDS,
        "detail_tables": DETAIL_TABLES,
        "detail_screenshots": sorted(DETAIL_SCREENSHOTS),
        "industries": INDUSTRIES,
        "sections": [{"id": sid, "label": label} for sid, label in SECTIONS],
        "outline": [{"id": sid, "number": num, "title": title, "level": lvl, "kind": kind}
                     for sid, num, title, lvl, kind in OUTLINE],
        "project_types": PROJECT_TYPES,
        "compliance_map": COMPLIANCE_MAP,
        "role_presets": ROLE_PRESETS,
        "nfr_checklist": NFR_CHECKLIST,
        "org_defaults": ORG_DEFAULTS,
        "templates": sorted(f.name for f in UPLOAD_TEMPLATES.glob("*.doc*")),
        "table_presets": TABLE_PRESETS,
        "mvi_rules": MVI_RULES,
        "gap_questions": {k: {"priority": v[0], "question": v[1]}
                           for k, v in GAP_QUESTIONS.items()},
        "flowchart_object_types": FLOWCHART_OBJECT_TYPES,
        "quality": {
            "placeholders": PLACEHOLDER_ANSWERS,
            "none_answers": NONE_ANSWERS,
            "min_words_text": MIN_WORDS_TEXT,
            "min_words_row_desc": MIN_WORDS_ROW_DESC,
        },
        "role_suggestions": ROLE_SUGGESTIONS,
        "access_levels": ACCESS_LEVELS,
        "template_fill_prompt": TEMPLATE_FILL_PROMPT,
    })


def _drop_unfilled_prompts(answers):
    """Remove questionnaire lines the user left as "[mention as per your
    application]" so the placeholder never reaches the BRD."""
    out = {}
    for k, v in (answers or {}).items():
        if isinstance(v, str) and TEMPLATE_FILL_PROMPT in v:
            v = "\n".join(l for l in v.splitlines() if TEMPLATE_FILL_PROMPT not in l).strip()
        out[k] = v
    return out


@app.post("/api/tables/preview")
def api_tables_preview():
    """Preview the rows that would be auto-derived from the current
    answers/RFP-drafted intake for every house-template table, so the
    wizard can show them for review/edit *before* the document is built
    instead of only after. Rows the user has already typed always win
    (same rule the generator itself applies)."""
    payload = request.get_json(force=True) or {}
    project = payload.get("project", {})
    answers = _drop_unfilled_prompts(payload.get("answers", {}))
    detail = dict(payload.get("detail", {}))
    tables = payload.get("tables", [])

    # Structured row data for row-based questions (used by table derivation)
    row_data = payload.get("row_data", {})
    if row_data:
        detail["_row_data"] = row_data

    inferred = infer_details(answers)
    for key, value in inferred.items():
        if key not in detail or not str(detail.get(key, "")).strip():
            detail[key] = value

    user_tables, _leftovers = brd_generator.index_user_tables(tables)

    out = {}
    for spec in TABLE_SPECS:
        has_user_rows = bool(user_tables.get(spec["id"]))
        rows, grounded = brd_generator.resolve_table(
            spec, user_tables.get(spec["id"]), project, answers, detail)
        out[spec["id"]] = {"rows": rows, "grounded": grounded, "user_entered": has_user_rows}
    return jsonify(out)


@app.post("/api/flowchart/preview")
def api_flowchart_preview():
    """Generate a flowchart preview from free text and return it as a
    base64-encoded PNG so the wizard can show an inline preview before
    the full document is built."""
    import base64
    from brd_agent.flowchart import matplotlib_available, steps_from_text, render_flowchart

    if not matplotlib_available():
        return jsonify({"error": "matplotlib is not installed on the server. "
                        "Run  pip install matplotlib  to enable flowchart previews."}), 500

    payload = request.get_json(force=True) or {}
    title = payload.get("title", "Process Flow")
    key = payload.get("key", "preview")

    # Accept either structured steps [{text, type}] or plain text
    structured = payload.get("steps")
    if structured and isinstance(structured, list):
        steps = [s for s in structured
                 if isinstance(s, dict) and (s.get("text") or "").strip()]
    else:
        text = payload.get("text", "")
        steps = steps_from_text(text)

    if len(steps) < 2:
        plain = [s["text"] if isinstance(s, dict) else s for s in steps]
        return jsonify({
            "error": "Need at least 2 steps to draw a flowchart. "
                     "Add more steps using the + button.",
            "steps": plain,
            "step_count": len(steps),
        }), 400

    swim_lanes = bool(payload.get("swim_lanes"))
    path = (render_swimlane_flowchart(steps, title, key)
            if swim_lanes else render_flowchart(steps, title, key))
    if not path:
        return jsonify({"error": "Could not render flowchart."}), 500

    with open(path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("ascii")

    plain = [s["text"] if isinstance(s, dict) else s for s in steps]
    return jsonify({
        "image": f"data:image/png;base64,{img_data}",
        "steps": plain,
        "step_count": len(steps),
    })


@app.post("/api/build")
def api_build():
    payload = request.get_json(force=True) or {}
    project = payload.get("project", {})
    answers = _drop_unfilled_prompts(payload.get("answers", {}))
    detail = dict(payload.get("detail", {}))
    tables = payload.get("tables", [])
    template_name = payload.get("template")

    # Custom flowcharts: pass through to SectionBuilder via detail
    custom_flowcharts = payload.get("custom_flowcharts", [])
    if custom_flowcharts:
        detail["_custom_flowcharts"] = custom_flowcharts

    # Structured row data for row-based questions (used by tables)
    row_data = payload.get("row_data", {})
    if row_data:
        detail["_row_data"] = row_data
    include_diagnostics = bool(payload.get("include_diagnostics", True))

    images = []
    for img in payload.get("images", []):
        fname = (img or {}).get("filename")
        if not fname:
            continue
        candidate = UPLOAD_IMAGES / secure_filename(fname)
        if candidate.exists():
            images.append({"path": str(candidate), "caption": (img or {}).get("caption", "")})

    template_path = None
    if template_name:
        candidate = UPLOAD_TEMPLATES / secure_filename(template_name)
        if candidate.exists():
            template_path = str(candidate)

    # Fallback: if no template was selected, use the first .docx/.dotx in uploads/templates
    if not template_path:
        defaults = sorted(UPLOAD_TEMPLATES.glob("*.doc*"))
        defaults = [f for f in defaults if f.suffix.lower() in (".docx", ".dotx")]
        if defaults:
            template_path = str(defaults[0])

    try:
        summary = brd_generator.build(project, answers, detail, tables, OUTPUT_DIR,
                                       template_path, include_diagnostics, images)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    summary["download_url"] = f"/api/download/{summary['filename']}"
    summary["preview_url"] = f"/api/preview/{summary['filename']}"
    return jsonify(summary)


@app.get("/api/download/<path:filename>")
def api_download(filename):
    response = send_from_directory(OUTPUT_DIR, filename, as_attachment=True)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.get("/api/preview/<path:filename>")
def api_preview(filename):
    """Render a generated .docx as HTML so the user can review it in the
    wizard before downloading. Uses mammoth -- a straight docx->html
    converter, no external service."""
    import mammoth
    path = OUTPUT_DIR / secure_filename(filename)
    if not path.exists():
        return jsonify({"error": "File not found"}), 404
    try:
        with open(path, "rb") as f:
            result = mammoth.convert_to_html(f)
        return jsonify({"html": result.value, "warnings": [str(w) for w in result.messages]})
    except Exception as e:
        return jsonify({"error": f"Could not render preview: {e}"}), 500


@app.post("/api/images/upload")
def api_images_upload():
    """Upload a 'current system' screenshot for Section 12."""
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(ALLOWED_IMAGE_EXT):
        return jsonify({"error": "Upload a PNG, JPG, GIF, BMP or WEBP image"}), 400
    name = secure_filename(file.filename)
    # avoid overwriting an existing upload with the same name
    stem, ext = Path(name).stem, Path(name).suffix
    candidate = UPLOAD_IMAGES / name
    n = 1
    while candidate.exists():
        candidate = UPLOAD_IMAGES / f"{stem}_{n}{ext}"
        n += 1
    file.save(candidate)
    return jsonify({"filename": candidate.name, "url": f"/api/images/{candidate.name}"})


@app.get("/api/images/<path:filename>")
def api_images_serve(filename):
    return send_from_directory(UPLOAD_IMAGES, secure_filename(filename))


@app.delete("/api/images/<path:filename>")
def api_images_delete(filename):
    path = UPLOAD_IMAGES / secure_filename(filename)
    if path.exists():
        path.unlink()
    return jsonify({"deleted": filename})


@app.post("/api/template/upload")
def api_template_upload():
    """Upload a company .docx template (letterhead / cover page / house
    styles). The generator opens this as the base document and appends
    the generated sections after a page break, instead of building a
    blank document from scratch."""
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith((".docx", ".dotx")):
        return jsonify({"error": "Upload a .docx or .dotx file"}), 400
    name = secure_filename(file.filename)
    file.save(UPLOAD_TEMPLATES / name)
    return jsonify({"saved": name,
                    "templates": sorted(f.name for f in UPLOAD_TEMPLATES.glob("*.doc*"))})


@app.get("/api/templates")
def api_templates_list():
    return jsonify({"templates": sorted(f.name for f in UPLOAD_TEMPLATES.glob("*.doc*"))})


_KPMG_TEMPLATE_NAME = "KPMG_BRD_Template.docx"


@app.get("/api/kpmg-template/info")
def api_kpmg_template_info():
    return jsonify({"available": True, "filename": _KPMG_TEMPLATE_NAME, "source": "generated"})


@app.get("/api/kpmg-template/download")
def api_kpmg_template_download():
    """Blank KPMG house-format template, built fresh on every request so it
    always matches the current outline and never contains a generated BRD."""
    import io
    buf = io.BytesIO()
    brd_generator.build_blank_template().save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True, download_name=_KPMG_TEMPLATE_NAME,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.post("/api/rfp/parse")
def api_rfp_parse():
    """Upload a past RFP/RFI or any notes document (.docx, .txt, .xlsx/.xls)
    to pre-fill a draft intake. The matcher works paragraph-by-paragraph
    (embeddings, FLAN-T5 or TF-IDF against the same intake schema) so it does not
    require headings or a fixed structure -- unstructured notes work the
    same way a formal RFP does. The result is always a *draft*: nothing
    is saved until the user reviews it in the wizard and clicks through."""
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    if not file.filename.lower().endswith(ALLOWED_NOTES_EXT):
        return jsonify({"error": "Upload a .docx, .txt, .xlsx or .xls file"}), 400
    name = secure_filename(file.filename)
    path = UPLOAD_RFPS / name
    file.save(path)
    try:
        draft = rfp_parser.parse(path)
    except Exception as e:
        return jsonify({"error": f"Could not parse file: {e}"}), 400
    return jsonify(draft)


@app.post("/generate-pdf")
def api_generate_pdf():
    """Accept JSON, validate required fields, return a PDF download.

    Expected JSON body (fields defined in pdf_generator.FIELDS)::

        {
            "name":    "Acme Corp",
            "email":   "info@acme.com",
            "date":    "2026-08-24",
            "details": "Optional free-text notes..."
        }

    Any extra keys in the payload are ignored; missing required keys
    return a 400 JSON error.
    """
    from pdf_generator import generate_pdf, validate

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    errors = validate(payload)
    if errors:
        return jsonify({"error": "Validation failed.", "details": errors}), 400

    title = payload.get("title") or "Generated Document"

    try:
        buf = generate_pdf(payload, title=title)
    except Exception as exc:
        return jsonify({"error": f"PDF generation failed: {exc}"}), 500

    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)
    filename = f"{safe_name.strip()}.pdf"

    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


# ---------------------------------------------------------------------------
# Current user identity  (used by the "Use my name" button)
# ---------------------------------------------------------------------------

@app.get("/api/whoami")
def api_whoami():
    """Return the current OS user's name so the wizard can pre-fill
    Prepared by / Reviewed by fields without the user typing them."""
    import getpass

    username = getpass.getuser()          # e.g. "CORP\\jsmith" or "jsmith"

    # On Windows, try to get the full display name from the registry
    display_name = ""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList",
        )
        # Build SID → display name map via net user or environment
        import ctypes
        buf = ctypes.create_unicode_buffer(256)
        buf_sz = ctypes.c_ulong(256)
        ctypes.windll.secur32.GetUserNameExW(3, buf, ctypes.byref(buf_sz))
        display_name = buf.value  # "First Last" format (EXTENDED_NAME_FORMAT 3)
    except Exception:
        pass

    # Strip domain prefix if present (DOMAIN\user -> user)
    short = username.split("\\")[-1] if "\\" in username else username

    return jsonify({
        "username": short,
        "display_name": display_name or short,
    })


# ---------------------------------------------------------------------------
# Project list  (server-side JSON files in PROJECTS_DIR)
# ---------------------------------------------------------------------------

@app.get("/api/projects")
def api_projects_list():
    projects = []
    for p in sorted(PROJECTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            import json as _json
            meta = _json.loads(p.read_text(encoding="utf-8"))
            projects.append({
                "id": p.stem,
                "name": meta.get("project", {}).get("name") or p.stem,
                "saved_at": meta.get("saved_at", ""),
            })
        except Exception:
            pass
    return jsonify({"projects": projects})


@app.post("/api/projects/save")
def api_projects_save():
    import json as _json, time as _time, uuid as _uuid
    payload = request.get_json(force=True) or {}
    project_id = payload.get("id") or _uuid.uuid4().hex[:12]
    payload["saved_at"] = _time.strftime("%Y-%m-%dT%H:%M:%S")
    path = PROJECTS_DIR / f"{secure_filename(project_id)}.json"
    path.write_text(_json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"id": project_id, "saved_at": payload["saved_at"]})


@app.get("/api/projects/load/<project_id>")
def api_projects_load(project_id):
    import json as _json
    path = PROJECTS_DIR / f"{secure_filename(project_id)}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    return jsonify(_json.loads(path.read_text(encoding="utf-8")))


@app.delete("/api/projects/<project_id>")
def api_projects_delete(project_id):
    path = PROJECTS_DIR / f"{secure_filename(project_id)}.json"
    if path.exists():
        path.unlink()
    return jsonify({"deleted": project_id})


# ---------------------------------------------------------------------------
# Duplicate detection for requirement tables
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# In-house Sample BRD  (reference/House_Sample_BRD.docx)
# ---------------------------------------------------------------------------

REFERENCE_DIR = BASE_DIR / "reference"
_SAMPLE_DOCX  = REFERENCE_DIR / "House_Sample_BRD.docx"
_SAMPLE_PDF   = REFERENCE_DIR / "House_Sample_BRD.pdf"


def _sample_pdf_path():
    """Return path to a PDF rendering of the sample BRD (cached next to .docx).
    Returns None if no converter is available."""
    if _SAMPLE_PDF.exists():
        # Use pre-exported PDF if it's up-to-date
        if not _SAMPLE_DOCX.exists() or _SAMPLE_PDF.stat().st_mtime >= _SAMPLE_DOCX.stat().st_mtime:
            return _SAMPLE_PDF
    if not _SAMPLE_DOCX.exists():
        return None
    # Try docx2pdf
    try:
        from docx2pdf import convert as _docx2pdf
        _docx2pdf(str(_SAMPLE_DOCX), str(_SAMPLE_PDF))
        if _SAMPLE_PDF.exists():
            return _SAMPLE_PDF
    except Exception:
        pass
    # Try LibreOffice
    try:
        import subprocess as _sp
        r = _sp.run(
            ["libreoffice", "--headless", "--convert-to", "pdf",
             "--outdir", str(REFERENCE_DIR), str(_SAMPLE_DOCX)],
            capture_output=True, timeout=60,
        )
        if r.returncode == 0 and _SAMPLE_PDF.exists():
            return _SAMPLE_PDF
    except Exception:
        pass
    return None


@app.get("/api/sample-brd/info")
def api_sample_brd_info():
    """Return availability metadata for the in-house sample BRD."""
    if not _SAMPLE_DOCX.exists():
        return jsonify({"available": False})
    import time as _t
    mtime = _SAMPLE_DOCX.stat().st_mtime
    updated = _t.strftime("%Y-%m-%dT%H:%M:%S", _t.localtime(mtime))
    has_pdf = _SAMPLE_PDF.exists() and (
        _SAMPLE_PDF.stat().st_mtime >= mtime)
    return jsonify({
        "available": True,
        "filename": _SAMPLE_DOCX.name,
        "has_pdf": has_pdf,
        "updated": updated,
    })


@app.get("/api/sample-brd/pdf")
def api_sample_brd_pdf():
    """Serve the sample BRD as a PDF for inline browser preview."""
    if not _SAMPLE_DOCX.exists():
        return jsonify({"error": "Sample BRD not found. Place House_Sample_BRD.docx in the reference/ folder."}), 404
    pdf = _sample_pdf_path()
    if pdf:
        return send_file(str(pdf), mimetype="application/pdf",
                         as_attachment=False, download_name="House_Sample_BRD.pdf")
    # Fallback: mammoth HTML preview
    try:
        import mammoth
        with open(_SAMPLE_DOCX, "rb") as f:
            result = mammoth.convert_to_html(f)
        return jsonify({"fallback_html": result.value,
                        "warning": "Approximate preview — download the .docx for the exact layout."})
    except Exception as e:
        return jsonify({"error": f"No PDF converter available and mammoth preview failed: {e}"}), 500


@app.get("/api/sample-brd/download")
def api_sample_brd_download():
    """Download the in-house sample BRD as a .docx attachment."""
    if not _SAMPLE_DOCX.exists():
        return jsonify({"error": "Sample BRD not found."}), 404
    return send_file(str(_SAMPLE_DOCX), as_attachment=True,
                     download_name="House_Sample_BRD.docx")


@app.post("/api/tables/duplicates")
def api_tables_duplicates():
    """Detect near-duplicate rows in a table using TF-IDF cosine similarity.
    Expects JSON: { "rows": [["cell", ...], ...], "threshold": 0.6 }
    Returns: { "pairs": [[row_i, row_j, score], ...] }"""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return jsonify({"error": "scikit-learn is required for duplicate detection."}), 500

    payload   = request.get_json(force=True) or {}
    rows      = payload.get("rows", [])
    threshold = float(payload.get("threshold", 0.60))

    if len(rows) < 2:
        return jsonify({"pairs": []})

    # Join all cells in each row into a single string for comparison
    texts = [" ".join(str(c) for c in row if c).strip() for row in rows]
    non_empty = [(i, t) for i, t in enumerate(texts) if t]
    if len(non_empty) < 2:
        return jsonify({"pairs": []})

    indices, docs = zip(*non_empty)
    try:
        vecs = TfidfVectorizer(ngram_range=(1, 2)).fit_transform(docs)
        sim  = cosine_similarity(vecs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    pairs = []
    for a in range(len(indices)):
        for b in range(a + 1, len(indices)):
            score = float(sim[a, b])
            if score >= threshold:
                pairs.append([int(indices[a]), int(indices[b]), round(score, 3)])
    pairs.sort(key=lambda x: -x[2])
    return jsonify({"pairs": pairs})


# ---------------------------------------------------------------------------
# Speech-to-text via SpeechRecognition (server-side, no HTTPS needed)
# ---------------------------------------------------------------------------

UPLOAD_AUDIO = DATA_DIR / "uploads" / "audio"
UPLOAD_AUDIO.mkdir(parents=True, exist_ok=True)

def _transcribe_google_direct(wav_path, lang="en-US"):
    """Encode WAV → FLAC via pydub/ffmpeg and POST directly to Google Speech API.

    Used as a fallback when SpeechRecognition cannot find its bundled flac.exe
    (common on Windows systems where the binary path is not resolved correctly).
    """
    import io, urllib.request, urllib.parse, json as _json
    from pydub import AudioSegment

    seg = AudioSegment.from_wav(str(wav_path))
    buf = io.BytesIO()
    seg.export(buf, format="flac")
    flac_data = buf.getvalue()

    url = "https://www.google.com/speech-api/v2/recognize?" + urllib.parse.urlencode({
        "client": "chromium",
        "lang": lang,
        "key": "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw",
    })
    req = urllib.request.Request(url, data=flac_data, headers={
        "Content-Type": f"audio/x-flac; rate={seg.frame_rate}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")

    for line in raw.strip().split("\n"):
        try:
            obj = _json.loads(line)
            alts = (obj.get("result") or [{}])[0].get("alternative", [])
            if alts:
                return alts[0].get("transcript", "")
        except Exception:
            pass
    return ""


def _stt_backend():
    """Return the configured STT backend: 'vosk' or 'google'."""
    forced = os.environ.get("BRD_STT_BACKEND", "").lower()
    if forced in ("vosk", "google"):
        return forced
    # Auto-detect: prefer vosk when a model directory is present
    model_dir = os.environ.get("BRD_VOSK_MODEL") or str(DATA_DIR / "models" / "vosk")
    if Path(model_dir).is_dir():
        return "vosk"
    return "google"


def _transcribe_vosk(wav_path, lang="en-US"):
    """Transcribe a 16 kHz mono WAV using a local Vosk model."""
    import wave
    import json as _json
    from vosk import Model, KaldiRecognizer

    model_dir = os.environ.get("BRD_VOSK_MODEL") or str(DATA_DIR / "models" / "vosk")
    if not Path(model_dir).is_dir():
        raise RuntimeError(f"Vosk model directory not found: {model_dir}")

    model = Model(model_dir)
    wf = wave.open(str(wav_path), "rb")
    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(False)

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        rec.AcceptWaveform(data)
    wf.close()

    result = _json.loads(rec.FinalResult())
    return result.get("text", "")


@app.post("/api/speech/transcribe")
def api_speech_transcribe():
    """Accept audio from the browser (WAV recorded via AudioContext, or an
    uploaded MP3/WebM/OGG/M4A/FLAC file), transcribe using vosk (offline)
    or Google (online), and return JSON.

    Non-WAV files are converted to 16 kHz mono WAV via pydub (preferred) or
    ffmpeg.  Install pydub with:  pip install pydub
    """
    try:
        import speech_recognition as sr
    except ImportError:
        sr = None

    file = request.files.get("audio")
    if not file:
        return jsonify({"error": "No audio file uploaded"}), 400

    import uuid as _uuid
    uid = _uuid.uuid4().hex[:8]
    orig_ext = Path(file.filename or "audio.wav").suffix.lower()
    if orig_ext not in {".wav", ".mp3", ".ogg", ".webm", ".m4a", ".flac", ".aiff", ".opus"}:
        orig_ext = ".wav"

    orig_path = UPLOAD_AUDIO / f"stt_{uid}_orig{orig_ext}"
    wav_path  = UPLOAD_AUDIO / f"stt_{uid}.wav"
    file.save(orig_path)

    converted = False
    try:
        # WAV from RecordRTC is already 16 kHz mono — use directly.
        # Non-WAV formats are converted via pydub or ffmpeg.
        if orig_ext != ".wav":
            try:
                from pydub import AudioSegment
                seg = AudioSegment.from_file(str(orig_path))
                seg = seg.set_frame_rate(16000).set_channels(1)
                seg.export(str(wav_path), format="wav")
                converted = True
            except ImportError:
                import subprocess
                r = subprocess.run(
                    ["ffmpeg", "-y", "-i", str(orig_path),
                     "-ar", "16000", "-ac", "1", str(wav_path)],
                    capture_output=True,
                )
                if r.returncode != 0:
                    return jsonify({
                        "error": "Cannot decode audio. Install pydub: pip install pydub"
                    }), 500
                converted = True
        else:
            wav_path = orig_path  # RecordRTC WAV is already 16 kHz mono

        backend = _stt_backend()

        if backend == "vosk":
            text = _transcribe_vosk(wav_path)
            return jsonify({"text": text, "backend": "vosk"})
        else:
            if sr is None:
                return jsonify({"error": "SpeechRecognition is not installed. "
                                "Run: pip install SpeechRecognition"}), 500
            lang = request.form.get("lang", "en-US")
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 200
            recognizer.dynamic_energy_threshold = False
            with sr.AudioFile(str(wav_path)) as source:
                audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data, language=lang)
            except OSError as e:
                # flac.exe not found on this system — fall back to pydub direct call
                if getattr(e, "winerror", None) == 2 or "flac" in str(e).lower():
                    text = _transcribe_google_direct(wav_path, lang)
                else:
                    raise
            return jsonify({"text": text, "backend": "google"})

    except Exception as e:
        ename = type(e).__name__
        if ename == "UnknownValueError":
            return jsonify({"text": "", "warning": "Could not understand audio",
                            "backend": _stt_backend()})
        if ename == "RequestError":
            return jsonify({"error": f"Speech service unavailable: {e}"}), 503
        return jsonify({"error": f"Transcription failed: {e}"}), 500
    finally:
        try:
            orig_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            if converted:
                wav_path.unlink(missing_ok=True)
        except Exception:
            pass



# ---------------------------------------------------------------------------
# People lookup  (users.db populated by import_users.py)
# ---------------------------------------------------------------------------

_USERS_DB_PATH = DATA_DIR / "data" / "users.db"
(DATA_DIR / "data").mkdir(parents=True, exist_ok=True)


def _maybe_auto_import_users():
    """At startup: if data/users.xlsx is newer than users.db, re-import it."""
    xlsx = DATA_DIR / "data" / "users.xlsx"
    if not xlsx.exists():
        return
    db = _USERS_DB_PATH
    if db.exists() and db.stat().st_mtime >= xlsx.stat().st_mtime:
        return
    try:
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("import_users",
                                             BASE_DIR / "import_users.py")
        if spec is None:
            return
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.import_users(str(xlsx), str(db))
    except Exception as e:
        print(f"[BRD] Auto-import of users.xlsx failed: {e}")


_maybe_auto_import_users()


def _ensure_namelist_db():
    """Auto-rebuild users.db if it is missing or older than any file in name_list/."""
    files = list(NAME_LIST_DIR.glob("*.xls*"))
    if not files:
        return
    if not _USERS_DB_PATH.exists():
        _rebuild_namelist_db()
        return
    db_mtime = _USERS_DB_PATH.stat().st_mtime
    if any(f.stat().st_mtime > db_mtime for f in files):
        _rebuild_namelist_db()


@app.get("/api/users/search")
def api_users_search():
    """Search users by name or email. Returns up to `limit` results.
    q must be ≥ 2 characters; returns [] otherwise."""
    q = (request.args.get("q") or "").strip()
    limit = min(int(request.args.get("limit", 8)), 20)
    if len(q) < 2:
        return jsonify([])
    try:
        _ensure_namelist_db()
    except Exception:
        pass
    if not _USERS_DB_PATH.exists():
        return jsonify([])
    try:
        from brd_agent.users_db import search_users
        results = search_users(str(_USERS_DB_PATH), q, limit)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/namelist/rebuild")
def api_namelist_rebuild():
    """Manually trigger a rebuild of the people-search DB from name_list/ files.
    Open in browser: http://localhost:5050/api/namelist/rebuild
    """
    try:
        total = _rebuild_namelist_db()
        files = sorted(f.name for f in NAME_LIST_DIR.glob("*.xls*"))
        return jsonify({"status": "ok", "total_records": total, "files": files})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Name List  (name_list/ — EmployeeName + EmailId spreadsheets)
# ---------------------------------------------------------------------------

_NL_NAME_ALIASES  = {"employeename", "employee name", "employee_name", "empname",
                      "name", "full name", "fullname", "full_name"}
_NL_EMAIL_ALIASES = {"emailid", "email id", "email_id", "emailaddress",
                     "email", "e-mail", "mail", "email address"}


def _find_nl_cols(header_row):
    """Return (name_col_idx, email_col_idx) from a header row. Either may be None."""
    name_col = email_col = None
    for ci, cell in enumerate(header_row):
        if cell is None:
            continue
        h = str(cell).strip().lower()
        h_compact = h.replace(" ", "").replace("_", "")
        if h in _NL_NAME_ALIASES or h_compact in _NL_NAME_ALIASES:
            name_col = ci
        elif h in _NL_EMAIL_ALIASES or h_compact in _NL_EMAIL_ALIASES:
            email_col = ci
    return name_col, email_col


def _parse_namelist_file(path):
    """Parse an Excel file and extract EmployeeName + EmailId rows.

    Returns list of {name, email, designation, department} dicts.
    Column matching is case-insensitive; both .xlsx and .xls are supported.
    """
    path = Path(path)
    rows_out = []
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        ws = wb.active

        name_col = email_col = header_ri = None
        for ri, row in enumerate(ws.iter_rows(values_only=True)):
            if not row or all(c is None for c in row):
                continue
            nc, ec = _find_nl_cols(row)
            if nc is not None or ec is not None:
                name_col, email_col, header_ri = nc, ec, ri
                break

        if header_ri is None:
            wb.close()
            return rows_out

        seen = set()
        for ri, row in enumerate(ws.iter_rows(values_only=True)):
            if ri <= header_ri:
                continue
            if not row or all(c is None for c in row):
                continue

            def _cell(idx):
                if idx is None or idx >= len(row) or row[idx] is None:
                    return ""
                return str(row[idx]).strip()

            name  = _cell(name_col)
            email = _cell(email_col).lower()
            if not name and not email:
                continue
            key = email if email else name.lower()
            if key in seen:
                continue
            seen.add(key)
            rows_out.append({"name": name, "email": email,
                              "designation": "", "department": ""})
        wb.close()
    except Exception as e:
        print(f"[name_list] Could not parse {path.name}: {e}")
    return rows_out


def _rebuild_namelist_db():
    """Re-read every xlsx/xls in NAME_LIST_DIR, merge, and update users.db.

    Returns the total number of records written.
    """
    files = sorted(NAME_LIST_DIR.glob("*.xls*"))
    if not files:
        return 0
    all_rows, seen = [], set()
    for f in files:
        for row in _parse_namelist_file(f):
            key = row["email"] if row["email"] else row["name"].lower()
            if key and key not in seen:
                seen.add(key)
                all_rows.append(row)
    if all_rows:
        from brd_agent.users_db import replace_all
        replace_all(str(_USERS_DB_PATH), all_rows)
    return len(all_rows)


@app.post("/api/namelist/upload")
def api_namelist_upload():
    """Upload an Excel (.xlsx / .xls) to name_list/ and rebuild the people-search DB.

    Reads only the EmployeeName and EmailId columns (case-insensitive match).
    Multiple files can be uploaded; every file in the folder is merged each time.
    """
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"error": "Upload a .xlsx or .xls file"}), 400
    name = secure_filename(file.filename)
    file.save(NAME_LIST_DIR / name)
    try:
        total = _rebuild_namelist_db()
    except Exception as e:
        return jsonify({"error": f"File saved but DB rebuild failed: {e}"}), 500
    return jsonify({
        "saved": name,
        "total_records": total,
        "files": sorted(f.name for f in NAME_LIST_DIR.glob("*.xls*")),
    })


@app.get("/api/namelist/files")
def api_namelist_files():
    """List all Excel files currently in the name_list folder."""
    return jsonify({"files": sorted(f.name for f in NAME_LIST_DIR.glob("*.xls*"))})


@app.delete("/api/namelist/files/<path:filename>")
def api_namelist_delete(filename):
    """Remove an Excel file from name_list/ and rebuild the search DB."""
    path = NAME_LIST_DIR / secure_filename(filename)
    if path.exists():
        path.unlink()
    try:
        total = _rebuild_namelist_db()
    except Exception:
        total = 0
    return jsonify({
        "deleted": filename,
        "total_records": total,
        "files": sorted(f.name for f in NAME_LIST_DIR.glob("*.xls*")),
    })


# Auto-rebuild name-list DB at startup if files are already present
if list(NAME_LIST_DIR.glob("*.xls*")):
    try:
        _rebuild_namelist_db()
    except Exception as _e:
        print(f"[BRD] Name-list DB rebuild at startup failed: {_e}")


def _get_ssl_context(host="127.0.0.1"):
    """Return an (cert_path, key_path) tuple for a persistent self-signed cert.

    The cert is stored under DATA_DIR/ssl/ and reused on every start.
    SAN covers the FQDN, hostname, ``localhost`` and ``127.0.0.1`` so
    browsers accept it once IT imports it into the trusted root store.
    """
    import datetime as _dt
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import ipaddress

    ssl_dir = DATA_DIR / "ssl"
    ssl_dir.mkdir(parents=True, exist_ok=True)
    cert_path = ssl_dir / "cert.pem"
    key_path = ssl_dir / "key.pem"

    # Reuse existing cert if it exists and is not expired
    if cert_path.exists() and key_path.exists():
        try:
            existing = x509.load_pem_x509_certificate(cert_path.read_bytes())
            if existing.not_valid_after_utc > _dt.datetime.now(_dt.timezone.utc):
                return (str(cert_path), str(key_path))
        except Exception:
            pass  # regenerate

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "BRD Studio"),
    ])

    # Build SAN list — include all LAN IPs so mic works from any address
    san_dns = list({socket.getfqdn(), socket.gethostname(), "localhost"})
    san_ips_raw = ["127.0.0.1"]
    if host in ("0.0.0.0", "::", "localhost"):
        # Auto-detect all local IPs so the cert covers LAN/VPN access
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if ip not in san_ips_raw:
                    san_ips_raw.append(ip)
        except Exception:
            pass
        # Also grab the default-route IP (catches VPN adapters)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            default_ip = s.getsockname()[0]
            s.close()
            if default_ip not in san_ips_raw:
                san_ips_raw.append(default_ip)
        except Exception:
            pass
        # On Windows, use ipconfig to catch all adapter IPs
        try:
            import subprocess, re
            out = subprocess.check_output("ipconfig", text=True, timeout=5)
            for m in re.findall(r"IPv4[^:]*:\s*([\d.]+)", out):
                if m not in san_ips_raw and not m.startswith("169.254."):
                    san_ips_raw.append(m)
        except Exception:
            pass
    elif host not in ("127.0.0.1",):
        try:
            san_ips_raw.append(host)
        except Exception:
            san_dns.append(host)
    san_entries = [x509.DNSName(n) for n in san_dns]
    for ip_str in san_ips_raw:
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except ValueError:
            san_entries.append(x509.DNSName(ip_str))

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.timezone.utc))
        .not_valid_after(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return (str(cert_path), str(key_path))


def _parse_args():
    p = argparse.ArgumentParser(description="BRD Studio server")
    p.add_argument("--host", default="0.0.0.0",
                   help="Bind address (use 0.0.0.0 for LAN access)")
    p.add_argument("--port", type=int, default=5050)
    p.add_argument("--no-ssl", dest="no_ssl", action="store_true",
                   help="Disable HTTPS (use when behind a TLS-terminating proxy)")
    p.add_argument("--cert", default=None,
                   help="Path to TLS certificate file (PEM).  "
                        "When omitted a self-signed cert is auto-generated.")
    p.add_argument("--key", default=None,
                   help="Path to TLS private-key file (PEM).  "
                        "Required when --cert is supplied.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    ssl_ctx = None
    if not args.no_ssl:
        # ── Custom certificate supplied on the command line ──────────────
        if args.cert and args.key:
            cert_p, key_p = Path(args.cert), Path(args.key)
            if not cert_p.exists():
                print(f"ERROR: cert file not found: {cert_p}")
                sys.exit(1)
            if not key_p.exists():
                print(f"ERROR: key file not found: {key_p}")
                sys.exit(1)
            ssl_ctx = (str(cert_p), str(key_p))
            print(f"\n  Using TLS certificate: {cert_p}")
        elif args.cert or args.key:
            print("ERROR: both --cert and --key must be supplied together.")
            sys.exit(1)
        # ── Auto-generate self-signed cert ───────────────────────────────
        else:
            try:
                ssl_ctx = _get_ssl_context(args.host)
            except ImportError:
                # cryptography not installed — fall back to Flask adhoc SSL (pyOpenSSL)
                try:
                    import OpenSSL  # noqa: F401 — just check it's available
                    ssl_ctx = "adhoc"
                    print("\n  cryptography not installed — using adhoc SSL (pyOpenSSL).")
                    print("  The cert changes on every restart; accept the browser warning once.")
                    print("  For a stable cert: pip install cryptography\n")
                except ImportError:
                    print("WARNING: No SSL backend found — running on plain HTTP.")
                    print("         Mic will NOT work on remote browsers.")
                    print("         Fix: pip install cryptography   OR   pip install pyOpenSSL")
            except Exception as e:
                print(f"WARNING: Could not generate SSL cert: {e}")

    scheme = "https" if ssl_ctx else "http"

    if ssl_ctx and ssl_ctx != "adhoc":
        if not (args.cert and args.key):   # only print trust hint for self-signed certs
            print(f"\n  HTTPS certificate: {ssl_ctx[0]}")
            print("  To silence browser warnings, import this cert into your")
            print("  Trusted Root Certification Authorities store.\n")

    if getattr(sys, "frozen", False):
        threading.Timer(1.5, lambda: webbrowser.open(
            f"{scheme}://localhost:{args.port}")).start()
    else:
        print(f"  BRD Studio running at {scheme}://{args.host}:{args.port}")
        # Show all accessible URLs when binding to all interfaces
        if args.host in ("0.0.0.0", "::"):
            print(f"  Also accessible at:")
            print(f"    {scheme}://localhost:{args.port}")
            try:
                import subprocess as _sp, re as _re
                _out = _sp.check_output("ipconfig", text=True, timeout=5)
                for _m in _re.findall(r"IPv4[^:]*:\s*([\d.]+)", _out):
                    if not _m.startswith("169.254."):
                        print(f"    {scheme}://{_m}:{args.port}")
            except Exception:
                pass
        print()

    app.run(host=args.host, port=args.port, debug=False,
            use_reloader=False, ssl_context=ssl_ctx)

