"""
rfp_parser.py -- optional helper that pre-fills the intake from an
uploaded RFP/RFI document, so the user edits a draft instead of typing
from a blank page.

Matching backends:

  1. Sentence embeddings (BERT-family) via sentence-transformers when
     installed -- semantic similarity between each RFP paragraph and
     the field seed phrases. Default model: all-MiniLM-L6-v2 (local,
     ~80MB, no API key, no training).

  2. FLAN-T5 via transformers when requested -- each paragraph is
     classified into one or two intake field IDs, then matched source
     text is rewritten into BRD-style draft content. Default model:
     google/flan-t5-small.

  3. TF-IDF + cosine similarity (scikit-learn) -- always available,
     classical unsupervised NLP fit on the fly on the document you
     give it. Used automatically when the selected model backend is not
     installed or fails to load.

There is no training step and no dataset to collect. Improving the
matcher means editing SEED_PHRASES below (better example wording),
not retraining anything.

Force a backend with the environment variable:
    BRD_RFP_MATCHER=tfidf | embeddings | flan-t5 | auto   (default: auto)
"""

import os
import re
from pathlib import Path

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _sklearn_available = True
except ImportError:
    _sklearn_available = False

from .config import DETAIL_FIELDS, QUESTIONS  # noqa: F401 (re-exported)

# TF-IDF threshold is low because bag-of-words scores are sparse.
TFIDF_SIM_THRESHOLD = 0.08
# Embedding threshold is higher -- MiniLM cosine on related prose
# typically lands in the 0.25–0.55 band for real matches.
EMBED_SIM_THRESHOLD = 0.28
MAX_PARAS_PER_FIELD = 3
FLAN_T5_MAX_INPUT_CHARS = 1200
FLAN_T5_MAX_REWRITE_CHARS = 1800
FLAN_T5_MAX_PARAS = int(os.environ.get("BRD_FLAN_T5_MAX_PARAS", "80"))

# Default local sentence-transformer (BERT-family MiniLM). Small, fast,
# runs fully offline after the first download into the HF cache.
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_FLAN_T5_MODEL = "google/flan-t5-small"

# Hand-written phrasing per question -- examples, not training data.
# Written as natural language so both TF-IDF and embeddings can use them;
# embeddings benefit from full sentences, TF-IDF from the keyword density.
SEED_PHRASES = {
    # --- core questions (map to sections 1-5, 8) ---
    "q_problem": (
        "business problem pain point challenge issue manual effort error rate "
        "current as-is process today staff extract reconcile spreadsheet manual steps. "
        "What is broken in the current process and how does work run today?"
    ),
    "q_objective": (
        "objective goal aim outcome after go-live target state improve automate "
        "success metrics measurable benefit fte reduction cycle time savings percentage. "
        "What will be different after go-live and how is success measured?"
    ),
    "q_inscope": (
        "in scope this phase includes covered modules entities locations duration "
        "pilot rollout implementation timeline go-live. "
        "What is explicitly in scope for this phase?"
    ),
    "q_outscope": (
        "out of scope excluded not included deferred later phase. "
        "What is explicitly out of scope or deferred to a later phase?"
    ),
    "q_users": (
        "users roles user base analyst maker checker approver reviewer read-only "
        "administrator store manager supervisor. "
        "Who are the user roles and what does each need to do?"
    ),
    "q_features": (
        "functional requirements features must have capabilities system shall provide "
        "reports dashboards outputs mis summary weekly quarterly board pack extract "
        "artificial intelligence machine learning advanced analytics. "
        "What are the must-have features, reports and outputs?"
    ),
    "q_systems": (
        "integrate integration interface source system connect sap oracle finacle "
        "api erp power bi active directory. "
        "Which systems must this solution integrate with?"
    ),
    "q_regs": (
        "regulation regulatory compliance rbi sebi irdai dpdp gdpr pci-dss fssai gst "
        "deadline clause soc "
        "authentication authorization sso saml oauth mfa multi-factor single sign-on "
        "access control rbac role-based permission audit trail logging data residency "
        "encryption security compliance penetration vulnerability. "
        "Which specific regulations apply and are there hard compliance deadlines? "
        "How should users authenticate and what security rules apply?"
    ),
    "q_tech": (
        "deployment cloud on-premise hybrid azure aws gcp infrastructure device laptop "
        "desktop mobile tablet scanner hardware data format csv xml json api sftp "
        "transfer protocol communication email smtp https notification webhook network. "
        "What is the technical setup — deployment, devices, data formats, protocols?"
    ),
    "q_nonfunc": (
        "performance response time latency throughput sla seconds availability uptime "
        "disaster recovery rto rpo backup failover scalability concurrent users volume "
        "growth capacity peak load non-functional quality attribute. "
        "What performance, uptime and scalability expectations apply?"
    ),
    # --- detail fields (map to sections 3, 4, 5.2, 11-12) ---
    "d_if_hardware": (
        "hardware device scanner server appliance on-premise kit peripherals "
        "barcode handheld zebra"
    ),
    "d_if_software": (
        "software component version database library operating system middleware "
        "application stack"
    ),
    "d_if_data": (
        "data exchange file format csv xml json sftp transfer encryption aes "
        "batch import export"
    ),
    "d_if_security": (
        "authentication authorization single sign-on saml mfa encryption access control "
        "azure ad active directory"
    ),
    "d_if_comm": (
        "email notification smtp https protocol network communication messaging "
        "in-app push webhook"
    ),
    "d_challenges": (
        "existing challenges limitation gaps bottleneck delay rework duplication "
        "error-prone stockouts"
    ),
    "d_to_be": (
        "to-be process future state proposed workflow automated straight through "
        "after go-live"
    ),
    "d_proposed": (
        "proposed solution architecture platform deployment cloud module design "
        "centralized system"
    ),
    "d_performance": (
        "performance response time seconds throughput batch window sla latency "
        "page load concurrent"
    ),
    "d_availability": (
        "availability uptime disaster recovery rto rpo retention business continuity "
        "maintenance window"
    ),
    "d_security_nfr": (
        "security audit trail logging data residency encryption at rest privileged "
        "access soc 2"
    ),
    "d_scalability": (
        "volume concurrent users records per day growth scalability transactions "
        "peak season sku"
    ),
    "d_prototype": (
        "prototype mock-up wireframe demo proof of concept screenshot"
    ),
}

# ---------------------------------------------------------------------------
# Embedding backend (optional)
# ---------------------------------------------------------------------------

_embed_model = None          # sentence_transformers.SentenceTransformer | None
_embed_load_attempted = False
_embed_load_error = None


def embeddings_available():
    """True if sentence-transformers is importable (model may still need download)."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _get_embed_model():
    """Lazy-load and cache the sentence-transformer model. Returns None on failure."""
    global _embed_model, _embed_load_attempted, _embed_load_error
    if _embed_model is not None:
        return _embed_model
    if _embed_load_attempted and _embed_model is None:
        return None
    _embed_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        model_name = os.environ.get("BRD_EMBED_MODEL", DEFAULT_EMBED_MODEL)
        _embed_model = SentenceTransformer(model_name)
        return _embed_model
    except Exception as exc:
        _embed_load_error = str(exc)
        _embed_model = None
        return None


def _route_with_embeddings(paras, field_ids, seed_texts):
    """Semantic routing via sentence embeddings + cosine similarity."""
    import numpy as np

    model = _get_embed_model()
    if model is None:
        return None

    # Encode paragraphs and seeds in one batch for speed.
    all_texts = list(paras) + list(seed_texts)
    vectors = model.encode(
        all_texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    para_m = vectors[: len(paras)]
    seed_m = vectors[len(paras):]
    # Normalized vectors → cosine = dot product
    sims = np.matmul(para_m, seed_m.T)

    assignments = {f: [] for f in field_ids}
    for pi, row in enumerate(sims):
        top = sorted(enumerate(row.tolist()), key=lambda x: -x[1])[:2]
        for fi, score in top:
            if score >= EMBED_SIM_THRESHOLD:
                assignments[field_ids[fi]].append((float(score), pi))

    draft = {}
    for field, hits in assignments.items():
        hits.sort(key=lambda x: -x[0])
        chosen = sorted([pi for _, pi in hits[:MAX_PARAS_PER_FIELD]])
        if chosen:
            draft[field] = "\n".join(paras[pi] for pi in chosen)
    return draft


# ---------------------------------------------------------------------------
# FLAN-T5 backend (optional)
# ---------------------------------------------------------------------------

_flan_pipeline = None
_flan_load_attempted = False
_flan_load_error = None


def flan_t5_available():
    """True if transformers is importable (model may still need download)."""
    try:
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _get_flan_pipeline():
    """Lazy-load and cache the FLAN-T5 text2text pipeline."""
    global _flan_pipeline, _flan_load_attempted, _flan_load_error
    if _flan_pipeline is not None:
        return _flan_pipeline
    if _flan_load_attempted and _flan_pipeline is None:
        return None
    _flan_load_attempted = True
    try:
        from transformers import pipeline
        model_name = os.environ.get("BRD_FLAN_T5_MODEL", DEFAULT_FLAN_T5_MODEL)
        _flan_pipeline = pipeline(
            "text2text-generation",
            model=model_name,
            tokenizer=model_name,
        )
        return _flan_pipeline
    except Exception as exc:
        _flan_load_error = str(exc)
        _flan_pipeline = None
        return None


def _field_labels():
    labels = {q["id"]: q["q"] for q in QUESTIONS}
    for fields in DETAIL_FIELDS.values():
        for field in fields:
            labels[field["key"]] = field["label"]
    return labels


def _parse_flan_ids(text, field_ids):
    allowed = set(field_ids)
    lowered = (text or "").lower()
    hits = []
    for token in re.split(r"[^a-z0-9_]+", lowered):
        if token in allowed and token not in hits:
            hits.append(token)
    if not hits and "none" not in lowered:
        compact = re.sub(r"\s+", "", lowered)
        for field_id in field_ids:
            if field_id in compact and field_id not in hits:
                hits.append(field_id)
    return hits[:2]


def _route_with_flan_t5(paras, field_ids, seed_texts):
    """Instruction-based paragraph routing via FLAN-T5.

    The model first chooses relevant intake field IDs, then rewrites the
    matched source text into concise BRD-style draft content.
    """
    pipe = _get_flan_pipeline()
    if pipe is None:
        return None

    labels = _field_labels()
    options = "\n".join(f"{fid}: {labels.get(fid, fid)}" for fid in field_ids)
    assignments = {f: [] for f in field_ids}

    for pi, para in enumerate(paras[:FLAN_T5_MAX_PARAS]):
        prompt = (
            "You route RFP text into a Business Requirements Document intake.\n"
            "Choose the best one or two field IDs from the list. If the text "
            "does not match any field, answer none. Return only field IDs, "
            "comma separated.\n\n"
            f"Field IDs:\n{options}\n\n"
            f"RFP text:\n{para[:FLAN_T5_MAX_INPUT_CHARS]}\n\n"
            "Answer:"
        )
        result = pipe(prompt, max_new_tokens=24, do_sample=False, truncation=True)
        generated = (result[0] or {}).get("generated_text", "")
        for field_id in _parse_flan_ids(generated, field_ids):
            assignments[field_id].append(pi)

    draft = {}
    for field, hits in assignments.items():
        chosen = sorted(dict.fromkeys(hits))[:MAX_PARAS_PER_FIELD]
        if not chosen:
            continue
        source = "\n".join(paras[pi] for pi in chosen)
        rewrite_prompt = (
            "Rewrite the source text as concise Business Requirements Document "
            "draft content for this intake field. Preserve specific facts, names, "
            "systems, metrics, constraints and dates from the source. Do not add "
            "facts that are not present. Use clear professional wording. If there "
            "are multiple items, use short bullet lines.\n\n"
            f"Field ID: {field}\n"
            f"Field question: {labels.get(field, field)}\n\n"
            f"Source text:\n{source[:FLAN_T5_MAX_REWRITE_CHARS]}\n\n"
            "Rewritten BRD draft:"
        )
        result = pipe(rewrite_prompt, max_new_tokens=160, do_sample=False, truncation=True)
        rewritten = ((result[0] or {}).get("generated_text") or "").strip()
        draft[field] = rewritten or source
    return draft


_STOPWORDS = {
    "the","and","for","are","this","that","with","have","will","from",
    "they","been","more","also","than","its","can","not","all","any",
    "has","was","but","our","their","your","which","when","what","how",
}

def _route_keyword_fallback(paras, field_ids, seed_texts):
    """Simple keyword overlap fallback used when scikit-learn is not installed."""
    assignments = {f: [] for f in field_ids}
    for fi, seed in enumerate(seed_texts):
        seed_words = set(re.findall(r'\b[a-z]{3,}\b', seed.lower())) - _STOPWORDS
        if not seed_words:
            continue
        for pi, para in enumerate(paras):
            para_words = set(re.findall(r'\b[a-z]{3,}\b', para.lower()))
            overlap = len(seed_words & para_words)
            if overlap > 0:
                score = overlap / max(len(seed_words), 1)
                if score >= 0.05:
                    assignments[field_ids[fi]].append((score, pi))
    draft = {}
    for field, hits in assignments.items():
        hits.sort(key=lambda x: -x[0])
        chosen = sorted([pi for _, pi in hits[:MAX_PARAS_PER_FIELD]])
        if chosen:
            draft[field] = "\n".join(paras[pi] for pi in chosen)
    return draft


def _route_with_tfidf(paras, field_ids, seed_texts):
    """Lexical routing via TF-IDF + cosine similarity, or keyword fallback."""
    if not _sklearn_available:
        return _route_keyword_fallback(paras, field_ids, seed_texts)
    vec = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2), sublinear_tf=True, min_df=1
    )
    matrix = vec.fit_transform(paras + seed_texts)
    para_m, seed_m = matrix[: len(paras)], matrix[len(paras):]
    sims = cosine_similarity(para_m, seed_m)

    assignments = {f: [] for f in field_ids}
    for pi, row in enumerate(sims):
        top = sorted(enumerate(row), key=lambda x: -x[1])[:2]
        for fi, score in top:
            if score >= TFIDF_SIM_THRESHOLD:
                assignments[field_ids[fi]].append((float(score), pi))

    draft = {}
    for field, hits in assignments.items():
        hits.sort(key=lambda x: -x[0])
        chosen = sorted([pi for _, pi in hits[:MAX_PARAS_PER_FIELD]])
        if chosen:
            draft[field] = "\n".join(paras[pi] for pi in chosen)
    return draft


def _preferred_matcher():
    """auto | embeddings | flan-t5 | tfidf from BRD_RFP_MATCHER env."""
    choice = (os.environ.get("BRD_RFP_MATCHER") or "auto").strip().lower()
    if choice in ("embeddings", "embedding", "bert", "sbert", "mini-lm", "minilm"):
        return "embeddings"
    if choice in ("flan", "flan-t5", "flan_t5", "t5"):
        return "flan-t5"
    if choice in ("tfidf", "tf-idf", "sklearn"):
        return "tfidf"
    return "auto"


def route_paragraphs(paras):
    """Route RFP paragraphs to intake fields.

    Uses the requested backend. In auto mode it tries embeddings first,
    then falls back to TF-IDF. FLAN-T5 is opt-in because it is slower
    and usually needs a separate transformers install/download.
    """
    if not paras:
        return {}, "none"

    field_ids = list(SEED_PHRASES.keys())
    seed_texts = [SEED_PHRASES[f] for f in field_ids]
    prefer = _preferred_matcher()

    if prefer in ("auto", "embeddings"):
        try:
            draft = _route_with_embeddings(paras, field_ids, seed_texts)
            if draft is not None:
                return draft, "embeddings"
        except Exception:
            draft = None  # fall through to the next available backend

    if prefer == "flan-t5":
        try:
            draft = _route_with_flan_t5(paras, field_ids, seed_texts)
            if draft is not None:
                return draft, "flan-t5"
        except Exception:
            draft = None  # fall through to TF-IDF

    draft = _route_with_tfidf(paras, field_ids, seed_texts)
    return draft, "tfidf"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def read_rfp(path):
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".docx":
        from docx import Document
        doc = Document(p)
        # Blank line between Word paragraphs so split_paragraphs keeps
        # each as its own chunk (many RFPs have no empty paragraphs).
        return "\n\n".join(par.text for par in doc.paragraphs if par.text.strip())
    if suffix in (".xlsx", ".xls"):
        return read_excel(p)
    return p.read_text(encoding="utf-8", errors="ignore")


def read_excel(path):
    """Flatten every sheet's cells into pseudo-paragraphs (one per row),
    so unstructured notes kept in a spreadsheet -- meeting notes, a
    requirements list, anything without headings -- feed the same
    paragraph-by-paragraph matcher as a .docx RFP does."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    lines = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n\n".join(lines)


def split_paragraphs(text):
    """Split into blank-line-delimited chunks, merge short bullet runs.

    Also splits on numbered section headings (e.g. '3.1 In Scope') when a
    long block has no blank lines, so dense RFPs still yield useful units.
    """
    rows = re.split(r"\n\s*\n", text)
    paras, buf = [], []
    for chunk in rows:
        lines = [l.strip() for l in chunk.split("\n") if l.strip()]
        if not lines:
            continue
        # Further split a dense block on numbered headings if it is long
        if len(lines) == 1 and len(lines[0]) > 400:
            pieces = re.split(
                r"(?=(?:^|\s)(?:\d+\.)+\d*\s+[A-Z])", lines[0]
            )
            lines = [p.strip() for p in pieces if p and p.strip()]
        joined = " ".join(lines)
        if len(joined) < 25:
            buf.append(joined)
            continue
        if buf:
            joined = " ".join(buf) + " " + joined
            buf = []
        paras.append(joined)
    if buf:
        paras.append(" ".join(buf))
    return paras


PROJECT_PATTERNS = {
    "organization": r"(?:issued by|on behalf of)\s+([A-Z][\w&.,'\- ]{2,60})",
    "project_name": r"(?:project name|initiative)[:\s]+([\w \-]{4,80})",
}


def extract_project_fields(text):
    out = {}
    for key, pattern in PROJECT_PATTERNS.items():
        m = re.search(pattern, text, re.I)
        if m:
            out[key] = m.group(1).strip(" .")
    return out


def parse(rfp_path):
    """Read an RFP file and return a draft intake payload for the wizard.

    Extra keys in the response:
      matcher          -- 'embeddings' | 'flan-t5' | 'tfidf' | 'none'
      embeddings_available -- whether sentence-transformers is installed
      flan_t5_available -- whether transformers is installed
    """
    text = read_rfp(rfp_path)
    paras = split_paragraphs(text)
    routed, matcher = route_paragraphs(paras)
    project_fields = extract_project_fields(text)
    draft_answers = {k: v for k, v in routed.items() if k.startswith("q_")}
    draft_detail = {k: v for k, v in routed.items() if k.startswith("d_")}
    return {
        "project": project_fields,
        "answers": draft_answers,
        "detail": draft_detail,
        "paragraphs_read": len(paras),
        "fields_matched": len(draft_answers) + len(draft_detail),
        "matcher": matcher,
        "embeddings_available": embeddings_available(),
        "flan_t5_available": flan_t5_available(),
    }


def parse_text(text, extra_project=None):
    """Parse raw text (e.g. an email body) exactly like parse() does for files.

    extra_project -- optional dict of project fields already known (e.g. sender
    name, subject) that will override/supplement what extract_project_fields
    finds in the body text.
    """
    paras = split_paragraphs(text)
    routed, matcher = route_paragraphs(paras)
    project_fields = extract_project_fields(text)
    if extra_project:
        project_fields.update({k: v for k, v in extra_project.items() if v})
    draft_answers = {k: v for k, v in routed.items() if k.startswith("q_")}
    draft_detail  = {k: v for k, v in routed.items() if k.startswith("d_")}
    return {
        "project": project_fields,
        "answers": draft_answers,
        "detail":  draft_detail,
        "paragraphs_read": len(paras),
        "fields_matched": len(draft_answers) + len(draft_detail),
        "matcher": matcher,
        "embeddings_available": embeddings_available(),
        "flan_t5_available": flan_t5_available(),
    }
