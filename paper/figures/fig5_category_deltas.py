"""Figure 5: Dual delta chart — C1 to C4g and C6 to C4g per-category accuracy change (Opus 4.6, evaluator v2)."""

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
# C6→C4g: Change 23.3→100=+76.7, Sequence 0→65=+65, Historical 0→60=+60,
#          Current 44→70=+26, Uncertainty 27.5→50=+22.5, Family 43.3→56.7=+13.3,
#          Negation 69.1→80.9=+11.8, Conditional 35→45=+10, Duration 66.7→66.7=0
categories = [
    'Change',          # C6 to C4g: +76.7
    'Sequence',        # C6 to C4g: +65.0
    'Historical',      # C6 to C4g: +60.0
    'Current State',   # C6 to C4g: +26.0
    'Uncertainty',     # C6 to C4g: +22.5
    'Family History',  # C6 to C4g: +13.3
    'Negation',        # C6 to C4g: +11.8
    'Conditional',     # C6 to C4g: +10.0
    'Duration',        # C6 to C4g: +0.0
]

# C6 to C4g deltas (Opus, evaluator v2)
c6_deltas = [+76.7, +65.0, +60.0, +26.0, +22.5, +13.3, +11.8, +10.0, +0.0]

# C1 to C4g deltas (Opus, evaluator v2) — matching category order above
c1_deltas = [+93.3, +55.0, +54.0, +44.0, +37.5, +53.3, +35.5, +45.0, +36.7]

# Sample sizes (matching category order)
n_questions = [30, 40, 50, 50, 40, 30, 110, 20, 30]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(5.5, 3.5), sharey=True)
fig.patch.set_facecolor('white')

y_pos = np.arange(len(categories))
bar_height = 0.6

# --- Left panel: C6 to C4g ---
colors_c6 = ['#1B5E8C' if d > 0 else ('#999999' if d == 0 else '#C44E4E') for d in c6_deltas]
bars1 = ax1.barh(y_pos, c6_deltas, height=bar_height, color=colors_c6,
                  edgecolor='white', linewidth=0.5, zorder=3)
ax1.axvline(x=0, color='#444444', linewidth=0.8, zorder=2)
ax1.set_title('C6 to C4g\n(long context to KG-RAG)', fontsize=8.5, fontweight='bold', pad=8)

for i, (val, n) in enumerate(zip(c6_deltas, n_questions)):
    x_label = val + 1.5 if val >= 0 else val - 1.5
    ha = 'left' if val >= 0 else 'right'
    label = f'{val:+.0f}' if val != 0 else '0'
    ax1.text(x_label, i, label, ha=ha, va='center',
             fontsize=7, fontweight='bold', color=colors_c6[i])

ax1.set_yticks(y_pos)
ax1.set_yticklabels(categories, fontsize=8)
ax1.set_xlabel('Accuracy Change (pp)', fontsize=8)
ax1.set_xlim(-10, 100)
ax1.tick_params(axis='x', labelsize=7)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.spines['left'].set_color('#CCCCCC')
ax1.spines['bottom'].set_color('#CCCCCC')
ax1.invert_yaxis()
ax1.axvspan(0, 100, alpha=0.02, color='#1B5E8C', zorder=0)
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
