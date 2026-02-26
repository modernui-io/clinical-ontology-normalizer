"""Figure 3: Complexity-Dependent KG Benefit — B2->B3 delta by tier.

Improvements: gradient coloring by tier, overall CI annotation, cleaner styling.
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
tiers = ['Tier A\n(1\u20132 enc.)', 'Tier B\n(5\u201310 enc.)', 'Tier C\n(15+ enc.)']
deltas = [0.6, 1.0, 5.0]

# Gradient colors — darker = more complex
bar_colors = ['#A8D0E6', '#4A96B5', '#1B5E8C']

fig, ax = plt.subplots(figsize=(4.2, 3.0))
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

bars = ax.bar(range(len(tiers)), deltas, color=bar_colors, edgecolor='white',
              linewidth=0.8, width=0.55, zorder=3)

# Value labels on top
for bar, val, color in zip(bars, deltas, bar_colors):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15,
            f'+{val:.1f} pp', ha='center', va='bottom', fontsize=8.5,
            fontweight='bold', color=color)

# Zero line
ax.axhline(y=0, color='#AAAAAA', linestyle='-', linewidth=0.5, zorder=1)

# Overall CI band
ci_lo, ci_hi = -1.5, 5.9
ax.axhspan(ci_lo, ci_hi, alpha=0.06, color='#1B5E8C', zorder=0)
ax.axhline(y=2.2, color='#1B5E8C', linestyle=':', linewidth=0.8, alpha=0.5, zorder=1)
ax.text(2.35, 2.2, 'Overall: +2.2 pp\n(CI: [-1.5, +5.9])',
        ha='left', va='bottom', fontsize=6, color='#1B5E8C', fontstyle='italic')

# Sample note
ax.text(0.98, 0.02, 'n = 2 patients/tier, 24 Q/patient\nPoint estimates; per-tier CIs not available',
        transform=ax.transAxes, ha='right', va='bottom',
        fontsize=5.5, color='#888888', linespacing=1.3)

ax.set_xticks(range(len(tiers)))
ax.set_xticklabels(tiers, fontsize=8.5)
ax.set_ylabel(r'B2 $\rightarrow$ B3 Accuracy Gain (pp)', fontsize=9)
ax.set_ylim(-2.0, 7.0)
ax.tick_params(axis='y', labelsize=8)

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#CCCCCC')
ax.spines['bottom'].set_color('#CCCCCC')

plt.tight_layout()
plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig3_complexity_bars.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig3_complexity_bars.pdf generated successfully")
