#!/usr/bin/env python3
"""
Static numbered chart — dark theme (white on black) for Substack.
"""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import geopandas as gpd
from adjustText import adjust_text

COUNTIES_SHP = r"E:\grid\data\census_tiger\cb_2024_us_county_500k.shp"
DATA_CSV = r"E:\grid\reports\scbc_immigrant\scbc_decline_immigrant_rural_data.csv"
OUT_PNG = r"E:\grid\reports\scbc_immigrant\scbc_immigrant_rural_chart.png"

DPI = 200
FIG_W, FIG_H = 14, 11.5

BG = "#111111"
COUNTY_FACE = "#1e1e1e"
COUNTY_EDGE = "#333333"
TEXT_COLOR = "#ffffff"
SUBTLE = "#888888"
LEADER_COLOR = "#555555"

print("Loading SC county boundaries...")
counties = gpd.read_file(COUNTIES_SHP)
sc = counties[counties["STATEFP"] == "45"].copy()

print("Loading church data...")
churches = []
with open(DATA_CSV) as f:
    for row in csv.DictReader(f):
        churches.append(row)

fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

sc.plot(ax=ax, facecolor=COUNTY_FACE, edgecolor=COUNTY_EDGE, linewidth=0.6)

points = []
labels = []
label_colors = []

for ch in churches:
    lon = float(ch["longitude"])
    lat = float(ch["latitude"])
    score = float(ch["opportunity_score"])
    rank = int(ch["rank"])

    if score >= 70:
        color = "#ff6b6b"; z = 8
    elif score >= 55:
        color = "#ffa94d"; z = 7
    else:
        color = "#74c0fc"; z = 6

    ax.scatter(lon, lat, c=color, s=100, edgecolors=BG, linewidth=1.5, zorder=z)
    points.append((lon, lat))
    labels.append(str(rank))
    label_colors.append(color)

# Numbered labels
texts = []
for (lon, lat), label, color in zip(points, labels, label_colors):
    t = ax.text(
        lon, lat, label,
        fontsize=7, fontweight="bold", color="#111111",
        ha="center", va="center",
        bbox=dict(boxstyle="circle,pad=0.25", facecolor=color,
                   edgecolor="#111111", linewidth=1.5, alpha=1.0),
        zorder=10,
    )
    texts.append(t)

adjust_text(
    texts, ax=ax,
    arrowprops=dict(arrowstyle="-", color=LEADER_COLOR, lw=0.5, shrinkA=5, shrinkB=3),
    force_text=(0.6, 1.0),
    force_points=(0.4, 0.6),
    expand=(1.3, 1.4),
    only_move={"points": "y", "text": "xy"},
    lim=80,
)

# ── Styling ────────────────────────────────────────────────────────
ax.set_xticks([])
ax.set_yticks([])
for spine in ax.spines.values():
    spine.set_visible(False)

bounds = sc.total_bounds
pad = 0.2
ax.set_xlim(bounds[0] - pad, bounds[2] + pad)
ax.set_ylim(bounds[1] - pad, bounds[3] + pad)

# Legend
legend_elements = [
    mpatches.Patch(color="#ff6b6b", label="High Priority  (>= 70)"),
    mpatches.Patch(color="#ffa94d", label="Strong Potential  (55-69)"),
    mpatches.Patch(color="#74c0fc", label="Monitor  (< 55)"),
]
legend = ax.legend(handles=legend_elements, loc="lower left",
                    fontsize=7.5, framealpha=0.85,
                    facecolor="#1a1a1a", edgecolor="#333333",
                    title="Opportunity Tier", title_fontsize=8,
                    labelcolor=TEXT_COLOR)
legend.get_title().set_color(TEXT_COLOR)
legend.get_frame().set_linewidth(0.5)

# Title
ax.set_title(
    "SCBC Rural Immigrant Congregation Opportunities\n"
    "25 Declining SBC Churches Across 11 Non-Metro South Carolina Counties",
    fontsize=14, fontweight="bold", pad=18, color=TEXT_COLOR,
)

# Footer
fig.text(
    0.5, 0.004,
    "Scoring: 35% immigrant proximity (ZIP) + 30% SBC decline (ARDA 2010-2020) + 15% 15km catchment + 20% facility viability    |    "
    "Max 3 per county  |  RUCC 4-9 only  |  GRID 2026",
    ha="center", fontsize=6.5, color=SUBTLE,
)

plt.tight_layout(rect=[0, 0.02, 1, 0.97])
fig.savefig(OUT_PNG, dpi=DPI, bbox_inches="tight", facecolor=BG, edgecolor=BG)
plt.close()

print(f"\n[OK] Dark chart saved: {OUT_PNG}")
print(f"     {len(churches)} churches across {len(set(ch['county'] for ch in churches))} counties")
