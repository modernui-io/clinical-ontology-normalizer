"""Figure 1: EpiKG System Architecture — assertion preservation pipeline.

NeurIPS 2026 version — fits exactly within \textwidth (5.5in).
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 9,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'mathtext.fontset': 'stix',
})

# NeurIPS \textwidth = 5.5in; keep figure exactly that wide
fig_w = 5.5
fig_h = 2.3
fig, ax = plt.subplots(figsize=(fig_w, fig_h))
# Use exact axes filling the figure — no bbox_inches='tight' overflow
ax.set_position([0.0, 0.0, 1.0, 1.0])
ax.set_xlim(0, fig_w)
ax.set_ylim(0, fig_h)
ax.axis('off')
fig.patch.set_facecolor('white')

# ── Colors ──
BLUE_DARK  = '#1B5E8C'
BLUE_LIGHT = '#E4EFF8'
GRAY_DARK  = '#2D3748'
GRAY_MED   = '#5A6B80'
GREEN_DARK = '#2D7B4F'
GREEN_LT   = '#EAF5EF'
NOTE_BG    = '#FAF6EF'
NOTE_BD    = '#A89B8A'
PURPLE     = '#6B4FA0'
PURPLE_LT  = '#F2ECF8'
RED_DARK   = '#B83A3A'
RED_LT     = '#FDECEC'
AMBER_DARK = '#9A7200'
AMBER_LT   = '#FFF7E0'

# ── Pipeline stages ──
stages = [
    ('Clinical\nNote',   NOTE_BG,   NOTE_BD),
    ('NLP\nExtract',     BLUE_LIGHT, BLUE_DARK),
    ('OMOP\nMap',        BLUE_LIGHT, BLUE_DARK),
    ('Clinical\nFact',   BLUE_LIGHT, BLUE_DARK),
    ('KG\nEdge',         BLUE_LIGHT, BLUE_DARK),
    ('Graph\nRAG',       BLUE_LIGHT, BLUE_DARK),
    ('LLM\nAnswer',      GREEN_LT,  GREEN_DARK),
]

n_stages = len(stages)
margin = 0.25
usable = fig_w - 2 * margin
box_w = 0.62
gap = (usable - n_stages * box_w) / (n_stages - 1)
box_h = 0.55
pipeline_y = 1.68

def stage_x(i):
    return margin + i * (box_w + gap) + box_w / 2

# Draw boxes
for i, (label, bg, bd) in enumerate(stages):
    cx = stage_x(i)
    rect = FancyBboxPatch(
        (cx - box_w / 2, pipeline_y - box_h / 2), box_w, box_h,
        boxstyle="round,pad=0.06", facecolor=bg, edgecolor=bd,
        linewidth=1.0, zorder=3)
    ax.add_patch(rect)
    ax.text(cx, pipeline_y, label, ha='center', va='center',
            fontsize=6.5, fontweight='semibold', color=GRAY_DARK,
            linespacing=1.1, zorder=4)

# Arrows between boxes
for i in range(n_stages - 1):
    x1 = stage_x(i) + box_w / 2 + 0.02
    x2 = stage_x(i + 1) - box_w / 2 - 0.02
    ax.annotate('', xy=(x2, pipeline_y), xytext=(x1, pipeline_y),
                arrowprops=dict(arrowstyle='->', color=GRAY_MED, lw=1.0),
                zorder=2)

# ── Assertion chain (NLP → Graph RAG, stages 1–5) ──
# Tight vertical gap: just below pipeline boxes
chain_y = pipeline_y - box_h / 2 - 0.28
cx_first = stage_x(1)
cx_last = stage_x(5)
pad = 0.08
chain_rect = FancyBboxPatch(
    (cx_first - box_w / 2 - pad, chain_y - 0.14),
    (cx_last - cx_first) + box_w + 2 * pad, 0.28,
    boxstyle="round,pad=0.04", facecolor='#D6E9F5', edgecolor=BLUE_DARK,
    linewidth=0.8, alpha=0.35, linestyle='--', zorder=1)
ax.add_patch(chain_rect)

# Chain label — sits on top edge of the dashed box
ax.text((cx_first + cx_last) / 2, chain_y + 0.20,
        'Assertion Preservation Invariant', ha='center', va='center',
        fontsize=5.5, color=BLUE_DARK, fontweight='bold', fontstyle='italic',
        bbox=dict(facecolor='white', edgecolor='none', pad=1.0))

# α symbols
for idx in range(1, 6):
    ax.text(stage_x(idx), chain_y, r'$\boldsymbol{\alpha}$',
            ha='center', va='center', fontsize=8.5, color=BLUE_DARK, zorder=4)
# α arrows
for idx in range(1, 5):
    ax.annotate('', xy=(stage_x(idx + 1) - 0.18, chain_y),
                xytext=(stage_x(idx) + 0.18, chain_y),
                arrowprops=dict(arrowstyle='->', color=BLUE_DARK, lw=0.6, alpha=0.45),
                zorder=2)

# ── Tri-temporal annotation — straight down into KG Edge box ──
kg_cx = stage_x(4)
ax.text(kg_cx, pipeline_y + box_h / 2 + 0.14,
        'Tri-temporal  (valid / txn / NLP)',
        ha='center', va='bottom', fontsize=5, color=PURPLE,
        fontweight='semibold', fontstyle='italic', zorder=5)
ax.annotate('', xy=(kg_cx, pipeline_y + box_h / 2 + 0.01),
            xytext=(kg_cx, pipeline_y + box_h / 2 + 0.13),
            arrowprops=dict(arrowstyle='->', color=PURPLE, lw=0.8), zorder=5)

# ── 7 assertion pills ──
pills = ['Present', 'Absent', 'Possible', 'Conditional',
         'Hypothetical', 'Family Hx', 'Historical']
pill_colors = {
    'Present':      (GREEN_LT,  GREEN_DARK),
    'Absent':       (RED_LT,    RED_DARK),
    'Possible':     (AMBER_LT,  AMBER_DARK),
    'Conditional':  (AMBER_LT,  AMBER_DARK),
    'Hypothetical': (AMBER_LT,  AMBER_DARK),
    'Family Hx':    (PURPLE_LT, PURPLE),
    'Historical':   (PURPLE_LT, PURPLE),
}

y_pills = 0.38
pill_w = 0.65
pill_h = 0.22
n_pills = len(pills)
pill_total = fig_w - 2 * margin
pill_gap = (pill_total - n_pills * pill_w) / (n_pills - 1)

# Schema label
ax.text(fig_w / 2, y_pills + 0.28,
        r'7-value assertion schema  $\alpha \in \mathcal{A}$',
        ha='center', va='center', fontsize=6, color=BLUE_DARK, fontweight='bold')

for i, p in enumerate(pills):
    cx = margin + i * (pill_w + pill_gap) + pill_w / 2
    bg, bd = pill_colors[p]
    rect = FancyBboxPatch(
        (cx - pill_w / 2, y_pills - pill_h / 2), pill_w, pill_h,
        boxstyle="round,pad=0.04", facecolor=bg, edgecolor=bd,
        linewidth=0.6, zorder=3)
    ax.add_patch(rect)
    ax.text(cx, y_pills, p, ha='center', va='center',
            fontsize=5, color=bd, fontweight='medium', zorder=4)

# Grouping labels
lbl_y = y_pills - 0.19
ax.text(margin + pill_w / 2, lbl_y, 'affirmed',
        ha='center', va='top', fontsize=4, color=GREEN_DARK, fontstyle='italic')
ax.text(margin + (pill_w + pill_gap) + pill_w / 2, lbl_y, 'negated',
        ha='center', va='top', fontsize=4, color=RED_DARK, fontstyle='italic')
ax.text(margin + 3 * (pill_w + pill_gap) + pill_w / 2, lbl_y, 'uncertain',
        ha='center', va='top', fontsize=4, color=AMBER_DARK, fontstyle='italic')
ax.text(margin + 5.5 * (pill_w + pill_gap) + pill_w / 2, lbl_y, 'attributed',
        ha='center', va='top', fontsize=4, color=PURPLE, fontstyle='italic')

plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig1_architecture.pdf',
            dpi=300, facecolor='white')
plt.close()
print("fig1_architecture.pdf generated successfully")
