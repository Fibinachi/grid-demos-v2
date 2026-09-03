"""
SBC Adherence Heatmap — Churches per 300 Adherents by County (Microsegmented)
Uses arda_counts for SBC-specific adherent data per county.
Uses church_arda for per-church local religious context (evangelical/catholic %).
Red = oversupply (more churches per 300 adherents) | Green = undersupply
"""
import sqlite3, csv, os, statistics, json
from collections import defaultdict
import plotly.express as px
import numpy as np
import pandas as pd

DB = r"E:\grid\churches.db"
OUTPUT_HTML = r"E:\grid\outputs\sbc_adherence_heatmap.html"
OUTPUT_CSV = r"E:\grid\outputs\sbc_adherence_data.csv"
os.makedirs("outputs", exist_ok=True)

print("Connecting...")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ── 1. ARDA SBC adherence per county (arda_counts — microsegmented by denom) ──
print("1. ARDA SBC adherence per county (arda_counts)...")
c.execute("""
    SELECT county_fips, arda_adherents, arda_congregations
    FROM arda_counts
    WHERE denom_code='SBC' AND arda_adherents IS NOT NULL AND arda_adherents > 0
""")
arda_sbc = {}
for r in c.fetchall():
    # FIPS may be 4-digit (missing leading zero) — pad to 5 digits
    fips = str(r['county_fips']).zfill(5)
    arda_sbc[fips] = {
        'adherents': r['arda_adherents'],
        'congregations': r['arda_congregations'] or 0,
    }
total_adherents = sum(v['adherents'] for v in arda_sbc.values())
total_arda_congs = sum(v['congregations'] for v in arda_sbc.values())
print(f"   {len(arda_sbc):,} counties | {total_adherents:,} SBC adherents | {total_arda_congs:,} ARDA congregations")

# ── 2. GRID SBC churches per county ──
print("2. GRID SBC churches (movement_id → Southern Baptist Convention)...")
c.execute("SELECT id FROM taxonomy WHERE name='Southern Baptist Convention'")
sbc_id = c.fetchone()['id']

c.execute("""
    SELECT county_fips_5, COUNT(*) as n
    FROM churches 
    WHERE movement_id=? AND country='US' AND latitude IS NOT NULL AND county_fips_5 IS NOT NULL
    GROUP BY county_fips_5
""", (sbc_id,))
church_by_county = {r['county_fips_5']: r['n'] for r in c.fetchall()}
total_churches = sum(church_by_county.values())
print(f"   {total_churches:,} churches across {len(church_by_county):,} counties")

# ── 3. church_arda — per-church local religious context ──
print("3. Per-church microsegmentation (church_arda)...")
c.execute("""
    SELECT ca.church_id, ca.evangelical_pct, ca.catholic_pct, ca.adherence_rate,
           ch.county_fips_5
    FROM church_arda ca
    JOIN churches ch ON ca.church_id = ch.id
    WHERE ch.movement_id=? AND ch.country='US' AND ch.county_fips_5 IS NOT NULL
""", (sbc_id,))
church_arda_rows = c.fetchall()
print(f"   {len(church_arda_rows):,} SBC churches have church_arda context")

# Build county-level microsegment aggregations
# For each county: avg evangelical %, avg catholic %, and count of churches with ARDA context
county_micro = defaultdict(lambda: {'n_arda_linked': 0, 'sum_evan_pct': 0.0, 'sum_cath_pct': 0.0, 'sum_adh_rate': 0.0})
for r in church_arda_rows:
    fips = r['county_fips_5']
    if fips:
        cm = county_micro[fips]
        cm['n_arda_linked'] += 1
        try:
            cm['sum_evan_pct'] += float(r['evangelical_pct'] or 0)
        except (ValueError, TypeError):
            pass
        try:
            cm['sum_cath_pct'] += float(r['catholic_pct'] or 0)
        except (ValueError, TypeError):
            pass
        try:
            cm['sum_adh_rate'] += float(r['adherence_rate'] or 0)
        except (ValueError, TypeError):
            pass

# Average the microsegment data
county_micro_avg = {}
for fips, cm in county_micro.items():
    n = cm['n_arda_linked']
    county_micro_avg[fips] = {
        'n_arda_linked': n,
        'avg_evangelical_pct': round(cm['sum_evan_pct'] / n, 1) if n else None,
        'avg_catholic_pct': round(cm['sum_cath_pct'] / n, 1) if n else None,
        'avg_adherence_rate': round(cm['sum_adh_rate'] / n, 1) if n else None,
    }

# ── 4. Merge: churches per 300 adherents ──
print("4. Computing churches per 300 adherents...")
ADHERENT_BASE = 300  # churches per 300 adherents

# Build FIPS → county name + state lookup from churches table
print("   Building county name lookup...")
c.execute("""
    SELECT county_fips_5, state, COUNT(*) as n
    FROM churches 
    WHERE country='US' AND county_fips_5 IS NOT NULL
    GROUP BY county_fips_5
""")
fips_to_state = {r['county_fips_5']: r['state'] for r in c.fetchall()}

county_data = []
for fips, arda in arda_sbc.items():
    ch = church_by_county.get(fips, 0)
    adh = arda['adherents']
    acong = arda['congregations']
    # GRID churches per 300 adherents
    p300 = round((ch / adh) * ADHERENT_BASE, 2) if adh > 0 else 0
    # ARDA congregations per 300 adherents (more complete count)
    arda_p300 = round((acong / adh) * ADHERENT_BASE, 2) if adh > 0 else 0
    # GRID completeness: what % of expected SBC churches do we have?
    grid_completeness = round((ch / acong) * 100, 1) if acong > 0 else None
    
    micro = county_micro_avg.get(fips, {})
    state = fips_to_state.get(fips, '')
    
    county_data.append({
        'fips': fips,
        'state': state,
        'churches': ch,
        'adherents': adh,
        'arda_congregations': acong,
        'per_300': p300,
        'arda_per_300': arda_p300,
        'grid_completeness': grid_completeness,
        'evangelical_pct': micro.get('avg_evangelical_pct'),
        'catholic_pct': micro.get('avg_catholic_pct'),
        'adherence_rate': micro.get('avg_adherence_rate'),
        'n_arda_linked': micro.get('n_arda_linked', 0),
    })

per_300_vals = [d['per_300'] for d in county_data if d['per_300'] > 0]
arda_per_300_vals = [d['arda_per_300'] for d in county_data if d['arda_per_300'] > 0]
nat_ratio = (total_churches / total_adherents) * ADHERENT_BASE
arda_nat_ratio = (total_arda_congs / total_adherents) * ADHERENT_BASE
q50 = statistics.median(per_300_vals) if per_300_vals else 0
q90 = np.percentile(per_300_vals, 90) if per_300_vals else 0

print(f"   GRID national ratio: {nat_ratio:.2f} churches/{ADHERENT_BASE} adherents")
print(f"   ARDA national ratio: {arda_nat_ratio:.2f} congregations/{ADHERENT_BASE} adherents")
print(f"   Median county (GRID): {q50:.2f} churches/{ADHERENT_BASE}")
print(f"   Range: {min(per_300_vals):.2f} – {max(per_300_vals):.2f}")

# ── 5. Build county name map from geojson ──
print("5. Loading county names from geojson...")
import requests, io
GEOJSON_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
geojson_cache = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'us_counties.geojson')

if not os.path.exists(geojson_cache):
    print("   Downloading geojson (first time, caching)...")
    resp = requests.get(GEOJSON_URL, timeout=30)
    resp.raise_for_status()
    with open(geojson_cache, 'wb') as f:
        f.write(resp.content)
    gj = resp.json()
else:
    with open(geojson_cache, 'r', encoding='utf-8') as f:
        gj = json.load(f)

# Extract FIPS → county name
fips_to_name = {}
state_fips_map = {
    '01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE',
    '11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA',
    '20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN',
    '28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM',
    '36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI',
    '45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA',
    '54':'WV','55':'WI','56':'WY','60':'AS','66':'GU','69':'MP','72':'PR','78':'VI',
}

for feature in gj['features']:
    props = feature['properties']
    fid = str(feature.get('id', ''))
    name = props.get('NAME', '')
    state_fips = props.get('STATE', '')
    if fid and name:
        state_abbr = state_fips_map.get(state_fips, '')
        label = f"{name}, {state_abbr}" if state_abbr else name
        fips_to_name[fid] = label

print(f"   Loaded {len(fips_to_name):,} county names from geojson")

# ── 6. Build map ──
print("6. Building choropleth...")
df = pd.DataFrame(county_data)

# Cap the color range using ARDA-based metric (more complete)
arda_q90 = np.percentile(arda_per_300_vals, 90) if arda_per_300_vals else 0
vmax = min(arda_q90 * 1.5, 10)

hover_text = []
for _, d in df.iterrows():
    p300_str = f"{d['per_300']:.2f}"
    arda_str = f"{d['arda_per_300']:.2f}"
    ratio_to_nat = d['arda_per_300'] / arda_nat_ratio if arda_nat_ratio > 0 else 1
    
    if ratio_to_nat < 0.3:
        label = "Adequately supplied"
    elif ratio_to_nat < 0.6:
        label = "Well supplied"
    elif ratio_to_nat < 1.5:
        label = "Near national avg"
    elif ratio_to_nat < 3.0:
        label = "Oversupply"
    else:
        label = "Severe oversupply"
    
    county_name = fips_to_name.get(d['fips'], f"FIPS {d['fips']}")
    state = d.get('state', '')
    location = county_name if county_name else f"FIPS {d['fips']}, {state}" if state else f"FIPS {d['fips']}"
    
    completeness = ""
    gc = d['grid_completeness']
    if gc is not None and not (isinstance(gc, float) and np.isnan(gc)):
        completeness = f"<br>GRID completeness: {gc}% of expected congregations"
    
    micro_str = ""
    evan = d['evangelical_pct']
    cath = d['catholic_pct']
    adhr = d['adherence_rate']
    if evan is not None and not (isinstance(evan, float) and np.isnan(evan)):
        micro_str = (f"<br>Area evangelical: {evan}% | "
                     f"Catholic: {cath if cath is not None and not (isinstance(cath, float) and np.isnan(cath)) else '?'}% | "
                     f"Religious adherence: {adhr if adhr is not None and not (isinstance(adhr, float) and np.isnan(adhr)) else '?'}%")
    
    hover_text.append(
        f"<b>{location}</b><br>"
        f"<b>{label}</b><br>"
        f"ARDA congregations: {d['arda_congregations']:,}<br>"
        f"GRID churches: {d['churches']:,}<br>"
        f"ARDA SBC adherents: {d['adherents']:,}<br>"
        f"ARDA per 300: <b>{arda_str}</b> | GRID per 300: {p300_str}{completeness}"
        f"{micro_str}"
    )

fig = px.choropleth(
    df,
    geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
    locations='fips',
    color='arda_per_300',
    color_continuous_scale=[
        [0.0, '#1b7837'],
        [0.20, '#5aae61'],
        [0.40, '#a6dba0'],
        [0.50, '#f7f7f7'],
        [0.65, '#f4a582'],
        [0.80, '#ca0020'],
        [1.0, '#7f0000'],
    ],
    range_color=[0, vmax],
    labels={'arda_per_300': f'ARDA congregations per {ADHERENT_BASE} Adherents'},
    scope='usa',
    title=(f'<b>Southern Baptist Convention</b>: Church Infrastructure vs. Adherent Population<br>'
           f'<sup>'
           f'<span style="color:#1b7837">■ Green = Adequately supplied</span> &nbsp; '
           f'<span style="color:#f7f7f7">■ White = Balanced (~{arda_nat_ratio:.1f}/{ADHERENT_BASE})</span> &nbsp; '
           f'<span style="color:#7f0000">■ Red = Oversupply</span>'
           f'<br>Using ARDA congregation counts ({total_arda_congs:,}) — more complete than GRID tags ({total_churches:,}) | '
           f'{total_adherents:,} adherents · {len(county_data):,} counties</sup>'),
)
fig.update_traces(
    hovertemplate='%{customdata}<extra></extra>',
    customdata=hover_text,
    marker_line_width=0.3, marker_line_color='#ffffff',
)
fig.update_layout(
    margin=dict(l=10, r=10, t=80, b=10),
    coloraxis_colorbar=dict(
        title=f"Churches<br>per {ADHERENT_BASE}<br>Adherents",
        thickness=15, len=0.6,
    ),
    font=dict(family='Segoe UI, sans-serif'),
)

fig.write_html(OUTPUT_HTML)
print(f"   ✅ {OUTPUT_HTML}")

# ── 7. CSV ──
print("7. Exporting CSV...")
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=[
        'fips','county_name','state','churches','adherents','arda_congregations',
        'per_300','arda_per_300','grid_completeness',
        'evangelical_pct','catholic_pct','adherence_rate','n_arda_linked'
    ])
    w.writeheader()
    for d in sorted(county_data, key=lambda x: -x['per_300']):
        d['county_name'] = fips_to_name.get(d['fips'], '')
        w.writerow(d)
print(f"   ✅ {OUTPUT_CSV}")

# ── 8. Microsegment breakdown ──
print(f"\n{'='*65}")
print(f"SOUTHERN BAPTIST CONVENTION — Microsegmented Analysis")
print(f"{'='*65}")
print(f"  GRID SBC churches:                          {total_churches:>8,}")
print(f"  ARDA SBC congregations:                     {total_arda_congs:>8,}")
print(f"  ARDA SBC adherents (arda_counts):           {total_adherents:>8,}")
print(f"  National GRID ratio:                         {nat_ratio:>7.2f} churches/{ADHERENT_BASE} adh")
print(f"  National ARDA ratio:                         {arda_nat_ratio:>7.2f} congregations/{ADHERENT_BASE} adh")
print(f"  Median county (ARDA):                        {q50:>7.2f}")
print(f"  90th percentile (ARDA):                      {arda_q90:>7.2f}")
print(f"  Counties with SBC churches:                 {sum(1 for d in county_data if d['churches']>0):>8,}")
print(f"  Counties with zero churches:                {sum(1 for d in county_data if d['churches']==0):>8,}")
print(f"  Counties with church_arda microsegment:     {sum(1 for d in county_data if d['n_arda_linked']>0):>8,}")
print(f"{'='*65}")

# ── Top/bottom counties ──
sorted_data = sorted(county_data, key=lambda x: -x['per_300'])
print(f"\nTop 5 oversupplied counties (most churches/{ADHERENT_BASE} adherents):")
for d in sorted_data[:5]:
    print(f"  FIPS {d['fips']}: {d['churches']} churches / {d['adherents']:,} adh = {d['per_300']:.1f}/{ADHERENT_BASE} | evan {d['evangelical_pct']}%")
print(f"\nBottom 5 undersupplied counties:")
for d in sorted_data[-5:]:
    print(f"  FIPS {d['fips']}: {d['churches']} churches / {d['adherents']:,} adh = {d['per_300']:.1f}/{ADHERENT_BASE} | evan {d['evangelical_pct']}%")

print(f"\nDone! Open outputs/sbc_adherence_heatmap.html")
conn.close()
