"""Figure 2: ClinicalBench Radar Chart — per-category accuracy for C6, C1, C3, C4g (Claude Opus 4.6, evaluator v2)."""

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

# All 9 categories: Task A (assertion) then Task B (temporal)
categories = [
    'Negation', 'Conditional', 'Uncertainty', 'Family\nHistory',
    'Sequence', 'Current\nState', 'Duration', 'Historical', 'Change'
]
N = len(categories)

# Opus 4.6 data (400 questions, keyword evaluator v2 with abstention detection)
c6_vals  = [ 69.1, 35.0, 27.5, 43.3,  0.0, 44.0, 66.7,  0.0, 23.3]
c1_vals  = [ 45.5,  0.0, 12.5,  3.3, 10.0, 26.0, 30.0,  6.0,  6.7]
c3_vals  = [ 65.5, 30.0, 37.5, 43.3, 57.5, 54.0, 60.0, 42.0, 16.7]
c4g_vals = [ 80.9, 45.0, 50.0, 56.7, 65.0, 70.0, 66.7, 60.0, 100.0]

# Compute angles
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]
c6_vals += c6_vals[:1]
c1_vals += c1_vals[:1]
c3_vals += c3_vals[:1]
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

# Plot C6 — pink dash-dot (long context bookend)
ax.plot(angles, c6_vals, color='#CC79A7', linewidth=1.4,
        linestyle='dashdot', marker='v', markersize=3.5, alpha=0.8, zorder=2)
ax.fill(angles, c6_vals, color='#CC79A7', alpha=0.05, zorder=1)

# Plot C1 — gray dotted baseline
ax.plot(angles, c1_vals, color='#999999', linewidth=1.3,
        linestyle='dotted', marker='o', markersize=3, alpha=0.7, zorder=3)
ax.fill(angles, c1_vals, color='#999999', alpha=0.04, zorder=1)

# Plot C3 — orange dashed (KG-RAG without assertions)
ax.plot(angles, c3_vals, color='#E69F00', linewidth=1.6,
        linestyle='dashed', marker='s', markersize=3.5, alpha=0.85, zorder=4)
ax.fill(angles, c3_vals, color='#E69F00', alpha=0.06, zorder=1)

# Plot C4g — dark blue solid (intent-aware, best condition)
ax.plot(angles, c4g_vals, color='#1B5E8C', linewidth=2.2,
        linestyle='solid', marker='D', markersize=4, alpha=0.95, zorder=5)
ax.fill(angles, c4g_vals, color='#1B5E8C', alpha=0.08, zorder=1)

# Annotate C4g on change (100%)
change_angle = angles[8]
ax.annotate(
    '+93 pp\n(C1->C4g)',
    xy=(change_angle, c4g_vals[8]),
    xytext=(change_angle + 0.25, c4g_vals[8] + 8),
    fontsize=7, fontweight='bold', color='#1B5E8C',
    arrowprops=dict(arrowstyle='->', color='#1B5E8C', lw=1.0),
    ha='left', va='bottom', zorder=10,
)

# Annotate C3 on change (16.7%) — shows epistemic gap
ax.annotate(
    'C3: 17%',
    xy=(change_angle, c3_vals[8]),
    xytext=(change_angle - 0.30, c3_vals[8] + 18),
    fontsize=6.5, fontweight='bold', color='#E69F00',
    arrowprops=dict(arrowstyle='->', color='#E69F00', lw=0.8),
    ha='right', va='bottom', zorder=10,
)

# Annotate C6 collapse on sequence
seq_angle = angles[4]
ax.annotate(
    'C6: 0%',
    xy=(seq_angle, 2),
    xytext=(seq_angle + 0.30, 25),
    fontsize=6.5, fontweight='bold', color='#D64545',
    arrowprops=dict(arrowstyle='->', color='#D64545', lw=0.8),
    ha='left', va='bottom', zorder=10,
)

# Annotate C1 collapse on conditional
cond_angle = angles[1]
ax.annotate(
    'C1: 0%',
    xy=(cond_angle, 2),
    xytext=(cond_angle + 0.30, 22),
    fontsize=6.5, fontweight='bold', color='#D64545',
    arrowprops=dict(arrowstyle='->', color='#D64545', lw=0.8),
    ha='left', va='bottom', zorder=10,
)

# Legend
legend_elements = [
    Line2D([0], [0], color='#CC79A7', linestyle='dashdot', linewidth=1.4,
           marker='v', markersize=3.5, label='C6: Long Context (39.0%)'),
    Line2D([0], [0], color='#999999', linestyle='dotted', linewidth=1.3,
           marker='o', markersize=3.5, label='C1: LLM Alone (21.8%)'),
    Line2D([0], [0], color='#E69F00', linestyle='dashed', linewidth=1.6,
           marker='s', markersize=3.5, label='C3: KG-RAG no assert. (50.0%)'),
    Line2D([0], [0], color='#1B5E8C', linestyle='solid', linewidth=2.2,
           marker='D', markersize=4, label='C4g: +Intent-Aware (69.0%)'),
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
