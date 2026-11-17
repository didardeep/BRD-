/* Frontend for the BRD wizard.

   Holds no schema of its own -- the outline, questions, detail fields,
   house-template tables, readiness rules and gap bank all come from
   GET /api/config, so brd_agent/config.py is the only place that ever
   needs editing. */

let CFG = null;

// Inline SVG icons — no CDN dependency
const IC_MIC   = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg>`;
const IC_STOP  = `<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>`;
const IC_TRASH = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6M9 6V4h6v2"/></svg>`;

const state = {
  step: 0,
  activeDetail: null,    // key of currently shown detail group (step 3)
  activeTable: null,     // id of currently shown table preset (step 4)
  fcDrawerOpen: false,   // whether the flowchart drawer is open
  sidebarExpanded: {},   // { stepIndex: boolean } — non-active step peek-expanded
  project: { version: "1.0" },
  answers: {},
  answerHistory: {},     // { q_id: string[] } - last 5 values for undo (Feature 8)
  detail: {},
  tables: {},            // { table_spec_id: [[cell, ...], ...] }
  tableAuto: {},          // { table_spec_id: true } - currently showing auto-derived rows
  tableEditing: {},       // { table_spec_id: true } - table is unlocked for hand-editing
  custom: [],            // freeform tables with no slot in the template
  images: [],            // [{ filename, url, caption }] - Prototype system screenshots
  customFlowcharts: [],  // [{ title, steps: [{text, type, lane?}], swimLanes? }] for §12.1
  fcCollapsed: {},       // { index: true } - tracks collapsed flowchart cards
  rowData: {},           // { q_id: [{label, desc}] } - structured row input for row-based questions
  rowEditing: {},        // { q_id: true } - row inputs are unlocked for hand-editing
  roleSugOpen: {},       // { q_id: true } - role suggestion panel expanded
  regData: null,         // { _industry, items: [{reg, checked, note}], other } - regulation picker state
  customQuestions: [],   // [{ id, q }] - user-defined questions (Feature 6)
  sectionLocks: {},      // { key: true } - approved/locked sections (Feature 5)
  mdPreview: {},         // { q_id: true } - markdown preview active (Feature 7)
  activeCat: null,
  openAcc: {},
  openTbl: {},
  template: null,
  projectId: null,       // server-side project id (Feature 2)
  includeDiagnostics: true,
  buildResult: null,
  buildError: null,
  stepError: null,
};

const STEP_META = [
  { label: "Project Details", sub: "Cover page & document control" },
  { label: "Core Questions", sub: "" },
  { label: "Detail Fields", sub: "Auto-derived; override if needed" },
  { label: "Template Tables", sub: "Functional, integrations & more" },
  { label: "Create Document", sub: "Build the .docx" },
];

/* ------------------------------------------------------------------ */
/* draft save / load (localStorage)                                    */
/* ------------------------------------------------------------------ */

const DRAFT_KEY = "brd_studio_draft";

function saveDraft() {
  const draft = {
    project: state.project,
    answers: state.answers,
    answerHistory: state.answerHistory,
    detail: state.detail,
    tables: state.tables,
    custom: state.custom,
    images: state.images,
    customFlowcharts: state.customFlowcharts,
    rowData: state.rowData,
    regData: state.regData,
    customQuestions: state.customQuestions,
    sectionLocks: state.sectionLocks,
    projectId: state.projectId,
    step: state.step,
    activeDetail: state.activeDetail,
    activeTable: state.activeTable,
    savedAt: new Date().toISOString(),
  };
  localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  showToast("Draft saved");
  updateDraftStatus();
}

function loadDraft() {
  const raw = localStorage.getItem(DRAFT_KEY);
  if (!raw) return false;
  try {
    const d = JSON.parse(raw);
    if (d.project) Object.assign(state.project, d.project);
    if (d.answers) Object.assign(state.answers, d.answers);
    if (d.detail) Object.assign(state.detail, d.detail);
    if (d.tables) Object.assign(state.tables, d.tables);
    if (d.custom) state.custom = d.custom;
    if (d.images) state.images = d.images;
    if (d.customFlowcharts) {
      // Migrate old {title, text} format to {title, steps: [{text, type}]}
      state.customFlowcharts = d.customFlowcharts.map(fc => {
        if (fc.steps) return fc;
        const lines = (fc.text || "").split("\n").filter(l => l.trim());
        return { title: fc.title || "", steps: lines.map(l => ({ text: l.trim(), type: "process" })) };
      });
    }
    if (d.rowData)          state.rowData          = d.rowData;
    if (d.regData)          state.regData          = d.regData;
    if (d.answerHistory)    state.answerHistory    = d.answerHistory;
    if (d.customQuestions)  state.customQuestions  = d.customQuestions;
    if (d.projectId)        state.projectId        = d.projectId;
    if (typeof d.step === "number") state.step = d.step;
    if (d.activeDetail) state.activeDetail = d.activeDetail;
    if (d.activeTable)  state.activeTable  = d.activeTable;
    return true;
  } catch { return false; }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY);
  showToast("Draft cleared");
}

function hasDraft() {
  return !!localStorage.getItem(DRAFT_KEY);
}

function draftTimestamp() {
  try {
    const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || "{}");
    if (!d.savedAt) return null;
    return new Date(d.savedAt).toLocaleString();
  } catch { return null; }
}

function showErrorDialog(errors) {
  let overlay = document.getElementById("err-dialog-overlay");
  if (overlay) overlay.remove();
  overlay = document.createElement("div");
  overlay.id = "err-dialog-overlay";
  overlay.className = "err-dialog-overlay";
  overlay.innerHTML = `
    <div class="err-dialog" role="alertdialog" aria-modal="true">
      <div class="err-dialog-icon"><i class="ti ti-alert-triangle"></i></div>
      <div class="err-dialog-title">Please Review Your Entries</div>
      <div class="err-dialog-body">
        <p>Please fix the following before continuing:</p>
        <ul>${errors.map(e => `<li>${esc(e)}</li>`).join("")}</ul>
      </div>
      <button class="err-dialog-btn" id="err-dialog-ok">OK</button>
    </div>`;
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  document.getElementById("err-dialog-ok").addEventListener("click", close);
  overlay.addEventListener("click", e => { if (e.target === overlay) close(); });
}

function showToast(msg, isError) {
  let el = document.getElementById("draft-toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "draft-toast";
    el.className = "draft-toast";
    document.body.appendChild(el);
  }
  el.innerHTML = (isError ? '<i class="ti ti-alert-triangle"></i> ' : "") + esc(msg);
  el.classList.toggle("error", !!isError);
  el.classList.add("show");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("show"), isError ? 4000 : 2000);
}


/* Push the current answer into history before overwriting (Feature 8). */
function pushAnswerHistory(qid, oldVal) {
  if (!oldVal && oldVal !== 0) return;
  if (!state.answerHistory[qid]) state.answerHistory[qid] = [];
  state.answerHistory[qid].push(String(oldVal));
  if (state.answerHistory[qid].length > 5) state.answerHistory[qid].shift();
}

/* Sync row-based question data into the flat answers string.
   Format: "Label: Description" per line — works with split_items() in the backend.
   For tables, the structured rowData is sent separately. */
function syncRowToAnswer(qid) {
  const rows = state.rowData[qid] || [];
  state.answers[qid] = rows
    .filter(r => (r.label || "").trim() || (r.desc || "").trim())
    .map(r => {
      const label = (r.label || "").trim();
      const desc = (r.desc || "").trim();
      const access = (r.access || "").trim();
      const line = desc ? `${label}: ${desc}` : label;
      return access ? `${line} (Access: ${access})` : line;
    })
    .join("\n");
  updateProgressBar();
}

function syncRegsToAnswer() {
  if (!state.regData) return;
  const lines = [];
  state.regData.items.forEach(item => {
    if (item.checked) {
      lines.push(item.note ? `${item.reg}: ${item.note}` : item.reg);
    }
  });
  if ((state.regData.other || "").trim()) {
    state.regData.other.trim().split(/[\n,]/).forEach(l => {
      if (l.trim()) lines.push(l.trim());
    });
  }
  state.answers.q_regs = lines.join("\n");
  updateProgressBar();
}

/* Initialise rowData for all row-type questions (migrates old text answers). */
function initRowData() {
  (CFG.questions || []).forEach(q => {
    if (q.input !== "rows") return;
    if (state.rowData[q.id] && state.rowData[q.id].length) return; // already loaded from draft
    // Migrate from existing text answer
    const text = (state.answers[q.id] || "").trim();
    if (text) {
      state.rowData[q.id] = text.split("\n").filter(l => l.trim()).map(line => {
        const idx = line.indexOf(": ");
        if (idx > 0) return { label: line.slice(0, idx).trim(), desc: line.slice(idx + 2).trim() };
        return { label: line.trim(), desc: "" };
      });
    } else {
      state.rowData[q.id] = [{ label: "", desc: "" }];
    }
  });
}

/* Initialise regulation picker state from COMPLIANCE_MAP + existing answer. */
function initRegData() {
  const industry = state.project.industry || "";
  const regs = (CFG.compliance_map || {})[industry] || [];

  // Already initialised for this industry
  if (state.regData && state.regData._industry === industry) return;

  // Carry over state from a previous industry selection
  const oldItems = (state.regData && state.regData.items) || [];
  const oldMap = {};
  oldItems.forEach(item => { oldMap[item.reg] = item; });

  // Migration: parse existing free-text answer into structured data
  const existingText = (state.answers.q_regs || "").trim();
  const textMap = {};
  const otherLines = [];
  if (existingText && oldItems.length === 0) {
    existingText.split("\n").filter(l => l.trim()).forEach(line => {
      const colonIdx = line.indexOf(": ");
      const regName = colonIdx > 0 ? line.slice(0, colonIdx).trim() : line.trim();
      const note    = colonIdx > 0 ? line.slice(colonIdx + 2).trim() : "";
      const matched = regs.find(r => r.toLowerCase() === regName.toLowerCase());
      if (matched) { textMap[matched] = note; }
      else         { otherLines.push(line.trim()); }
    });
  }

  state.regData = {
    _industry: industry,
    items: regs.map(r => ({
      reg:     r,
      checked: oldMap[r] ? oldMap[r].checked : (r in textMap),
      note:    oldMap[r] ? oldMap[r].note    : (textMap[r] || ""),
    })),
    other: state.regData ? state.regData.other : otherLines.join(", "),
  };
  syncRegsToAnswer();
}

let _whoami = { username: "", display_name: "" };

async function boot() {
  [CFG] = await Promise.all([
    fetch("/api/config").then(r => r.json()),
    fetch("/api/whoami").then(r => r.json()).then(d => { _whoami = d; }).catch(() => {}),
  ]);
  const cats = coreQuestionCats();
  state.activeCat = cats[0];
  (CFG.table_presets || []).forEach(p => { state.tables[p.id] = []; });
  const hadDraft = hasDraft();
  if (hadDraft) loadDraft();
  // Apply org defaults to empty project fields (only matters for fresh sessions)
  const defs = CFG.org_defaults || {};
  Object.entries(defs).forEach(([k, v]) => {
    if (v && !(state.project[k] || "").trim()) state.project[k] = v;
  });
  // prepared_by left blank — user types it manually
  applyFieldDefaults();
  initRowData();
  initRegData();
  bindGlobalUploads();
  render();
  if (state.step === 2 || state.step === 3) syncAutoTables();
}

/* ------------------------------------------------------------------ */
/* readiness -- mirrors brd_generator.mvi_status()                      */
/* ------------------------------------------------------------------ */

function filled(key) {
  return String(state.answers[key] ?? state.detail[key] ?? "").trim().length > 0;
}

function openGaps() {
  return Object.entries(CFG.gap_questions || {})
    .filter(([k]) => !filled(k))
    .map(([k, v]) => ({ field: k, ...v }))
    .sort((a, b) => ({ High: 0, Medium: 1, Low: 2 }[a.priority] - { High: 0, Medium: 1, Low: 2 }[b.priority]));
}

/* ------------------------------------------------------------------ */
/* step validation / gating                                            */
/* ------------------------------------------------------------------ */

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/* Fill project fields that declare a default (e.g. Document date = today). */
function applyFieldDefaults() {
  (CFG.project_fields || []).forEach(f => {
    if (f.default === "today" && !(state.project[f.key] || "").trim()) state.project[f.key] = todayISO();
  });
}

/* Blocking date rules -- go-live can't be backdated, and
   document date <= project start date <= target go-live date. */
function dateErrors() {
  const e = [];
  const { doc_date, start_date, end_date } = state.project;
  if (end_date && end_date < todayISO())
    e.push("Target go-live date cannot be a past (backdated) date.");
  if (start_date && end_date && end_date < start_date)
    e.push("Target go-live date cannot be earlier than the project start date.");
  if (doc_date && start_date && start_date < doc_date)
    e.push("Project start date cannot be earlier than the document date.");
  if (doc_date && end_date && !start_date && end_date < doc_date)
    e.push("Target go-live date cannot be earlier than the document date.");
  return e;
}

/* ---------------- answer quality (completeness / relevance) ---------------- */

function _norm(s) {
  return String(s || "").trim().toLowerCase().replace(/[\s.!]+$/, "").replace(/\s+/g, " ");
}

function _words(s) {
  return String(s || "").match(/[A-Za-z0-9][A-Za-z0-9'&/.+#-]*/g) || [];
}

function _isPlaceholder(s) {
  const n = _norm(s);
  if (!n) return true;
  if ((CFG.quality?.placeholders || []).includes(n)) return true;
  if (/^[\W_]+$/.test(n)) return true;                       // only punctuation
  if (/^(.)\1+$/.test(n.replace(/\s/g, ""))) return true;    // "aaaa", "xxxxx"
  return false;
}

function _isNoneAnswer(s) {
  return (CFG.quality?.none_answers || []).includes(_norm(s));
}

/* Real one- and two-letter words, so they don't count as stray letters. */
const _SHORT_WORDS = new Set(["a","i","am","an","as","at","be","by","do","go","he","if","in","is",
  "it","me","my","no","of","on","or","so","to","up","us","we","ai","ui","hr","id","ok","vs","eg","ie"]);

function _looksMeaningless(s) {
  const words = _words(s).map(w => w.toLowerCase());
  if (words.length >= 4 && new Set(words).size / words.length < 0.35) return true;  // "test test test test"
  const stray = words.filter(w => w.length <= 2 && /^[a-z]+$/.test(w) && !_SHORT_WORDS.has(w));
  if (words.length >= 3 && stray.length / words.length > 0.4) return true;          // "bd f d s a a h f"
  const long = words.filter(w => w.length >= 4 && /^[a-z]+$/.test(w));
  const noVowel = long.filter(w => !/[aeiouy]/.test(w));
  return long.length >= 2 && noVowel.length / long.length > 0.5;                    // "sdfg hjkl"
}

/* Remove the headings of an inserted questionnaire template, so that an
   untouched template doesn't count as an answer. */
function _stripTemplate(text, template) {
  if (!template) return String(text || "");
  const heads = template.split("\n").map(l => l.split(":")[0].trim()).filter(Boolean);
  const prompt = CFG.template_fill_prompt || "";
  return String(text || "").split("\n").map(line => {
    if (prompt) line = line.split(prompt).join("");
    const h = heads.find(hd => line.trim().startsWith(hd + ":"));
    return h ? line.trim().slice(h.length + 1) : line;
  }).join("\n").trim();
}

/* Returns a reason string if `text` isn't meaningful, else null. */
function textIssue(text, minWords, opts = {}) {
  const t = String(text || "").trim();
  if (opts.allowNone && _isNoneAnswer(t)) return null;
  if (_isPlaceholder(t))
    return `contains a placeholder ("${t}") \u2014 enter meaningful information${opts.optional ? " or leave it blank" : ""}`;
  if (_looksMeaningless(t)) return "does not look like meaningful text — please write useful, real details";
  const n = _words(t).length;
  if (minWords && n < minWords) return `is too brief (${n} word${n === 1 ? "" : "s"}) \u2014 please give at least ${minWords} words of detail`;
  return null;
}

function _short(q) {
  return q.cat ? `${q.cat}: "${q.q.length > 60 ? q.q.slice(0, 57) + "\u2026" : q.q}"` : `"${q.q}"`;
}

/* All problems with one core question -- missing (if required) or low quality. */
function questionErrors(q) {
  const errs = [];
  const minText = CFG.quality?.min_words_text || 8;
  const minDesc = CFG.quality?.min_words_row_desc || 4;
  if (q.input === "rows") {
    const fields = q.row_fields || ["Item", "Description"];
    const rows = (state.rowData[q.id] || []).filter(r => (r.label || "").trim() || (r.desc || "").trim());
    if (!rows.length) {
      if (q.required) errs.push(q.q);
      return errs;
    }
    // A single "None" / "Standalone" row is a valid answer where allowed.
    if (q.allow_none && rows.length === 1 && _isNoneAnswer(rows[0].label) && !(rows[0].desc || "").trim()) return errs;
    rows.forEach((r, i) => {
      const label = (r.label || "").trim();
      const tag = `${_short(q)} \u2014 row ${i + 1}${label ? ` ("${label}")` : ""}`;
      if (!label) errs.push(`${tag}: ${fields[0]} is missing.`);
      else if (_isPlaceholder(label)) errs.push(`${tag}: ${fields[0]} contains a placeholder \u2014 enter a real ${fields[0].toLowerCase()}.`);
      const di = textIssue(r.desc, minDesc);
      if (di) errs.push(`${tag}: ${fields[1]} ${(r.desc || "").trim() ? di : "is missing"}.`);
      if (q.access_field && !(r.access || "").trim()) errs.push(`${tag}: select an access level.`);
    });
    return errs;
  }
  const raw = _stripTemplate(state.answers[q.id], q.template);
  if (!raw.trim()) {
    if (q.required) errs.push(q.q);
    return errs;
  }
  const issue = textIssue(raw, minText, { allowNone: q.allow_none, optional: !q.required });
  if (issue) errs.push(`${_short(q)} ${issue}.`);
  return errs;
}

function projectErrors() {
  const errors = [];
  (CFG.project_fields || []).forEach(f => {
    const v = (state.project[f.key] || "").trim();
    if (!v) {
      if (f.required) errors.push(`"${f.label}" is required.`);
      return;
    }
    if (f.type === "text" || f.type === "textarea") {
      const issue = textIssue(v, f.type === "textarea" ? (CFG.quality?.min_words_text || 8) : 0);
      if (issue) errors.push(`"${f.label}" ${issue}.`);
    }
  });
  if (state.project.industry === "Other" && !(state.project.industry_other || "").trim()) {
    errors.push(`"Industry (specify)" is required when "Other" is selected.`);
  }
  return errors.concat(dateErrors());
}

function validateStep(i) {
  if (i === 0) return projectErrors();
  if (i === 1) return (CFG.questions || []).flatMap(questionErrors);
  return [];
}

function errorBanner() {
  if (!state.stepError || !state.stepError.length) return "";
  return `<div class="step-error"><i class="ti ti-alert-triangle" aria-hidden="true"></i>
    <div>${state.stepError.map(esc).join("<br>")}</div></div>`;
}

/* ------------------------------------------------------------------ */
/* rail                                                                */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/* Status helpers for sidebar dots                                     */
/* ------------------------------------------------------------------ */

function titleCase(s) {
  const small = new Set(["a","an","the","and","but","or","of","in","on","at","to","for","with","by"]);
  return s.replace(/\S+/g, (w, i) =>
    (i === 0 || !small.has(w.toLowerCase())) ? w[0].toUpperCase() + w.slice(1) : w.toLowerCase()
  );
}

function catStatus(cat) {
  if (!CFG) return "verify";
  const qs = (CFG.questions || []).filter(q => q.cat === cat);
  const answered = qs.filter(q =>
    (state.answers[q.id] || "").trim() ||
    (state.rowData[q.id] || []).some(r => (r.label || "").trim() || (r.desc || "").trim())
  ).length;
  if (qs.length > 0 && answered === qs.length) return "done";
  if (answered > 0) return "partial";
  return "verify";
}

/* Detail groups edited as a template table (e.g. Non-Functional) */
function detailTableId(area) {
  return (CFG.detail_tables || {})[area] || null;
}

function detailHasScreenshots(area) {
  return (CFG.detail_screenshots || []).includes(area);
}

/* Template-table presets shown on the Template Tables step -- tables that
   are edited inside a Detail Fields group are left out. */
function templateTablePresets() {
  const hosted = Object.values(CFG.detail_tables || {});
  return (CFG.table_presets || []).filter(p => !hosted.includes(p.id));
}

function detailStatus(area) {
  if (!CFG) return "verify";
  const tid = detailTableId(area);
  if (tid) return tableStatus(tid);
  const lockKey = `detail_${area}`;
  if (state.sectionLocks[lockKey]) return "approved";
  const fields = (CFG.detail_fields || {})[area] || [];
  const n = fields.filter(f => (state.detail[f.key] || "").trim()).length;
  if (fields.length > 0 && n === fields.length) return "done";
  if (n > 0) return "partial";
  return "verify";
}

function tableStatus(id) {
  if (state.sectionLocks[`tbl_${id}`]) return "approved";
  const rows = state.tables[id] || [];
  if (rows.length && state.tableAuto[id] === false) return "done";
  if (rows.length) return "partial";
  return "verify";
}

/* stepDone(i) — content-based completion, independent of navigation order */
function stepDone(i) {
  if (!CFG) return false;
  switch (i) {
    case 0:
      return Object.values(state.project).some(v => v && String(v).trim());
    case 1:
      return Object.values(state.answers).some(v => v && String(v).trim()) ||
             Object.values(state.rowData).some(rows => rows.some(r => (r.label||"").trim() || (r.desc||"").trim()));
    case 2:
      return Object.values(state.detail).some(v => v && String(v).trim());
    case 3:
      return Object.values(state.tables).some(rows => rows.length > 0);
    default:
      return false;
  }
}

function renderSidebar() {
  const el = document.getElementById("steps");
  if (!el) return;

  const detailGroups = Object.keys(CFG.detail_fields || {});
  const presets = templateTablePresets();
  const cats = coreQuestionCats();
  const allCats = state.customQuestions.length ? [...cats, "Custom"] : cats;

  el.innerHTML = STEP_META.map((s, i) => {
    const isActive = i === state.step;
    const isDone = !isActive && stepDone(i);
    const isExpanded = isActive || !!state.sidebarExpanded[i];

    let subHtml = "";
    if (i === 0) {
      subHtml = `<div class="sub-items">
        <div class="sub-item" data-anchor="s1-info"><span class="sub-dot"></span> Project Information</div>
        <div class="sub-item" data-anchor="s1-dates"><span class="sub-dot"></span> Dates &amp; Version</div>
        <div class="sub-item" data-anchor="s1-desc"><span class="sub-dot"></span> Description &amp; Regulations</div>
      </div>`;
    } else if (i === 1) {
      subHtml = `<div class="sub-items">${allCats.map(cat => {
        const st = cat === "Custom"
          ? (state.customQuestions.some(q => (state.answers[q.id]||"").trim()) ? "partial" : "verify")
          : catStatus(cat);
        return `<div class="sub-item ${(cat === state.activeCat && isActive) ? 'active' : ''}" data-cat-sub="${esc(cat)}"><span class="sub-dot ${st}"></span> ${esc(cat)}</div>`;
      }).join("")}</div>`;
    } else if (i === 2) {
      subHtml = `<div class="sub-items">${detailGroups.map(area => {
        const st = detailStatus(area);
        return `<div class="sub-item ${(area === state.activeDetail && isActive) ? 'active' : ''}" data-open-detail="${esc(area)}"><span class="sub-dot ${st}"></span> ${esc(area)}</div>`;
      }).join("")}</div>`;
    } else if (i === 3) {
      const selectedTable = state.activeTable || (presets[0] && presets[0].id) || "_custom";
      subHtml = `<div class="sub-items table-select-wrap">
        <select class="rail-table-select" data-table-select aria-label="Choose template table">
          ${presets.map(p => `<option value="${esc(p.id)}" ${p.id === selectedTable ? 'selected' : ''}>${esc(p.name)}</option>`).join("")}
          <option value="_custom" ${selectedTable === '_custom' ? 'selected' : ''}>Custom Tables</option>
        </select>
      </div>`;
    }

    const numLabel = isDone ? "\u2713" : String(i + 1).padStart(2, "0");
    const showConn = i < 4;

    return `
    <div class="step-item ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}" data-step="${i}" style="position:relative;">
      ${showConn ? `<div class="step-connector ${isDone ? 'done' : ''}"></div>` : ''}
      <div class="step-num">${numLabel}</div>
      <div class="step-meta">
        <span class="step-label">${esc(s.label)}</span>
        ${s.sub ? `<span class="step-sublabel">${esc(s.sub)}</span>` : ""}
      </div>
      ${i < 4 ? `<button class="step-chev" data-step-expand="${i}" aria-label="Expand"><i class="ti ti-chevron-down" aria-hidden="true"></i></button>` : ""}
    </div>
    ${isExpanded ? subHtml : ""}`;
  }).join("");

  // Bind step clicks (navigate to step)
  el.querySelectorAll("[data-step]").forEach(n =>
    n.addEventListener("click", e => {
      if (e.target.closest("[data-step-expand]")) return;
      goToStep(+n.dataset.step);
    }));

  // Bind peek-expand chevrons
  el.querySelectorAll("[data-step-expand]").forEach(b =>
    b.addEventListener("click", e => {
      e.stopPropagation();
      const idx = +b.dataset.stepExpand;
      state.sidebarExpanded[idx] = !state.sidebarExpanded[idx];
      renderSidebar();
    }));

  // Sub-item: scroll anchor (step 1)
  el.querySelectorAll("[data-anchor]").forEach(b =>
    b.addEventListener("click", () => {
      const target = document.getElementById(b.dataset.anchor);
      if (target) target.scrollIntoView({ behavior: "smooth" });
    }));

  // Sub-item: cat navigation (step 2)
  el.querySelectorAll("[data-cat-sub]").forEach(b =>
    b.addEventListener("click", () => { state.activeCat = b.dataset.catSub; render(); }));

  // Sub-item: detail group navigation (step 3)
  el.querySelectorAll("[data-open-detail]").forEach(b =>
    b.addEventListener("click", () => {
      state.step = 2; state.activeDetail = b.dataset.openDetail; render();
      if (detailTableId(state.activeDetail)) syncAutoTables();
    }));

  // Sub-item: table navigation (step 4)
  el.querySelectorAll("[data-open-table]").forEach(b =>
    b.addEventListener("click", () => { state.step = 3; state.activeTable = b.dataset.openTable; render(); }));
  el.querySelectorAll("[data-table-select]").forEach(s =>
    s.addEventListener("change", () => { state.step = 3; state.activeTable = s.value; render(); }));

  // Template status
  const ts = document.getElementById("template-status");
  if (ts) {
    if (state.template) {
      ts.innerHTML = `Auto-filling: <b>${esc(state.template)}</b> <a href="#" id="tpl-remove" style="color:var(--kpmg-orange);font-size:11.5px;margin-left:6px;">Remove</a>`;
      const rm = document.getElementById("tpl-remove");
      if (rm) rm.addEventListener("click", e => {
        e.preventDefault();
        state.template = null;
        renderSidebar();
        showToast("Reverted to house format");
      });
    } else {
      ts.textContent = "House format";
    }
  }

  // Rail template download button
  const railGen = document.getElementById("rail-generate");
  if (railGen) railGen.onclick = async () => {
    try {
      const res = await fetch("/api/kpmg-template/info");
      const info = await res.json();
      if (!info.available) {
        showToast("KPMG template not found on the server.", true);
        return;
      }
      window.location.href = "/api/kpmg-template/download";
    } catch (e) {
      showToast("Could not check KPMG template: " + e.message, true);
    }
  };

  updateProgressBar();
}


function coreQuestionCats() {
  return CFG && CFG.questions ? [...new Set(CFG.questions.map(q => q.cat))] : [];
}

function moveCoreCategory(direction) {
  const cats = coreQuestionCats();
  const idx = cats.indexOf(state.activeCat);
  const next = cats[idx + direction];
  if (!next) return false;

  if (direction > 0) {
    const errors = (CFG.questions || []).filter(q => q.cat === state.activeCat).flatMap(questionErrors);
    if (errors.length) {
      showErrorDialog(errors);
      return true;
    }
  }

  state.activeCat = next;
  state.stepError = null;
  render();
  return true;
}

function _allCoreAnswered() {
  return (CFG.questions || []).every(q => !questionErrors(q).length);
}

function goToStep(target) {
  if (state.step === 1 && target === 2 && moveCoreCategory(1)) return;
  if (state.step === 1 && target === 0 && moveCoreCategory(-1)) return;

  if (target > state.step) {
    // Skip sequential validation if all core questions are already answered
    if (!_allCoreAnswered()) {
      const errors = validateStep(state.step);
      if (errors.length) {
        showErrorDialog(errors);
        return;
      }
    }
  }
  state.stepError = null;
  state.step = target;
  render();
  if (target === 2 || target === 3) syncAutoTables();  // tables on these steps -- refresh live preview
}

/* A table counts as edited by the user only if it has a non-blank cell;
   blank rows (e.g. from "+ Row") still get auto-filled. */
function tableEditedByUser(id) {
  return state.tableAuto[id] === false &&
    (state.tables[id] || []).some(row => row.some(c => String(c || "").trim()));
}

async function syncAutoTables() {
  if (!CFG) return;
  try {
    const tables = Object.entries(state.tables)
      .filter(([id, rows]) => rows && rows.length && tableEditedByUser(id))
      .map(([tid, rows]) => {
        const p = CFG.table_presets.find(p => p.id === tid);
        return p ? { id: tid, name: p.name, cols: p.cols, rows } : null;
      })
      .filter(Boolean);
    const res = await fetch("/api/tables/preview", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: state.project, answers: state.answers, detail: state.detail, tables, row_data: state.rowData }),
    });
    if (!res.ok) return;
    const json = await res.json();
    let changed = false;
    Object.entries(json).forEach(([id, info]) => {
      if (tableEditedByUser(id)) return;                   // user has customized this table -- don't touch
      if (!info.rows || !info.rows.length) return;          // nothing to show yet
      state.tables[id] = info.rows.map(r => r.slice());
      state.tableAuto[id] = true;
      changed = true;
    });
    if (changed) render();
  } catch { /* silent -- this is a background convenience sync, not a required step */ }
}

function updateProgressBar() {
  if (!CFG) return;
  const pFields = CFG.project_fields || [];
  const pFilled = pFields.filter(f => (state.project[f.key] || "").trim()).length;
  const qTotal = CFG.questions ? CFG.questions.length : 0;
  const qFilled = CFG.questions ? CFG.questions.filter(q => (state.answers[q.id] || "").trim()).length : 0;
  const total = pFields.length + qTotal;
  const done = pFilled + qFilled;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const fill = document.getElementById("progress-fill");
  const label = document.getElementById("progress-label");
  if (fill) fill.style.width = pct + "%";
  if (label) label.textContent = done + " / " + total + " fields (" + pct + "%)";
}

/* ------------------------------------------------------------------ */
/* steps                                                               */
/* ------------------------------------------------------------------ */

function dateSanityWarnings() {
  const w = [];
  const { doc_date, version } = state.project;
  if (doc_date && doc_date > todayISO())
    w.push("Document date is in the future.");
  if (version && !/^\d+\.\d+/.test(version))
    w.push('Version doesn\u2019t follow the expected format (e.g. "1.0").');
  const errs = dateErrors();
  return (errs.length ? `<div class="step-error"><i class="ti ti-alert-triangle" aria-hidden="true"></i>
      <div>${errs.map(esc).join("<br>")}</div></div>` : "")
    + (w.length ? `<div class="date-warning">
    <b>\u26a0 Heads up</b><ul>${w.map(m => `<li>${esc(m)}</li>`).join("")}</ul></div>` : "");
}

/* min= bounds for the date pickers so invalid dates can't be picked. */
function dateMin(key) {
  const { doc_date, start_date } = state.project;
  if (key === "start_date") return doc_date || "";
  if (key === "end_date") return [todayISO(), start_date || "", doc_date || ""].sort().pop();
  return "";
}

function stepProject() {
  return `
  <div class="page-head"><span class="page-step-num">01</span><h1 class="page-title">Project Details</h1><span class="page-wm" aria-hidden="true">01</span></div>
  <div class="row2 project-details-grid">
    ${CFG.project_fields.map(f => `
      <div class="field" style="${f.type === 'textarea' ? 'grid-column:1/-1' : ''}">
        <label>${f.required ? '<span class="req">*</span> ' : ''}${f.label}</label>
        ${f.type === 'select'
          ? `<select data-pf="${f.key}"><option value="">Select\u2026</option>${f.options.map(o => `<option ${state.project[f.key] === o ? 'selected' : ''}>${o}</option>`).join("")}</select>`
          : f.type === 'textarea'
          ? `<div class="ta-wrap"><textarea data-pf="${f.key}">${esc(state.project[f.key] || '')}</textarea><button class="mic-btn" data-mic-pf="${f.key}" title="Click to dictate"><span class="btn-icon">${IC_MIC}</span></button></div>`
          : f.type === 'text'
          ? `<div class="input-mic-wrap"><input type="text" data-pf="${f.key}" value="${esc(state.project[f.key] || '')}"/><button class="mic-btn-sm" data-mic-pf-inp="${f.key}" title="Dictate"><span class="btn-icon">${IC_MIC}</span></button></div>`
          : `<input type="${f.type}" data-pf="${f.key}" value="${esc(state.project[f.key] || '')}"${f.type === 'date' && dateMin(f.key) ? ` min="${dateMin(f.key)}"` : ''}/>`}        ${f.key === 'industry' && state.project.industry === 'Other' ? `
          <input type="text" data-pf="industry_other" placeholder="Please specify your industry\u2026" value="${esc(state.project.industry_other || '')}" style="margin-top:6px;"/>` : ''}
      </div>`).join("")}
  </div>
  ${dateSanityWarnings()}
  ${footerNav(0)}`;
}

function nfrChecklist() {
  const checks = CFG.nfr_checklist || [];
  if (!checks.length) return "";
  const text = (state.answers.q_nonfunc || "").toLowerCase();
  const covered = checks.filter(c => new RegExp(c.pattern, "i").test(text));
  return `<div style="margin-top:8px;padding:8px 10px;border:1px solid var(--line);border-radius:4px;background:var(--card);font-size:12px;">
    <div style="font-weight:500;margin-bottom:4px;">NFR coverage: ${covered.length}/${checks.length}</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px 14px;">
      ${checks.map(c => {
        const hit = new RegExp(c.pattern, "i").test(text);
        return `<span style="color:${hit ? 'var(--kpmg-teal)' : 'var(--ink-soft)'};white-space:nowrap;">${hit ? '\u2713' : '\u25cb'} ${esc(c.label)}</span>`;
      }).join("")}
    </div>
  </div>`;
}

/* ------------------------------------------------------------------ */
/* Module-scope render helpers (used by workspace section renderers)   */
/* ------------------------------------------------------------------ */

function renderTextareaQ(q, reqStar) {
  const hasAnswer = !!(state.answers[q.id] || "").trim();
  const mdOn = !!state.mdPreview[q.id];
  return `
  <div class="qcard">
    <div class="qmeta">
      <span class="badge ${hasAnswer ? 'answered' : 'empty'}">${hasAnswer ? 'Answered' : 'Empty'}</span>
      <button class="btn small ghost" data-mdpreview="${q.id}" title="Toggle markdown preview"><i class="ti ti-eye" aria-hidden="true"></i></button>
      ${q._custom ? `<button class="btn small danger" data-rm-cq="${q.id}" title="Remove question"><span class="btn-icon">${IC_TRASH}</span></button>` : ''}
    </div>
    <label style="margin-bottom:6px;">${reqStar}${q.q}</label>
    ${q.optional_note ? `<div class="field-hint">${esc(q.optional_note)}</div>` : ''}
    ${q.template && !mdOn ? `<div style="margin:4px 0 8px;"><button class="btn small ghost" data-q-template="${q.id}" title="Insert a structured questionnaire to fill in"><i class="ti ti-list-check" aria-hidden="true"></i> Insert questionnaire</button></div>` : ''}
    ${qualityHint(q)}
    ${mdOn
      ? `<div class="md-preview">${typeof marked !== 'undefined' ? marked.parse(state.answers[q.id] || '') : esc(state.answers[q.id] || '')}</div>`
      : `<div class="ta-wrap">
          <textarea data-q="${q.id}" placeholder="Type or dictate the client\u2019s answer\u2026"${q.template ? ' rows="12"' : ''}>${esc(state.answers[q.id] || '')}</textarea>
          <button class="mic-btn" data-mic="${q.id}" title="Click to dictate"><span class="btn-icon">${IC_MIC}</span></button>
        </div>`
    }
  </div>`;
}

/* Inline note listing quality problems for an answered question. */
function qualityHint(q) {
  const answered = q.input === "rows"
    ? (state.rowData[q.id] || []).some(r => (r.label || "").trim() || (r.desc || "").trim())
    : !!_stripTemplate(state.answers[q.id], q.template).trim();
  const errs = (answered ? questionErrors(q) : []).filter(e => !e.includes("is too brief"));
  if (!errs.length) return "";
  return `<div class="quality-hint"><i class="ti ti-alert-circle" aria-hidden="true"></i>
    <div>${errs.map(e => esc(e.replace(/^.*?\u2014 (?=row \d)/, "").replace(/^[^"]*"[^"]*" /, ""))).join("<br>")}</div></div>`;
}

function renderRowQ(q) {
  const rows = state.rowData[q.id] || [];
  const hasAnswer = rows.some(r => (r.label || "").trim() || (r.desc || "").trim());
  const reqStar = q.required ? '<span class="req">*</span> ' : '';
  const fields = q.row_fields || ["Item", "Description"];
  const editing = !!state.rowEditing[q.id];
  const acc = !!q.access_field;
  const levels = CFG.access_levels || [];
  // Role suggestions are opt-in: hidden behind a button, and clicking one only
  // pre-fills a row -- users can always type their own roles.
  const sugOpen = !!state.roleSugOpen[q.id];
  const roleHint = acc ? `<div class="role-sug-wrap">
      <button class="btn small ghost" data-role-sug-toggle="${q.id}"><i class="ti ti-bulb" aria-hidden="true"></i> Role suggestions <i class="ti ti-chevron-${sugOpen ? 'up' : 'down'}" aria-hidden="true"></i></button>
      ${sugOpen ? `<div class="role-sug">
        <div class="role-sug-note">Click a role to add it, or type your own.</div>
        <ul class="role-sug-list">${(CFG.role_suggestions || []).map(r =>
          `<li><button class="role-item" data-role-sug="${q.id}" data-role="${esc(r)}">${esc(r)}</button></li>`).join("")}</ul>
      </div>` : ''}
    </div>` : '';
  return `
  <div class="qcard">
    <div class="qmeta">
      <span class="badge ${hasAnswer ? 'answered' : 'empty'}">${hasAnswer ? 'Answered' : 'Empty'}</span>
    </div>
    <label style="margin-bottom:6px;">${reqStar}${q.q}</label>
    ${roleHint}
    ${qualityHint(q)}
    <div class="qrow-table${acc ? ' has-access' : ''}">
      <div class="qrow-header${editing ? ' editing' : ''}">
        <div class="qrow-hcol">${esc(fields[0])}</div>
        <div class="qrow-hcol">${esc(fields[1])}</div>
        ${acc ? '<div class="qrow-hcol">Access level</div>' : ''}
        ${editing ? '<div class="qrow-hcol-act"></div>' : ''}
      </div>
      ${rows.map((r, ri) => `
      <div class="qrow-row${editing ? ' editing' : ''}">
        <div class="qrow-cell">
          <input type="text" class="qrow-inp" data-qr-label="${q.id}:${ri}" value="${esc(r.label || '')}" placeholder="${esc(fields[0])}\u2026" ${editing ? '' : 'disabled'}/>
          ${editing ? `<button class="mic-btn-sm" data-mic-qr="${q.id}:${ri}:label" title="Dictate ${fields[0].toLowerCase()}"><span class="btn-icon">${IC_MIC}</span></button>` : ''}
        </div>
        <div class="qrow-cell">
          <input type="text" class="qrow-inp" data-qr-desc="${q.id}:${ri}" value="${esc(r.desc || '')}" placeholder="${esc(fields[1])}\u2026" ${editing ? '' : 'disabled'}/>
          ${editing ? `<button class="mic-btn-sm" data-mic-qr="${q.id}:${ri}:desc" title="Dictate ${fields[1].toLowerCase()}"><span class="btn-icon">${IC_MIC}</span></button>` : ''}
        </div>
        ${acc ? `<div class="qrow-cell">
          <select class="qrow-inp" data-qr-access="${q.id}:${ri}" ${editing ? '' : 'disabled'}>
            <option value="">Select\u2026</option>
            ${levels.map(l => `<option ${r.access === l ? 'selected' : ''}>${esc(l)}</option>`).join("")}
          </select>
        </div>` : ''}
        ${editing ? `<div class="qrow-cell-act"><button class="btn small danger" data-qr-rm="${q.id}:${ri}" title="Remove row"><span class="btn-icon">${IC_TRASH}</span></button></div>` : ''}
      </div>`).join("")}
      <div class="qrow-footer">
        <button class="btn small ${editing ? 'primary' : ''}" data-qr-edit="${q.id}">
          <i class="ti ti-${editing ? 'device-floppy' : 'pencil'}" aria-hidden="true"></i>${editing ? ' Save' : ''}
        </button>
        ${editing ? `<button class="btn small ghost" data-qr-add="${q.id}"><i class="ti ti-plus" aria-hidden="true"></i> Add row</button>` : ''}
      </div>
    </div>
  </div>`;
}

/* ------------------------------------------------------------------ */

function stepQuestions() {
  const catQs = state.activeCat === "Custom"
    ? state.customQuestions
    : CFG.questions.filter(q => q.cat === state.activeCat);

  return `
  <div class="page-head"><span class="page-step-num">02</span><h1 class="page-title">${esc(state.activeCat || "Core Questions")}</h1><span class="page-wm" aria-hidden="true">02</span></div>
  ${state.activeCat === "Custom" ? `
    <div style="margin-bottom:10px;">
      <button class="btn small" id="add-custom-q"><i class="ti ti-plus" aria-hidden="true"></i> Add question</button>
    </div>
    ${state.customQuestions.length === 0
      ? '<p class="panel-desc">No custom questions yet. Click "Add question" to define your own.</p>'
      : state.customQuestions.map(q => renderTextareaQ(q, '')).join("")}
  ` : catQs.map(q => {
    const isRow = q.input === "rows";
    const rows = isRow ? (state.rowData[q.id] || []) : [];
    const hasAnswer = isRow ? rows.some(r => (r.label || "").trim() || (r.desc || "").trim()) : (state.answers[q.id] || "").trim();
    const reqStar = q.required ? '<span class="req">*</span> ' : '';
    if (!isRow) return renderTextareaQ(q, reqStar);
    return renderRowQ(q);
  }).join("")}
  ${footerNav(1)}`;
}

function fcObjectTypes() {
  return (CFG && CFG.flowchart_object_types) || [
    {id:"process",label:"Process"},{id:"decision",label:"Decision"},
    {id:"data",label:"Data / IO"},{id:"subprocess",label:"Subprocess"},
    {id:"start_end",label:"Start / End"}
  ];
}

function fcTypeOptions(selected) {
  return fcObjectTypes().map(o =>
    `<option value="${o.id}" ${selected === o.id ? 'selected' : ''}>${o.label}</option>`
  ).join("");
}

/* flowchartCards() renders the full editor cards into the fc-drawer body.
   Called by renderFcDrawer(). The #add-custom-flow button lives in the drawer footer. */
function flowchartCards() {
  if (!state.customFlowcharts.length) {
    return `<p style="color:var(--ink-soft);font-size:13px;text-align:center;padding:20px 0;">No flowcharts yet.<br>Click <b>Add Flowchart</b> below to start.</p>`;
  }
  return `
    <div class="flowchart-custom-section">
        <div class="flowchart-custom-header"></div>
        ${state.customFlowcharts.map((fc, fi) => {
          const steps = fc.steps || [];
          const hasSteps = steps.filter(s => (s.text || "").trim()).length >= 2;
          const swimLanes = !!fc.swimLanes;
          const collapsed = !!state.fcCollapsed[fi];
          return `
          <div class="fc-card ${collapsed ? 'fc-collapsed' : ''}">
            <div class="fc-card-head">
              <button class="fc-toggle-btn" data-fc-toggle="${fi}" title="${collapsed ? 'Expand' : 'Roll up'}"><i class="ti ${collapsed ? 'ti-chevron-down' : 'ti-chevron-up'}" aria-hidden="true"></i></button>
              <input type="text" class="fc-card-title" data-fc-title="${fi}" value="${esc(fc.title)}" placeholder="Flowchart title\u2026"/>
              <button class="mic-btn-sm" data-mic-fctitle="${fi}" title="Dictate title"><span class="btn-icon">${IC_MIC}</span></button>
              ${collapsed ? `<span class="fc-step-count">${steps.length} step${steps.length !== 1 ? 's' : ''}</span>` : ''}
              <div class="fc-card-actions">
                <label title="Enable swim lanes (one row per role/department)" style="font-size:12px;display:flex;align-items:center;gap:4px;cursor:pointer;">
                  <input type="checkbox" data-fc-swimlanes="${fi}" ${swimLanes ? 'checked' : ''}/> Swim lanes
                </label>
                <button class="btn small" data-fc-save="${fi}" title="Save flowchart to draft"><i class="ti ti-device-floppy" aria-hidden="true"></i> Save</button>
                <button class="btn small" data-fc-preview="${fi}" ${hasSteps ? '' : 'disabled'} title="${hasSteps ? 'Preview flowchart' : 'Add at least 2 steps'}"><i class="ti ti-eye" aria-hidden="true"></i></button>
                <button class="btn small" data-fc-download="${fi}" ${hasSteps ? '' : 'disabled'} title="${hasSteps ? 'Download as PNG' : 'Add at least 2 steps'}"><i class="ti ti-download" aria-hidden="true"></i></button>
                <button class="btn small danger" data-fc-rm="${fi}" title="Remove flowchart"><span class="btn-icon">${IC_TRASH}</span></button>
              </div>
            </div>
            <div class="fc-card-body" ${collapsed ? 'style="display:none;"' : ''}>
              <div class="fc-steps">
                ${steps.map((s, si) => {
                  const prevStep = si > 0 ? steps[si - 1] : null;
                  const afterDecision = prevStep && prevStep.type === "decision";
                  const mainPh = s.type === "decision" ? "Decision Question\u2026"
                    : afterDecision ? "Yes Branch Process\u2026"
                    : "Step description\u2026";
                  return `
                <div class="fc-step-row">
                  <select class="fc-step-type" data-fcs-type="${fi}:${si}">
                    ${fcTypeOptions(s.type || "process")}
                  </select>
                  <input type="text" class="fc-step-text" data-fcs-text="${fi}:${si}" value="${esc(s.text || '')}" placeholder="${mainPh}"/>
                  ${s.type === "decision" ? `
                    <input type="text" class="fc-step-yes-text" data-fcs-yestext="${fi}:${si}" value="${esc(s.yes_text || '')}" placeholder="YES Branch\u2026" title="Label for the YES path"/>
                    <input type="text" class="fc-step-no-text" data-fcs-notext="${fi}:${si}" value="${esc(s.no_text || '')}" placeholder="NO Branch\u2026" title="What happens when the answer is No?"/>
                  ` : afterDecision ? `
                    <input type="text" class="fc-step-no-text" data-fcs-notext="${fi}:${si}" value="${esc(s.no_text || '')}" placeholder="No Branch Process\u2026" title="What happens in the No branch?"/>
                  ` : ''}
                  ${swimLanes ? `<input type="text" class="fc-step-lane" data-fcs-lane="${fi}:${si}" value="${esc(s.lane || '')}" placeholder="Lane (role/dept)\u2026" style="width:120px;"/>` : ''}
                  <button class="mic-btn-sm" data-mic-fcstep="${fi}:${si}" title="Dictate step"><span class="btn-icon">${IC_MIC}</span></button>
                  <button class="btn small danger" data-fcs-rm="${fi}:${si}" title="Remove step"><span class="btn-icon">${IC_TRASH}</span></button>
                </div>`;
                }).join("")}
              </div>
              <button class="btn small ghost fc-add-step" data-fc-addstep="${fi}"><i class="ti ti-plus" aria-hidden="true"></i> Add step</button>
            </div>
          </div>`;
        }).join("")}
      </div>
    </div>`;
}

function renderFcDrawer() {
  const drawer = document.getElementById("fc-drawer");
  const body = document.getElementById("fc-drawer-body");
  if (!drawer || !body) return;
  drawer.hidden = !state.fcDrawerOpen;
  body.innerHTML = flowchartCards();
  document.body.classList.toggle("drawer-open", state.fcDrawerOpen);
}

function stepDetail() {
  const groups = Object.keys(CFG.detail_fields || {});
  if (!state.activeDetail || !groups.includes(state.activeDetail)) state.activeDetail = groups[0];
  const area = state.activeDetail;
  const fields = (CFG.detail_fields || {})[area] || [];
  const lockKey = `detail_${area}`;
  const locked = !!state.sectionLocks[lockKey];
  const isAsis = area === "As-Is / To-Be";
  const n = fields.filter(f => (state.detail[f.key] || "").trim()).length;

  const tid = detailTableId(area);
  const tpset = tid && (CFG.table_presets || []).find(p => p.id === tid);
  if (tpset) {
    return `
  <div class="page-head"><span class="page-step-num">03</span><h1 class="page-title">${esc(area)}</h1><span class="page-wm" aria-hidden="true">03</span></div>
  ${presetTableBlock(tpset)}
  ${footerNav(2)}`;
  }

  return `
  <div class="page-head"><span class="page-step-num">03</span><h1 class="page-title">${esc(area)}</h1><span class="page-wm" aria-hidden="true">03</span></div>
  <div class="status-card">
    <span class="status-card-label">${n} of ${fields.length} field${fields.length !== 1 ? 's' : ''} filled</span>
  </div>
  ${isAsis ? `
    <div class="flowchart-bar" style="margin-bottom:18px;">
      <div class="flowchart-bar-label"><i class="ti ti-chart-dots" aria-hidden="true"></i> Process Flowcharts (Annexure 12.1)</div>
      <div class="fc-summary">
        ${state.customFlowcharts.length === 0
          ? '<span style="font-size:12px;color:var(--ink-soft);">No flowcharts yet.</span>'
          : state.customFlowcharts.map((fc, fi) =>
              `<button class="fc-chip" data-fc-open-drawer="${fi}">${esc(fc.title || 'Untitled')} \u00b7 ${fc.steps.length} step${fc.steps.length !== 1 ? 's' : ''}</button>`
            ).join("")}
        <button class="btn small" data-fc-new><i class="ti ti-plus" aria-hidden="true"></i> Add</button>
        <button class="btn small ghost" data-fc-open-drawer="any"><i class="ti ti-pencil" aria-hidden="true"></i> Open Editor</button>
      </div>
    </div>
  ` : ''}
  ${fields.map(f => `
    <div class="qcard ${(state.detail[f.key] || '').trim() ? 'filled' : ''}">
      <label style="display:block;font-size:12.5px;font-weight:600;margin-bottom:8px;">${esc(f.label)}</label>
      <div class="ta-wrap">
        <textarea data-d="${f.key}" ${locked ? 'disabled' : ''}>${esc(state.detail[f.key] || '')}</textarea>
        ${locked ? '' : `<button class="mic-btn" data-mic-d="${f.key}" title="Click to dictate"><span class="btn-icon">${IC_MIC}</span></button>`}
      </div>
    </div>`).join("")}
  ${detailHasScreenshots(area) ? `
    <div class="qcard ${state.images.length ? 'filled' : ''}">
      <label style="display:block;font-size:12.5px;font-weight:600;margin-bottom:8px;">System Screenshots</label>
      ${screenshotsGrid()}
    </div>` : ''}
  ${footerNav(2)}`;
}

const SECTION_LABEL = {
  _doc_control: "Document Control", _distribution: "Distribution List",
};

function sectionLabelFor(sid) {
  if (SECTION_LABEL[sid]) return SECTION_LABEL[sid];
  const row = (CFG.outline || []).find(o => o.id === sid);
  return row ? row.title : sid;
}

function outlineNumberFor(sid) {
  const row = (CFG.outline || []).find(o => o.id === sid);
  return row ? `\u00a7${row.number}` : "";
}

function stepTables() {
  const presets = templateTablePresets();
  if (!state.activeTable ||
      (!presets.find(p => p.id === state.activeTable) && state.activeTable !== "_custom")) {
    state.activeTable = presets[0]?.id || "_custom";
  }
  if (state.activeTable === "_custom") return stepTablesCustom();

  const pset = presets.find(p => p.id === state.activeTable);
  if (!pset) return `<p>Table not found.</p>${footerNav(3)}`;

  return `
  <div class="page-head"><span class="page-step-num">04</span><h1 class="page-title">${esc(pset.name)}</h1><span class="page-wm" aria-hidden="true">04</span></div>
  ${presetTableBlock(pset)}
  ${footerNav(3)}`;
}

/* Status card + editable table for one template-table preset. */
function presetTableBlock(pset) {
  const rows = state.tables[pset.id] || [];
  const isAuto = state.tableAuto[pset.id] !== false;
  const editing = !!state.tableEditing[pset.id];
  const lockKey = `tbl_${pset.id}`;
  const locked = !!state.sectionLocks[lockKey];

  return `
  <div class="status-card">
    <span class="status-card-label">${rows.length ? (isAuto ? `${rows.length} row(s) \u00b7 Auto-synced` : `${rows.length} row(s) \u00b7 Edited by you`) : 'Empty \u2014 will auto-derive at generation'}</span>
  </div>
  <div class="table-block">
    <div class="table-block-head" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <div style="font-weight:600;font-size:14px;">${esc(pset.name)}</div>
      <div style="display:flex;gap:6px;">
        ${!locked ? `<button class="btn small ${editing ? 'primary' : ''}" data-tbledit="${esc(pset.id)}">
          <i class="ti ti-${editing ? 'device-floppy' : 'pencil'}" aria-hidden="true"></i>${editing ? ' Save' : ''}
        </button>` : ''}
        ${(editing && !locked) ? `<button class="btn small" data-addtr="${esc(pset.id)}"><i class="ti ti-plus" aria-hidden="true"></i> Row</button>` : ''}
      </div>
    </div>
    <table class="builder ${(editing && !locked) ? '' : 'locked'}">
      <thead><tr>
        <th style="width:52px;">${esc(pset.id_col)}</th>
        ${pset.cols.map(c => `<th>${esc(c)}</th>`).join("")}
        ${(editing && !locked) ? '<th style="width:26px;"></th>' : ''}
      </tr></thead>
      <tbody>${rows.map((row, ri) => `<tr>
        <td style="color:var(--ink-soft);font-size:11px;text-align:center;">${isAuto ? "auto" : ri + 1}</td>
        ${pset.cols.map((_c, ci) => `<td><input type="text" data-tc="${esc(pset.id)}:${ri}:${ci}" value="${esc(row[ci] || '')}" ${(editing && !locked) ? '' : 'disabled'}/></td>`).join("")}
        ${(editing && !locked) ? `<td class="rm-row" data-tr="${esc(pset.id)}:${ri}"><span class="btn-icon">${IC_TRASH}</span></td>` : ''}
      </tr>`).join("")}
      </tbody>
    </table>
  </div>`;
}

function stepTablesCustom() {
  return `
  <div class="tbl-toolbar">
    <button class="btn" id="add-custom"><i class="ti ti-plus" aria-hidden="true"></i> Add custom table</button>
  </div>
  ${state.custom.map((t, ti) => `
    <div class="table-block">
      <div class="table-block-head">
        <input type="text" data-cname="${ti}" value="${esc(t.name)}"/>
        <div style="display:flex;gap:6px;">
          <button class="btn small" data-caddcol="${ti}"><i class="ti ti-plus" aria-hidden="true"></i> Column</button>
          <button class="btn small" data-caddrow="${ti}"><i class="ti ti-plus" aria-hidden="true"></i> Row</button>
          <button class="btn small danger" data-crm="${ti}"><span class="btn-icon">${IC_TRASH}</span></button>
        </div>
      </div>
      <table class="builder">
        <thead><tr>${t.cols.map((c, ci) => `<th><input type="text" data-cth="${ti}:${ci}" value="${esc(c)}"/></th>`).join("")}</tr></thead>
        <tbody>${t.rows.map((row, ri) => `<tr>${row.map((cell, ci) => `<td><input type="text" data-ctd="${ti}:${ri}:${ci}" value="${esc(cell)}"/></td>`).join("")}</tr>`).join("")}</tbody>
      </table>
    </div>`).join("")}
  <div style="margin-top:20px;margin-bottom:10px;">
    <button class="btn small" id="add-custom-q"><i class="ti ti-plus" aria-hidden="true"></i> Add custom question</button>
  </div>
  ${state.customQuestions.length === 0
    ? '<p class="panel-desc">No custom questions yet.</p>'
    : state.customQuestions.map(q => renderTextareaQ(q, '')).join("")}
  ${footerNav(3)}`;
}

function screenshotsGrid() {
  return `
  <div class="image-grid">
    ${state.images.map((img, ii) => `
      <div class="image-card">
        <button class="image-rm" data-imgrm="${ii}" title="Remove image"><i class="ti ti-x" aria-hidden="true"></i></button>
        <img src="${img.url}" alt="${esc(img.caption || img.filename)}"/>
        <input type="text" class="image-caption" placeholder="Caption\u2026" data-imgcap="${ii}" value="${esc(img.caption || '')}"/>
      </div>`).join("")}
    <label class="image-upload-tile">
      <i class="ti ti-upload" aria-hidden="true"></i>
      <span>Upload screenshot</span>
      <input type="file" id="image-input" accept=".png,.jpg,.jpeg,.gif,.bmp,.webp" hidden />
    </label>
  </div>`;
}

function stepGenerate() {
  const r = state.buildResult;
  // Readiness items
  const detailGroups = Object.keys(CFG.detail_fields || {});
  const presets = templateTablePresets();
  const pFilled = (CFG.project_fields || []).filter(f => (state.project[f.key] || "").trim()).length;
  const pTotal  = (CFG.project_fields || []).length;
  const qFilled = (CFG.questions || []).filter(q => (state.answers[q.id] || "").trim()).length;
  const qTotal  = (CFG.questions || []).length;
  const dFilled = detailGroups.filter(a => detailStatus(a) !== "verify").length;
  const tFilled = presets.filter(p => tableStatus(p.id) !== "verify").length;
  const totalItems = 4;
  const doneItems  = [pFilled === pTotal, qFilled > 0, dFilled > 0, tFilled > 0].filter(Boolean).length;
  const pct = totalItems ? Math.round((doneItems / totalItems) * 100) : 0;

  const readList = [
    { label: "Project Details",   st: pFilled === pTotal ? "done" : (pFilled > 0 ? "partial" : "empty"), nav: 0 },
    { label: "Core Questions",    st: qFilled === qTotal ? "done" : (qFilled > 0 ? "partial" : "empty"), nav: 1 },
    { label: "Detail Fields",     st: dFilled === detailGroups.length ? "done" : (dFilled > 0 ? "partial" : "empty"), nav: 2 },
    { label: "Template Tables",   st: tFilled === presets.length ? "done" : (tFilled > 0 ? "partial" : "empty"), nav: 3 },
  ];

  return `
  <div class="page-head"><span class="page-step-num">05</span><h1 class="page-title">Create Document</h1><span class="page-wm" aria-hidden="true">05</span></div>
  <div class="gen-layout">
    <div class="gen-readiness">
      <h3>Readiness Checklist</h3>
      <div class="readiness-ring-wrap">
        <div class="readiness-score">
          <div class="readiness-score-num">${pct}%</div>
          <div class="readiness-score-label">Ready</div>
        </div>
        <div class="readiness-note">${doneItems} of ${totalItems} sections filled in. ${pct >= 75 ? 'Looking good \u2014 ready to create.' : 'Fill in more sections for a complete BRD.'}</div>
      </div>
      <ul class="readiness-list">
        ${readList.map(item => `
          <li class="readiness-item ${item.st}">
            <span class="ri-dot"></span>
            <span>${esc(item.label)}</span>
            <span class="ri-review" data-nav="${item.nav}">Review \u2192</span>
          </li>`).join("")}
      </ul>
    </div>
    <div class="gen-output">
      <h3>Output</h3>
      <p style="font-size:13px;color:var(--ink-soft);margin-bottom:14px;">Template: ${state.template ? esc(state.template) : "House format"}</p>
      <label class="toggle">
        <input type="checkbox" id="diag" ${state.includeDiagnostics ? 'checked' : ''}/>
        Include diagnostics annexure (readiness + open questions)
      </label>
      <div style="display:flex;gap:10px;margin-top:16px;">
        <button class="btn primary lg" id="do-build" style="flex:1;justify-content:center;">
          <i class="ti ti-file-text" aria-hidden="true"></i> Create Document (.docx)
        </button>
        <button class="btn lg" id="do-preview" ${r ? '' : 'disabled title="Create the document first"'}
          style="flex:0 0 auto;${r ? '' : 'opacity:.45;cursor:not-allowed;'}">
          <i class="ti ti-eye" aria-hidden="true"></i> Preview
        </button>
      </div>
      ${r ? `
        <div style="margin-top:14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
          <a class="btn primary" style="display:inline-flex;align-items:center;gap:6px;" href="${r.download_url}"><i class="ti ti-download" aria-hidden="true"></i> Download .docx</a>
        </div>
        ${r.template_fill ? (() => {
          const tf = r.template_fill;
          const nFilled  = (tf.filled  || []).length;
          const nMissing = (tf.missing || []).length;
          const nVerify  = (tf.placeholders_cleared || 0) + (tf.verify_count || 0);
          const sections = tf.sections_refilled || tf.filled || [];
          const isShell  = tf.upload_type === "uploaded_template_shell";
          if (isShell) {
            return `<div class="build-fill-report" style="margin-top:12px;padding:10px 14px;background:var(--paper);border:1px solid var(--line);border-radius:8px;font-size:13px;">
              <b>Template filled:</b> Your template's styles, header and footer were used. All BRD sections were generated inside your template.
              ${sections.length > 0 ? `<div style="margin-top:6px;font-size:11.5px;color:var(--ink-soft);">${sections.length} section${sections.length !== 1 ? "s" : ""} written: ${sections.map(esc).join(", ")}</div>` : ""}
            </div>`;
          }
          return `<div class="build-fill-report" style="margin-top:12px;padding:10px 14px;background:var(--paper);border:1px solid var(--line);border-radius:8px;font-size:13px;">
            <b>Template auto-fill summary:</b>
            Filled: ${nFilled} sections
            ${nVerify ? ` \u00b7 Marked VERIFY: ${nVerify}` : ""}
            ${nMissing ? ` \u00b7 Left empty: ${nMissing}` : ""}
            ${(tf.filled || []).length > 0 ? `<div style="margin-top:6px;font-size:11.5px;color:var(--ink-soft);">Filled: ${(tf.filled || []).map(esc).join(", ")}</div>` : ""}
            ${(tf.missing || []).length > 0 ? `<div style="margin-top:4px;font-size:11.5px;color:var(--kpmg-orange);">Not matched: ${(tf.missing || []).map(esc).join(", ")}</div>` : ""}
          </div>`;
        })() : ""}` : ""}
      ${state.buildError ? `<div class="build-error" style="margin-top:14px;">${esc(state.buildError)}</div>` : ""}
    </div>
  </div>

  ${footerNav(4)}`;
}

function footerNav(i) {
  return `<div class="footer-nav">
    <button class="btn ${i === 0 ? 'ghost' : ''}" ${i === 0 ? 'style="visibility:hidden"' : ''} data-nav="${i - 1}"><i class="ti ti-arrow-left" aria-hidden="true"></i> Back</button>
    ${i < 4 ? `<button class="btn primary" data-nav="${i + 1}">Continue <i class="ti ti-arrow-right" aria-hidden="true"></i></button>` : ''}
  </div>`;
}


function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function render() {
  renderSidebar();

  const stepFns = [stepProject, stepQuestions, stepDetail, stepTables, stepGenerate];
  const mainEl = document.getElementById("main");
  mainEl.innerHTML = (stepFns[state.step] || stepProject)();
  renderFcDrawer();
  bindMainEvents();
  updateDraftStatus();
}

function bindMainEvents() {
  const $$ = sel => document.querySelectorAll(sel);

  // Footer nav and review links (data-nav="0".."4")
  $$("[data-nav]").forEach(b => b.addEventListener("click", () => goToStep(+b.dataset.nav)));

  // fc-drawer close / done / backdrop
  const fcClose = document.getElementById("fc-drawer-close");
  if (fcClose && !fcClose._bound) {
    fcClose._bound = true;
    fcClose.addEventListener("click", () => { state.fcDrawerOpen = false; renderFcDrawer(); });
  }
  const fcDone = document.getElementById("fc-drawer-done");
  if (fcDone && !fcDone._bound) {
    fcDone._bound = true;
    fcDone.addEventListener("click", () => { state.fcDrawerOpen = false; renderFcDrawer(); });
  }
  const fcDrawer = document.getElementById("fc-drawer");
  if (fcDrawer && !fcDrawer._bound) {
    fcDrawer._bound = true;
    fcDrawer.addEventListener("click", e => {
      if (e.target === fcDrawer) { state.fcDrawerOpen = false; renderFcDrawer(); }
    });
    document.addEventListener("keydown", e => {
      if (e.key === "Escape" && state.fcDrawerOpen) { state.fcDrawerOpen = false; renderFcDrawer(); }
    }, { once: false });
  }

  // Flowchart open-drawer chips in step 3
  $$("[data-fc-open-drawer]").forEach(b => b.addEventListener("click", () => {
    state.fcDrawerOpen = true;
    render();
  }));
  // "Add" flowchart button in step 3 summary bar
  $$("[data-fc-new]").forEach(b => b.addEventListener("click", () => {
    state.customFlowcharts.push({ title: "", steps: [{ text: "", type: "process" }] });
    state.fcDrawerOpen = true;
    render();
  }));

  $$("[data-pf]").forEach(inp => inp.addEventListener("input", () => {
    state.project[inp.dataset.pf] = inp.value;
    state.stepError = null;
    updateProgressBar();
  }));
  $$("select[data-pf], input[type=date][data-pf]").forEach(inp => inp.addEventListener("change", () => {
    state.project[inp.dataset.pf] = inp.value;
    render();
  }));
  $$(".cat-tab").forEach(b => b.addEventListener("click", () => { state.activeCat = b.dataset.cat; render(); }));
  $$("[data-q]").forEach(t => t.addEventListener("input", () => {
    const qid = t.dataset.q;
    pushAnswerHistory(qid, state.answers[qid]);
    state.answers[qid] = t.value;
    updateProgressBar();
    // NFR checklist removed
  }));
  // Regulation picker (q_regs)
  $$("[data-reg-chk]").forEach(chk => chk.addEventListener("change", () => {
    const idx = +chk.dataset.regChk;
    if (state.regData) state.regData.items[idx].checked = chk.checked;
    syncRegsToAnswer();
  }));
  $$("[data-reg-note]").forEach(inp => inp.addEventListener("input", () => {
    const idx = +inp.dataset.regNote;
    if (state.regData) state.regData.items[idx].note = inp.value;
    syncRegsToAnswer();
  }));
  const regOtherAdd = document.getElementById("reg-other-add");
  const regOtherInput = document.getElementById("reg-other-input");
  if (regOtherAdd && regOtherInput) {
    const addReg = () => {
      const val = regOtherInput.value.trim();
      if (!val || !state.regData) return;
      const existing = (state.regData.other || "").split(",").map(s => s.trim()).filter(Boolean);
      existing.push(val);
      state.regData.other = existing.join(", ");
      syncRegsToAnswer();
      regOtherInput.value = "";
      render();
    };
    regOtherAdd.addEventListener("click", addReg);
    regOtherInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addReg(); } });
  }
  $$("[data-reg-other-rm]").forEach(btn => btn.addEventListener("click", () => {
    const idx = +btn.dataset.regOtherRm;
    if (!state.regData) return;
    const parts = (state.regData.other || "").split(",").map(s => s.trim()).filter(Boolean);
    parts.splice(idx, 1);
    state.regData.other = parts.join(", ");
    syncRegsToAnswer();
    render();
  }));

  // Row-based question inputs
  $$("[data-qr-label]").forEach(inp => inp.addEventListener("input", () => {
    const [qid, ri] = inp.dataset.qrLabel.split(":");
    state.rowData[qid][+ri].label = inp.value;
    syncRowToAnswer(qid);
  }));
  $$("[data-qr-desc]").forEach(inp => inp.addEventListener("input", () => {
    const [qid, ri] = inp.dataset.qrDesc.split(":");
    state.rowData[qid][+ri].desc = inp.value;
    syncRowToAnswer(qid);
  }));
  $$("[data-qr-access]").forEach(sel => sel.addEventListener("change", () => {
    const [qid, ri] = sel.dataset.qrAccess.split(":");
    state.rowData[qid][+ri].access = sel.value;
    syncRowToAnswer(qid);
  }));
  $$("[data-role-sug-toggle]").forEach(b => b.addEventListener("click", () => {
    const qid = b.dataset.roleSugToggle;
    state.roleSugOpen[qid] = !state.roleSugOpen[qid];
    render();
  }));
  $$("[data-role-sug]").forEach(b => b.addEventListener("click", () => {
    const qid = b.dataset.roleSug;
    const role = b.dataset.role;
    const rows = state.rowData[qid] || (state.rowData[qid] = []);
    if (rows.some(r => (r.label || "").trim().toLowerCase() === role.toLowerCase())) {
      showToast(`"${role}" is already added`);
      return;
    }
    const empty = rows.find(r => !(r.label || "").trim());
    if (empty) empty.label = role;
    else rows.push({ label: role, desc: "", access: "" });
    state.rowEditing[qid] = true;   // open the table so the user can describe the role
    state.roleSugOpen[qid] = false;
    syncRowToAnswer(qid);
    render();
  }));
  $$("[data-q-template]").forEach(b => b.addEventListener("click", () => {
    const q = (CFG.questions || []).find(x => x.id === b.dataset.qTemplate);
    if (!q || !q.template) return;
    const cur = (state.answers[q.id] || "").trim();
    if (cur.includes(q.template.split("\n")[0].split(":")[0])) { showToast("Questionnaire already inserted"); return; }
    pushAnswerHistory(q.id, state.answers[q.id]);
    state.answers[q.id] = cur ? `${cur}\n\n${q.template}` : q.template;
    updateProgressBar();
    render();
  }));
  $$("[data-qr-rm]").forEach(b => b.addEventListener("click", () => {
    const [qid, ri] = b.dataset.qrRm.split(":");
    state.rowData[qid].splice(+ri, 1);
    syncRowToAnswer(qid);
    render();
  }));
  $$("[data-qr-edit]").forEach(b => b.addEventListener("click", () => {
    const qid = b.dataset.qrEdit;
    if (state.rowEditing[qid]) {
      // Save: lock the rows and persist draft
      state.rowEditing[qid] = false;
      saveDraft();
    } else {
      // Edit: unlock the rows
      state.rowEditing[qid] = true;
    }
    render();
  }));
  $$("[data-qr-add]").forEach(b => b.addEventListener("click", () => {
    const qid = b.dataset.qrAdd;
    if (!state.rowData[qid]) state.rowData[qid] = [];
    state.rowData[qid].push({ label: "", desc: "", access: "" });
    render();
    setTimeout(() => {
      const inputs = document.querySelectorAll(`[data-qr-label^="${qid}:"]`);
      if (inputs.length) inputs[inputs.length - 1].focus();
    }, 50);
  }));
  $$("[data-d]").forEach(t => t.addEventListener("input", () => { state.detail[t.dataset.d] = t.value; }));
  $$("[data-acc-toggle]").forEach(h => h.addEventListener("click", () => {
    const k = h.dataset.accToggle; state.openAcc[k] = !state.openAcc[k];
    const acc = h.closest(".accordion");
    if (acc) acc.classList.toggle("open", state.openAcc[k]);
  }));

  // house-template tables
  $$("[data-tbl-toggle]").forEach(h => h.addEventListener("click", () => {
    const k = h.dataset.tblToggle; state.openTbl[k] = !state.openTbl[k];
    const acc = h.closest(".accordion");
    if (acc) acc.classList.toggle("open", state.openTbl[k]);
  }));
  $$("[data-tbledit]").forEach(b => b.addEventListener("click", (e) => {
    e.stopPropagation();
    const id = b.dataset.tbledit;
    state.tableEditing[id] = !state.tableEditing[id];
    render();
  }));
  $$("[data-addtr]").forEach(b => b.addEventListener("click", (e) => {
    e.stopPropagation();
    const id = b.dataset.addtr;
    const pset = CFG.table_presets.find(p => p.id === id);
    (state.tables[id] = state.tables[id] || []).push(pset.cols.map(() => ""));
    state.tableAuto[id] = false;   // user is now hand-building this table
    state.openTbl[id] = true; render();
  }));
  $$("[data-tblauto]").forEach(b => b.addEventListener("click", async (e) => {
    e.stopPropagation();
    const id = b.dataset.tblauto;
    b.disabled = true;
    try {
      const tables = Object.entries(state.tables)
        .filter(([, rows]) => rows && rows.length)
        .map(([tid, rows]) => {
          const p = CFG.table_presets.find(p => p.id === tid);
          return { id: tid, name: p.name, cols: p.cols, rows };
        });
      const res = await fetch("/api/tables/preview", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project: state.project, answers: state.answers, detail: state.detail, tables, row_data: state.rowData }),
      });
      const json = await res.json();
      if (!res.ok) { alert(json.error || "Could not preview rows"); return; }
      const preview = json[id];
      if (!preview || !preview.rows.length) { alert("Nothing to auto-fill yet \u2014 answer more core questions or upload an RFP first."); return; }
      state.tables[id] = preview.rows.map(r => r.slice());
      state.tableAuto[id] = true;   // explicit re-derive -- fine to keep silently refreshing this one
      state.openTbl[id] = true;
      render();
    } catch (err) {
      alert("Could not reach the backend: " + err.message);
    }
  }));
  $$("[data-tc]").forEach(inp => inp.addEventListener("input", () => {
    const [id, ri, ci] = inp.dataset.tc.split(":");
    state.tables[id][+ri][+ci] = inp.value;
    state.tableAuto[id] = false;   // hand-edited -- stop silently overwriting this table
  }));
  $$("[data-tr]").forEach(b => b.addEventListener("click", () => {
    const [id, ri] = b.dataset.tr.split(":");
    state.tables[id].splice(+ri, 1);
    state.tableAuto[id] = false;
    render();
  }));

  // custom annexure tables
  const addCustom = document.getElementById("add-custom");
  if (addCustom) addCustom.addEventListener("click", () => {
    state.custom.push({ name: "Custom table", cols: ["Column A", "Column B"], rows: [["", ""]] });
    render();
  });
  $$("[data-cname]").forEach(i => i.addEventListener("input", () => { state.custom[+i.dataset.cname].name = i.value; }));
  $$("[data-cth]").forEach(i => i.addEventListener("input", () => { const [t, c] = i.dataset.cth.split(":").map(Number); state.custom[t].cols[c] = i.value; }));
  $$("[data-ctd]").forEach(i => i.addEventListener("input", () => { const [t, r, c] = i.dataset.ctd.split(":").map(Number); state.custom[t].rows[r][c] = i.value; }));
  $$("[data-caddcol]").forEach(b => b.addEventListener("click", () => { const t = +b.dataset.caddcol; state.custom[t].cols.push("New column"); state.custom[t].rows.forEach(r => r.push("")); render(); }));
  $$("[data-caddrow]").forEach(b => b.addEventListener("click", () => { const t = +b.dataset.caddrow; state.custom[t].rows.push(state.custom[t].cols.map(() => "")); render(); }));
  const refreshAll = document.getElementById("refresh-all-tables");
  if (refreshAll) refreshAll.addEventListener("click", () => syncAutoTables());

  $$("[data-crm]").forEach(b => b.addEventListener("click", () => { state.custom.splice(+b.dataset.crm, 1); render(); }));

  // system screenshots (Prototype detail group)
  const imgInput = document.getElementById("image-input");
  if (imgInput) imgInput.addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    try {
      const res = await fetch("/api/images/upload", { method: "POST", body: fd });
      const json = await res.json();
      if (!res.ok) { alert(json.error || "Upload failed"); return; }
      state.images.push({ filename: json.filename, url: json.url, caption: "" });
      render();
    } catch (err) {
      alert("Could not reach the backend: " + err.message);
    }
  });
  $$("[data-imgcap]").forEach(inp => inp.addEventListener("input", () => {
    state.images[+inp.dataset.imgcap].caption = inp.value;
  }));
  $$("[data-imgrm]").forEach(b => b.addEventListener("click", async () => {
    const ii = +b.dataset.imgrm;
    const img = state.images[ii];
    state.images.splice(ii, 1);
    render();
    if (img && img.filename) {
      try { await fetch(`/api/images/${encodeURIComponent(img.filename)}`, { method: "DELETE" }); } catch {}
    }
  }));

  const diag = document.getElementById("diag");
  if (diag) diag.addEventListener("change", () => { state.includeDiagnostics = diag.checked; });

  const doPreview = document.getElementById("do-preview");
  if (doPreview) doPreview.addEventListener("click", () => openPreview(state.buildResult.preview_url));

  // --- Custom flowcharts ---
  const addCustomFlow = document.getElementById("add-custom-flow");
  if (addCustomFlow && !addCustomFlow._bound) {
    addCustomFlow._bound = true;
    addCustomFlow.addEventListener("click", () => {
      state.customFlowcharts.push({ title: "", steps: [{ text: "", type: "process" }] });
      state.fcDrawerOpen = true;
      render();
      // Focus the new flowchart's title input
      setTimeout(() => {
        const fi = state.customFlowcharts.length - 1;
        const inp = document.querySelector(`[data-fc-title="${fi}"]`);
        if (inp) inp.focus();
      }, 80);
    });
  }
  $$("[data-fc-title]").forEach(inp => inp.addEventListener("input", () => {
    state.customFlowcharts[+inp.dataset.fcTitle].title = inp.value;
  }));
  $$("[data-fc-toggle]").forEach(b => b.addEventListener("click", () => {
    const fi = +b.dataset.fcToggle;
    state.fcCollapsed[fi] = !state.fcCollapsed[fi];
    render();
  }));
  $$("[data-fc-rm]").forEach(b => b.addEventListener("click", () => {
    state.customFlowcharts.splice(+b.dataset.fcRm, 1);
    render();
  }));
  $$("[data-fc-addstep]").forEach(b => b.addEventListener("click", () => {
    const fi = +b.dataset.fcAddstep;
    state.customFlowcharts[fi].steps.push({ text: "", type: "process" });
    render();
  }));
  $$("[data-fcs-text]").forEach(inp => inp.addEventListener("input", () => {
    const [fi, si] = inp.dataset.fcsText.split(":").map(Number);
    state.customFlowcharts[fi].steps[si].text = inp.value;
  }));
  $$('[data-fcs-notext]').forEach(inp => inp.addEventListener("input", () => {
    const [fi, si] = inp.dataset.fcsNotext.split(":").map(Number);
    state.customFlowcharts[fi].steps[si].no_text = inp.value;
  }));
  $$('[data-fcs-yestext]').forEach(inp => inp.addEventListener("input", () => {
    const [fi, si] = inp.dataset.fcsYestext.split(":").map(Number);
    state.customFlowcharts[fi].steps[si].yes_text = inp.value;
  }));
  $$("[data-fcs-type]").forEach(sel => sel.addEventListener("change", () => {
    const [fi, si] = sel.dataset.fcsType.split(":").map(Number);
    state.customFlowcharts[fi].steps[si].type = sel.value;
    render();
  }));
  $$("[data-fcs-lane]").forEach(inp => inp.addEventListener("input", () => {
    const [fi, si] = inp.dataset.fcsLane.split(":").map(Number);
    state.customFlowcharts[fi].steps[si].lane = inp.value;
  }));
  $$("[data-fc-swimlanes]").forEach(chk => chk.addEventListener("change", () => {
    state.customFlowcharts[+chk.dataset.fcSwimlanes].swimLanes = chk.checked;
    render();
  }));
  $$("[data-fcs-rm]").forEach(b => b.addEventListener("click", () => {
    const [fi, si] = b.dataset.fcsRm.split(":").map(Number);
    state.customFlowcharts[fi].steps.splice(si, 1);
    render();
  }));
  // Custom questions (Feature 6)
  const addCQ = document.getElementById("add-custom-q");
  if (addCQ) addCQ.addEventListener("click", () => {
    const id = `cq_${Date.now()}`;
    state.customQuestions.push({ id, q: "New question", _custom: true });
    render();
    setTimeout(() => {
      const inp = document.querySelector(`[data-cq-label="${id}"]`);
      if (inp) inp.focus();
    }, 50);
  });
  $$("[data-cq-label]").forEach(inp => inp.addEventListener("input", () => {
    const cq = state.customQuestions.find(q => q.id === inp.dataset.cqLabel);
    if (cq) cq.q = inp.value;
  }));
  $$("[data-rm-cq]").forEach(b => b.addEventListener("click", () => {
    state.customQuestions = state.customQuestions.filter(q => q.id !== b.dataset.rmCq);
    render();
  }));

  // Markdown preview toggle (Feature 7)
  $$("[data-mdpreview]").forEach(b => b.addEventListener("click", () => {
    const qid = b.dataset.mdpreview;
    state.mdPreview[qid] = !state.mdPreview[qid];
    render();
  }));



  $$("[data-fc-save]").forEach(b => b.addEventListener("click", () => {
    saveDraft();
  }));
  $$("[data-fc-preview]").forEach(b => b.addEventListener("click", () => {
    const fi = +b.dataset.fcPreview;
    const fc = state.customFlowcharts[fi];
    const steps = (fc.steps || []).filter(s => (s.text || "").trim());
    previewFlowchart("custom", null, fc.title || `Custom Flowchart ${fi + 1}`, steps, !!fc.swimLanes);
  }));
  $$("[data-fc-download]").forEach(b => b.addEventListener("click", async () => {
    const fi = +b.dataset.fcDownload;
    const fc = state.customFlowcharts[fi];
    const steps = (fc.steps || []).filter(s => (s.text || "").trim());
    if (steps.length < 2) return;
    const fcTitle = fc.title || `Custom Flowchart ${fi + 1}`;
    b.disabled = true;
    b.innerHTML = '<i class="ti ti-loader" aria-hidden="true"></i> Downloading\u2026';
    try {
      const res = await fetch("/api/flowchart/preview", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: fcTitle, key: "custom", steps, swim_lanes: !!fc.swimLanes }),
      });
      const json = await res.json();
      if (res.ok && json.image) {
        const a = document.createElement("a");
        a.href = json.image;
        a.download = (fcTitle.replace(/[^a-zA-Z0-9_\- ]/g, "_") || "flowchart") + ".png";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } else {
        showToast(json.error || "Could not generate flowchart", true);
      }
    } catch (e) {
      showToast("Download failed: " + e.message, true);
    }
    b.disabled = false;
    b.innerHTML = '<i class="ti ti-download" aria-hidden="true"></i>';
  }));

  // --- Speech-to-text (Web Speech API) ---
  bindSpeechButtons();

  const doBuild = document.getElementById("do-build");
  if (doBuild) doBuild.addEventListener("click", async () => {
    const gateErrors = validateStep(0).concat(validateStep(1));
    if (gateErrors.length) { showErrorDialog(gateErrors); return; }
    doBuild.disabled = true;
    doBuild.innerHTML = "Generating\u2026";
    state.buildError = null;
    try {
      const tables = Object.entries(state.tables)
        .filter(([, rows]) => rows && rows.length)
        .map(([id, rows]) => {
          const pset = CFG.table_presets.find(p => p.id === id);
          return { id, name: pset.name, cols: pset.cols, rows };
        })
        .concat(state.custom);
      const payload = {
        project: state.project, answers: state.answers, detail: state.detail,
        row_data: state.rowData,
        tables, template: state.template, include_diagnostics: state.includeDiagnostics,
        images: state.images.map(({ filename, caption }) => ({ filename, caption })),
        custom_flowcharts: state.customFlowcharts
          .filter(fc => (fc.steps || []).some(s => (s.text || "").trim()))
          .map(fc => ({ title: fc.title, steps: (fc.steps || []).filter(s => (s.text || "").trim()) })),
      };
      const res = await fetch("/api/build", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) state.buildError = json.error || "Build failed";
      else state.buildResult = json;
    } catch (e) {
      state.buildError = "Could not reach the backend: " + e.message;
    }
    render();
  });

  attachFormatBars();
}

/* ------------------------------------------------------------------ */
/* Rich-text editing for free-text answers. Each textarea is shown as a
   formatted editor (bold looks bold, bullets look like bullets). The
   textarea stays as the hidden source of truth and holds light markup the
   generator turns into Word formatting:
     **bold**   *italic*   "- " bullet lines   "## " sub-heading lines
     blank line = new paragraph                                        */

const _fmtIcon = d => `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;

// group: buttons in the same group sit together; a divider separates groups
const FMT_ACTIONS = [
  { k: "bold",    group: 1, label: "Bold",
    icon: _fmtIcon('<path d="M7 5h6a3.5 3.5 0 0 1 0 7H7z"/><path d="M13 12h1a3.5 3.5 0 0 1 0 7H7v-7"/>'),
    title: "Bold \u2014 select text, then click (Ctrl+B)" },
  { k: "italic",  group: 1, label: "Italic",
    icon: _fmtIcon('<line x1="11" y1="5" x2="17" y2="5"/><line x1="7" y1="19" x2="13" y2="19"/><line x1="14" y1="5" x2="10" y2="19"/>'),
    title: "Italic \u2014 select text, then click (Ctrl+I)" },
  { k: "bullet",  group: 2, label: "Bullets",
    icon: _fmtIcon('<line x1="9" y1="6" x2="20" y2="6"/><line x1="9" y1="12" x2="20" y2="12"/><line x1="9" y1="18" x2="20" y2="18"/><circle cx="4.5" cy="6" r="1" fill="currentColor"/><circle cx="4.5" cy="12" r="1" fill="currentColor"/><circle cx="4.5" cy="18" r="1" fill="currentColor"/>'),
    title: "Bullet list \u2014 click again to turn a bullet back into normal text" },
  { k: "heading", group: 2, label: "Heading",
    icon: _fmtIcon('<path d="M6 5v14M18 5v14M6 12h12"/>'),
    title: "Sub-heading \u2014 turns the current line into a heading" },
  { k: "para",    group: 2, label: "New paragraph",
    icon: _fmtIcon('<path d="M13 4v16M17 4v16M19 4H9.5a4.5 4.5 0 0 0 0 9H13"/>'),
    title: "Start a new paragraph (also leaves a bullet list)" },
];

function mdInlineToHtml(s) {
  return esc(s)
    .replace(/\*\*([^*\n]+?)\*\*/g, "<b>$1</b>")
    .replace(/\*([^*\s](?:[^*\n]*?[^*\s])?)\*/g, "<i>$1</i>");
}

function mdToHtml(text) {
  const out = [];
  let list = null;
  const closeList = () => { if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; } };
  (text || "").split("\n").forEach(line => {
    const bullet = line.match(/^\s*(?:[-•]|\*(?=\s))\s+(.*)$/);
    const head = line.match(/^\s*#{1,3}\s+(.*)$/);
    if (bullet) { (list = list || []).push(`<li>${mdInlineToHtml(bullet[1]) || "<br>"}</li>`); return; }
    closeList();
    if (head) out.push(`<h4>${mdInlineToHtml(head[1]) || "<br>"}</h4>`);
    else out.push(`<div>${mdInlineToHtml(line) || "<br>"}</div>`);
  });
  closeList();
  return out.join("");
}

function htmlInlineToMd(node) {
  let s = "";
  node.childNodes.forEach(ch => {
    if (ch.nodeType === Node.TEXT_NODE) { s += ch.textContent.replace(/ /g, " "); return; }
    if (ch.nodeType !== Node.ELEMENT_NODE) return;
    const tag = ch.tagName;
    if (tag === "BR") { s += "\n"; return; }
    const inner = htmlInlineToMd(ch);
    const fw = ch.style ? ch.style.fontWeight : "";
    const bold = tag === "B" || tag === "STRONG" || fw === "bold" || +fw >= 600;
    const ital = tag === "I" || tag === "EM" || (ch.style && ch.style.fontStyle === "italic");
    if (!inner.trim() || (!bold && !ital)) { s += inner; return; }
    // keep surrounding spaces outside the markers so "**x**" stays valid
    const m = inner.match(/^(\s*)([\s\S]*?)(\s*)$/);
    let core = m[2];
    if (ital) core = `*${core}*`;
    if (bold) core = `**${core}**`;
    s += m[1] + core + m[3];
  });
  return s;
}

function htmlToMd(root) {
  const lines = [];
  let cur = null;                       // inline content sitting directly in the editor
  const flush = () => { if (cur !== null) { lines.push(...cur.split("\n")); cur = null; } };
  const blockText = el => htmlInlineToMd(el).replace(/\n$/, "");
  root.childNodes.forEach(ch => {
    const tag = ch.nodeType === Node.ELEMENT_NODE ? ch.tagName : "";
    if (tag === "UL" || tag === "OL") {
      flush();
      ch.querySelectorAll(":scope > li").forEach(li => lines.push("- " + blockText(li).replace(/\n/g, " ")));
    } else if (/^H[1-6]$/.test(tag)) {
      flush();
      lines.push("## " + blockText(ch).replace(/\n/g, " "));
    } else if (tag === "DIV" || tag === "P") {
      flush();
      lines.push(...blockText(ch).split("\n"));
    } else if (tag === "BR") {
      if (cur === null) lines.push(""); else flush();
    } else {
      cur = (cur || "") + htmlInlineToMd({ childNodes: [ch] });
    }
  });
  flush();
  return lines.join("\n").replace(/\*\*\*\*/g, "").replace(/\s+$/, "");
}

function attachFormatBars() {
  document.querySelectorAll("textarea[data-q], textarea[data-d], textarea[data-pf]").forEach(ta => {
    if (ta._rte) return;
    const host = ta.closest(".ta-wrap") || ta;
    const ed = document.createElement("div");
    ed.className = "rte";
    ed.contentEditable = ta.disabled ? "false" : "true";
    if (ta.disabled) ed.classList.add("disabled");
    if (ta.placeholder) ed.dataset.placeholder = ta.placeholder;
    if (ta.getAttribute("rows")) ed.style.minHeight = `${ta.rows * 1.5}em`;
    ed.innerHTML = mdToHtml(ta.value);
    ta.style.display = "none";
    ta.parentNode.insertBefore(ed, ta);
    ta._rte = ed;
    attachMinWordsWarning(ta, host);

    const markEmpty = () => ed.classList.toggle("empty", !ta.value.trim());
    const syncToTextarea = () => {
      ensureLineAfterList(ed);
      ta.value = htmlToMd(ed);
      markEmpty();
      ta.dispatchEvent(new Event("input", { bubbles: true }));   // existing handlers save the value
    };
    markEmpty();
    ensureLineAfterList(ed);
    ed.addEventListener("input", syncToTextarea);
    // Enter on an empty bullet always ends the list (don't rely on the browser)
    ed.addEventListener("keydown", e => {
      if (e.key !== "Enter" || e.shiftKey) return;
      const li = currentListItem(ed);
      if (li && !li.textContent.trim()) {
        e.preventDefault();
        listItemToLine(li);
        syncToTextarea();
      }
    });
    // dictation writes to the textarea directly -- redraw from it
    ta.addEventListener("rte-sync", () => { ed.innerHTML = mdToHtml(ta.value); ensureLineAfterList(ed); markEmpty(); });
    // paste as plain text so Word/web formatting junk does not come along
    ed.addEventListener("paste", e => {
      e.preventDefault();
      const text = (e.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, text);
    });
    if (ta.disabled) return;

    const bar = document.createElement("div");
    bar.className = "fmt-bar";
    bar.innerHTML = FMT_ACTIONS.map((a, i) =>
      (i && a.group !== FMT_ACTIONS[i - 1].group ? '<span class="fmt-sep" aria-hidden="true"></span>' : "") +
      `<button type="button" class="fmt-btn" data-fmt="${a.k}" title="${a.title}" aria-label="${a.label}">` +
      `${a.icon}<span>${a.label}</span></button>`).join("");
    bar.addEventListener("mousedown", e => e.preventDefault());   // keep the editor selection
    bar.addEventListener("click", e => {
      const b = e.target.closest("[data-fmt]");
      if (!b) return;
      ed.focus();
      applyFormat(b.dataset.fmt, ed);
      syncToTextarea();
      updateFmtState(bar, ed);
    });
    host.parentNode.insertBefore(bar, host);
    if (ta._minWarn) bar.appendChild(ta._minWarn);   // note sits on the right of the toolbar
    const refresh = () => updateFmtState(bar, ed);
    ["keyup", "mouseup", "focus"].forEach(ev => ed.addEventListener(ev, refresh));
  });
}

/* Minimum word count for a free-text box, or 0 when it has none. */
function minWordsFor(ta) {
  if (ta.disabled) return 0;
  const min = CFG.quality?.min_words_text || 8;
  if (ta.dataset.pf === "description") return min;
  const q = ta.dataset.q && (CFG.questions || []).find(x => x.id === ta.dataset.q);
  return q && q.input !== "rows" ? min : 0;
}

/* Italic "write at least N words" note under a box, updated as you type. */
function attachMinWordsWarning(ta, host) {
  const min = minWordsFor(ta);
  if (!min) return;
  const q = ta.dataset.q && (CFG.questions || []).find(x => x.id === ta.dataset.q);
  const warn = document.createElement("div");
  warn.className = "min-words-warn";
  host.before(warn);
  ta._minWarn = warn;
  const update = () => {
    const text = q ? _stripTemplate(ta.value, q.template) : ta.value;
    const n = _words(text).length;
    const none = q && q.allow_none && _isNoneAnswer(text);
    const junk = !none && text.trim() && _looksMeaningless(text);
    const ok = !junk && (n >= min || none);
    // always shown; turns green once the minimum is met, warns on gibberish
    warn.classList.toggle("met", !!ok);
    warn.textContent = junk
      ? "This doesn't look like meaningful text — please write something useful."
      : `Write at least ${min} words.`;
  };
  update();
  ta.addEventListener("input", update);
  ta.addEventListener("rte-sync", update);
}

function selectionElement() {
  const sel = window.getSelection();
  const n = sel && sel.anchorNode;
  if (!n) return null;
  return n.nodeType === Node.ELEMENT_NODE ? n : n.parentElement;
}

function currentListItem(ed) {
  const el = selectionElement();
  const li = el && el.closest("li");
  return li && ed.contains(li) ? li : null;
}

function placeCaret(node, atEnd) {
  const r = document.createRange();
  r.selectNodeContents(node);
  r.collapse(!atEnd);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(r);
}

/* Split the list around *li*: items after it move to a new list, and
   *line* (a plain div) goes in between. Empty lists are removed. */
function splitListAt(li, line, keepItem) {
  const ul = li.parentElement;
  const rest = document.createElement(ul.tagName);
  while (li.nextSibling) rest.appendChild(li.nextSibling);
  ul.after(line);
  if (rest.childNodes.length) line.after(rest);
  if (!keepItem) li.remove();
  if (!ul.querySelector("li")) ul.remove();
}

/* Turn one bullet back into a plain line, keeping its text. */
function listItemToLine(li) {
  const line = document.createElement("div");
  while (li.firstChild) line.appendChild(li.firstChild);
  if (!line.textContent.trim() && !line.querySelector("br")) line.innerHTML = "<br>";
  splitListAt(li, line, false);
  placeCaret(line, true);
}

/* Start an empty plain line straight after the bullet *li*. */
function lineAfterListItem(li) {
  const line = document.createElement("div");
  line.innerHTML = "<br>";
  splitListAt(li, line, true);
  placeCaret(line, false);
}

/* A list at the very end gets an empty plain line under it, so there is
   always somewhere to click to carry on writing normal text. */
function ensureLineAfterList(ed) {
  const last = ed.lastElementChild;
  if (last && (last.tagName === "UL" || last.tagName === "OL")) {
    const line = document.createElement("div");
    line.innerHTML = "<br>";
    ed.appendChild(line);
  }
}

function applyFormat(kind, ed) {
  if (kind === "bold")    document.execCommand("bold");
  if (kind === "italic")  document.execCommand("italic");
  if (kind === "bullet") {
    const li = currentListItem(ed);
    if (li) listItemToLine(li);                       // bullet off for this line
    else document.execCommand("insertUnorderedList"); // bullet on
  }
  if (kind === "para") {
    const li = currentListItem(ed);
    if (li) {
      lineAfterListItem(li);                          // leave the list, plain line below
    } else {
      // a blank line between lines is what starts a new paragraph in the BRD
      document.execCommand("insertParagraph");
      document.execCommand("insertParagraph");
    }
  }
  if (kind === "heading") {
    const el = selectionElement();
    document.execCommand("formatBlock", false, el && el.closest("h4") ? "div" : "h4");
  }
}

function updateFmtState(bar, ed) {
  if (document.activeElement !== ed) return;
  const el = selectionElement();
  const on = {
    bold: document.queryCommandState("bold"),
    italic: document.queryCommandState("italic"),
    bullet: !!(el && el.closest("li")),
    heading: !!(el && el.closest("h4")),
  };
  bar.querySelectorAll("[data-fmt]").forEach(b => b.classList.toggle("active", !!on[b.dataset.fmt]));
}

function bindGlobalUploads() {
  document.getElementById("rfp-input").addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    const json = await (await fetch("/api/rfp/parse", { method: "POST", body: fd })).json();
    if (json.error) { alert(json.error); return; }
    // Feature 4: if answers already exist, ask merge or replace
    const hasExisting = Object.values(state.answers).some(v => (v || "").trim());
    let mergeMode = false;
    if (hasExisting) {
      const choice = confirm(
        `You already have answers filled in.\n\n` +
        `Click OK to MERGE (only fill empty fields).\n` +
        `Click Cancel to REPLACE all answers with the RFP content.`
      );
      mergeMode = choice;
    }
    if (mergeMode) {
      // Only fill fields that are currently empty
      Object.entries(json.project || {}).forEach(([k, v]) => {
        if (!(state.project[k] || "").trim()) state.project[k] = v;
      });
      Object.entries(json.answers || {}).forEach(([k, v]) => {
        if (!(state.answers[k] || "").trim()) state.answers[k] = v;
      });
      Object.entries(json.detail || {}).forEach(([k, v]) => {
        if (!(state.detail[k] || "").trim()) state.detail[k] = v;
      });
    } else {
      state.project = { ...state.project, ...json.project };
      state.answers = { ...state.answers, ...json.answers };
      state.detail  = { ...state.detail,  ...(json.detail || {}) };
    }
    const matcherLabel = json.matcher === "embeddings"
      ? "semantic embeddings (MiniLM)"
      : (json.matcher === "flan-t5" ? "FLAN-T5 field routing"
      : (json.matcher === "tfidf" ? "TF-IDF keyword match" : (json.matcher || "matcher")));
    alert(`Read ${json.paragraphs_read} paragraphs/rows and drafted ${json.fields_matched} fields `
          + `(via ${matcherLabel}) \u2014 ${mergeMode ? "merged into empty fields" : "replaced all fields"}.\n\n`
          + `This is a draft only \u2014 review it in Core questions and Detail fields before generating.`);
    render();
    syncAutoTables();
  });

  document.getElementById("template-input").addEventListener("change", async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    const json = await (await fetch("/api/template/upload", { method: "POST", body: fd })).json();
    if (json.error) { showToast(json.error, true); return; }
    state.template = json.saved;
    renderSidebar();
    showToast("Template set: " + json.saved);
  });

  // Feature 2: Project list
  document.getElementById("open-projects").addEventListener("click", openProjectsModal);
  document.getElementById("projects-close").addEventListener("click", () => {
    document.getElementById("projects-modal").hidden = true;
  });
  document.getElementById("projects-modal").addEventListener("click", e => {
    if (e.target.id === "projects-modal") document.getElementById("projects-modal").hidden = true;
  });
  document.getElementById("proj-save-new").addEventListener("click", async () => {
    const nameInp = document.getElementById("proj-name-inp");
    if (nameInp.value.trim()) state.project.name = nameInp.value.trim();
    await saveProject();
    loadProjectsList();
  });

  document.getElementById("save-draft").addEventListener("click", saveDraft);
  document.getElementById("clear-draft").addEventListener("click", () => {
    if (confirm("Discard the saved draft? This cannot be undone.")) {
      clearDraft();
      updateDraftStatus();
    }
  });

  document.getElementById("preview-close").addEventListener("click", closePreview);
  document.getElementById("preview-modal").addEventListener("click", (e) => {
    if (e.target.id === "preview-modal") closePreview();
  });

  updateDraftStatus();
  bindSampleBrd();
  bindTemplateExplainer();
}


async function openPreview(url) {
  const modal = document.getElementById("preview-modal");
  const body = document.getElementById("preview-body");
  body.innerHTML = "<p>Loading preview\u2026</p>";
  modal.hidden = false;
  try {
    const res = await fetch(url);
    const json = await res.json();
    if (!res.ok) { body.innerHTML = `<p class="build-error">${esc(json.error || "Could not load preview")}</p>`; return; }
    body.innerHTML = `<div class="doc-preview">${json.html}</div>`;
  } catch (e) {
    body.innerHTML = `<p class="build-error">Could not reach the backend: ${esc(e.message)}</p>`;
  }
}

function closePreview() {
  document.getElementById("preview-modal").hidden = true;
}

function updateDraftStatus() {
  const el = document.getElementById("draft-status");
  if (!el) return;
  const ts = draftTimestamp();
  el.textContent = ts ? `Last saved: ${ts}` : "";
}

/* ------------------------------------------------------------------ */
/* Speech-to-text: MediaRecorder → server-side transcription           */
/* Click to record, click again to stop & transcribe.                  */
/* ------------------------------------------------------------------ */

let _activeRecording = null;  // { recorder, stream, btn }

function bindSpeechButtons() {
  // Core question mic buttons  (data-mic="q_problem")
  document.querySelectorAll("[data-mic]").forEach(btn => {
    btn.addEventListener("click", () => {
      const qid = btn.dataset.mic;
      const ta = btn.closest(".ta-wrap").querySelector("textarea");
      toggleSpeech(btn, ta, val => { state.answers[qid] = val; });
    });
  });

  // Project field mic buttons  (data-mic-pf="description")
  document.querySelectorAll("[data-mic-pf]").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.micPf;
      const ta = btn.closest(".ta-wrap").querySelector("textarea");
      toggleSpeech(btn, ta, val => { state.project[key] = val; });
    });
  });

  // Detail field mic buttons  (data-mic-d="d_if_user")
  document.querySelectorAll("[data-mic-d]").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.micD;
      const ta = btn.closest(".ta-wrap").querySelector("textarea");
      toggleSpeech(btn, ta, val => { state.detail[key] = val; });
    });
  });

  // Project text-input mic buttons (data-mic-pf-inp="sponsor")
  document.querySelectorAll("[data-mic-pf-inp]").forEach(btn => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.micPfInp;
      const inp = btn.closest(".input-mic-wrap").querySelector("input");
      toggleSpeech(btn, inp, val => { state.project[key] = val; });
    });
  });

  // Row-based question mic buttons (data-mic-qr="q_users:0:label")
  document.querySelectorAll("[data-mic-qr]").forEach(btn => {
    btn.addEventListener("click", () => {
      const parts = btn.dataset.micQr.split(":");
      const qid = parts[0], ri = +parts[1], field = parts[2];
      const selector = field === "label"
        ? `[data-qr-label="${qid}:${ri}"]`
        : `[data-qr-desc="${qid}:${ri}"]`;
      const inp = document.querySelector(selector);
      if (!inp) return;
      toggleSpeech(btn, inp, val => {
        if (!state.rowData[qid]) state.rowData[qid] = [];
        if (!state.rowData[qid][ri]) state.rowData[qid][ri] = { label: "", desc: "" };
        state.rowData[qid][ri][field] = val;
        syncRowToAnswer(qid);
      });
    });
  });

  // Flowchart title mic buttons (data-mic-fctitle="0")
  document.querySelectorAll("[data-mic-fctitle]").forEach(btn => {
    btn.addEventListener("click", () => {
      const fi = +btn.dataset.micFctitle;
      const inp = document.querySelector(`[data-fc-title="${fi}"]`);
      if (!inp) return;
      toggleSpeech(btn, inp, val => { state.customFlowcharts[fi].title = val; });
    });
  });

  // Flowchart step text mic buttons (data-mic-fcstep="0:1")
  document.querySelectorAll("[data-mic-fcstep]").forEach(btn => {
    btn.addEventListener("click", () => {
      const [fi, si] = btn.dataset.micFcstep.split(":").map(Number);
      const inp = document.querySelector(`[data-fcs-text="${fi}:${si}"]`);
      if (!inp) return;
      toggleSpeech(btn, inp, val => { state.customFlowcharts[fi].steps[si].text = val; });
    });
  });
}

/**
 * toggleSpeech – records via RecordRTC (16 kHz mono WAV, browser-side).
 * First click starts; second click stops and POSTs WAV to /api/speech/transcribe.
 * RecordRTC handles resampling in the browser — no server conversion needed.
 */
async function toggleSpeech(btn, field, onUpdate) {
  const iconWrap = btn.querySelector(".btn-icon");

  // Second click → stop
  if (btn.classList.contains("recording")) {
    if (_activeRecording) _activeRecording.stop();
    return;
  }

  // Another button already recording → stop it
  if (_activeRecording) { _activeRecording.stop(); return; }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showToast("Microphone not available. Check that the page is served over HTTPS.");
    return;
  }

  if (typeof RecordRTC === "undefined") {
    showToast("RecordRTC failed to load. Check your internet connection.");
    return;
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError")
      showToast("Microphone access denied. Please allow it in browser settings.");
    else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError")
      showToast("No microphone found. Please connect one and try again.");
    else
      showToast("Could not start microphone: " + (err.message || err.name));
    return;
  }

  const rtc = RecordRTC(stream, {
    type: "audio",
    mimeType: "audio/wav",
    recorderType: StereoAudioRecorder,
    numberOfAudioChannels: 1,
    desiredSampRate: 16000,
  });

  rtc.startRecording();
  btn.classList.add("recording");
  if (iconWrap) iconWrap.innerHTML = IC_STOP;

  async function stop() {
    rtc.stopRecording(async () => {
      stream.getTracks().forEach(t => t.stop());
      _activeRecording = null;
      btn.classList.remove("recording");

      const wav = rtc.getBlob();
      if (!wav || wav.size < 100) {
        if (iconWrap) iconWrap.innerHTML = IC_MIC;
        return;
      }

      btn.classList.add("transcribing");
      if (iconWrap) iconWrap.innerHTML =
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>';

      const fd = new FormData();
      fd.append("audio", wav, "recording.wav");
      fd.append("lang", "en-US");

      try {
        const res = await fetch("/api/speech/transcribe", { method: "POST", body: fd });
        const json = await res.json();
        if (!res.ok) { showToast(json.error || "Transcription failed"); return; }
        if (json.warning) showToast(json.warning + " — speak clearly and hold for 2–3 s");
        const text = (json.text || "").trim();
        if (text) {
          const isTextarea = field.tagName === "TEXTAREA";
          const baseText = field.value;
          const separator = !baseText ? ""
            : isTextarea ? (baseText.endsWith("\n") ? "" : "\n")
            : (baseText.endsWith(" ") ? "" : " ");
          field.value = baseText + separator + text;
          onUpdate(field.value);
          field.dispatchEvent(new Event("rte-sync"));   // refresh the rich editor, if any
        } else if (!json.warning) {
          showToast("No speech detected. Try again.");
        }
      } catch (err) {
        showToast("Could not reach speech server: " + err.message);
      } finally {
        btn.classList.remove("transcribing");
        if (iconWrap) iconWrap.innerHTML = IC_MIC;
      }
    });
  }

  _activeRecording = { stop };
}

/* ------------------------------------------------------------------ */
/* Project management  (Feature 2)                                     */
/* ------------------------------------------------------------------ */

function projectPayload() {
  return {
    id: state.projectId,
    project: state.project,
    answers: state.answers,
    answerHistory: state.answerHistory,
    detail: state.detail,
    tables: state.tables,
    custom: state.custom,
    images: state.images,
    customFlowcharts: state.customFlowcharts,
    rowData: state.rowData,
    regData: state.regData,
    customQuestions: state.customQuestions,
    sectionLocks: state.sectionLocks,
    step: state.step,
  };
}

async function saveProject() {
  try {
    const res = await fetch("/api/projects/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectPayload()),
    });
    const json = await res.json();
    if (!res.ok) { alert(json.error || "Could not save project"); return; }
    state.projectId = json.id;
    showToast(`Project saved \u2713`);
  } catch (e) { alert("Could not reach the backend: " + e.message); }
}

async function loadProject(id) {
  try {
    const res = await fetch(`/api/projects/load/${encodeURIComponent(id)}`);
    const json = await res.json();
    if (!res.ok) { alert(json.error || "Could not load project"); return; }
    if (json.project)         Object.assign(state.project, json.project);
    if (json.answers)         state.answers         = json.answers;
    if (json.answerHistory)   state.answerHistory   = json.answerHistory;
    if (json.detail)          state.detail          = json.detail;
    if (json.tables)          Object.assign(state.tables, json.tables);
    if (json.custom)          state.custom          = json.custom;
    if (json.images)          state.images          = json.images;
    if (json.customFlowcharts)state.customFlowcharts= json.customFlowcharts;
    if (json.rowData)         state.rowData         = json.rowData;
    if (json.regData)         state.regData         = json.regData;
    if (json.customQuestions) state.customQuestions = json.customQuestions;
    if (typeof json.step === "number") state.step = json.step;
    state.projectId = id;
    document.getElementById("projects-modal").hidden = true;
    render();
    showToast("Project loaded \u2713");
  } catch (e) { alert("Could not reach the backend: " + e.message); }
}

async function deleteProject(id) {
  if (!confirm("Delete this project? This cannot be undone.")) return;
  try {
    await fetch(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
    loadProjectsList();
  } catch (e) { alert("Could not reach the backend: " + e.message); }
}

async function duplicateProject(id) {
  try {
    const res = await fetch(`/api/projects/load/${encodeURIComponent(id)}`);
    const json = await res.json();
    if (!res.ok) { alert(json.error || "Could not load project"); return; }
    // Load all content
    if (json.project)          Object.assign(state.project, json.project);
    if (json.answers)          state.answers          = json.answers;
    if (json.detail)           state.detail           = json.detail;
    if (json.tables)           Object.assign(state.tables, json.tables);
    if (json.custom)           state.custom           = json.custom;
    if (json.images)           state.images           = json.images;
    if (json.customFlowcharts) state.customFlowcharts = json.customFlowcharts;
    if (json.rowData)          state.rowData          = json.rowData;
    if (json.regData)          state.regData          = json.regData;
    if (json.customQuestions)  state.customQuestions  = json.customQuestions;
    // Clear identity fields so it becomes a new project
    state.projectId = null;
    state.project.version = "1.0";
    state.project.doc_date = todayISO();
    state.project.project_name = (state.project.project_name || "") + " (Copy)";
    state.tables.version_history = [];
    state.tables.approval_matrix = [];
    state.step = 0;
    state.buildResult = null;
    state.buildError = null;
    document.getElementById("projects-modal").hidden = true;
    render();
    showToast("Project duplicated \u2014 review and save as new \u2713");
  } catch (e) { alert("Could not reach the backend: " + e.message); }
}

async function loadProjectsList() {
  const listEl = document.getElementById("proj-list");
  if (!listEl) return;
  listEl.innerHTML = '<p style="color:var(--ink-soft);font-size:13px;">Loading…</p>';
  try {
    const res = await fetch("/api/projects");
    const json = await res.json();
    if (!json.projects.length) {
      listEl.innerHTML = '<p style="color:var(--ink-soft);font-size:13px;">No saved projects yet.</p>';
      return;
    }
    listEl.innerHTML = json.projects.map(p => `
      <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--line);">
        <div style="flex:1;">
          <div style="font-weight:500;font-size:13px;">${esc(p.name || p.id)}</div>
          <div style="font-size:11px;color:var(--ink-soft);">${esc(p.saved_at)}</div>
        </div>
        <button class="btn small" onclick="loadProject('${esc(p.id)}')"><i class="ti ti-folder-open" aria-hidden="true"></i> Load</button>
        <button class="btn small ghost" onclick="duplicateProject('${esc(p.id)}')"><i class="ti ti-copy" aria-hidden="true"></i> Duplicate</button>
        <button class="btn small danger" onclick="deleteProject('${esc(p.id)}')"><span class="btn-icon">${IC_TRASH}</span></button>
      </div>`).join("");
  } catch (e) {
    listEl.innerHTML = `<p style="color:var(--ink-soft);font-size:13px;">Could not load projects: ${esc(e.message)}</p>`;
  }
}

async function openProjectsModal() {
  document.getElementById("projects-modal").hidden = false;
  const nameInp = document.getElementById("proj-name-inp");
  if (nameInp && state.project.name) nameInp.value = state.project.name;
  loadProjectsList();
}

/* ------------------------------------------------------------------ */
/* Flowchart preview (calls /api/flowchart/preview, shows in modal)    */
/* ------------------------------------------------------------------ */

async function previewFlowchart(type, customText, customTitle, structuredSteps, swimLanes) {
  const text = customText || "";
  const title = customTitle || "Process Flow";

  const modal = document.getElementById("preview-modal");
  const body = document.getElementById("preview-body");
  modal.querySelector("h2").textContent = title + " \u2014 preview";
  body.innerHTML = '<p style="text-align:center;padding:40px 0;">Generating flowchart\u2026</p>';
  modal.hidden = false;

  const payload = { title, key: type, swim_lanes: !!swimLanes };
  if (structuredSteps) {
    payload.steps = structuredSteps;
  } else {
    payload.text = text;
  }

  try {
    const res = await fetch("/api/flowchart/preview", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const json = await res.json();
    if (!res.ok) {
      body.innerHTML = `<div style="text-align:center;padding:30px 20px;">
        <p style="color:var(--amber);font-weight:600;margin-bottom:8px;">${esc(json.error)}</p>
        ${json.step_count != null ? `<p style="font-size:12px;color:var(--ink-soft);">Steps detected: ${json.step_count}${json.steps && json.steps.length ? ' \u2014 ' + json.steps.map(esc).join(', ') : ''}</p>` : ''}
        <p style="font-size:12px;color:var(--ink-soft);margin-top:12px;">Tip: add at least 2 steps with descriptions to generate a flowchart.</p>
      </div>`;
      return;
    }
    const imgId = "fc-preview-img-" + Date.now();
    body.innerHTML = `<div style="text-align:center;padding:16px;">
      <img id="${imgId}" src="${json.image}" alt="${esc(title)}" style="max-width:100%;height:auto;border-radius:4px;box-shadow:0 2px 12px rgba(0,0,0,.1);"/>
      <div style="margin-top:14px;display:flex;gap:10px;justify-content:center;align-items:center;">
        <button class="btn small" id="fc-download-btn"><i class="ti ti-download" aria-hidden="true"></i></button>
        <span style="font-size:12px;color:var(--ink-soft);">${json.step_count} step(s)</span>
      </div>
    </div>`;
    document.getElementById("fc-download-btn").addEventListener("click", () => {
      const a = document.createElement("a");
      a.href = json.image;
      a.download = (title.replace(/[^a-zA-Z0-9_\- ]/g, "_") || "flowchart") + ".png";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    });
  } catch (e) {
    body.innerHTML = `<p class="build-error" style="margin:20px;">Could not generate flowchart: ${esc(e.message)}</p>`;
  }
}

/* ------------------------------------------------------------------ */
/* Sample BRD viewer                                                   */
/* ------------------------------------------------------------------ */

async function openSampleBrd() {
  const modal  = document.getElementById("sample-brd-modal");
  const frame  = document.getElementById("sample-brd-frame");
  const loading = document.getElementById("sample-brd-loading");
  const fallback = document.getElementById("sample-brd-fallback");
  if (!modal) return;

  // Show modal immediately with loading state
  frame.style.display = "none";
  fallback.style.display = "none";
  loading.style.display = "flex";
  modal.hidden = false;

  try {
    const infoRes = await fetch("/api/sample-brd/info");
    const info = await infoRes.json();
    if (!info.available) {
      loading.style.display = "none";
      fallback.style.display = "block";
      fallback.innerHTML = `<div style="padding:40px;text-align:center;color:var(--ink-soft);">
        <i class="ti ti-file-off" style="font-size:40px;display:block;margin-bottom:12px;"></i>
        <b>Sample BRD not available.</b><br>
        Place <code>reference/House_Sample_BRD.docx</code> next to <code>app.py</code> to enable this feature.
      </div>`;
      return;
    }

    // Attempt PDF route
    const pdfRes = await fetch("/api/sample-brd/pdf");
    if (pdfRes.ok) {
      const ct = pdfRes.headers.get("content-type") || "";
      if (ct.includes("application/pdf")) {
        frame.src = "/api/sample-brd/pdf";
        frame.style.display = "block";
        loading.style.display = "none";
        return;
      }
      // JSON fallback_html response
      const json = await pdfRes.json();
      if (json.fallback_html) {
        loading.style.display = "none";
        fallback.style.display = "block";
        fallback.style.padding = "20px 28px";
        fallback.style.overflowY = "auto";
        fallback.innerHTML = `<div style="background:var(--kpmg-orange);color:#fff;padding:10px 16px;border-radius:6px;font-size:13px;margin-bottom:16px;">
          <i class="ti ti-info-circle"></i> ${esc(json.warning || "Approximate preview — download the .docx for the exact layout.")}
        </div><div class="doc-preview">${json.fallback_html}</div>`;
        return;
      }
    }
    // Fallback error
    const errJson = await pdfRes.json().catch(() => ({}));
    loading.style.display = "none";
    fallback.style.display = "block";
    fallback.innerHTML = `<div style="padding:40px;text-align:center;color:var(--kpmg-red);">
      <b>Could not load preview.</b><br>
      <span style="font-size:13px;">${esc(errJson.error || "Unknown error")}</span>
    </div>`;
  } catch (e) {
    loading.style.display = "none";
    fallback.style.display = "block";
    fallback.innerHTML = `<div style="padding:40px;text-align:center;color:var(--kpmg-red);"><b>Error: ${esc(e.message)}</b></div>`;
  }
}

function closeSampleBrd() {
  const modal = document.getElementById("sample-brd-modal");
  if (modal) modal.hidden = true;
  const frame = document.getElementById("sample-brd-frame");
  if (frame) { frame.src = ""; frame.style.display = "none"; }
}

function bindSampleBrd() {
  const btn = document.getElementById("sample-brd-btn");
  if (btn && !btn._bound) { btn._bound = true; btn.addEventListener("click", openSampleBrd); }
  const closeBtn = document.getElementById("sample-brd-close");
  if (closeBtn && !closeBtn._bound) { closeBtn._bound = true; closeBtn.addEventListener("click", closeSampleBrd); }
  const modal = document.getElementById("sample-brd-modal");
  if (modal && !modal._bound) {
    modal._bound = true;
    modal.addEventListener("click", e => { if (e.target === modal) closeSampleBrd(); });
  }
  const newTab = document.getElementById("sample-brd-newtab");
  if (newTab && !newTab._bound) {
    newTab._bound = true;
    newTab.addEventListener("click", () => window.open("/api/sample-brd/pdf", "_blank"));
  }
  // Hide Sample BRD button if feature is not available (graceful)
  fetch("/api/sample-brd/info").then(r => r.json()).then(info => {
    const b = document.getElementById("sample-brd-btn");
    if (b) b.style.display = info.available ? "" : "none";
  }).catch(() => {});
}


/* ------------------------------------------------------------------ */
/* Template upload explainer dialog                                    */
/* ------------------------------------------------------------------ */

const _TPL_EXPLAINER_KEY = "brd_tpl_explainer_seen";

function bindTemplateExplainer() {
  // The REAL template-input (in the rail) still needs to work for direct uploads
  // (e.g. programmatic calls). Intercept the label click to show explainer.
  const label = document.querySelector(".rail-tpl-upload");
  const realInput = document.getElementById("template-input");
  const modal = document.getElementById("tpl-explainer-modal");
  const cancel1 = document.getElementById("tpl-explainer-cancel");
  const cancel2 = document.getElementById("tpl-explainer-cancel2");
  const explainerInput = document.getElementById("template-input-explainer");
  const noShowChk = document.getElementById("tpl-explainer-noshowin");

  if (!label || !realInput || !modal || !explainerInput) return;

  // Prevent the label from opening the file picker directly
  if (!label._explainerBound) {
    label._explainerBound = true;
    label.addEventListener("click", e => {
      e.preventDefault();
      const seen = sessionStorage.getItem(_TPL_EXPLAINER_KEY);
      if (seen) {
        realInput.click();
      } else {
        modal.hidden = false;
      }
    });
  }

  if (cancel1 && !cancel1._bound) {
    cancel1._bound = true;
    cancel1.addEventListener("click", () => { modal.hidden = true; });
  }
  if (cancel2 && !cancel2._bound) {
    cancel2._bound = true;
    cancel2.addEventListener("click", () => { modal.hidden = true; });
  }
  if (modal && !modal._modalBound) {
    modal._modalBound = true;
    modal.addEventListener("click", e => { if (e.target === modal) modal.hidden = true; });
  }

  // When user picks a file via the explainer dialog, pass to the real handler
  if (!explainerInput._bound) {
    explainerInput._bound = true;
    explainerInput.addEventListener("change", async (e) => {
      modal.hidden = true;
      if (noShowChk && noShowChk.checked) sessionStorage.setItem(_TPL_EXPLAINER_KEY, "1");
      const file = e.target.files[0];
      if (!file) return;
      const fd = new FormData(); fd.append("file", file);
      const json = await (await fetch("/api/template/upload", { method: "POST", body: fd })).json();
      if (json.error) { showToast(json.error, true); return; }
      state.template = json.saved;
      renderSidebar();
      showToast("Template uploaded: " + json.saved + ". It will be used when you generate.");
    });
  }
}



boot();
