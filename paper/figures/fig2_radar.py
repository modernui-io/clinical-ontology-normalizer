"""Figure 2: ClinicalBench Radar Chart — per-category accuracy for C1, C2, C4.
   Change category omitted (near zero for all conditions)."""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 9
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42

# Data — 8 categories (Change omitted: 0.0, 0.0, 3.3 for C1/C2/C4)
categories = [
    'Negation', 'Conditional', 'Uncertainty', 'Family\nHistory',
    'Sequence', 'Current\nState', 'Duration', 'Historical'
]
N = len(categories)

c1_vals = [100.0, 100.0, 37.5, 0.0, 80.0, 64.0, 100.0, 94.0]
c2_vals = [93.6, 90.0, 2.5, 0.0, 80.0, 54.0, 100.0, 78.0]
c4_vals = [100.0, 70.0, 57.5, 70.0, 87.5, 54.0, 83.3, 60.0]

# Compute angles (evenly spaced)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
# Close the polygon
angles += angles[:1]
c1_vals += c1_vals[:1]
c2_vals += c2_vals[:1]
c4_vals += c4_vals[:1]

fig, ax = plt.subplots(figsize=(5.5, 4.8), subplot_kw=dict(polar=True))
fig.patch.set_facecolor('white')

# Style the grid
ax.set_facecolor('white')
ax.spines['polar'].set_visible(False)
ax.set_ylim(0, 108)
ax.set_yticks([20, 40, 60, 80, 100])
ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'], fontsize=6.5,
                    color='#888888')
ax.yaxis.grid(True, color='#E0E0E0', linewidth=0.5)
ax.xaxis.grid(True, color='#E0E0E0', linewidth=0.5)

# Set category labels
ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=8, fontweight='medium', color='#333333')

# Adjust label padding
ax.tick_params(axis='x', pad=15)

# Plot C1 (gray, dotted) — reference
ax.plot(angles, c1_vals, color='#888888', linewidth=1.5,
        linestyle='dotted', marker='o', markersize=3.5, alpha=0.8, zorder=2)
ax.fill(angles, c1_vals, color='#888888', alpha=0.06, zorder=1)

# Plot C2 (red/coral, dashed) — vanilla RAG collapse
ax.plot(angles, c2_vals, color='#E74C3C', linewidth=1.5,
        linestyle='dashed', marker='s', markersize=3.5, alpha=0.8, zorder=3)
ax.fill(angles, c2_vals, color='#E74C3C', alpha=0.08, zorder=1)

# Plot C4 (blue/teal, solid) — epistemic KG-RAG
ax.plot(angles, c4_vals, color='#2980B9', linewidth=2.0,
        linestyle='solid', marker='D', markersize=4, alpha=0.9, zorder=4)
ax.fill(angles, c4_vals, color='#2980B9', alpha=0.10, zorder=1)

# Legend
legend_elements = [
    Line2D([0], [0], color='#888888', linestyle='dotted', linewidth=1.5,
           marker='o', markersize=4, label='C1: LLM Alone'),
    Line2D([0], [0], color='#E74C3C', linestyle='dashed', linewidth=1.5,
           marker='s', markersize=4, label='C2: +Vanilla RAG'),
    Line2D([0], [0], color='#2980B9', linestyle='solid', linewidth=2.0,
           marker='D', markersize=4, label='C4: +Epistemic KG-RAG'),
]
ax.legend(handles=legend_elements, loc='upper right',
          bbox_to_anchor=(1.28, 1.10), fontsize=7.5, frameon=True,
          fancybox=True, shadow=False, edgecolor='#CCCCCC',
          borderpad=0.6, handletextpad=0.5)

plt.tight_layout(pad=1.5)
plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig2_radar.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig2_radar.pdf generated successfully")
