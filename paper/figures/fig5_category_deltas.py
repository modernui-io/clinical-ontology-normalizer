"""Figure 5: Triple delta chart — C3->C4 (assertions), C4->C4g (routing), C1->C4g (overall) per-category (Opus 4.6, evaluator v2)."""

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 9,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

# Categories sorted by C3->C4 delta: assertion categories positive (top), temporal negative (bottom)
categories = [
    'Negation',        # C3->C4: +24.5
    'Conditional',     # C3->C4: +20.0
    'Uncertainty',     # C3->C4: +15.0
    'Family History',  # C3->C4: +6.7
    'Change',          # C3->C4: -6.7
    'Duration',        # C3->C4: -13.3
    'Current State',   # C3->C4: -24.0
    'Historical',      # C3->C4: -30.0
    'Sequence',        # C3->C4: -47.5
]

# C3->C4 deltas (assertions without routing — what do assertions alone contribute?)
c3_c4_deltas = [+24.5, +20.0, +15.0, +6.7, -6.7, -13.3, -24.0, -30.0, -47.5]

# C4->C4g deltas (intent routing — what does routing add on top of assertions?)
c4_c4g_deltas = [-9.1, -5.0, -2.5, +6.7, +90.0, +20.0, +40.0, +48.0, +55.0]

# C1->C4g deltas (overall — net effect, matching category order above)
c1_c4g_deltas = [+35.5, +45.0, +37.5, +53.3, +93.3, +36.7, +44.0, +54.0, +55.0]

# Sample sizes (matching category order)
n_questions = [110, 20, 40, 30, 30, 30, 50, 50, 40]

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(7.5, 3.5), sharey=True)
fig.patch.set_facecolor('white')

y_pos = np.arange(len(categories))
bar_height = 0.6

def style_panel(ax, deltas, title, xlim, color_pos='#1B5E8C', color_neg='#C44E4E'):
    colors = [color_pos if d > 0 else ('#999999' if d == 0 else color_neg) for d in deltas]
    ax.barh(y_pos, deltas, height=bar_height, color=colors,
            edgecolor='white', linewidth=0.5, zorder=3)
    ax.axvline(x=0, color='#444444', linewidth=0.8, zorder=2)
    ax.set_title(title, fontsize=8, fontweight='bold', pad=8)

    for i, val in enumerate(deltas):
        x_label = val + 1.5 if val >= 0 else val - 1.5
        ha = 'left' if val >= 0 else 'right'
        label = f'{val:+.0f}' if val != 0 else '0'
        ax.text(x_label, i, label, ha=ha, va='center',
                fontsize=6.5, fontweight='bold', color=colors[i])

    ax.set_xlabel('Accuracy Change (pp)', fontsize=7)
    ax.set_xlim(*xlim)
    ax.tick_params(axis='x', labelsize=6.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#CCCCCC')
    ax.spines['bottom'].set_color('#CCCCCC')
    ax.invert_yaxis()
    ax.axvspan(0, xlim[1], alpha=0.02, color=color_pos, zorder=0)
    ax.axvspan(xlim[0], 0, alpha=0.02, color=color_neg, zorder=0)

# --- Left panel: C3->C4 (assertions alone) ---
style_panel(ax1, c3_c4_deltas,
            'C3 -> C4\n(+ assertions, no routing)',
            xlim=(-55, 35))
ax1.set_yticks(y_pos)
ax1.set_yticklabels(categories, fontsize=8)

# Add divider line between Task A (assertion) and Task B (temporal) categories
ax1.axhline(y=3.5, color='#AAAAAA', linewidth=0.5, linestyle='--', zorder=1)
# Task labels
ax1.text(-54, 1.5, 'Task A\n(assertion)', fontsize=6, color='#888888',
         ha='left', va='center', style='italic')
ax1.text(-54, 6.5, 'Task B\n(temporal)', fontsize=6, color='#888888',
         ha='left', va='center', style='italic')

# --- Middle panel: C4->C4g (intent routing) ---
style_panel(ax2, c4_c4g_deltas,
            'C4 -> C4g\n(+ intent routing)',
            xlim=(-15, 100))

# Add divider
ax2.axhline(y=3.5, color='#AAAAAA', linewidth=0.5, linestyle='--', zorder=1)

# --- Right panel: C1->C4g (overall) ---
style_panel(ax3, c1_c4g_deltas,
            'C1 -> C4g\n(overall gain)',
            xlim=(-10, 100))

# Add divider
ax3.axhline(y=3.5, color='#AAAAAA', linewidth=0.5, linestyle='--', zorder=1)

plt.tight_layout(w_pad=1.5)
plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig5_category_deltas.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig5_category_deltas.pdf generated successfully")
