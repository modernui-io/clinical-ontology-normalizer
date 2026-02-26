"""Figure 4: SliceBench Condition Progression by Tier — grouped bar chart.

Improvements: visual emphasis on B2→B3 transition via bracket, cleaner legend,
better color differentiation.
"""

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

# Data
conditions = ['B0', 'B1', 'B2', 'B3', 'B4']
cond_labels = ['B0 LLM Alone', 'B1 Latest Note', 'B2 All Notes',
               'B3 KG-RAG', 'B4 Full System']
tier_a = [51.7, 66.7, 81.1, 81.8, 82.6]
tier_b = [49.5, 79.4, 86.4, 87.4, 90.1]
tier_c = [48.4, 74.2, 86.5, 91.5, 90.3]

# Color palette — progressively deeper with B2/B3 transition highlighted
cond_colors = ['#CBD5E1', '#93B5CF', '#5B9BD5', '#1B5E8C', '#0D3B5E']

n_cond = len(conditions)
n_tiers = 3
x = np.arange(n_tiers)
bar_width = 0.14
offsets = np.arange(n_cond) - (n_cond - 1) / 2

fig, ax = plt.subplots(figsize=(6.0, 3.8))
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

tier_labels = ['Tier A (1\u20132 enc.)', 'Tier B (5\u201310 enc.)', 'Tier C (15+ enc.)']

for i, (cond, color, clabel) in enumerate(zip(conditions, cond_colors, cond_labels)):
    vals = [tier_a[i], tier_b[i], tier_c[i]]
    pos = x + offsets[i] * bar_width
    edge_width = 1.2 if i in (2, 3) else 0.5  # highlight B2, B3
    edge_color = '#1B5E8C' if i in (2, 3) else 'white'
    ax.bar(pos, vals, bar_width, color=color, edgecolor=edge_color,
           linewidth=edge_width, zorder=3, label=clabel)

# B2→B3 delta annotations with brackets
delta_info = [
    (0, tier_a[2], tier_a[3], '+0.6'),
    (1, tier_b[2], tier_b[3], '+1.0'),
    (2, tier_c[2], tier_c[3], '+5.0'),
]

for j, b2_val, b3_val, dlabel in delta_info:
    # Position bracket between B2 and B3 bars
    b2_x = x[j] + offsets[2] * bar_width
    b3_x = x[j] + offsets[3] * bar_width
    mid_x = (b2_x + b3_x) / 2
    top = max(b2_val, b3_val) + 1.5

    # Bracket
    ax.plot([b2_x, b2_x, b3_x, b3_x], [top - 0.8, top, top, top - 0.8],
            color='#1B5E8C', linewidth=0.8, zorder=5)

    # Delta label
    color = '#1B5E8C' if j < 2 else '#1B5E8C'
    weight = 'bold' if j == 2 else 'medium'
    ax.text(mid_x, top + 0.5, f'$\\Delta${dlabel} pp', ha='center', va='bottom',
            fontsize=7, fontweight=weight, color=color, zorder=5)

ax.set_xticks(x)
ax.set_xticklabels(tier_labels, fontsize=8.5)
ax.set_ylabel('Accuracy (%)', fontsize=9)
ax.set_ylim(0, 100)
ax.set_yticks(np.arange(0, 101, 20))
ax.tick_params(axis='y', labelsize=8)

# Legend — compact row above
ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.16),
          ncol=5, fontsize=7, frameon=False, handlelength=1.2,
          columnspacing=0.8)

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#CCCCCC')
ax.spines['bottom'].set_color('#CCCCCC')

plt.tight_layout()
plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig4_waterfall.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig4_waterfall.pdf generated successfully")
