#!/usr/bin/env python3
"""Generate charts for the bifilter security report."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# Register fonts that support basic Latin and digits
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False

# Chart 1: API endpoint status code distribution
fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
codes = ['200 OK', '204 No\nContent', '404 Not\nFound', '403\nForbidden', '500 Server\nError', '405 Method\nNotAllowed']
counts = [22, 2, 37, 1, 4, 1]
colors = ['#79b78e', '#7b98b5', '#9b9993', '#c3aa7a', '#c77c75', '#c7b889']
bars = ax.bar(codes, counts, color=colors, edgecolor='#24231f', linewidth=0.8)
ax.set_ylabel('Number of endpoints', fontsize=11)
ax.set_title('API Endpoint Status Code Distribution (67 endpoints tested)', fontsize=12, pad=12)
ax.set_ylim(0, max(counts) + 4)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#9b9993')
ax.spines['bottom'].set_color('#9b9993')
ax.tick_params(colors='#24231f')
ax.yaxis.grid(True, alpha=0.25, linestyle='--')
ax.set_axisbelow(True)
for bar, c in zip(bars, counts):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6, str(c),
            ha='center', va='bottom', fontsize=11, fontweight='bold', color='#24231f')
fig.savefig('/home/z/my-project/scripts/chart_status.png', dpi=160, facecolor='white')
plt.close(fig)
print("chart_status.png saved")

# Chart 2: Security findings severity
fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
sev_labels = ['Critical', 'High', 'Medium', 'Low', 'Info']
sev_counts = [1, 1, 4, 4, 2]
sev_colors = ['#c77c75', '#c3aa7a', '#c7b889', '#7b98b5', '#9b9993']
bars = ax.barh(sev_labels, sev_counts, color=sev_colors, edgecolor='#24231f', linewidth=0.8)
ax.set_xlabel('Number of findings', fontsize=11)
ax.set_title('Security Findings by Severity', fontsize=12, pad=12)
ax.set_xlim(0, max(sev_counts) + 1)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#9b9993')
ax.spines['bottom'].set_color('#9b9993')
ax.xaxis.grid(True, alpha=0.25, linestyle='--')
ax.set_axisbelow(True)
for bar, c in zip(bars, sev_counts):
    ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2, str(c),
            ha='left', va='center', fontsize=11, fontweight='bold', color='#24231f')
fig.savefig('/home/z/my-project/scripts/chart_severity.png', dpi=160, facecolor='white')
plt.close(fig)
print("chart_severity.png saved")

# Chart 3: API response time scatter
fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
# (path_index, response_ms, size_bytes, color_by_status)
import random
random.seed(42)
data = [
    (1, 1430, 1747, '200'), (2, 1072, 0, '204'), (3, 2530, 643, '200'),
    (4, 1399, 4239, '200'), (5, 1080, 13728, '200'), (6, 1096, 185, '200'),
    (7, 1215, 91, '200'), (8, 1111, 65433, '200'), (9, 1552, 4551, '200'),
    (10, 1062, 7335, '200'), (11, 14319, 2, '200'), (12, 1605, 2, '200'),
    (13, 1094, 2, '200'), (14, 1489, 167887, '200'), (15, 7947, 18108, '200'),
    (16, 1084, 17279, '200'), (17, 1142, 6433, '200'), (18, 1176, 17360, '200'),
    (19, 4361, 274075, '200'), (20, 2691, 5056, '200'), (21, 1125, 45, '200'),
    (22, 1083, 10753, '200'),
    # 500s
    (23, 1121, 144, '500'), (24, 1074, 120, '500'), (25, 2984, 96, '500'), (26, 1157, 94, '500'),
]
status_color = {'200': '#79b78e', '204': '#7b98b5', '500': '#c77c75', '403': '#c3aa7a'}
for idx, ms, sz, st in data:
    ax.scatter(idx, ms, s=max(15, sz/300), c=status_color.get(st, '#9b9993'),
               alpha=0.7, edgecolor='#24231f', linewidth=0.5)
ax.set_xlabel('Endpoint index (sorted)', fontsize=11)
ax.set_ylabel('Response time (ms)', fontsize=11)
ax.set_title('API Response Time vs Payload Size (bubble = response bytes)', fontsize=11, pad=12)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#9b9993')
ax.spines['bottom'].set_color('#9b9993')
ax.yaxis.grid(True, alpha=0.25, linestyle='--')
ax.set_axisbelow(True)
ax.set_ylim(0, 16000)
# legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#79b78e', label='200 OK'),
    Patch(facecolor='#7b98b5', label='204 No Content'),
    Patch(facecolor='#c3aa7a', label='403 Forbidden'),
    Patch(facecolor='#c77c75', label='500 Server Error'),
]
ax.legend(handles=legend_elements, loc='upper left', framealpha=0.95, fontsize=9)
fig.savefig('/home/z/my-project/scripts/chart_responsetime.png', dpi=160, facecolor='white')
plt.close(fig)
print("chart_responsetime.png saved")
print("All charts generated.")
