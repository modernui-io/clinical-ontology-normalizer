"""Figure 3: Complexity-Dependent KG Benefit — B2->B3 delta by tier.
   Camera-ready: neutral color, sample note, no decorative emphasis."""

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42

# Data — point estimates (per-tier CIs not available; overall B2→B3 CI: [-1.5, +5.9])
tiers = ['Tier A\n(1\u20132 enc.)', 'Tier B\n(5\u201310 enc.)', 'Tier C\n(15+ enc.)']
deltas = [0.6, 1.0, 5.0]

# One neutral bar color for all tiers
bar_color = '#2C7DA0'

fig, ax = plt.subplots(figsize=(4.4, 3.1))
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

bars = ax.bar(range(len(tiers)), deltas, color=bar_color, edgecolor='white',
              linewidth=0.8, width=0.55, zorder=3)

# Value labels on top
for bar, val in zip(bars, deltas):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.10,
            f'+{val:.1f} pp', ha='center', va='bottom', fontsize=8,
            fontweight='bold', color='#1A202C')

# Horizontal line at 0
ax.axhline(y=0, color='#999999', linestyle='-', linewidth=0.5, zorder=1)

# Sample note — bottom right inside plot
ax.text(0.98, 0.02, 'n=2 patients/tier, 24 Q/patient',
        transform=ax.transAxes, ha='right', va='bottom',
        fontsize=7, color='#4B5563')

ax.set_xticks(range(len(tiers)))
ax.set_xticklabels(tiers, fontsize=8.5)
ax.set_ylabel('B2 \u2192 B3 Accuracy Gain (pp)', fontsize=10)
ax.set_ylim(-0.5, 6.0)
ax.tick_params(axis='y', labelsize=8.5)

# Remove top and right spines
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#CCCCCC')
ax.spines['bottom'].set_color('#CCCCCC')

plt.tight_layout()
plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig3_complexity_bars.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig3_complexity_bars.pdf generated successfully")
