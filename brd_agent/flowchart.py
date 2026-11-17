"""
flowchart.py -- deterministic, rule-based process-flowchart renderer.

Uses **matplotlib only** (Agg backend, headless). No Graphviz, no external
executables, no network access, no LLM calls. Safe for laptops that block
.exe files via AppLocker.

Public API
----------
    matplotlib_available()        -> bool
    steps_from_text(text)         -> list[str]
    render_flowchart(steps, title, key) -> str | None   (PNG path or None)

Steps may be plain strings (auto-generated flowcharts) or dicts with
``{"text": str, "type": str}`` where *type* is one of:

    process     rectangle (default)
    decision    diamond
    data        parallelogram (input / output)
    subprocess  double-bordered rectangle
    start_end   rounded terminator (Start / End)
"""

import hashlib
import os
import re
import tempfile
import textwrap


# ---------------------------------------------------------------------------
# Graceful degradation if matplotlib is not installed
# ---------------------------------------------------------------------------

def matplotlib_available():
    """Return True if matplotlib can be imported."""
    try:
        import matplotlib  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Object types for flowchart nodes
# ---------------------------------------------------------------------------

OBJECT_TYPES = [
    {"id": "process",    "label": "Process"},
    {"id": "decision",   "label": "Decision"},
    {"id": "data",       "label": "Data / IO"},
    {"id": "subprocess", "label": "Subprocess"},
    {"id": "start_end",  "label": "Start / End"},
]

_VALID_TYPES = {o["id"] for o in OBJECT_TYPES}


def _normalise_step(step):
    """Accept a plain string or a {text, type, no_text?, yes_text?} dict.

    Returns (text, type, no_text, yes_text).
    *no_text*  – optional "No-path" action for any node type.
    *yes_text* – optional label for the YES arrow from a decision diamond.
    """
    if isinstance(step, dict):
        text     = (step.get("text") or "").strip()
        stype    = step.get("type", "process")
        no_text  = (step.get("no_text") or "").strip()
        yes_text = (step.get("yes_text") or "").strip()
        if stype not in _VALID_TYPES:
            stype = "process"
        return text, stype, no_text, yes_text
    return str(step).strip(), "process", "", ""


# ---------------------------------------------------------------------------
# Step extraction from free text
# ---------------------------------------------------------------------------

_NUMBERED_RE = re.compile(
    r"(?:^|\s)(?:step\s*)?\d+[.):\-]\s*",
    re.IGNORECASE,
)

_BULLET_CHARS = " \t-*\u2022\u25cf\u25cb\u2023\u27a2\u2013\u2014"

_VERIFY_PREFIX = re.compile(r"^\s*\[VERIFY\]\s*", re.IGNORECASE)

MAX_STEPS   = 12
MIN_STEP_LEN = 3


def steps_from_text(text):
    """Split a free-text process description into ordered steps.

    Priority order:
        1. One step per line (if >=2 non-trivial lines)
        2. Numbered markers  ("1.", "1)", "Step 2:")
        3. Semicolons / pipes
        4. Sentence split    (. ! ?)

    Each step is stripped of bullet characters and any "[VERIFY]" prefix.
    Fragments shorter than 3 characters are dropped.
    The list is capped at ~12 steps for readability.
    """
    text = (text or "").strip()
    if not text:
        return []

    # --- try newline split first ---
    lines = [ln.strip(_BULLET_CHARS) for ln in text.splitlines() if ln.strip()]
    lines = [_VERIFY_PREFIX.sub("", ln).strip() for ln in lines]
    lines = [ln for ln in lines if len(ln) >= MIN_STEP_LEN]
    if len(lines) >= 2:
        return lines[:MAX_STEPS]

    # --- numbered markers ---
    parts = _NUMBERED_RE.split(text)
    parts = [_VERIFY_PREFIX.sub("", p).strip(_BULLET_CHARS).strip()
             for p in parts if p and p.strip()]
    parts = [p for p in parts if len(p) >= MIN_STEP_LEN]
    if len(parts) >= 2:
        return parts[:MAX_STEPS]

    # --- semicolons / pipes ---
    parts = re.split(r"\s*[;|]\s*", text)
    parts = [_VERIFY_PREFIX.sub("", p).strip(_BULLET_CHARS).strip()
             for p in parts if p and p.strip()]
    parts = [p for p in parts if len(p) >= MIN_STEP_LEN]
    if len(parts) >= 2:
        return parts[:MAX_STEPS]

    # --- sentence split ---
    parts = re.split(r"(?<=[.!?])\s+", text)
    parts = [_VERIFY_PREFIX.sub("", p).strip(_BULLET_CHARS).strip()
             for p in parts if p and p.strip()]
    parts = [p for p in parts if len(p) >= MIN_STEP_LEN]
    if len(parts) >= 2:
        return parts[:MAX_STEPS]

    # single chunk -- not enough for a flowchart
    single = _VERIFY_PREFIX.sub("", text).strip()
    return [single] if len(single) >= MIN_STEP_LEN else []


# ---------------------------------------------------------------------------
# Colour palette (KPMG-ish)
# ---------------------------------------------------------------------------

_EDGE_COLOR   = "#1F4E79"
_TERM_FILL    = "#1F4E79"
_TERM_TEXT    = "#FFFFFF"
_BOX_FILL     = "#EAF1FB"
_BOX_EDGE     = "#1F4E79"
_BOX_TEXT     = "#1F3864"
_TITLE_COLOR  = "#1F3864"

_DECISION_FILL = "#FFF5E0"
_DECISION_EDGE = "#C47F0A"
_DECISION_TEXT = "#7A4D00"

_DATA_FILL = "#E6F9F1"
_DATA_EDGE = "#0D9B6D"
_DATA_TEXT = "#065E42"

_SUB_FILL = "#F0E6FB"
_SUB_EDGE = "#6B3FA0"
_SUB_TEXT = "#3D2066"

# ---------------------------------------------------------------------------
# Horizontal layout constants
# ---------------------------------------------------------------------------

_H_BOX_W     = 2.0    # node width  (inches)
_H_BOX_H     = 0.85   # node height (inches)
_H_GAP       = 0.32   # horizontal gap between nodes (inches)
_H_MARGIN    = 0.4    # left / right page margin (inches)
_H_TITLE_SP  = 0.50   # vertical space above nodes reserved for the title
_H_WRAP_W    = 18     # character wrap width inside each node
_H_MAX_FIG_W = 16.0   # max figure width before proportional scaling kicks in
_DPI         = 160
_MAX_PER_ROW = 4      # nodes per row before wrapping to a new row
_ROW_V_GAP   = 0.65   # vertical gap (inches) between wrapped rows


# ---------------------------------------------------------------------------
# Flowchart rendering  -- horizontal (left → right)
# ---------------------------------------------------------------------------

def render_flowchart(steps, title="Process Flow", key="flowchart"):
    """Draw a multi-row snake-pattern flowchart and save as PNG.

    Even rows (0, 2, …) flow left → right.
    Odd  rows (1, 3, …) flow right → left (arrows reversed).
    Rows are linked by an L-shaped connector on the outer margin so the
    sequence reads naturally like a page of text.

    Parameters
    ----------
    steps : list[str | dict]   Ordered process steps (2+).
    title : str                Chart title.
    key   : str                Stem used in the cached PNG filename.

    Returns
    -------
    str | None   Absolute path to the PNG, or None on failure.
    """
    if not steps or len(steps) < 2:
        return None
    if not matplotlib_available():
        return None

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    raw = [_normalise_step(s) for s in steps]
    raw = [(t, st, nt, yt) for t, st, nt, yt in raw if t]
    if len(raw) < 2:
        return None

    first_is_term = raw[0][1] == "start_end"
    last_is_term  = raw[-1][1] == "start_end"

    all_nodes: list[tuple[str, str, str, str]] = []
    if not first_is_term:
        all_nodes.append(("Start", "start_end", "", ""))
    all_nodes.extend(raw)
    if not last_is_term:
        all_nodes.append(("End", "start_end", "", ""))

    # Count nodes with a "No" branch to reserve extra vertical space
    no_branch_count = sum(1 for _, st, nt, _ in all_nodes if nt)

    # Chunk into rows of _MAX_PER_ROW
    rows     = [all_nodes[i:i + _MAX_PER_ROW]
                for i in range(0, len(all_nodes), _MAX_PER_ROW)]
    n_rows   = len(rows)
    max_cols = max(len(r) for r in rows)

    bw         = _H_BOX_W
    bh         = _H_BOX_H
    gap        = _H_GAP
    margin     = _H_MARGIN
    font_box   = 7.5
    font_title = 11
    font_term  = 9

    # Scale only if a single row is wider than the page limit
    single_row_w = margin * 2 + max_cols * bw + (max_cols - 1) * gap
    if single_row_w > _H_MAX_FIG_W:
        scale        = max(_H_MAX_FIG_W / single_row_w, 0.5)
        bw          *= scale; bh    *= scale
        gap         *= scale; margin *= scale
        font_box     = max(5.5, font_box   * scale)
        font_title   = max(8,   font_title * scale)
        font_term    = max(6.5, font_term  * scale)
        single_row_w = margin * 2 + max_cols * bw + (max_cols - 1) * gap

    half_h   = bh / 2.0
    overhang = margin * 0.65       # extra space for L-connector outside content
    no_box_h = bh                  # No-branch box is now full height
    no_branch_depth = 0.30 + no_box_h   # gap_y + box height
    row_v_gap = _ROW_V_GAP
    if no_branch_count:
        # Keep a branch below one row clear of the node in the next row.
        row_v_gap = max(row_v_gap, no_branch_depth + 0.25)
    no_extra = (no_branch_depth + 0.25) if no_branch_count else 0.0
    fig_w    = single_row_w
    fig_h    = _H_TITLE_SP + n_rows * bh + (n_rows - 1) * row_v_gap + 0.45 + no_extra

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(fig_w / 2.0, fig_h - 0.10, title,
            fontsize=font_title, fontweight="bold",
            color=_TITLE_COLOR, ha="center", va="top",
            fontfamily="sans-serif")

    def _draw_node(x, cy, text, stype):
        wrapped = textwrap.fill(text, _H_WRAP_W)
        if stype == "start_end":
            _draw_terminator_h(ax, x, cy, bw, bh, wrapped, font_term)
        elif stype == "decision":
            _draw_diamond_h(ax, x, cy, bw, bh, wrapped, font_box)
        elif stype == "data":
            _draw_parallelogram_h(ax, x, cy, bw, bh, wrapped, font_box)
        elif stype == "subprocess":
            _draw_subprocess_h(ax, x, cy, bw, bh, wrapped, font_box)
        else:
            ax.add_patch(mpatches.FancyBboxPatch(
                (x, cy - half_h), bw, bh,
                boxstyle="round,pad=0.06",
                facecolor=_BOX_FILL, edgecolor=_BOX_EDGE, linewidth=1.2,
            ))
            ax.text(x + bw / 2.0, cy, wrapped,
                    fontsize=font_box, color=_BOX_TEXT,
                    ha="center", va="center",
                    fontfamily="sans-serif", linespacing=1.3, clip_on=False)

    def _lconnect(x1, y1, x2, y2):
        """Draw a right-angle connector with an arrowhead at (x2, y2)."""
        # Determine corner: share x with start, y with end
        ax.plot([x1, x1], [y1, y2],
                color=_EDGE_COLOR, lw=1.8, solid_capstyle="round", clip_on=False)
        ax.annotate("", xy=(x2, y2), xytext=(x1, y2),
                    arrowprops=dict(arrowstyle="-|>", color=_EDGE_COLOR,
                                    lw=1.8, mutation_scale=16))

    _YES_NO_FS = 6.2   # font size for Yes / No labels
    _LABEL_PAD = 0.06  # gap between node edge and label

    for ri, row in enumerate(rows):
        is_reverse = (ri % 2 == 1)
        cy         = fig_h - _H_TITLE_SP - half_h - ri * (bh + row_v_gap)
        next_cy    = cy - (bh + row_v_gap)

        if is_reverse:
            # ── Right → Left ─────────────────────────────────────────────
            x          = fig_w - margin - bw   # left edge of rightmost node
            prev_left  = None
            prev_stype = None
            prev_yes   = ""

            for text, stype, no_text, yes_text in row:
                if prev_left is not None:
                    _draw_arrow_h(ax, prev_left, cy, x + bw, cy)
                    if prev_stype == "decision":
                        ax.text(prev_left - _LABEL_PAD, cy + _LABEL_PAD,
                                prev_yes or "Yes", fontsize=_YES_NO_FS, color=_DECISION_EDGE,
                                ha="right", va="bottom", fontfamily="sans-serif",
                                fontweight="bold", clip_on=False)
                _draw_node(x, cy, text, stype)
                if no_text:
                    _draw_no_branch(ax, x, cy, bw, bh, no_text, font_box)
                elif stype == "decision":
                    ax.text(x + bw / 2.0, cy - half_h - _LABEL_PAD,
                            "No", fontsize=_YES_NO_FS, color=_DECISION_EDGE,
                            ha="center", va="top", fontfamily="sans-serif",
                            fontweight="bold", clip_on=False)
                prev_left  = x
                prev_stype = stype
                prev_yes   = yes_text
                x         -= (bw + gap)

            # Wrap connector: left side  (RTL end → next LTR start)
            if ri < n_rows - 1:
                oh_x = margin - overhang
                ax.plot([prev_left, oh_x], [cy, cy],
                        color=_EDGE_COLOR, lw=1.8, solid_capstyle="round", clip_on=False)
                _lconnect(oh_x, cy, margin, next_cy)
                if prev_stype == "decision":
                    ax.text(oh_x + _LABEL_PAD, cy + _LABEL_PAD,
                            prev_yes or "Yes", fontsize=_YES_NO_FS, color=_DECISION_EDGE,
                            ha="left", va="bottom", fontfamily="sans-serif",
                            fontweight="bold", clip_on=False,
                            bbox=dict(facecolor="white", edgecolor="none", pad=0.15))

        else:
            # ── Left → Right ─────────────────────────────────────────────
            x          = margin
            prev_right = None
            prev_stype = None
            prev_yes   = ""

            for text, stype, no_text, yes_text in row:
                if prev_right is not None:
                    _draw_arrow_h(ax, prev_right, cy, x, cy)
                    if prev_stype == "decision":
                        ax.text(prev_right + _LABEL_PAD, cy + _LABEL_PAD,
                                prev_yes or "Yes", fontsize=_YES_NO_FS, color=_DECISION_EDGE,
                                ha="left", va="bottom", fontfamily="sans-serif",
                                fontweight="bold", clip_on=False)
                _draw_node(x, cy, text, stype)
                if no_text:
                    _draw_no_branch(ax, x, cy, bw, bh, no_text, font_box)
                elif stype == "decision":
                    ax.text(x + bw / 2.0, cy - half_h - _LABEL_PAD,
                            "No", fontsize=_YES_NO_FS, color=_DECISION_EDGE,
                            ha="center", va="top", fontfamily="sans-serif",
                            fontweight="bold", clip_on=False)
                prev_right = x + bw
                prev_stype = stype
                prev_yes   = yes_text
                x          = prev_right + gap

            # Wrap connector: right side  (LTR end → next RTL start)
            if ri < n_rows - 1:
                oh_x = fig_w - margin + overhang
                ax.plot([prev_right, oh_x], [cy, cy],
                        color=_EDGE_COLOR, lw=1.8, solid_capstyle="round", clip_on=False)
                _lconnect(oh_x, cy, fig_w - margin, next_cy)
                if prev_stype == "decision":
                    ax.text(oh_x - _LABEL_PAD, cy + _LABEL_PAD,
                            prev_yes or "Yes", fontsize=_YES_NO_FS, color=_DECISION_EDGE,
                            ha="right", va="bottom", fontfamily="sans-serif",
                            fontweight="bold", clip_on=False,
                            bbox=dict(facecolor="white", edgecolor="none", pad=0.15))

    plt.tight_layout(pad=0.1)

    hash_parts   = [title] + [f"{st}:{tx}:{nt}:{yt}" for tx, st, nt, yt in raw]
    content_hash = hashlib.md5("|".join(hash_parts).encode("utf-8")).hexdigest()[:12]
    safe_key     = re.sub(r"[^a-zA-Z0-9_-]", "_", key)[:40]
    fname        = f"flowchart_{safe_key}_{content_hash}.png"
    out_path     = os.path.join(tempfile.gettempdir(), fname)

    fig.savefig(out_path, dpi=_DPI, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Drawing helpers  (horizontal left-to-right layout)
# ---------------------------------------------------------------------------

def _draw_terminator_h(ax, left, cy, w, h, label, fontsize=9):
    """Dark-blue rounded terminator (Start / End)."""
    import matplotlib.patches as mpatches
    half_h = h / 2.0
    ax.add_patch(mpatches.FancyBboxPatch(
        (left, cy - half_h), w, h,
        boxstyle="round,pad=0.10",
        facecolor=_TERM_FILL, edgecolor=_EDGE_COLOR, linewidth=1.5,
    ))
    ax.text(left + w / 2.0, cy, label,
            fontsize=fontsize, fontweight="bold", color=_TERM_TEXT,
            ha="center", va="center", fontfamily="sans-serif")


def _draw_diamond_h(ax, left, cy, w, h, label, fontsize=7):
    """Amber decision diamond -- points at left, top, right, bottom."""
    from matplotlib.patches import Polygon
    import numpy as np
    mid_x  = left + w / 2.0
    half_h = h / 2.0
    verts  = np.array([
        [left,      cy       ],   # left  point
        [mid_x,     cy + half_h], # top   point
        [left + w,  cy       ],   # right point
        [mid_x,     cy - half_h], # bottom point
    ])
    ax.add_patch(Polygon(verts, closed=True,
                         facecolor=_DECISION_FILL, edgecolor=_DECISION_EDGE,
                         linewidth=1.3))
    ax.text(mid_x, cy, label,
            fontsize=fontsize, color=_DECISION_TEXT,
            ha="center", va="center",
            fontfamily="sans-serif", linespacing=1.3, clip_on=False)


def _draw_parallelogram_h(ax, left, cy, w, h, label, fontsize=7.5):
    """Green right-leaning parallelogram (Data / IO node)."""
    from matplotlib.patches import Polygon
    import numpy as np
    half_h = h / 2.0
    skew   = 0.18   # horizontal skew (inches)
    verts  = np.array([
        [left  + skew, cy + half_h],
        [left + w + skew, cy + half_h],
        [left + w - skew, cy - half_h],
        [left  - skew, cy - half_h],
    ])
    ax.add_patch(Polygon(verts, closed=True,
                         facecolor=_DATA_FILL, edgecolor=_DATA_EDGE,
                         linewidth=1.2))
    ax.text(left + w / 2.0, cy, label,
            fontsize=fontsize, color=_DATA_TEXT,
            ha="center", va="center",
            fontfamily="sans-serif", linespacing=1.3, clip_on=False)


def _draw_subprocess_h(ax, left, cy, w, h, label, fontsize=7.5):
    """Purple double-bordered rectangle (Subprocess node)."""
    import matplotlib.patches as mpatches
    half_h    = h / 2.0
    bar_inset = 0.14
    ax.add_patch(mpatches.FancyBboxPatch(
        (left, cy - half_h), w, h,
        boxstyle="round,pad=0.04",
        facecolor=_SUB_FILL, edgecolor=_SUB_EDGE, linewidth=1.3,
    ))
    # Vertical inner bars on the left and right sides (subprocess convention)
    for bar_x in (left + bar_inset, left + w - bar_inset):
        ax.plot([bar_x, bar_x],
                [cy - half_h + 0.04, cy + half_h - 0.04],
                color=_SUB_EDGE, linewidth=0.9, solid_capstyle="round")
    ax.text(left + w / 2.0, cy, label,
            fontsize=fontsize, color=_SUB_TEXT,
            ha="center", va="center",
            fontfamily="sans-serif", linespacing=1.3, clip_on=False)


def _draw_arrow_h(ax, x1, y1, x2, y2):
    """Rightward arrow connecting two nodes."""
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="-|>",
            color=_EDGE_COLOR,
                lw=1.8,
            mutation_scale=16,
        ),
    )


def _draw_no_branch(ax, diamond_left, diamond_cy, bw, bh, no_text, fontsize=7.5):
    """Draw a full-sized 'No' branch box below a decision diamond.

    The box is the same size as a regular process node so both Yes and No
    paths look equally important. A labeled arrow connects the diamond's
    bottom point to the top of the No box.

    Returns the total extra height consumed below the diamond's centre
    so the caller can account for it in the figure size.
    """
    import matplotlib.patches as mpatches

    half_h   = bh / 2.0
    box_w    = bw               # same width as other nodes
    box_h    = bh               # same height as other nodes
    gap_y    = 0.30             # gap between diamond bottom and No box top
    mid_x    = diamond_left + bw / 2.0
    box_left = mid_x - box_w / 2.0
    box_top  = diamond_cy - half_h - gap_y
    box_cy   = box_top - box_h / 2.0

    # Downward arrow from diamond bottom point to top of No box
    ax.annotate(
        "", xy=(mid_x, box_top), xytext=(mid_x, diamond_cy - half_h),
        arrowprops=dict(arrowstyle="-|>", color=_DECISION_EDGE,
                        lw=1.8, mutation_scale=14))

    # "No" label on the downward arrow
    label_y = diamond_cy - half_h - gap_y * 0.45
    ax.text(mid_x + 0.10, label_y, "No",
            fontsize=6.5, color=_DECISION_EDGE, fontweight="bold",
            ha="left", va="center", fontfamily="sans-serif", clip_on=False)

    # Full-sized rounded box (same style as process nodes)
    ax.add_patch(mpatches.FancyBboxPatch(
        (box_left, box_top - box_h), box_w, box_h,
        boxstyle="round,pad=0.06",
        facecolor="#FFF5E0", edgecolor=_DECISION_EDGE, linewidth=1.2,
    ))
    wrapped = textwrap.fill(no_text, _H_WRAP_W)
    ax.text(mid_x, box_cy, wrapped,
            fontsize=fontsize, color=_DECISION_TEXT,
            ha="center", va="center",
            fontfamily="sans-serif", linespacing=1.3, clip_on=False)

    # total extra height below diamond centre
    return half_h + gap_y + box_h


# ---------------------------------------------------------------------------
# Swim-lane flowchart  (horizontal lanes, left → right flow)
# ---------------------------------------------------------------------------

def render_swimlane_flowchart(steps, title="Process Flow", key="flowchart"):
    """Draw a horizontal swim-lane flowchart and save as PNG.

    Each step element may be a dict with keys ``text``, ``type``, and
    optionally ``lane`` (string).  Steps with no ``lane`` value go into a
    "General" lane.  Unique lane names (in order of first appearance) become
    horizontal bands stacked top-to-bottom.

    Returns
    -------
    str | None   Absolute path to the PNG, or None on failure.
    """
    if not steps or len(steps) < 2:
        return None
    if not matplotlib_available():
        return None

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    # Normalise to (text, stype, lane, no_text, yes_text) quints
    triples = []
    for s in steps:
        text, stype, no_text, yes_text = _normalise_step(s)
        lane = (s.get("lane") or "General").strip() if isinstance(s, dict) else "General"
        if text:
            triples.append((text, stype, lane, no_text, yes_text))

    if len(triples) < 2:
        return None

    # Ordered unique lanes (preserve first-appearance order)
    seen_lanes: list[str] = []
    for _, _, ln, _, _ in triples:
        if ln not in seen_lanes:
            seen_lanes.append(ln)
    n_lanes = len(seen_lanes)

    # Layout parameters -- taller lanes for clear row separation
    bw        = _H_BOX_W * 0.85
    bh        = _H_BOX_H
    gap       = _H_GAP * 0.75
    lane_pad  = 0.42           # tall padding → clearly distinct rows
    lane_h    = bh + 2 * lane_pad
    label_w   = 1.30           # wider label column
    margin    = 0.30
    title_sp  = _H_TITLE_SP
    font_box   = 7.0
    font_title = 11.0
    font_lane  = 8.5

    n = len(triples)
    if any(no_text for _, _, _, no_text, _ in triples):
        # Reserve room below decision diamonds for their full-sized No branch boxes.
        lane_pad += 0.30 + bh * 0.5
        lane_h = bh + 2 * lane_pad
    total_w = label_w + margin + n * bw + (n - 1) * gap + margin
    if total_w > _H_MAX_FIG_W:
        scale      = max(_H_MAX_FIG_W / total_w, 0.50)
        bw        *= scale; bh        *= scale; gap       *= scale
        lane_pad  *= scale; lane_h     = bh + 2 * lane_pad
        label_w   *= scale; margin    *= scale
        font_box   = max(5.0, font_box   * scale)
        font_lane  = max(5.5, font_lane  * scale)
        font_title = max(8.0, font_title * scale)
        total_w    = label_w + margin + n * bw + (n - 1) * gap + margin

    fig_w = total_w
    fig_h = title_sp + n_lanes * lane_h + 0.25

    # Y-centre per lane (top lane first)
    lane_ys: dict[str, float] = {}
    for li, ln in enumerate(seen_lanes):
        lane_ys[ln] = fig_h - title_sp - lane_pad - bh / 2.0 - li * lane_h

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # Title
    ax.text(fig_w / 2.0, fig_h - 0.10, title,
            fontsize=font_title, fontweight="bold", color=_TITLE_COLOR,
            ha="center", va="top", fontfamily="sans-serif")

    # Lane bands: dark-blue label header + alternating light body
    label_colors = ["#1F4E79", "#2E6096"]
    band_colors  = ["#EAF1FB", "#F4F8FC"]
    for li, ln in enumerate(seen_lanes):
        cy  = lane_ys[ln]
        top = cy + bh / 2.0 + lane_pad
        bot = cy - bh / 2.0 - lane_pad

        # Body strip (right of label column)
        ax.add_patch(mpatches.FancyBboxPatch(
            (label_w, bot), fig_w - label_w, top - bot,
            boxstyle="square",
            facecolor=band_colors[li % 2], edgecolor="none", linewidth=0,
        ))

        # Dark label column
        ax.add_patch(mpatches.FancyBboxPatch(
            (0, bot), label_w, top - bot,
            boxstyle="square",
            facecolor=label_colors[li % 2], edgecolor="none", linewidth=0,
        ))
        ax.text(label_w / 2.0, cy, ln,
                fontsize=font_lane, fontweight="bold", color="white",
                ha="center", va="center", fontfamily="sans-serif", clip_on=True)

        # Horizontal divider between lanes
        ax.plot([0, fig_w], [top, top], color="#9AB4CC", linewidth=1.0)
        if li == n_lanes - 1:
            ax.plot([0, fig_w], [bot, bot], color="#9AB4CC", linewidth=1.0)

    # Vertical separator after label column
    first_top = lane_ys[seen_lanes[0]]  + bh / 2.0 + lane_pad
    last_bot  = lane_ys[seen_lanes[-1]] - bh / 2.0 - lane_pad
    ax.plot([label_w, label_w], [last_bot, first_top], color="#9AB4CC", linewidth=1.2)

    # Steps and connecting arrows
    x          = label_w + margin
    half_h     = bh / 2.0
    prev_right = None
    prev_cy    = None
    prev_stype = None
    prev_yes   = ""
    _YES_NO_FS = 6.0
    _LABEL_PAD = 0.05

    for text, stype, lane, no_text, yes_text in triples:
        cy      = lane_ys[lane]
        wrapped = textwrap.fill(text, _H_WRAP_W)

        if prev_right is not None:
            same_lane = (cy == prev_cy)
            conn = "arc3,rad=0.0" if same_lane else "arc3,rad=-0.45"
            ax.annotate("", xy=(x, cy), xytext=(prev_right, prev_cy),
                        arrowprops=dict(
                            arrowstyle="-|>", color=_EDGE_COLOR,
                            lw=1.8, mutation_scale=16,
                            connectionstyle=conn,
                        ))
            if prev_stype == "decision":
                ax.text(prev_right + _LABEL_PAD, prev_cy + _LABEL_PAD,
                        prev_yes or "Yes", fontsize=_YES_NO_FS, color=_DECISION_EDGE,
                        ha="left", va="bottom", fontfamily="sans-serif",
                        fontweight="bold", clip_on=False)

        if stype == "start_end":
            _draw_terminator_h(ax, x, cy, bw, bh, wrapped, font_box)
        elif stype == "decision":
            _draw_diamond_h(ax, x, cy, bw, bh, wrapped, max(5.0, font_box - 1))
        elif stype == "data":
            _draw_parallelogram_h(ax, x, cy, bw, bh, wrapped, font_box)
        elif stype == "subprocess":
            _draw_subprocess_h(ax, x, cy, bw, bh, wrapped, font_box)
        else:
            ax.add_patch(mpatches.FancyBboxPatch(
                (x, cy - half_h), bw, bh,
                boxstyle="round,pad=0.06",
                facecolor=_BOX_FILL, edgecolor=_BOX_EDGE, linewidth=1.2,
            ))
            ax.text(x + bw / 2.0, cy, wrapped,
                    fontsize=font_box, color=_BOX_TEXT,
                    ha="center", va="center",
                    fontfamily="sans-serif", linespacing=1.3, clip_on=False)

        if no_text:
            _draw_no_branch(ax, x, cy, bw, bh, no_text, font_box)
        elif stype == "decision":
            ax.text(x + bw / 2.0, cy - half_h - _LABEL_PAD,
                    "No", fontsize=_YES_NO_FS, color=_DECISION_EDGE,
                    ha="center", va="top", fontfamily="sans-serif",
                    fontweight="bold", clip_on=False)

        prev_right = x + bw
        prev_cy    = cy
        prev_stype = stype
        prev_yes   = yes_text
        x         += bw + gap

    plt.tight_layout(pad=0.1)

    hash_parts   = [title] + [f"{st}:{tx}:{ln}:{nt}:{yt}" for tx, st, ln, nt, yt in triples]
    content_hash = hashlib.md5("|".join(hash_parts).encode("utf-8")).hexdigest()[:12]
    safe_key     = re.sub(r"[^a-zA-Z0-9_-]", "_", key)[:40]
    fname        = f"flowchart_{safe_key}_{content_hash}.png"
    out_path     = os.path.join(tempfile.gettempdir(), fname)

    fig.savefig(out_path, dpi=_DPI, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    return out_path
