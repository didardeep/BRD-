/* =====================================================================
   BRD Studio — AI-assisted flow PROTOTYPE
   Frontend only: no fetch(), no backend, no LLM. Every "AI" step below
   is simulated with the MOCK data and setTimeout delays.
   ===================================================================== */

/* ---------------------------------------------------------------------
   MOCK DATA: swap this object to demo a different project.
   Placeholders {{users}} {{deployment}} {{regs}} {{golive}} in section
   HTML are filled from the Quick Questions answers.
   --------------------------------------------------------------------- */
const MOCK = {
  sampleFile: "Sample_RFP_Inventory_System.docx",
  dictation:
    "We need a smart inventory system for our 40 retail stores. Store staff should scan barcodes " +
    "on handhelds, get automatic reorder alerts when stock runs low, and everything has to sync " +
    "with SAP MM at head office. Go-live before the festive season.",
  detectedDomain: "Retail",
  projectName: "Smart Inventory Management",

  draftSteps: [
    { agent: "Parser",          text: "Parsing document",                                           detail: "14 pages · 3 tables · domain detected: {{domain}}" },
    { agent: "Analyst agent",   text: "extracting problem, objectives, users, systems",             detail: "6 objectives · 5 user roles · 3 source systems found" },
    { agent: "PM agent",        text: "writing scope, functional requirements, NFRs",               detail: "12 functional requirements · 7 NFRs drafted" },
    { agent: "Integration map", text: "mapping integrations",                                       detail: "SAP MM (IDoc/BAPI) · POS · Supplier EDI · Handheld MDM" },
    { agent: "Checklist agent", text: "validating 12 sections against the KPMG house template",     detail: "41 fields auto-filled · 4 low-confidence items" },
    { agent: "Gap finder",      text: "generating gap questions",                                   detail: "4 questions need your input (~1 min)" },
  ],

  stats: { autoFilled: 41, needYou: 4, minutes: 1 },

  questions: [
    {
      id: "users", placeholder: "e.g. around 8 per store, peak 400", type: "single", section: "Non-Functional",
      text: "How many concurrent users should the system support?",
      why: "The RFP mentions 40 stores but no headcount. Estimated from ~8 staff per store plus HQ planners.",
      options: ["Under 100", "100–300", "300–600", "600+"],
      suggested: "300–600",
    },
    {
      id: "deployment", placeholder: "e.g. azure cloud, india region, sap stays on prem", type: "single", section: "Non-Functional / Integrations",
      text: "Where will the solution be deployed?",
      why: "RFP §4.2 says SAP MM stays on-premise, but handheld scanning in stores implies a cloud API layer.",
      options: ["Cloud", "On-prem", "Hybrid"],
      suggested: "Hybrid",
    },
    {
      id: "regs", placeholder: "e.g. dpdp, gst, legal metrology", type: "multi", section: "Assumptions & Constraints",
      text: "Which regulations apply?",
      why: "Staff and supplier personal data is stored (DPDP), and stock transfers raise GST e-way bills. No card payments are in scope.",
      options: ["DPDP Act 2023", "GST", "PCI-DSS", "None"],
      suggested: ["DPDP Act 2023", "GST"],
    },
    {
      id: "golive", placeholder: "e.g. 6 months, pilot first in mumbai stores", type: "single", section: "Scope / Timeline",
      text: "What is the go-live timeline?",
      why: "The RFP only says \"before the festive season\". No date was given.",
      options: ["3 months", "6 months", "9 months", "Phased: 5-store pilot, then rollout"],
      suggested: "Phased: 5-store pilot, then rollout",
    },
  ],

  baseScore: 86,
  gapHints: [
    { text: "Out-of-scope inferred – verify", section: "scope" },
    { text: "NFR targets are defaults",       section: "nfr" },
    { text: "Assumptions not in RFP",         section: "assumptions" },
  ],

  sections: [
    {
      id: "exec", no: "1.1", name: "Executive Summary", conf: "H",
      source: { loc: "§1 Introduction, p.1", quote: "The client operates 40 stores and faces frequent stock-outs and excess inventory due to manual stock tracking." },
      html:
        "<p>The client, a retail chain with <b>40 stores</b>, tracks stock manually in spreadsheets and through periodic SAP MM uploads. This causes frequent stock-outs of fast-moving SKUs and over-stocking of slow movers.</p>" +
        "<p>This BRD defines a <b>Smart Inventory Management</b> solution that gives store staff handheld barcode scanning, raises automatic reorder alerts based on min/max levels, and synchronises stock positions with SAP MM in near real time. Delivery approach: <b>{{golive}}</b>.</p>",
      more: "<p>Expected benefits are a 30% cut in stock-outs, 15% less working capital tied up in inventory, and the end of the weekly manual stock reconciliation (about 6 hours per store).</p>",
    },
    {
      id: "objectives", no: "1.2", name: "Business Objectives", conf: "H",
      source: { loc: "§1.3 Objectives, p.2", quote: "Reduce stock-outs by at least 30% and provide real-time visibility of stock across all stores." },
      html:
        "<ul><li>Reduce stock-outs of A-class SKUs by at least <b>30%</b> within 6 months of go-live.</li>" +
        "<li>Give HQ and store managers real-time stock visibility across all 40 stores.</li>" +
        "<li>Replace manual stock counts with barcode-driven cycle counting.</li>" +
        "<li>Automate replenishment through reorder alerts and draft purchase requisitions in SAP MM.</li>" +
        "<li>Cut inventory carrying cost by 15%.</li>" +
        "<li>Provide an audit trail for every stock movement.</li></ul>",
      more: "<h4>Success measures</h4><ul><li>Stock accuracy ≥ 98% at cycle count.</li><li>Reorder alert acted on within 24 h for 90% of alerts.</li></ul>",
    },
    {
      id: "scope", no: "2", name: "Scope", conf: "M",
      source: { loc: "§3 Scope of Work, p.4", quote: "The solution shall cover goods receipt, stock transfer, cycle counting and replenishment for all stores." },
      html:
        "<h4>In scope</h4><ul><li>Goods receipt at store with barcode scan against PO.</li><li>Inter-store stock transfer.</li><li>Cycle counting and stock adjustment.</li><li>Min/max reorder alerts and draft PR creation in SAP MM.</li><li>Store and HQ inventory dashboards.</li></ul>" +
        "<h4>Out of scope <span class=\"verify\">VERIFY</span></h4><ul><li>POS billing and payments (inferred: RFP does not mention POS changes).</li><li>Warehouse / DC management.</li><li>Supplier portal.</li></ul>",
      more: "<p>Rollout plan: <b>{{golive}}</b>. Stores outside the first wave keep the current process until their cut-over date.</p>",
    },
    {
      id: "asis", no: "4", name: "As-Is / To-Be", conf: "M",
      source: { loc: "§2.1 Current Process, p.3", quote: "Store staff record receipts on paper; data is keyed into Excel and uploaded to SAP weekly." },
      html:
        "<h4>As-Is</h4><ul><li>Receipts are recorded on paper and keyed into Excel.</li><li>Stock is uploaded to SAP MM weekly in a batch.</li><li>Reorders depend on the store manager's judgement.</li></ul>" +
        "<h4>To-Be</h4><ul><li>Receipts are scanned on handhelds against the open PO.</li><li>Stock syncs with SAP MM every 15 minutes.</li><li>The system raises reorder alerts and draft PRs automatically.</li></ul>",
      more: "<p>Process flowcharts for Goods Receipt and Replenishment will be generated in Annexure 12.1.</p>",
    },
    {
      id: "fr", no: "5.1", name: "Functional Requirements", conf: "H", table: true,
      source: { loc: "§3.2 Functional Needs, pp.4–6", quote: "Staff must be able to scan items on receipt; the system should alert when stock drops below the reorder level." },
      rows: [
        ["FR-01", "Goods receipt by barcode scan against open SAP PO", "Store Staff", "Must"],
        ["FR-02", "Flag quantity mismatches between PO and received stock", "Store Staff", "Must"],
        ["FR-03", "Inter-store stock transfer with dispatch and receipt confirmation", "Store Manager", "Must"],
        ["FR-04", "Configurable min/max levels per SKU per store", "Category Planner", "Must"],
        ["FR-05", "Automatic reorder alert when stock falls below the minimum", "Store Manager", "Must"],
        ["FR-06", "Create draft purchase requisition in SAP MM from an alert", "Category Planner", "Should"],
        ["FR-07", "Cycle count tasks with variance approval workflow", "Store Manager", "Should"],
        ["FR-08", "Real-time stock dashboard by store, category and SKU", "HQ Ops", "Should"],
        ["FR-09", "Offline scanning with auto-sync when the connection returns", "Store Staff", "Should"],
        ["FR-10", "Export stock and movement reports to Excel", "HQ Ops", "Could"],
      ],
      moreRows: [
        ["FR-11", "Expiry / batch tracking for perishable SKUs", "Store Staff", "Could"],
        ["FR-12", "Push notifications for critical stock-outs", "Store Manager", "Could"],
      ],
    },
    {
      id: "nfr", no: "5.2", name: "Non-Functional", conf: "L",
      source: { loc: "Not stated in RFP", quote: "No performance or availability targets were given. Industry defaults applied." },
      html:
        "<ul><li><b>Users:</b> {{users}}.</li>" +
        "<li><b>Deployment:</b> {{deployment}}.</li>" +
        "<li><b>Performance:</b> scan-to-confirm under 2 s; dashboard load under 3 s.</li>" +
        "<li><b>Availability:</b> 99.5% during store hours (08:00–23:00 IST).</li>" +
        "<li><b>Security:</b> SSO with role-based access; data encrypted at rest and in transit.</li>" +
        "<li><b>Offline:</b> handhelds hold up to 8 h of transactions offline.</li>" +
        "<li><b>Retention:</b> stock movement history kept for 7 years.</li></ul>",
      more: "<p>Load test target: 2× peak festive-season volume (about 120k scans/hour).</p>",
    },
    {
      id: "risks", no: "6", name: "Open Items & Risks", conf: "M",
      source: { loc: "§5 Constraints, p.7", quote: "SAP MM upgrade is planned for next year; interfaces must be upgrade-safe." },
      html:
        "<ul><li><b>Risk:</b> the planned SAP MM upgrade may change IDoc structures. <i>Mitigation:</i> isolate mapping in a middleware layer.</li>" +
        "<li><b>Risk:</b> unreliable store Wi-Fi. <i>Mitigation:</i> offline mode on handhelds.</li>" +
        "<li><b>Risk:</b> low adoption by store staff. <i>Mitigation:</i> pilot stores and super-user training.</li>" +
        "<li><b>Open item:</b> confirm handheld device model and MDM tool.</li></ul>",
      more: "<p>A risk register with owners and review dates will be kept in the project RAID log.</p>",
    },
    {
      id: "integrations", no: "8", name: "Integrations", conf: "H",
      source: { loc: "§4.2 Systems Landscape, p.6", quote: "SAP MM (ECC 6.0) is the system of record for materials and purchasing." },
      html:
        "<ul><li><b>SAP MM (ECC 6.0):</b> material master, open POs, stock postings (IDoc MBGMCR / BAPI), every 15 min.</li>" +
        "<li><b>POS:</b> sales depletion feed, hourly batch (read-only).</li>" +
        "<li><b>Supplier EDI:</b> ASN for incoming deliveries.</li>" +
        "<li><b>Handheld MDM:</b> device enrolment and app distribution.</li></ul>" +
        "<p>Hosting model: <b>{{deployment}}</b>.</p>",
      more: "<p>All interfaces log payloads and failures to a monitoring console with automatic retries (3 attempts, exponential back-off).</p>",
    },
    {
      id: "stakeholders", no: "9", name: "Stakeholders & Roles", conf: "M",
      source: { loc: "§1.4 Users, p.2", quote: "Users include store staff, store managers, category planners and head-office operations." },
      html:
        "<ul><li><b>Store Staff:</b> scan receipts, transfers and counts.</li>" +
        "<li><b>Store Manager:</b> approve variances and act on reorder alerts.</li>" +
        "<li><b>Category Planner:</b> set min/max levels and approve PRs.</li>" +
        "<li><b>HQ Operations:</b> monitor dashboards and KPIs.</li>" +
        "<li><b>IT / SAP Team:</b> integration support and master data.</li></ul>",
      more: "<p>Business sponsor: Head of Retail Operations. Product owner: Supply Chain Manager (to be confirmed).</p>",
    },
    {
      id: "assumptions", no: "10", name: "Assumptions & Constraints", conf: "L",
      source: { loc: "Inferred, not stated in RFP", quote: "Derived from the systems landscape and your answers to the Quick Questions." },
      html:
        "<ul><li>All SKUs already carry GS1 barcodes.</li>" +
        "<li>Every store has Wi-Fi coverage on the shop floor and in the back room.</li>" +
        "<li>SAP MM master data is clean and owned by the IT / SAP team.</li>" +
        "<li><b>Regulatory:</b> {{regs}}.</li>" +
        "<li><b>Timeline:</b> {{golive}}.</li></ul>",
      more: "<p><b>Dependency:</b> handheld devices must be procured and enrolled 4 weeks before the pilot.</p>",
    },
  ],
};

/* ---------------------------------------------------------------------
   STATE
   --------------------------------------------------------------------- */
const STEPS = [
  { label: "Upload / Describe", sub: "RFP, notes or a short brief" },
  { label: "AI Drafting",       sub: "Analyst · PM · Checklist agents" },
  { label: "Quick Questions",   sub: "Only the gaps" },
  { label: "Review & Export",   sub: "Edit, refine, download" },
];

const IC_MIC = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg>`;

let state;
let timers = [];

function freshState() {
  const answers = {};
  MOCK.questions.forEach(q => { answers[q.id] = Array.isArray(q.suggested) ? [...q.suggested] : q.suggested; });
  return {
    step: 0, maxStep: 0,
    file: null, brief: "", domain: "Auto-detect",
    drafted: false,
    answers,
    activeSec: MOCK.sections[0].id,
    content: {},          // per-section edited HTML
    conf: Object.fromEntries(MOCK.sections.map(s => [s.id, s.conf])),
    notes: {},            // per-section "AI applied" notes
    custom: {},           // per-question typed answer + AI refinement
    upgrades: 0,
    busy: false,
  };
}

/* ---------------------------------------------------------------------
   HELPERS
   --------------------------------------------------------------------- */
const $ = sel => document.querySelector(sel);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const later = (fn, ms) => { const t = setTimeout(fn, ms); timers.push(t); return t; };
const clearTimers = () => { timers.forEach(clearTimeout); timers = []; };
const CONF_LABEL = { H: "High", M: "Medium", L: "Low" };

function showToast(msg) {
  // Reuses the existing .draft-toast style from style.css
  let el = document.getElementById("draft-toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "draft-toast";
    el.className = "draft-toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("show"), 2400);
}

function fill(html) {
  const a = state.answers;
  const regs = a.regs.length ? a.regs.join(", ") : "None identified";
  return html
    .replace(/\{\{users\}\}/g, esc(MOCK.questions[0].options.includes(a.users) ? a.users + " concurrent users across 40 stores and HQ" : a.users))
    .replace(/\{\{deployment\}\}/g, esc(a.deployment))
    .replace(/\{\{regs\}\}/g, esc(regs))
    .replace(/\{\{golive\}\}/g, esc(a.golive))
    .replace(/\{\{domain\}\}/g, esc(state.domain === "Auto-detect" ? MOCK.detectedDomain + " (auto, 94%)" : state.domain));
}

function frTable(rows) {
  return `<table class="builder"><thead><tr><th style="width:70px">ID</th><th>Requirement</th><th style="width:140px">Actor</th><th style="width:80px">Priority</th></tr></thead><tbody>` +
    rows.map(r => `<tr><td><b>${esc(r[0])}</b></td><td>${esc(r[1])}</td><td>${esc(r[2])}</td><td><span class="prio ${esc(r[3])}">${esc(r[3])}</span></td></tr>`).join("") +
    `</tbody></table>`;
}

function originalHtml(sec) {
  return sec.table ? frTable(sec.rows) : fill(sec.html);
}
function sectionHtml(sec) {
  return state.content[sec.id] ?? originalHtml(sec);
}

/* ---------------------------------------------------------------------
   RAIL + TOPBAR
   --------------------------------------------------------------------- */
function renderRail() {
  const el = $("#steps");
  el.innerHTML = STEPS.map((s, i) => {
    const isActive = i === state.step;
    const isDone = i < state.maxStep && !isActive;
    const locked = i > state.maxStep;
    const num = isDone ? "✓" : String(i + 1).padStart(2, "0");
    const sub = i === 2 && state.drafted ? `${MOCK.stats.needYou} gaps to confirm` : s.sub;
    return `
    <div class="step-item ${isActive ? "active" : ""} ${isDone ? "done" : ""} ${locked ? "locked" : ""}" data-step="${i}" style="position:relative;" ${locked ? 'aria-disabled="true"' : ""}>
      ${i < STEPS.length - 1 ? `<div class="step-connector ${isDone ? "done" : ""}"></div>` : ""}
      <div class="step-num">${num}</div>
      <div class="step-meta">
        <span class="step-label">${esc(s.label)}</span>
        <span class="step-sublabel">${esc(sub)}</span>
      </div>
    </div>`;
  }).join("");
  el.querySelectorAll("[data-step]").forEach(n => n.addEventListener("click", () => {
    const i = +n.dataset.step;
    if (i <= state.maxStep && !state.busy) goTo(i);
  }));

  const pct = Math.round(((state.maxStep + (state.step === 3 ? 1 : 0)) / STEPS.length) * 100);
  $("#progress-fill").style.width = pct + "%";
  $("#progress-label").textContent = `Step ${state.step + 1} / ${STEPS.length}`;
}

function goTo(i) {
  clearTimers();
  state.busy = false;
  state.step = i;
  state.maxStep = Math.max(state.maxStep, i);
  render();
  window.scrollTo({ top: 0 });
}

function pageHead(n, title) {
  const nn = String(n).padStart(2, "0");
  return `<div class="page-head"><span class="page-step-num">${nn}</span><h1 class="page-title">${esc(title)}</h1><span class="page-wm" aria-hidden="true">${nn}</span></div>`;
}

function render() {
  renderRail();
  const main = $("#main");
  main.style.animation = "none"; void main.offsetWidth; main.style.animation = "";
  [renderUpload, renderDrafting, renderQuestions, renderReview][state.step](main);
}

/* ---------------------------------------------------------------------
   STEP 1 — Upload / Describe
   --------------------------------------------------------------------- */
function renderUpload(main) {
  const domains = ["Auto-detect", "Telecom", "Retail", "BFSI", "Public Sector"];
  main.innerHTML = `
    ${pageHead(1, "Upload or Describe")}
    <p class="panel-desc" style="margin:-12px 0 26px;">Give the AI an RFP, meeting notes, or a two-line brief. It drafts the whole BRD and only asks you about the gaps.</p>

    <div class="field">
      <label>RFP or notes</label>
      <div class="dropzone ${state.file ? "has-file" : ""}" id="dz" tabindex="0" role="button" aria-label="Upload RFP or notes">
        ${state.file
          ? `<div class="dz-file">📄 ${esc(state.file)} <button id="dz-clear" title="Remove file" aria-label="Remove file">✕</button></div>
             <div class="dz-sub" style="margin-top:10px;">Ready. The AI will parse this document.</div>`
          : `<div class="dz-icon">📂</div>
             <div class="dz-title">Drop a file here or click to browse</div>
             <div class="dz-sub">.docx · .pdf · .xlsx · .txt (up to 20 MB)</div>`}
      </div>
    </div>

    <div class="or-divider">OR</div>

    <div class="field">
      <label for="brief">Describe the project in 2–3 lines</label>
      <div class="ta-wrap">
        <textarea id="brief" rows="4" style="padding-right:130px;" placeholder="e.g. Inventory system for 40 stores with barcode scanning, reorder alerts and SAP MM integration…">${esc(state.brief)}</textarea>
        <button class="mic-btn" id="dictate" title="Dictate a brief" style="width:auto;padding:0 12px;top:auto;bottom:10px;transform:none;">
          <span class="btn-icon">${IC_MIC}</span><span class="mic-label">Dictate</span>
        </button>
      </div>
      <div class="input-hint">Tip: click Dictate to fill in a sample brief.</div>
    </div>

    <div class="field" style="max-width:340px;">
      <label for="domain">Domain</label>
      <select id="domain">${domains.map(d => `<option ${d === state.domain ? "selected" : ""}>${d}</option>`).join("")}</select>
    </div>

    <div class="footer-nav">
      <span></span>
      <button class="btn primary lg" id="generate">Generate draft →</button>
    </div>`;

  const dz = $("#dz"), brief = $("#brief"), gen = $("#generate");
  const sync = () => { gen.disabled = !(state.file || state.brief.trim()); };
  sync();

  const pickFile = name => { state.file = name; renderUpload(main); };
  dz.addEventListener("click", e => { if (!e.target.closest("#dz-clear")) pickFile(MOCK.sampleFile); });
  dz.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pickFile(MOCK.sampleFile); } });
  dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", e => {
    e.preventDefault();
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    pickFile(f ? f.name : MOCK.sampleFile);   // name only; the file is never read
  });
  const clr = $("#dz-clear");
  if (clr) clr.addEventListener("click", e => { e.stopPropagation(); state.file = null; renderUpload(main); });

  brief.addEventListener("input", () => { state.brief = brief.value; sync(); });
  $("#domain").addEventListener("change", e => { state.domain = e.target.value; });

  $("#dictate").addEventListener("click", function () {
    if (this.classList.contains("recording")) return;
    this.classList.add("recording");
    this.querySelector(".mic-label").textContent = "Listening…";
    const words = MOCK.dictation.split(" ");
    brief.value = ""; state.brief = "";
    words.forEach((w, i) => later(() => {
      brief.value += (i ? " " : "") + w;
      state.brief = brief.value; sync();
      if (i === words.length - 1) {
        this.classList.remove("recording");
        this.querySelector(".mic-label").textContent = "Dictate";
      }
    }, 300 + i * 55));
  });

  gen.addEventListener("click", () => {
    if (gen.disabled) return;
    state.drafted = false;
    state.content = {}; state.notes = {}; state.upgrades = 0;
    state.conf = Object.fromEntries(MOCK.sections.map(s => [s.id, s.conf]));
    state.maxStep = 1;          // re-drafting resets later steps
    goTo(1);
  });
}

/* ---------------------------------------------------------------------
   STEP 2 — AI Drafting (simulated, ~4 s)
   --------------------------------------------------------------------- */
function renderDrafting(main) {
  const n = MOCK.draftSteps.length;
  const src = state.file ? state.file : "your brief";
  main.innerHTML = `
    ${pageHead(2, "AI Drafting")}
    <p class="panel-desc" style="margin:-12px 0 26px;">Drafting a KPMG-format BRD from <b>${esc(src)}</b>.</p>
    <div class="ai-progress-card">
      <div class="ai-progress-head">
        <span class="ai-progress-title">✨ ${state.drafted ? "Draft complete" : "Generating draft…"}</span>
        <span class="ai-progress-pct" id="pct">0%</span>
      </div>
      <div class="ai-bar"><div class="ai-bar-fill" id="bar"></div></div>
      <ul class="ai-log" id="log"></ul>
      <div id="done-slot"></div>
    </div>
    <div class="footer-nav">
      <button class="btn" id="back">← Back</button>
      <span></span>
    </div>`;
  $("#back").addEventListener("click", () => goTo(0));

  const log = $("#log"), bar = $("#bar"), pct = $("#pct");
  const lineHtml = (s, status) => `
    <li class="${status}"><span class="log-ic">${status === "done" ? "✓" : ""}</span>
      <span><span class="log-agent">${esc(s.agent)}:</span> ${esc(s.text)}
      ${status === "done" ? `<span class="log-detail">${fill(esc(s.detail))}</span>` : ""}</span></li>`;
  const setPct = p => { bar.style.width = p + "%"; pct.textContent = p + "%"; };

  const finish = () => {
    state.drafted = true;
    state.busy = false;
    state.maxStep = Math.max(state.maxStep, 2);
    renderRail();
    main.querySelector(".ai-progress-title").textContent = "✨ Draft complete";
    $("#done-slot").innerHTML = `
      <div class="ai-done-banner">
        <span>✓ ${MOCK.stats.autoFilled} fields auto-filled · ${MOCK.stats.needYou} questions need you</span>
        <button class="btn primary" id="to-q">Answer ${MOCK.stats.needYou} questions →</button>
      </div>`;
    $("#to-q").addEventListener("click", () => goTo(2));
  };

  if (state.drafted) {        // revisiting: show the finished log
    log.innerHTML = MOCK.draftSteps.map(s => lineHtml(s, "done")).join("");
    setPct(100);
    finish();
    return;
  }

  state.busy = true;
  const STEP_MS = 650;
  MOCK.draftSteps.forEach((s, i) => {
    later(() => {
      log.insertAdjacentHTML("beforeend", lineHtml(s, "running"));
      setPct(Math.round((i / n) * 100 + 100 / n / 2));
    }, i * STEP_MS);
    later(() => {
      log.children[i].outerHTML = lineHtml(s, "done");
      setPct(Math.round(((i + 1) / n) * 100));
      if (i === n - 1) finish();
    }, i * STEP_MS + STEP_MS - 80);
  });
}

/* ---------------------------------------------------------------------
   STEP 3 — Quick Questions (gaps only)
   --------------------------------------------------------------------- */
function renderQuestions(main) {
  const st = MOCK.stats;
  main.innerHTML = `
    ${pageHead(3, "Quick Questions")}
    <div class="stat-row">
      <div class="stat-tile"><b>${st.autoFilled}</b><span>fields auto-filled</span></div>
      <div class="stat-tile warn"><b>${st.needYou}</b><span>need you</span></div>
      <div class="stat-tile"><b>~${st.minutes} min</b><span>to finish</span></div>
    </div>
    <p class="panel-desc" style="margin:0 0 22px;">The AI was not confident about these ${st.needYou} items. Its suggestion is already selected (✨). Pick another option, or type your own answer and let the AI refine it.</p>
    <div id="qlist">${MOCK.questions.map(qCard).join("")}</div>
    <div class="footer-nav">
      <button class="btn" id="back">← Back</button>
      <div style="display:flex;gap:10px;">
        <button class="btn" id="skip">Skip – use AI suggestions</button>
        <button class="btn primary" id="cont">Continue →</button>
      </div>
    </div>`;

  $("#back").addEventListener("click", () => goTo(1));
  $("#skip").addEventListener("click", () => {
    MOCK.questions.forEach(q => { state.answers[q.id] = Array.isArray(q.suggested) ? [...q.suggested] : q.suggested; });
    state.custom = {};
    toReview();
  });
  $("#cont").addEventListener("click", toReview);

  // Event delegation: cards re-render one at a time, so text typed in other cards survives.
  const list = $("#qlist");
  list.addEventListener("click", e => {
    const b = e.target.closest("button");
    if (!b || b.disabled) return;
    const q = MOCK.questions.find(x => x.id === b.closest(".qcard").dataset.qid);
    const c = customOf(q.id);

    if (b.classList.contains("opt-pill")) {
      const v = b.dataset.v;
      if (q.type === "multi") {
        let cur = state.answers[q.id];
        if (v === "None") cur = cur.includes("None") ? [] : ["None"];
        else {
          cur = cur.filter(x => x !== "None");
          cur = cur.includes(v) ? cur.filter(x => x !== v) : [...cur, v];
        }
        state.answers[q.id] = cur;
      } else {
        state.answers[q.id] = v;
      }
    } else if (b.dataset.act === "refine") {
      if (!c.draft.trim()) { b.closest(".qcard").querySelector(".custom-inp").focus(); return; }
      c.busy = true; c.refined = null;
      later(() => { c.busy = false; c.refined = refineAnswer(q, c.draft); updateCard(q); }, 700);
    } else if (b.dataset.act === "use-refined" || b.dataset.act === "use-typed") {
      const vals = b.dataset.act === "use-refined"
        ? c.refined.values
        : (q.type === "multi" ? c.draft.split(/[,;]/) : [c.draft]).map(v => tidy(v, false)).filter(Boolean);
      applyCustom(q, vals);
      c.draft = ""; c.refined = null;
    } else if (b.dataset.act === "discard") {
      c.refined = null;
    } else if (b.dataset.act === "rm-custom") {
      const v = b.dataset.v;
      state.answers[q.id] = q.type === "multi" ? state.answers[q.id].filter(x => x !== v) : q.suggested;
    }
    updateCard(q);
  });
  list.addEventListener("input", e => {
    if (!e.target.classList.contains("custom-inp")) return;
    const c = customOf(e.target.closest(".qcard").dataset.qid);
    c.draft = e.target.value;
  });
  list.addEventListener("keydown", e => {
    if (e.key === "Enter" && e.target.classList.contains("custom-inp")) {
      e.preventDefault();
      e.target.closest(".qcard").querySelector('[data-act="refine"]').click();
    }
  });
}

function customOf(qid) {
  state.custom = state.custom || {};
  return (state.custom[qid] = state.custom[qid] || { draft: "", refined: null, busy: false });
}

function updateCard(q) {
  const old = document.querySelector(`.qcard[data-qid="${q.id}"]`);
  if (!old) return;
  old.outerHTML = qCard(q);
}

/* Accepted custom answers: text matching a preset option selects it; anything else becomes a custom pill. */
function applyCustom(q, vals) {
  const norm = s => s.toLowerCase().replace(/[^a-z0-9]/g, "");
  const mapped = vals.map(v => q.options.find(o => norm(o) === norm(v)) || v);
  if (q.type === "multi") {
    let cur = state.answers[q.id].filter(x => x !== "None");
    mapped.forEach(v => { if (v === "None") cur = ["None"]; else if (!cur.includes(v)) cur.push(v); });
    state.answers[q.id] = cur;
  } else {
    state.answers[q.id] = mapped[0];
  }
}

/* ---------- Simulated "AI refine": rule-based, no LLM ---------- */
function tidy(t, period = true) {
  let s = String(t).replace(/\s+/g, " ").trim()
    .replace(/\bapprox\.?(?=\s|$)/gi, "approximately").replace(/\bw\/\s?/gi, "with ")
    .replace(/\s&\s/g, " and ").replace(/\bi\b/g, "I").replace(/\bppl\b/gi, "people")
    .replace(/\bmgr(s?)\b/gi, "manager$1").replace(/\bhq\b/gi, "HQ").replace(/\bsap\b/gi, "SAP");
  if (!s) return s;
  s = s.charAt(0).toUpperCase() + s.slice(1);
  if (period && !/[.!?)]$/.test(s)) s += ".";
  return s;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const REFINERS = {
  users(t) {
    const nums = (t.match(/\d[\d,]*/g) || []).map(x => +x.replace(/,/g, "")).filter(n => n > 0);
    if (!nums.length) return null;
    const lo = Math.min(...nums), hi = Math.max(...nums);
    const perStore = /per\s*store|each\s*store|\/\s*store|a\s*store/i.test(t);
    const peak = perStore ? lo * 40 + 40 : hi;
    let s = `Approximately ${peak.toLocaleString("en-IN")} concurrent users at peak`;
    if (perStore) s += ` (${lo} per store × 40 stores, plus ~40 HQ users)`;
    else if (nums.length > 1) s += ` (normal load ~${lo.toLocaleString("en-IN")})`;
    return s + "; sized for 2× load in the festive season";
  },
  deployment(t) {
    const l = t.toLowerCase();
    const cloud = /cloud|aws|azure|gcp|google|saas/.test(l);
    const onprem = /on.?prem|data ?cent|own server|in.?house/.test(l);
    const kind = cloud && onprem ? "Hybrid" : cloud ? "Cloud" : onprem ? "On-prem" : null;
    if (!kind) return null;
    const prov = /aws|amazon/.test(l) ? "AWS" : /azure|microsoft/.test(l) ? "Microsoft Azure" : /gcp|google/.test(l) ? "Google Cloud" : "";
    let s = kind;
    if (kind === "Hybrid") s += ` – cloud application layer${prov ? " on " + prov : ""}, SAP MM stays on-prem`;
    else if (prov) s += ` – ${prov}`;
    if (/india|local|residency|mumbai|hyderabad|pune|chennai|delhi/.test(l)) s += ", India region (data residency)";
    return s;
  },
  regs(t) {
    const KNOWN = [[/dpdp|data protection|privacy/i, "DPDP Act 2023"], [/gst|e-?way/i, "GST"], [/pci/i, "PCI-DSS"],
      [/rbi/i, "RBI guidelines"], [/sebi/i, "SEBI regulations"], [/iso/i, "ISO 27001"], [/gdpr/i, "GDPR"],
      [/it act/i, "IT Act 2000"], [/fssai|food/i, "FSSAI"], [/trai/i, "TRAI regulations"],
      [/legal metrology|weights/i, "Legal Metrology Act 2009"], [/^none$|^no$|^nil$/i, "None"]];
    const parts = t.split(/,|;|\/|\band\b|\+/i).map(s => s.trim()).filter(Boolean);
    const out = [];
    parts.forEach(p => {
      const k = KNOWN.find(([re]) => re.test(p));
      const v = k ? k[1] : tidy(p, false);
      if (!out.includes(v)) out.push(v);
    });
    return out.length ? out : null;
  },
  golive(t) {
    const l = t.toLowerCase();
    let s = null;
    const m = l.match(/(\d+)\s*(months?|mon|mths?|weeks?|wks?)\b/);
    if (m) {
      const n = +m[1], weeks = /^w/.test(m[2]);
      const d = new Date();
      if (weeks) d.setDate(d.getDate() + n * 7); else d.setMonth(d.getMonth() + n);
      s = `Go-live in ${n} ${weeks ? "weeks" : "months"} (target: ${MONTHS[d.getMonth()]} ${d.getFullYear()})`;
    } else if (/diwali|festive|festival/.test(l)) {
      s = "Go-live before the festive season (target: September, ahead of Diwali)";
    } else {
      const q = l.match(/q([1-4])/), fy = l.match(/fy\s?'?(\d{2,4})/);
      if (q) s = `Go-live in Q${q[1]}${fy ? " FY" + fy[1].slice(-2) : ""}`;
    }
    if (/pilot|phase|wave/.test(l)) {
      const city = (t.match(/\b(mumbai|delhi|pune|bangalore|bengaluru|hyderabad|chennai|kolkata)\b/i) || [])[1];
      s = (s || "Phased go-live") + `; pilot in 5 ${city ? city.charAt(0).toUpperCase() + city.slice(1).toLowerCase() + " " : ""}stores first, then roll out in waves`;
    }
    return s;
  },
};

function refineAnswer(q, text) {
  const r = REFINERS[q.id] ? REFINERS[q.id](text) : null;
  if (Array.isArray(r)) return { values: r, display: r.join(" · ") };
  const v = r || tidy(text, false);
  return { values: [v], display: v };
}

/* Rebuild section text from the answers only if they changed, so manual edits survive Back/Continue. */
function toReview() {
  const snap = JSON.stringify(state.answers);
  if (snap !== state.answersUsed) { state.content = {}; state.notes = {}; state.answersUsed = snap; }
  goTo(3);
}

function qCard(q) {
  const a = state.answers[q.id];
  const c = customOf(q.id);
  const isSel = v => (Array.isArray(a) ? a.includes(v) : a === v);
  const isSug = v => (Array.isArray(q.suggested) ? q.suggested.includes(v) : q.suggested === v);
  const answered = Array.isArray(a) ? a.length > 0 : !!a;
  const customs = (Array.isArray(a) ? a : [a]).filter(v => v && !q.options.includes(v));
  return `
    <div class="qcard ${answered ? "filled" : ""}" data-qid="${q.id}">
      <div class="qcard-top">
        <span class="q-sec">Feeds: ${esc(q.section)}</span>
        <span class="conf-chip ${customs.length ? "H" : "L"}">${customs.length ? "Your answer" : "Low confidence"}</span>
      </div>
      <div class="q-text">${esc(q.text)}</div>
      <div class="why-line"><b>Why asking:</b> ${esc(q.why)}</div>
      <div class="opt-pills" role="${q.type === "multi" ? "group" : "radiogroup"}">
        ${q.options.map(o => `
          <button class="opt-pill ${isSel(o) ? "selected" : ""}" data-v="${esc(o)}" aria-pressed="${isSel(o)}">
            ${isSug(o) ? '<span class="sparkle">✨</span>' : ""}${esc(o)}${isSug(o) ? '<span class="ai-pick">AI pick</span>' : ""}
          </button>`).join("")}
        ${customs.map(v => `
          <span class="opt-pill selected custom-pill">✍ ${esc(v)}
            <button class="custom-x" data-act="rm-custom" data-v="${esc(v)}" title="Remove your answer" aria-label="Remove your answer">✕</button>
          </span>`).join("")}
      </div>
      ${q.type === "multi" ? '<div class="multi-note">Select all that apply, or type others below (comma-separated).</div>' : ""}

      <div class="custom-ans">
        <div class="ai-instr">
          <input type="text" class="custom-inp" value="${esc(c.draft)}" ${c.busy ? "disabled" : ""}
                 placeholder="${esc(q.placeholder || "Or type your own answer…")}" aria-label="Type your own answer" />
          <button class="btn" data-act="refine" ${c.busy ? "disabled" : ""}>${c.busy ? '<span class="mini-spin"></span> Refining…' : "✨ Refine with AI"}</button>
        </div>
        ${c.refined ? `
          <div class="refine-box">
            <div class="refine-row"><span class="refine-tag you">You typed</span><span class="refine-txt muted">${esc(c.draft)}</span></div>
            <div class="refine-row"><span class="refine-tag ai">✨ AI refined</span><span class="refine-txt">${esc(c.refined.display)}</span></div>
            <div class="refine-actions">
              <button class="btn small primary" data-act="use-refined">✓ Use refined</button>
              <button class="btn small" data-act="use-typed">Use as typed</button>
              <button class="btn small ghost" data-act="discard">Discard</button>
            </div>
          </div>` : ""}
      </div>
    </div>`;
}

/* ---------------------------------------------------------------------
   STEP 4 — Review & Export
   --------------------------------------------------------------------- */
function score() { return Math.min(98, MOCK.baseScore + state.upgrades * 2); }

function renderReview(main) {
  main.innerHTML = `
    ${pageHead(4, "Review & Export")}
    <div class="review-top">
      <div class="score-badge">
        <div><div class="score-num" id="score">${score()}<small>/100</small></div></div>
        <div class="score-label">BRD Quality<br>Score</div>
      </div>
      <div class="gap-hints" id="gap-hints"></div>
    </div>
    <div class="review-grid">
      <aside class="sec-list" id="sec-list"></aside>
      <section class="sec-pane" id="sec-pane"></section>
    </div>
    <div class="export-bar">
      <button class="btn" id="back">← Back</button>
      <div class="btns">
        <button class="btn" id="exp-pdf">Export PDF</button>
        <button class="btn primary" id="exp-docx">⬇ Download BRD .docx</button>
      </div>
    </div>`;

  $("#back").addEventListener("click", () => goTo(2));
  $("#exp-pdf").addEventListener("click", () => showToast("Prototype – export not connected"));
  $("#exp-docx").addEventListener("click", () => showToast("Prototype – export not connected"));

  renderSecList();
  renderGapHints();
  renderSecPane();
}

function renderGapHints() {
  const el = $("#gap-hints");
  el.innerHTML = `<span style="font-size:12px;font-weight:700;color:var(--ink-soft);">Gaps:</span>` +
    MOCK.gapHints.map(h => {
      const done = state.conf[h.section] === "H";
      return `<button class="gap-hint ${done ? "resolved" : ""}" data-sec="${h.section}" title="Go to section">⚠ ${esc(h.text)}</button>`;
    }).join("");
  el.querySelectorAll("[data-sec]").forEach(b => b.addEventListener("click", () => selectSec(b.dataset.sec)));
  $("#score").innerHTML = `${score()}<small>/100</small>`;
}

function renderSecList() {
  const el = $("#sec-list");
  el.innerHTML = `<div class="sec-list-head">House template sections</div>` +
    MOCK.sections.map(s => `
      <button class="sec-item ${s.id === state.activeSec ? "active" : ""}" data-sec="${s.id}">
        <span class="sec-no">${esc(s.no)}</span>
        <span class="sec-name">${esc(s.name)}</span>
        <span class="conf-chip compact ${state.conf[s.id]}" title="${CONF_LABEL[state.conf[s.id]]} confidence">${state.conf[s.id]}</span>
      </button>`).join("");
  el.querySelectorAll("[data-sec]").forEach(b => b.addEventListener("click", () => selectSec(b.dataset.sec)));
}

function selectSec(id) {
  if (state.busy) return;
  state.activeSec = id;
  renderSecList();
  renderSecPane();
}

function renderSecPane() {
  const sec = MOCK.sections.find(s => s.id === state.activeSec);
  const c = state.conf[sec.id];
  const srcDoc = state.file || "Your brief";
  const notes = state.notes[sec.id] || [];
  $("#sec-pane").innerHTML = `
    <div class="sec-pane-head">
      <h2>${esc(sec.no)} ${esc(sec.name)}</h2>
      <span class="conf-chip ${c}" id="pane-conf">${CONF_LABEL[c]} confidence</span>
    </div>
    <div class="sec-body" id="sec-body" contenteditable="true" spellcheck="true" aria-label="${esc(sec.name)} content">${sectionHtml(sec)}</div>
    <div id="notes">${notes.map(n => `<div class="ai-applied-note">✨ AI applied: ${esc(n)}</div>`).join("")}</div>
    <div class="source-box"><b>📎 Source: ${esc(srcDoc)} · ${esc(sec.source.loc)}</b><q>${esc(sec.source.quote)}</q></div>
    <div class="ai-bar-wrap">
      <div class="ai-instr">
        <input type="text" id="ai-input" placeholder="Tell the AI what to change, e.g. &quot;add a requirement for returns to vendor&quot;" />
        <button class="btn primary" id="ai-apply">✨ Apply</button>
      </div>
      <div class="quick-chips">
        <button class="quick-chip" data-act="shorter">Shorter</button>
        <button class="quick-chip" data-act="more">More detail</button>
        <button class="quick-chip" data-act="table">As table</button>
        <button class="quick-chip" data-act="regen">↻ Regenerate</button>
      </div>
    </div>`;

  const body = $("#sec-body");
  body.addEventListener("input", () => { state.content[sec.id] = body.innerHTML; });

  const input = $("#ai-input");
  const applyFree = () => {
    const txt = input.value.trim();
    if (!txt) { input.focus(); return; }
    const t = txt.toLowerCase();
    const act = /short|concise|trim/.test(t) ? "shorter"
      : /table/.test(t) ? "table"
      : /detail|expand|elaborate|more/.test(t) ? "more"
      : "custom";
    applyAI(sec, act, txt);
  };
  $("#ai-apply").addEventListener("click", applyFree);
  input.addEventListener("keydown", e => { if (e.key === "Enter") applyFree(); });
  $("#sec-pane").querySelectorAll("[data-act]").forEach(b =>
    b.addEventListener("click", () => applyAI(sec, b.dataset.act, b.textContent.replace("↻", "").trim())));
}

/* Simulated AI edit: fade out → 700 ms → transform → note → confidence High */
function applyAI(sec, act, label) {
  if (state.busy) return;
  state.busy = true;
  const body = $("#sec-body");
  $("#sec-pane").querySelectorAll("button, input").forEach(b => (b.disabled = true));
  body.classList.add("fading");

  later(() => {
    const tmp = document.createElement("div");
    tmp.innerHTML = act === "regen" ? originalHtml(sec) : body.innerHTML;

    if (act === "shorter") {
      tmp.querySelectorAll("ul").forEach(ul => [...ul.children].slice(3).forEach(li => li.remove()));
      tmp.querySelectorAll("tbody").forEach(tb => [...tb.children].slice(5).forEach(tr => tr.remove()));
      const ps = tmp.querySelectorAll(":scope > p"); [...ps].slice(1).forEach(p => p.remove());
    } else if (act === "more") {
      if (sec.table) {
        const tb = tmp.querySelector("tbody");
        if (tb) tb.insertAdjacentHTML("beforeend", frTable(sec.moreRows).match(/<tbody>([\s\S]*)<\/tbody>/)[1]);
      } else {
        tmp.insertAdjacentHTML("beforeend", fill(sec.more));
      }
    } else if (act === "table" && !tmp.querySelector("table")) {
      const items = [...tmp.querySelectorAll("li")];
      const rows = (items.length ? items : [...tmp.querySelectorAll("p")]).map(n => n.innerHTML);
      tmp.innerHTML = `<table class="builder"><thead><tr><th style="width:50px">#</th><th>${esc(sec.name)}</th></tr></thead><tbody>` +
        rows.map((r, i) => `<tr><td><b>${i + 1}</b></td><td>${r}</td></tr>`).join("") + `</tbody></table>`;
    } else if (act === "custom") {
      tmp.insertAdjacentHTML("beforeend", `<p><i>[AI draft]</i> ${esc(label)}. This change has been added to the section.</p>`);
    }

    state.content[sec.id] = tmp.innerHTML;
    const noteText = act === "custom" ? `"${label}"` : label;
    (state.notes[sec.id] = state.notes[sec.id] || []).push(noteText);
    if (state.conf[sec.id] !== "H") { state.conf[sec.id] = "H"; state.upgrades++; }

    state.busy = false;
    renderSecList();
    renderGapHints();
    renderSecPane();
    showToast(`✨ ${sec.name} updated`);
  }, 700);
}

/* ---------------------------------------------------------------------
   BOOT
   --------------------------------------------------------------------- */
function boot() {
  clearTimers();
  state = freshState();
  render();
}
document.getElementById("proto-reset").addEventListener("click", boot);
boot();
