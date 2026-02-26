"""Figure 1: EpiKG System Architecture — assertion preservation pipeline.

Improvements over v1:
- α starts at NLP Extraction (not Clinical Note — assertions don't exist yet)
- Removed redundant equation at bottom
- Cleaner assertion class display
- Better spacing and alignment
- Tri-temporal annotation repositioned for clarity
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

# NeurIPS-compatible styling
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 9,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'mathtext.fontset': 'stix',
})

fig, ax = plt.subplots(figsize=(5.5, 3.2))
ax.set_xlim(-0.3, 10.7)
ax.set_ylim(-1.7, 3.0)
ax.axis('off')
fig.patch.set_facecolor('white')

# Color palette — cohesive blue/gray scheme
PIPELINE_BG = '#EBF0F7'
PIPELINE_BORDER = '#3B4B64'
ASSERTION_COLOR = '#1B5E8C'
ASSERTION_BG = '#D4E8F7'
ARROW_COLOR = '#5A6B80'
TEMPORAL_COLOR = '#7B3FA0'
NOTE_BG = '#F5F0E8'  # warmer for input
NOTE_BORDER = '#8B7D6B'
LLM_BG = '#E8F5E8'   # green tint for output
LLM_BORDER = '#5A7B5A'

# Pipeline stages
stages = [
    ('Clinical\nNote',   0.0,   NOTE_BG,     NOTE_BORDER),
    ('NLP\nExtract',     1.7,   PIPELINE_BG, PIPELINE_BORDER),
    ('OMOP\nMap',        3.4,   PIPELINE_BG, PIPELINE_BORDER),
    ('Clinical\nFact',   5.1,   PIPELINE_BG, PIPELINE_BORDER),
    ('KG\nEdge',         6.8,   PIPELINE_BG, PIPELINE_BORDER),
    ('Graph\nRAG',       8.5,   PIPELINE_BG, PIPELINE_BORDER),
    ('LLM\nAnswer',     10.0,   LLM_BG,      LLM_BORDER),
]

box_w = 1.20
box_h = 0.90
pipeline_y = 1.2

# Draw boxes
for label, x, bg, border in stages:
    rect = FancyBboxPatch(
        (x - box_w / 2, pipeline_y - box_h / 2),
        box_w, box_h,
        boxstyle="round,pad=0.10",
        facecolor=bg,
        edgecolor=border,
        linewidth=1.2,
    )
    ax.add_patch(rect)
    ax.text(x, pipeline_y, label, ha='center', va='center', fontsize=7.5,
            fontweight='semibold', color='#1A202C', linespacing=1.15)

# Draw arrows between boxes
for i in range(len(stages) - 1):
    x_start = stages[i][1] + box_w / 2 + 0.05
    x_end = stages[i + 1][1] - box_w / 2 - 0.05
    ax.annotate('', xy=(x_end, pipeline_y), xytext=(x_start, pipeline_y),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                lw=1.4, connectionstyle='arc3,rad=0'))

# Assertion preservation chain — starts at NLP (stage 1), ends at Graph RAG (stage 5)
# Clinical Note has no assertion; LLM Answer consumes but doesn't store it
chain_stages = stages[1:6]  # NLP through Graph RAG
chain_y = 0.22

chain_x_start = chain_stages[0][1] - box_w / 2 - 0.05
chain_x_end = chain_stages[-1][1] + box_w / 2 + 0.05
chain_rect = FancyBboxPatch(
    (chain_x_start, chain_y - 0.22),
    chain_x_end - chain_x_start, 0.44,
    boxstyle="round,pad=0.06",
    facecolor=ASSERTION_BG,
    edgecolor=ASSERTION_COLOR,
    linewidth=1.0,
    alpha=0.40,
    linestyle='--',
)
ax.add_patch(chain_rect)

# α labels under each stage in the chain
for label, x, _, _ in chain_stages:
    ax.text(x, chain_y, r'$\alpha$', ha='center', va='center',
            fontsize=10, color=ASSERTION_COLOR, fontweight='bold')

# Chain connecting arrows between α symbols
for i in range(len(chain_stages) - 1):
    x1 = chain_stages[i][1] + 0.25
    x2 = chain_stages[i + 1][1] - 0.25
    ax.annotate('', xy=(x2, chain_y), xytext=(x1, chain_y),
                arrowprops=dict(arrowstyle='->', color=ASSERTION_COLOR,
                                lw=0.8, alpha=0.5))

# Chain label
ax.text((chain_x_start + chain_x_end) / 2, chain_y + 0.36,
        'Assertion Preservation Invariant', ha='center', va='center',
        fontsize=7, color=ASSERTION_COLOR, fontweight='bold', fontstyle='italic')

# Tri-temporal annotation on KG Edge box
kg_x = 6.8
ax.annotate(
    'Tri-temporal edge\n(valid / transaction / NLP)',
    xy=(kg_x, pipeline_y + box_h / 2 + 0.02),
    xytext=(kg_x + 0.1, 2.50),
    fontsize=6.5,
    color=TEMPORAL_COLOR,
    ha='center',
    va='bottom',
    fontweight='semibold',
    arrowprops=dict(arrowstyle='->', color=TEMPORAL_COLOR, lw=1.0),
)

# 7 assertion classes — compact single row with pills
assertion_classes = ['Present', 'Absent', 'Possible', 'Conditional',
                     'Hypothetical', 'Family Hx', 'Historical']

y_pills = -0.55
ax.text(5.0, y_pills + 0.42, '7-value assertion schema  ' + r'$\alpha \in \mathcal{A}$',
        ha='center', va='center',
        fontsize=7, color=ASSERTION_COLOR, fontweight='bold')

# Single row of pills, evenly distributed
n_pills = len(assertion_classes)
pill_total_w = 10.0
pill_start = 0.25
pill_spacing = pill_total_w / (n_pills - 1)
pill_w = 1.30
pill_h = 0.32

# Color-code by type: positive (green-ish), negative (red-ish), uncertain (yellow-ish), temporal (purple-ish)
pill_colors = {
    'Present': ('#E8F5E8', '#3A7D3A'),
    'Absent': ('#FDE8E8', '#B83A3A'),
    'Possible': ('#FFF8E1', '#B8860B'),
    'Conditional': ('#FFF8E1', '#B8860B'),
    'Hypothetical': ('#FFF8E1', '#B8860B'),
    'Family Hx': ('#F0E6F6', '#7B3FA0'),
    'Historical': ('#F0E6F6', '#7B3FA0'),
}

for i, a in enumerate(assertion_classes):
    x = pill_start + i * pill_spacing
    bg, border = pill_colors[a]
    pill = FancyBboxPatch(
        (x - pill_w / 2, y_pills - pill_h / 2),
        pill_w, pill_h,
        boxstyle="round,pad=0.06",
        facecolor=bg,
        edgecolor=border,
        linewidth=0.8,
    )
    ax.add_patch(pill)
    ax.text(x, y_pills, a, ha='center', va='center',
            fontsize=6, color=border, fontweight='medium')

# Subtle grouping labels
ax.text(pill_start, y_pills - 0.32, 'affirmed', ha='center', va='top',
        fontsize=5, color='#3A7D3A', fontstyle='italic')
ax.text(pill_start + pill_spacing, y_pills - 0.32, 'negated', ha='center', va='top',
        fontsize=5, color='#B83A3A', fontstyle='italic')
ax.text(pill_start + 3 * pill_spacing, y_pills - 0.32, 'uncertain', ha='center', va='top',
        fontsize=5, color='#B8860B', fontstyle='italic')
ax.text(pill_start + 5.5 * pill_spacing, y_pills - 0.32, 'attributed', ha='center', va='top',
        fontsize=5, color='#7B3FA0', fontstyle='italic')

plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig1_architecture.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig1_architecture.pdf generated successfully")
