"""Figure 1: EpiKG System Architecture — assertion preservation pipeline."""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 9

fig, ax = plt.subplots(figsize=(5.5, 3.8))
ax.set_xlim(-0.5, 10.5)
ax.set_ylim(-2.2, 3.2)
ax.axis('off')
fig.patch.set_facecolor('white')

# Color palette
BOX_COLOR = '#EDF2F7'
BORDER_COLOR = '#2D3748'
ASSERTION_COLOR = '#2B6CB0'
ASSERTION_BG = '#BEE3F8'
ARROW_COLOR = '#4A5568'
TEMPORAL_COLOR = '#6B46C1'

# Pipeline stages
stages = [
    ('Clinical\nNote', 0.0),
    ('NLP\nExtraction', 1.7),
    ('OMOP\nMapping', 3.4),
    ('Clinical\nFact', 5.1),
    ('KG Edge', 6.8),
    ('Graph\nRAG', 8.5),
    ('LLM', 10.0),
]

box_w = 1.25
box_h = 0.95

# Draw boxes
for label, x in stages:
    rect = FancyBboxPatch(
        (x - box_w / 2, 1.2 - box_h / 2),
        box_w, box_h,
        boxstyle="round,pad=0.12",
        facecolor=BOX_COLOR,
        edgecolor=BORDER_COLOR,
        linewidth=1.3,
    )
    ax.add_patch(rect)
    ax.text(x, 1.2, label, ha='center', va='center', fontsize=8,
            fontweight='semibold', color='#1A202C', linespacing=1.15)

# Draw arrows between boxes
for i in range(len(stages) - 1):
    x_start = stages[i][1] + box_w / 2 + 0.04
    x_end = stages[i + 1][1] - box_w / 2 - 0.04
    ax.annotate('', xy=(x_end, 1.2), xytext=(x_start, 1.2),
                arrowprops=dict(arrowstyle='->', color=ARROW_COLOR,
                                lw=1.5, connectionstyle='arc3,rad=0'))

# Assertion preservation chain (below boxes, stages 1-6)
assertion_stages = stages[1:]  # NLP through LLM
chain_y = 0.2

# Draw assertion chain background bar
chain_x_start = assertion_stages[0][1] - box_w / 2
chain_x_end = assertion_stages[-1][1] + box_w / 2
chain_rect = FancyBboxPatch(
    (chain_x_start, chain_y - 0.24),
    chain_x_end - chain_x_start, 0.48,
    boxstyle="round,pad=0.06",
    facecolor=ASSERTION_BG,
    edgecolor=ASSERTION_COLOR,
    linewidth=1.0,
    alpha=0.45,
    linestyle='--',
)
ax.add_patch(chain_rect)

# Assertion alpha labels under each stage
for label, x in assertion_stages:
    ax.text(x, chain_y, r'$\alpha$', ha='center', va='center',
            fontsize=9, color=ASSERTION_COLOR, fontweight='bold')

# Chain label
ax.text((chain_x_start + chain_x_end) / 2, chain_y + 0.38,
        'Assertion Preservation Chain', ha='center', va='center',
        fontsize=7.5, color=ASSERTION_COLOR, fontweight='bold')

# Tri-temporal annotation on KG Edge box
kg_x = 6.8
ax.annotate(
    'tri-temporal\n(valid / event / ingestion)',
    xy=(kg_x, 1.2 + box_h / 2),
    xytext=(kg_x + 0.1, 2.45),
    fontsize=6.5,
    color=TEMPORAL_COLOR,
    ha='center',
    va='bottom',
    fontweight='semibold',
    arrowprops=dict(arrowstyle='->', color=TEMPORAL_COLOR, lw=1.0),
)

# 7 assertion values — two rows for proper spacing
row1 = ['Present', 'Absent', 'Possible', 'Conditional']
row2 = ['Hypothetical', 'Family Hx', 'Historical']

y_label = -0.55
ax.text(5.0, y_label, '7 Assertion Classes',
        ha='center', va='center',
        fontsize=7.5, color=ASSERTION_COLOR, fontweight='bold')

# Row 1: 4 pills evenly spaced
y_r1 = -1.0
r1_width = 8.0
r1_start = 1.25
r1_spacing = r1_width / (len(row1) - 1)
pill_w = 1.6
pill_h = 0.36

for i, a in enumerate(row1):
    x = r1_start + i * r1_spacing
    pill = FancyBboxPatch(
        (x - pill_w / 2, y_r1 - pill_h / 2),
        pill_w, pill_h,
        boxstyle="round,pad=0.07",
        facecolor='white',
        edgecolor=ASSERTION_COLOR,
        linewidth=0.9,
    )
    ax.add_patch(pill)
    ax.text(x, y_r1, a, ha='center', va='center',
            fontsize=7, color=ASSERTION_COLOR, fontweight='medium')

# Row 2: 3 pills centered
y_r2 = -1.55
r2_width = 6.0
r2_start = 2.25
r2_spacing = r2_width / (len(row2) - 1)

for i, a in enumerate(row2):
    x = r2_start + i * r2_spacing
    pill = FancyBboxPatch(
        (x - pill_w / 2, y_r2 - pill_h / 2),
        pill_w, pill_h,
        boxstyle="round,pad=0.07",
        facecolor='white',
        edgecolor=ASSERTION_COLOR,
        linewidth=0.9,
    )
    ax.add_patch(pill)
    ax.text(x, y_r2, a, ha='center', va='center',
            fontsize=7, color=ASSERTION_COLOR, fontweight='medium')

plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig1_architecture.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig1_architecture.pdf generated successfully")
