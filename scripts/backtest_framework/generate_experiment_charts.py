#!/usr/bin/env python3
"""Generate comparison charts from experiments results."""
import json
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = Path(__file__).parent / "output"
RESULTS_FILE = OUTPUT_DIR / "experiments_results.json"
CHARTS_DIR = OUTPUT_DIR / "experiment_charts"
CHARTS_DIR.mkdir(exist_ok=True, parents=True)

with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
    results = json.load(f)

# Filter valid results
valid = [r for r in results if 'error' not in r and 'metrics' in r]

# ============================================================
# Chart 1: Success Rate Comparison Across All Experiments
# ============================================================
fig, ax = plt.subplots(figsize=(14, 7), constrained_layout=True)

names = [r['experiment'] for r in valid]
success = [r['metrics']['success_rate'] for r in valid]
beats = [r['metrics']['beats_benchmark_rate'] for r in valid]

x = np.arange(len(names))
width = 0.35

# Color by experiment set
colors_a = '#2196f3'  # blue for weight
colors_b = '#ff9800'  # orange for stop loss
colors_c = '#4caf50'  # green for threshold
colors_d = '#9c27b0'  # purple for ablation
colors_e = '#795548'  # brown for rec count

bar_colors = []
for n in names:
    if n.startswith('A'): bar_colors.append(colors_a)
    elif n.startswith('B'): bar_colors.append(colors_b)
    elif n.startswith('C'): bar_colors.append(colors_c)
    elif n.startswith('D'): bar_colors.append(colors_d)
    else: bar_colors.append(colors_e)

bars1 = ax.bar(x - width/2, success, width, label='Success Rate', 
               color=bar_colors, edgecolor='#24231f', linewidth=0.5, alpha=0.85)
bars2 = ax.bar(x + width/2, beats, width, label='Beats Benchmark', 
               color='#666', edgecolor='#24231f', linewidth=0.5, alpha=0.85)

ax.axhline(y=55, color='#f44336', linestyle='--', linewidth=2, 
           label='PASS Threshold (55%)')
ax.axhline(y=50, color='#999', linestyle=':', alpha=0.5, label='Random (50%)')

ax.set_ylabel('Rate (%)', fontsize=12)
ax.set_title('All 22 Experiments: Success Rate vs Beats Benchmark', fontsize=14, pad=15)
ax.set_xticks(x)
ax.set_xticklabels(names, rotation=45, ha='right', fontsize=8)
ax.legend(loc='upper right', fontsize=10)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.yaxis.grid(True, alpha=0.25, linestyle='--')
ax.set_axisbelow(True)
ax.set_ylim(0, 70)

# Add set labels
set_labels = {
    'A': ('Weight Sets', colors_a),
    'B': ('Stop Loss', colors_b),
    'C': ('Threshold', colors_c),
    'D': ('Ablation', colors_d),
    'E': ('Rec Count', colors_e),
}
for set_id, (label, color) in set_labels.items():
    ax.text(0.02 + (ord(set_id) - ord('A')) * 0.18, 0.95, 
            f"{set_id}: {label}", transform=ax.transAxes, 
            fontsize=9, color=color, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=color))

fig.savefig(CHARTS_DIR / "01_all_experiments.png", dpi=140, facecolor='white')
plt.close(fig)
print("✓ Chart 1 saved")

# ============================================================
# Chart 2: Stop Loss Impact (Set B)
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)

b_exps = [r for r in valid if r['experiment'].startswith('B')]
b_names = ['No SL', '5%', '8%\n(base)', '12%', '15%']
b_success = [r['metrics']['success_rate'] for r in b_exps]
b_sl_hit = [r['metrics']['stop_loss_hit_rate'] for r in b_exps]

ax1 = axes[0]
bars = ax1.bar(b_names, b_success, color=['#4caf50', '#f44336', '#ff9800', '#2196f3', '#9c27b0'],
                edgecolor='#24231f', linewidth=0.8)
ax1.axhline(y=55, color='#f44336', linestyle='--', alpha=0.7, label='PASS threshold')
ax1.set_ylabel('Success Rate (%)', fontsize=11)
ax1.set_title('Stop Loss Impact on Success Rate', fontsize=12)
ax1.set_ylim(0, 60)
ax1.legend(fontsize=9)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.yaxis.grid(True, alpha=0.25, linestyle='--')
ax1.set_axisbelow(True)
for bar, s in zip(bars, b_success):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f'{s:.1f}%',
             ha='center', va='bottom', fontsize=10, fontweight='bold')

ax2 = axes[1]
bars = ax2.bar(b_names, b_sl_hit, color=['#4caf50', '#f44336', '#ff9800', '#2196f3', '#9c27b0'],
                edgecolor='#24231f', linewidth=0.8)
ax2.set_ylabel('Stop Loss Hit Rate (%)', fontsize=11)
ax2.set_title('How Often Stop Loss Was Triggered', fontsize=12)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.yaxis.grid(True, alpha=0.25, linestyle='--')
ax2.set_axisbelow(True)
for bar, s in zip(bars, b_sl_hit):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f'{s:.1f}%',
             ha='center', va='bottom', fontsize=10, fontweight='bold')

fig.savefig(CHARTS_DIR / "02_stop_loss_impact.png", dpi=140, facecolor='white')
plt.close(fig)
print("✓ Chart 2 saved")

# ============================================================
# Chart 3: Signal Ablation (Set D)
# ============================================================
fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)

d_exps = [r for r in valid if r['experiment'].startswith('D')]
d_labels = ['Disable\nSmart Money', 'Disable\nTechnical', 'Disable\nFundamental', 'Disable\nDiversif.']
d_success = [r['metrics']['success_rate'] for r in d_exps]
d_sharpe = [r['metrics']['sharpe'] for r in d_exps]

# Add baseline (A1)
baseline = next(r for r in valid if r['experiment'] == 'A1_baseline_35_30_20_15')
d_labels = ['Baseline\n(all 4 layers)'] + d_labels
d_success = [baseline['metrics']['success_rate']] + d_success
d_sharpe = [baseline['metrics']['sharpe']] + d_sharpe

x = np.arange(len(d_labels))
width = 0.35

ax2 = ax.twinx()
bars1 = ax.bar(x - width/2, d_success, width, label='Success Rate (%)', 
               color='#2196f3', edgecolor='#24231f', linewidth=0.8)
bars2 = ax2.bar(x + width/2, d_sharpe, width, label='Sharpe Ratio', 
                color='#ff9800', edgecolor='#24231f', linewidth=0.8, alpha=0.7)

ax.set_ylabel('Success Rate (%)', fontsize=11, color='#2196f3')
ax2.set_ylabel('Sharpe Ratio', fontsize=11, color='#ff9800')
ax.set_title('Signal Ablation: Impact of Removing Each Layer', fontsize=13, pad=12)
ax.set_xticks(x)
ax.set_xticklabels(d_labels, fontsize=9)
ax.set_ylim(0, 50)
ax2.set_ylim(0, 1.5)
ax.spines['top'].set_visible(False)
ax2.spines['top'].set_visible(False)
ax.yaxis.grid(True, alpha=0.25, linestyle='--')
ax.set_axisbelow(True)

# Legend
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=10)

for bar, s in zip(bars1, d_success):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f'{s:.1f}',
            ha='center', va='bottom', fontsize=9, color='#2196f3', fontweight='bold')
for bar, s in zip(bars2, d_sharpe):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f'{s:.2f}',
             ha='center', va='bottom', fontsize=9, color='#e65100', fontweight='bold')

fig.savefig(CHARTS_DIR / "03_signal_ablation.png", dpi=140, facecolor='white')
plt.close(fig)
print("✓ Chart 3 saved")

# ============================================================
# Chart 4: Weight Combinations Comparison (Set A)
# ============================================================
fig, ax = plt.subplots(figsize=(11, 5), constrained_layout=True)

a_exps = [r for r in valid if r['experiment'].startswith('A')]
a_labels_short = ['35/30/20/15\n(baseline)', '50/20/20/10\n(smart heavy)', 
                  '20/50/15/15\n(tech heavy)', '25/20/35/20\n(fund heavy)',
                  '25/25/25/25\n(equal)', '20/20/20/40\n(div heavy)']
a_success = [r['metrics']['success_rate'] for r in a_exps]
a_beats = [r['metrics']['beats_benchmark_rate'] for r in a_exps]
a_excess = [r['metrics']['avg_excess_return_pct'] for r in a_exps]

x = np.arange(len(a_labels_short))
width = 0.28

bars1 = ax.bar(x - width, a_success, width, label='Success Rate (%)', 
               color='#4caf50', edgecolor='#24231f', linewidth=0.8)
bars2 = ax.bar(x, a_beats, width, label='Beats Benchmark (%)', 
               color='#2196f3', edgecolor='#24231f', linewidth=0.8)
bars3 = ax.bar(x + width, a_excess, width, label='Excess Return (%)', 
               color='#ff9800', edgecolor='#24231f', linewidth=0.8)

ax.axhline(y=55, color='#f44336', linestyle='--', alpha=0.5, label='PASS threshold')
ax.axhline(y=0, color='#666', linewidth=0.5)
ax.set_ylabel('Value (%)', fontsize=11)
ax.set_title('Weight Combinations: 6 Different Configurations', fontsize=13, pad=12)
ax.set_xticks(x)
ax.set_xticklabels(a_labels_short, fontsize=9)
ax.legend(loc='upper right', fontsize=9, ncol=2)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.yaxis.grid(True, alpha=0.25, linestyle='--')
ax.set_axisbelow(True)
ax.set_ylim(-10, 50)

fig.savefig(CHARTS_DIR / "04_weight_combinations.png", dpi=140, facecolor='white')
plt.close(fig)
print("✓ Chart 4 saved")

# ============================================================
# Chart 5: Threshold Tuning (Set C)
# ============================================================
fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)

c_exps = [r for r in valid if r['experiment'].startswith('C')]
c_labels = ['3%\nthreshold', '5%\n(baseline)', '7%\nthreshold', '10%\nthreshold']
c_success = [r['metrics']['success_rate'] for r in c_exps]
c_beats = [r['metrics']['beats_benchmark_rate'] for r in c_exps]

x = np.arange(len(c_labels))
width = 0.35

bars1 = ax.bar(x - width/2, c_success, width, label='Success Rate', 
               color='#4caf50', edgecolor='#24231f', linewidth=0.8)
bars2 = ax.bar(x + width/2, c_beats, width, label='Beats Benchmark', 
               color='#2196f3', edgecolor='#24231f', linewidth=0.8)

ax.set_ylabel('Rate (%)', fontsize=11)
ax.set_title('Success Threshold Tuning: How Strict Should "Success" Be?', fontsize=13, pad=12)
ax.set_xticks(x)
ax.set_xticklabels(c_labels, fontsize=10)
ax.legend(fontsize=10)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.yaxis.grid(True, alpha=0.25, linestyle='--')
ax.set_axisbelow(True)
ax.set_ylim(0, 50)

for bars, vals in [(bars1, c_success), (bars2, c_beats)]:
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f'{v:.1f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

fig.savefig(CHARTS_DIR / "05_threshold_tuning.png", dpi=140, facecolor='white')
plt.close(fig)
print("✓ Chart 5 saved")

# ============================================================
# Chart 6: Recommendation Count Impact (Set E)
# ============================================================
fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)

e_exps = [r for r in valid if r['experiment'].startswith('E')]
e_labels = ['2 buys + 1 sell\n(fewer)', '3 buys + 2 sells\n(baseline)', '5 buys + 3 sells\n(more)']
e_success = [r['metrics']['success_rate'] for r in e_exps]

bars = ax.bar(e_labels, e_success, color=['#4caf50', '#ff9800', '#f44336'],
               edgecolor='#24231f', linewidth=0.8)
ax.axhline(y=55, color='#f44336', linestyle='--', alpha=0.5, label='PASS threshold')
ax.set_ylabel('Success Rate (%)', fontsize=11)
ax.set_title('Daily Recommendation Count: Fewer is Better', fontsize=13, pad=12)
ax.legend(fontsize=10)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.yaxis.grid(True, alpha=0.25, linestyle='--')
ax.set_axisbelow(True)
ax.set_ylim(0, 50)

for bar, v in zip(bars, e_success):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f'{v:.1f}%',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

fig.savefig(CHARTS_DIR / "06_rec_count_impact.png", dpi=140, facecolor='white')
plt.close(fig)
print("✓ Chart 6 saved")

print(f"\nAll charts saved to: {CHARTS_DIR}")
print(f"Total charts: 6")
