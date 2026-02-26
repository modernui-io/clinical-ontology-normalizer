"""Figure 2: ClinicalBench Radar Chart — per-category accuracy for C1, C2, C4, C4g.

Major improvements over v1:
- INCLUDES C4g (the paper's main condition)
- INCLUDES Change category (the paper's central result: 0%→60%)
- All 9 categories shown
- Better visual hierarchy and styling
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 9,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

# All 9 categories in a logical order:
# Task A (assertion) then Task B (temporal)
categories = [
    'Negation', 'Conditional', 'Uncertainty', 'Family\nHistory',
    'Sequence', 'Current\nState', 'Duration', 'Historical', 'Change'
]
N = len(categories)

# Data from the paper's per-category table
c1_vals  = [100.0, 100.0, 37.5,  0.0, 80.0, 64.0, 100.0, 94.0,  0.0]
c2_vals  = [ 93.6,  90.0,  2.5,  0.0, 80.0, 54.0, 100.0, 78.0,  0.0]
c4_vals  = [100.0,  70.0, 57.5, 70.0, 87.5, 54.0,  83.3, 60.0,  3.3]
c4g_vals = [ 86.4,  65.0, 32.5, 56.7, 90.0, 76.0,  46.7, 40.0, 60.0]

# Compute angles
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]
c1_vals += c1_vals[:1]
c2_vals += c2_vals[:1]
c4_vals += c4_vals[:1]
c4g_vals += c4g_vals[:1]

fig, ax = plt.subplots(figsize=(5.5, 5.0), subplot_kw=dict(polar=True))
fig.patch.set_facecolor('white')

# Style the grid
ax.set_facecolor('white')
ax.spines['polar'].set_visible(False)
ax.set_ylim(0, 110)
ax.set_yticks([20, 40, 60, 80, 100])
ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'], fontsize=6,
                    color='#999999')
ax.yaxis.grid(True, color='#E2E2E2', linewidth=0.5)
ax.xaxis.grid(True, color='#E2E2E2', linewidth=0.5)

# Category labels
ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=7.5, fontweight='medium', color='#333333')
ax.tick_params(axis='x', pad=14)

# Plot C1 — gray dotted baseline
ax.plot(angles, c1_vals, color='#999999', linewidth=1.3,
        linestyle='dotted', marker='o', markersize=3, alpha=0.7, zorder=2)
ax.fill(angles, c1_vals, color='#999999', alpha=0.04, zorder=1)

# Plot C2 — red dashed (vanilla RAG hurts)
ax.plot(angles, c2_vals, color='#D64545', linewidth=1.3,
        linestyle='dashed', marker='s', markersize=3, alpha=0.7, zorder=3)
ax.fill(angles, c2_vals, color='#D64545', alpha=0.05, zorder=1)

# Plot C4 — medium blue (epistemic KG-RAG)
ax.plot(angles, c4_vals, color='#5B9BD5', linewidth=1.5,
        linestyle=(0, (5, 3)), marker='^', markersize=3.5, alpha=0.8, zorder=4)
ax.fill(angles, c4_vals, color='#5B9BD5', alpha=0.06, zorder=1)

# Plot C4g — dark blue solid (intent-aware, the paper's main condition)
ax.plot(angles, c4g_vals, color='#1B5E8C', linewidth=2.2,
        linestyle='solid', marker='D', markersize=4, alpha=0.95, zorder=5)
ax.fill(angles, c4g_vals, color='#1B5E8C', alpha=0.08, zorder=1)

# Annotate the breakthrough: Change category
change_angle = angles[8]  # Change is the 9th category (index 8)
change_c4g = c4g_vals[8]
ax.annotate(
    '+60 pp',
    xy=(change_angle, change_c4g),
    xytext=(change_angle + 0.25, change_c4g + 22),
    fontsize=8, fontweight='bold', color='#1B5E8C',
    arrowprops=dict(arrowstyle='->', color='#1B5E8C', lw=1.0),
    ha='left', va='bottom',
    zorder=10,
)

# Annotate the cost: Historical regression
hist_angle = angles[7]  # Historical is 8th (index 7)
hist_c4g = c4g_vals[7]
ax.annotate(
    '\u221254 pp',
    xy=(hist_angle, hist_c4g),
    xytext=(hist_angle - 0.20, hist_c4g + 25),
    fontsize=7, fontweight='bold', color='#D64545',
    arrowprops=dict(arrowstyle='->', color='#D64545', lw=0.8),
    ha='right', va='bottom',
    zorder=10,
)

# Legend
legend_elements = [
    Line2D([0], [0], color='#999999', linestyle='dotted', linewidth=1.3,
           marker='o', markersize=3.5, label='C1: LLM Alone (71.5%)'),
    Line2D([0], [0], color='#D64545', linestyle='dashed', linewidth=1.3,
           marker='s', markersize=3.5, label='C2: +Vanilla RAG (62.5%)'),
    Line2D([0], [0], color='#5B9BD5', linestyle=(0, (5, 3)), linewidth=1.5,
           marker='^', markersize=3.5, label='C4: +Epistemic KG-RAG (71.5%)'),
    Line2D([0], [0], color='#1B5E8C', linestyle='solid', linewidth=2.2,
           marker='D', markersize=4, label='C4g: +Intent-Aware (66.0%)'),
]
ax.legend(handles=legend_elements, loc='upper right',
          bbox_to_anchor=(1.38, 1.12), fontsize=7, frameon=True,
          fancybox=True, shadow=False, edgecolor='#CCCCCC',
          borderpad=0.6, handletextpad=0.5, labelspacing=0.4)

plt.tight_layout(pad=1.5)
plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig2_radar.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig2_radar.pdf generated successfully")
