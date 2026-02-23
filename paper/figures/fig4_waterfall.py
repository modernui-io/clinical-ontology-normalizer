"""Figure 4: Slice Bench Condition Progression by Tier — grouped bar chart.
   Camera-ready: full y-axis, no selective highlighting, delta labels at top."""

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10

# Data
conditions = ['B0', 'B1', 'B2', 'B3', 'B4']
cond_labels = ['B0 LLM Alone', 'B1 Latest Note', 'B2 All Notes',
               'B3 KG-RAG', 'B4 Full System']
tier_a = [51.7, 66.7, 81.1, 81.8, 82.6]
tier_b = [49.5, 79.4, 86.4, 87.4, 90.1]
tier_c = [48.4, 74.2, 86.5, 91.5, 90.3]

# B2→B3 deltas
b2b3_deltas = [
    tier_a[3] - tier_a[2],  # +0.7
    tier_b[3] - tier_b[2],  # +1.0
    tier_c[3] - tier_c[2],  # +5.0
]

# Color palette: progressively deeper blue/teal for B0-B4
cond_colors = ['#C6D8E4', '#83B5CF', '#4A96B5', '#2474A0', '#0D5A87']

n_cond = len(conditions)
n_tiers = 3
x = np.arange(n_tiers)
bar_width = 0.14
offsets = np.arange(n_cond) - (n_cond - 1) / 2

fig, ax = plt.subplots(figsize=(6.3, 3.9))
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

tier_labels = ['Tier A (1\u20132 enc.)', 'Tier B (5\u201310 enc.)', 'Tier C (15+ enc.)']

for i, (cond, color, clabel) in enumerate(zip(conditions, cond_colors, cond_labels)):
    vals = [tier_a[i], tier_b[i], tier_c[i]]
    pos = x + offsets[i] * bar_width
    # Identical edge style for all bars — no selective highlighting
    ax.bar(pos, vals, bar_width, color=color, edgecolor='white',
           linewidth=0.6, zorder=3, label=clabel)

# Per-tier delta labels at y=97, centered on each tier group
delta_labels = [
    '\u0394B2\u2192B3: +0.6 pp',
    '\u0394B2\u2192B3: +1.0 pp',
    '\u0394B2\u2192B3: +5.0 pp',
]
for j, dlabel in enumerate(delta_labels):
    ax.text(x[j], 97, dlabel, ha='center', va='top',
            fontsize=7.5, fontweight='medium', color='#2474A0')

# Axis formatting — full 0-100 scale
ax.set_xticks(x)
ax.set_xticklabels(tier_labels, fontsize=8.5)
ax.set_ylabel('Accuracy (%)', fontsize=9)
ax.set_ylim(0, 100)
ax.set_yticks(np.arange(0, 101, 10))
ax.tick_params(axis='y', labelsize=8)

# Single clean legend row above plot, no decorative frame
ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.17),
          ncol=5, fontsize=8.0, frameon=False)

# Remove top and right spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#CCCCCC')
ax.spines['bottom'].set_color('#CCCCCC')

plt.tight_layout()
plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig4_waterfall.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig4_waterfall.pdf generated successfully")
