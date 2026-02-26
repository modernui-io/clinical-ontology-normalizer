"""Figure 5 (NEW): C1→C4g Per-Category Delta — diverging bar chart.

This is the paper's signature visualization: shows exactly where intent-aware
KG-RAG helps (change +60, family_history +57, current_state +12, sequence +10)
and where it hurts (historical -54, duration -53, conditional -35, negation -14).
The diverging bar chart makes the category×condition interaction immediately visible.
"""

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 9,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

# Data: C1→C4g deltas, sorted by magnitude
categories = [
    'Change',          # +60.0
    'Family History',  # +56.7
    'Current State',   # +12.0
    'Sequence',        # +10.0
    'Uncertainty',     # -5.0
    'Negation',        # -13.6
    'Conditional',     # -35.0
    'Duration',        # -53.3
    'Historical',      # -54.0
]

deltas = [60.0, 56.7, 12.0, 10.0, -5.0, -13.6, -35.0, -53.3, -54.0]

# Sample sizes for annotation
n_questions = [30, 30, 50, 40, 40, 110, 20, 30, 50]

# Colors: gains in blue, losses in red/coral
colors = ['#1B5E8C' if d >= 0 else '#C44E4E' for d in deltas]

fig, ax = plt.subplots(figsize=(5.5, 3.5))
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

y_pos = np.arange(len(categories))
bars = ax.barh(y_pos, deltas, height=0.65, color=colors, edgecolor='white',
               linewidth=0.5, zorder=3)

# Zero line
ax.axvline(x=0, color='#444444', linewidth=0.8, zorder=2)

# Value labels at end of each bar
for i, (bar, val, n) in enumerate(zip(bars, deltas, n_questions)):
    # Position label outside the bar
    if val >= 0:
        x_label = val + 1.5
        ha = 'left'
    else:
        x_label = val - 1.5
        ha = 'right'
    ax.text(x_label, i, f'{val:+.1f} pp', ha=ha, va='center',
            fontsize=7.5, fontweight='bold', color=colors[i])
    # n annotation (smaller, inside or at bar base)
    ax.text(0.5 if val >= 0 else -0.5, i, f'n={n}',
            ha='left' if val >= 0 else 'right', va='center',
            fontsize=5.5, color='#888888')

# Category labels
ax.set_yticks(y_pos)
ax.set_yticklabels(categories, fontsize=8)

# X axis
ax.set_xlabel(r'C1 $\rightarrow$ C4g Accuracy Change (pp)', fontsize=9)
ax.set_xlim(-70, 78)
ax.set_xticks([-60, -40, -20, 0, 20, 40, 60])
ax.tick_params(axis='x', labelsize=7.5)

# Spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#CCCCCC')
ax.spines['bottom'].set_color('#CCCCCC')

# Invert y-axis so gains are on top
ax.invert_yaxis()

# Region labels
ax.text(35, -0.7, 'KG-RAG helps', ha='center', va='center',
        fontsize=7.5, color='#1B5E8C', fontweight='bold', fontstyle='italic',
        transform=ax.transData)
ax.text(-35, -0.7, 'KG-RAG hurts', ha='center', va='center',
        fontsize=7.5, color='#C44E4E', fontweight='bold', fontstyle='italic',
        transform=ax.transData)

# Subtle background shading
ax.axvspan(0, 78, alpha=0.02, color='#1B5E8C', zorder=0)
ax.axvspan(-70, 0, alpha=0.02, color='#C44E4E', zorder=0)

plt.tight_layout()
plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig5_category_deltas.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig5_category_deltas.pdf generated successfully")
