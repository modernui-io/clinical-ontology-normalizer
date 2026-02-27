"""Figure 5: Dual delta chart — C1 to C4g and C6 to C4g per-category accuracy change (Opus 4.6)."""

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 9,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
})

# Categories sorted by C6 to C4g delta (most positive first)
categories = [
    'Sequence',        # C6 to C4g: +100.0
    'Historical',      # C6 to C4g: +62.0
    'Change',          # C6 to C4g: +56.7
    'Current State',   # C6 to C4g: +26.0
    'Duration',        # C6 to C4g: +20.0
    'Uncertainty',     # C6 to C4g: +20.0
    'Negation',        # C6 to C4g: +18.2
    'Family History',  # C6 to C4g: +13.3
    'Conditional',     # C6 to C4g: +10.0
]

# C6 to C4g deltas (Opus, re-scored)
c6_deltas = [+100.0, +62.0, +56.7, +26.0, +20.0, +20.0, +18.2, +13.3, +10.0]

# C1 to C4g deltas (Opus, re-scored) — matching category order above
c1_deltas = [0.0, +56.0, +90.0, +32.0, +6.7, +32.5, +1.8, +53.3, +30.0]

# Sample sizes (matching category order)
n_questions = [40, 50, 30, 50, 30, 40, 110, 30, 20]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 3.5), sharey=True)
fig.patch.set_facecolor('white')

y_pos = np.arange(len(categories))
bar_height = 0.6

# --- Left panel: C6 to C4g ---
colors_c6 = ['#1B5E8C' if d >= 0 else '#C44E4E' for d in c6_deltas]
bars1 = ax1.barh(y_pos, c6_deltas, height=bar_height, color=colors_c6,
                  edgecolor='white', linewidth=0.5, zorder=3)
ax1.axvline(x=0, color='#444444', linewidth=0.8, zorder=2)
ax1.set_title('C6 to C4g\n(long context to KG-RAG)', fontsize=8.5, fontweight='bold', pad=8)

for i, (val, n) in enumerate(zip(c6_deltas, n_questions)):
    x_label = val + 1.5 if val >= 0 else val - 1.5
    ha = 'left' if val >= 0 else 'right'
    ax1.text(x_label, i, f'{val:+.0f}', ha=ha, va='center',
             fontsize=7, fontweight='bold', color=colors_c6[i])

ax1.set_yticks(y_pos)
ax1.set_yticklabels(categories, fontsize=8)
ax1.set_xlabel('Accuracy Change (pp)', fontsize=8)
ax1.set_xlim(-10, 115)
ax1.tick_params(axis='x', labelsize=7)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.spines['left'].set_color('#CCCCCC')
ax1.spines['bottom'].set_color('#CCCCCC')
ax1.invert_yaxis()
ax1.axvspan(0, 115, alpha=0.02, color='#1B5E8C', zorder=0)
ax1.axvspan(-10, 0, alpha=0.02, color='#C44E4E', zorder=0)

# --- Right panel: C1 to C4g ---
colors_c1 = ['#1B5E8C' if d > 0 else ('#999999' if d == 0 else '#C44E4E') for d in c1_deltas]
bars2 = ax2.barh(y_pos, c1_deltas, height=bar_height, color=colors_c1,
                  edgecolor='white', linewidth=0.5, zorder=3)
ax2.axvline(x=0, color='#444444', linewidth=0.8, zorder=2)
ax2.set_title('C1 to C4g\n(LLM alone to KG-RAG)', fontsize=8.5, fontweight='bold', pad=8)

for i, (val, n) in enumerate(zip(c1_deltas, n_questions)):
    x_label = val + 1.5 if val >= 0 else val - 1.5
    ha = 'left' if val >= 0 else 'right'
    label = f'{val:+.0f}' if val != 0 else '0'
    ax2.text(x_label, i, label, ha=ha, va='center',
             fontsize=7, fontweight='bold', color=colors_c1[i])
    # n annotation
    ax2.text(0.5 if val >= 0 else -0.5, i, f'n={n}',
             ha='left' if val >= 0 else 'right', va='center',
             fontsize=5, color='#AAAAAA')

ax2.set_xlabel('Accuracy Change (pp)', fontsize=8)
ax2.set_xlim(-10, 100)
ax2.tick_params(axis='x', labelsize=7)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.spines['left'].set_color('#CCCCCC')
ax2.spines['bottom'].set_color('#CCCCCC')
ax2.axvspan(0, 100, alpha=0.02, color='#1B5E8C', zorder=0)
ax2.axvspan(-10, 0, alpha=0.02, color='#C44E4E', zorder=0)

plt.tight_layout(w_pad=2.5)
plt.savefig('/Users/alexstinard/projects/brainstorm/jan-14-2026/paper/figures/fig5_category_deltas.pdf',
            bbox_inches='tight', dpi=300, facecolor='white')
plt.close()
print("fig5_category_deltas.pdf generated successfully")
