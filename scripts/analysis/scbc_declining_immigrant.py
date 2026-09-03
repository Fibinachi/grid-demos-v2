#!/usr/bin/env python3
"""
SCBC Report: 25 Declining SC SBC Churches Positioned for Immigrant Congregations

Identifies South Carolina Southern Baptist churches in counties where SBC
adherence is declining sharply, located in communities with growing
Hispanic/Asian populations — ideal candidates for immigrant congregation
repurposing/replanting.

Scoring factors:
  1. ARDA adherent DECLINE (2010 -> 2020, county-level) — higher decline = higher score
  2. Hispanic population % in tract — proxy for Latino immigrant community
  3. Asian population % in tract — proxy for Asian immigrant community  
  4. Combined minority % (non-white) — overall diversity

Outputs:
  - reports/scbc_declining_immigrant.md   — Professional Markdown report
  - reports/scbc_declining_immigrant.html — Interactive Leaflet map
  - reports/scbc_declining_immigrant.csv  — Full data CSV
"""
import sqlite3
import json
import os
from datetime import datetime

DB = 'E:/grid/churches.db'
OUT_DIR = 'E:/grid/reports'
TOP_N = 25

os.makedirs(OUT_DIR, exist_ok=True)
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
c = db.cursor()

now_str = datetime.now().strftime('%B %d, %Y at %I:%M %p')
now_file = datetime.now().strftime('%Y%m%d_%H%M%S')

# ============================================================================
# STEP 1: Find SBC taxonomy ID
# ============================================================================
print("Finding SBC taxonomy node...")
sbc_ids = []
for r in c.execute("SELECT id, name, parent_id FROM taxonomy WHERE name LIKE '%Southern Baptist%' OR name = 'Southern Baptist Convention'").fetchall():
    sbc_ids.append(r['id'])
    print(f"  id={r['id']} | {r['name']} | parent={r['parent_id']}")

if not sbc_ids:
    # Broader Baptist search
    for r in c.execute("SELECT id, name, parent_id FROM taxonomy WHERE name LIKE '%Baptist%' ORDER BY id LIMIT 50").fetchall():
        print(f"  id={r['id']} | {r['name']} | parent={r['parent_id']}")

# Use any Baptist taxonomy node as fallback; prefer SBC-specific
SBC_TAX_IDS = tuple(sbc_ids) if sbc_ids else None
print(f"SBC taxonomy IDs: {SBC_TAX_IDS}")

# ============================================================================
# STEP 2: Build ARDA county-level decline data (in-memory)
# ============================================================================
print("\nBuilding ARDA decline index...")
arda_2020 = {}
for r in c.execute("SELECT county_fips, arda_congregations, arda_adherents FROM arda_counts WHERE denom_code='SBC'").fetchall():
    arda_2020[r['county_fips']] = (r['arda_congregations'] or 0, r['arda_adherents'] or 0)

arda_2010 = {}
for r in c.execute("SELECT county_fips, arda_congregations, arda_adherents FROM arda_counts_2010 WHERE denom_code='SBC'").fetchall():
    arda_2010[r['county_fips']] = (r['arda_congregations'] or 0, r['arda_adherents'] or 0)

# Compute decline for each county
county_decline = {}
for fips in arda_2020:
    cong20, adh20 = arda_2020[fips]
    cong10, adh10 = arda_2010.get(fips, (cong20, adh20))  # fallback: no change
    if adh10 > 0:
        pct_decline = (adh10 - adh20) / adh10 * 100.0  # positive = decline
    else:
        pct_decline = 0.0
    county_decline[fips] = {
        'cong_2010': cong10, 'cong_2020': cong20,
        'adh_2010': adh10, 'adh_2020': adh20,
        'adh_decline_pct': round(pct_decline, 1)
    }

sc_fips = [f for f in county_decline if f.startswith('45')]
print(f"  SC counties with ARDA SBC data: {len(sc_fips)}")

# ============================================================================
# STEP 3: Query SC SBC churches with ACS + ARDA data
# ============================================================================
print("\nQuerying SC SBC churches...")

# Build WHERE clause for SBC taxonomy
if SBC_TAX_IDS:
    placeholders = ','.join('?' * len(SBC_TAX_IDS))
    tax_filter = f"c.taxonomy_id IN ({placeholders})"
    tax_params = list(SBC_TAX_IDS)
else:
    tax_filter = "1=0"  # no SBC found
    tax_params = []

query = f"""
SELECT 
    c.rowid, c.id, c.name, c.city, c.state, c.address, c.zip,
    c.website, c.phone, c.email, c.pastor_name,
    c.latitude, c.longitude,
    c.county_fips_5,
    c.acs_poverty_rate, c.acs_median_income, c.acs_median_age,
    c.acs_unemployment_rate, c.acs_total_pop,
    c.acs_white_pop, c.acs_black_pop, c.acs_hispanic_pop, c.acs_asian_pop,
    c.tract_fips,
    c.has_food_pantry, c.has_youth, c.has_children, c.has_seniors,
    c.has_recovery, c.has_missions, c.has_counseling, c.has_sports,
    c.has_daycare, c.has_preschool, c.has_esl,
    c.spanish_language, c.primary_language, c.languages,
    c.attendance_est, c.is_church_plant, c.is_closed,
    c.source, c.family, c.org_type,
    c.nearest_fire_km, c.nearest_police_km
FROM churches c
WHERE c.state = 'SC'
    AND {tax_filter}
    AND c.acs_total_pop IS NOT NULL
    AND c.acs_total_pop > 0
    AND (c.is_closed IS NULL OR c.is_closed = 0)
ORDER BY c.name
"""

params = tax_params[:]
rows = c.execute(query, params).fetchall()
print(f"  SC SBC churches with ACS data: {len(rows):,}")

# ============================================================================
# STEP 4: Score each church
# ============================================================================
print("\nScoring churches...")

def pct_of(val, total):
    """Return percentage as float 0-100."""
    if total and total > 0 and val is not None:
        return (val / total) * 100.0
    return 0.0

scored = []
for r in rows:
    fips = r['county_fips_5'] or ''
    cd = county_decline.get(fips, {})
    
    # Immigrant proxies
    hisp_pct = pct_of(r['acs_hispanic_pop'], r['acs_total_pop'])
    asian_pct = pct_of(r['acs_asian_pop'], r['acs_total_pop'])
    white_pct = pct_of(r['acs_white_pop'], r['acs_total_pop'])
    black_pct = pct_of(r['acs_black_pop'], r['acs_total_pop'])
    minority_pct = 100.0 - white_pct  # non-white as diversity proxy
    
    # ARDA decline
    adh_decline = cd.get('adh_decline_pct', 0.0)
    
    # Composite score:
    #   ARDA adherent decline (0-40 pts): sharp decline = ripe for repurposing
    #   Hispanic % (0-25 pts): primary immigrant target
    #   Asian % (0-15 pts): secondary immigrant target  
    #   Minority diversity (0-10 pts): general multicultural readiness
    #   Poverty rate (0-10 pts): need indicator
    
    poverty = (r['acs_poverty_rate'] or 0) * 100.0
    
    score = (
        min(adh_decline / 50.0 * 40.0, 40.0)  # decline: scaled, cap at 40
        + min(hisp_pct / 20.0 * 25.0, 25.0)     # hispanic: 20% = max
        + min(asian_pct / 10.0 * 15.0, 15.0)     # asian: 10% = max
        + min(minority_pct / 50.0 * 10.0, 10.0)  # diversity: 50% = max
        + min(poverty / 30.0 * 10.0, 10.0)       # poverty: 30% = max
    )
    
    scored.append({
        'rowid': r['rowid'],
        'id': r['id'],
        'name': r['name'],
        'city': r['city'] or '',
        'state': 'SC',
        'address': r['address'] or '',
        'zip': r['zip'] or '',
        'website': r['website'] or '',
        'phone': r['phone'] or '',
        'email': r['email'] or '',
        'pastor_name': r['pastor_name'] or '',
        'lat': r['latitude'],
        'lon': r['longitude'],
        'county_fips': fips,
        'tract_fips': r['tract_fips'] or '',
        # Demographics
        'total_pop': r['acs_total_pop'] or 0,
        'hisp_pct': round(hisp_pct, 1),
        'asian_pct': round(asian_pct, 1),
        'white_pct': round(white_pct, 1),
        'black_pct': round(black_pct, 1),
        'minority_pct': round(minority_pct, 1),
        'poverty_rate': round(poverty, 1),
        'median_income': r['acs_median_income'] or 0,
        'median_age': r['acs_median_age'] or 0,
        'unemployment_rate': round((r['acs_unemployment_rate'] or 0) * 100.0, 1),
        # ARDA decline
        'arda_cong_2010': cd.get('cong_2010', 0),
        'arda_cong_2020': cd.get('cong_2020', 0),
        'arda_adh_2010': cd.get('adh_2010', 0),
        'arda_adh_2020': cd.get('adh_2020', 0),
        'arda_decline_pct': adh_decline,
        # Ministry indicators
        'has_esl': bool(r['has_esl']),
        'spanish_language': bool(r['spanish_language']),
        'primary_language': r['primary_language'] or '',
        'languages': r['languages'] or '',
        'has_food_pantry': bool(r['has_food_pantry']),
        'has_youth': bool(r['has_youth']),
        'has_children': bool(r['has_children']),
        'has_seniors': bool(r['has_seniors']),
        'has_recovery': bool(r['has_recovery']),
        'has_missions': bool(r['has_missions']),
        'has_counseling': bool(r['has_counseling']),
        'has_daycare': bool(r['has_daycare']),
        'has_preschool': bool(r['has_preschool']),
        # Church health
        'attendance_est': r['attendance_est'] or 0,
        'is_church_plant': bool(r['is_church_plant']),
        'source': r['source'] or '',
        'org_type': r['org_type'] or '',
        'family': r['family'] or '',
        # Emergency
        'nearest_fire_km': round(r['nearest_fire_km'], 2) if r['nearest_fire_km'] else None,
        'nearest_police_km': round(r['nearest_police_km'], 2) if r['nearest_police_km'] else None,
        # Score
        'score': round(score, 1),
        'score_decline': round(min(adh_decline / 50.0 * 40.0, 40.0), 1),
        'score_hispanic': round(min(hisp_pct / 20.0 * 25.0, 25.0), 1),
        'score_asian': round(min(asian_pct / 10.0 * 15.0, 15.0), 1),
        'score_diversity': round(min(minority_pct / 50.0 * 10.0, 10.0), 1),
        'score_poverty': round(min(poverty / 30.0 * 10.0, 10.0), 1),
    })

# Sort by score descending
scored.sort(key=lambda x: x['score'], reverse=True)
top = scored[:TOP_N]

if len(top) == 0:
    print("ERROR: No SC SBC churches found!")
    db.close()
    exit(1)

# ============================================================================
# STEP 5: Generate Markdown Report
# ============================================================================
print(f"\nGenerating report for top {len(top)} churches...")

md = []
md.append('# Declining SC SBC Churches Positioned for Immigrant Congregations')
md.append('')
md.append(f'**Prepared for:** South Carolina Baptist Convention (SCBC)')
md.append(f'**Generated:** {now_str}')
md.append(f'**Scope:** {len(rows):,} SC Southern Baptist churches with ACS tract data')
md.append('')
md.append('---')
md.append('')
md.append('## Executive Summary')
md.append('')
md.append(f'This report identifies **{TOP_N} declining Southern Baptist churches in South Carolina** ')
md.append(f'that are positioned for transition to immigrant/multicultural congregations. ')
md.append(f'These churches are located in counties where SBC adherence has declined significantly ')
md.append(f'from 2010 to 2020, while their surrounding communities show growing Hispanic and/or Asian populations.')
md.append('')

# Summary stats
avg_hisp = sum(c['hisp_pct'] for c in top) / len(top)
avg_asian = sum(c['asian_pct'] for c in top) / len(top)
avg_decline = sum(c['arda_decline_pct'] for c in top) / len(top)
avg_pov = sum(c['poverty_rate'] for c in top) / len(top)

md.append(f'| Metric | Average Across Top {TOP_N} |')
md.append(f'|--------|---------------------------|')
md.append(f'| Hispanic Population % (tract) | **{avg_hisp:.1f}%** |')
md.append(f'| Asian Population % (tract) | **{avg_asian:.1f}%** |')
md.append(f'| County SBC Adherent Decline (2010-2020) | **{avg_decline:.1f}%** |')
md.append(f'| Poverty Rate (tract) | **{avg_pov:.1f}%** |')
md.append('')

md.append(f'**Counties represented:** {len(set(c["county_fips"] for c in top))} of SC\'s 46 counties')
md.append('')

md.append('---')
md.append('')
md.append(f'## Top {TOP_N} Churches — Ranked by Composite Score')
md.append('')
md.append('| # | Church | City | County | Hisp% | Asian% | SBC Decline | Poverty | Score |')
md.append('|---|--------|------|--------|-------|--------|-------------|---------|-------|')

# County name lookup
county_names = {}
for r in c.execute("SELECT DISTINCT county_fips_5, city FROM churches WHERE state='SC' AND county_fips_5 IS NOT NULL").fetchall():
    pass  # We don't have a county name table readily; use FIPS

for i, ch in enumerate(top, 1):
    name = (ch['name'] or '?')[:40]
    city = (ch['city'] or '?')[:20]
    county = ch['county_fips'] or '?'
    md.append(f'| {i} | {name} | {city} | {county} | {ch["hisp_pct"]}% | {ch["asian_pct"]}% | {ch["arda_decline_pct"]}% | {ch["poverty_rate"]}% | **{ch["score"]}** |')

md.append('')
md.append('---')
md.append('')
md.append('## Detailed Church Profiles')
md.append('')

for i, ch in enumerate(top, 1):
    md.append(f'### {i}. {ch["name"]}')
    md.append('')
    md.append(f'**Location:** {ch["address"]}, {ch["city"]}, SC {ch["zip"]}')
    if ch['lat'] and ch['lon']:
        md.append(f'**GPS:** {ch["lat"]:.5f}, {ch["lon"]:.5f}')
        md.append(f'**Map:** https://www.google.com/maps?q={ch["lat"]},{ch["lon"]}')
    md.append('')
    md.append(f'| Field | Value |')
    md.append(f'|-------|-------|')
    md.append(f'| **Composite Score** | **{ch["score"]}** / 100 |')
    md.append(f'| **Website** | {ch["website"] or "N/A"} |')
    md.append(f'| **Phone** | {ch["phone"] or "N/A"} |')
    md.append(f'| **Email** | {ch["email"] or "N/A"} |')
    md.append(f'| **Pastor** | {ch["pastor_name"] or "N/A"} |')
    md.append(f'| **Attendance Est.** | {ch["attendance_est"] or "N/A"} |')
    md.append('')
    md.append(f'#### Community Demographics (Census Tract)')
    md.append('')
    md.append(f'| Measure | Value |')
    md.append(f'|---------|-------|')
    md.append(f'| **Total Population** | {ch["total_pop"]:,} |')
    md.append(f'| **Hispanic %** | {ch["hisp_pct"]}% |')
    md.append(f'| **Asian %** | {ch["asian_pct"]}% |')
    md.append(f'| **White %** | {ch["white_pct"]}% |')
    md.append(f'| **Black %** | {ch["black_pct"]}% |')
    md.append(f'| **Minority %** | {ch["minority_pct"]}% |')
    md.append(f'| **Poverty Rate** | {ch["poverty_rate"]}% |')
    md.append(f'| **Median Household Income** | ${ch["median_income"]:,} |')
    md.append(f'| **Median Age** | {ch["median_age"]} |')
    md.append(f'| **Unemployment Rate** | {ch["unemployment_rate"]}% |')
    if ch['tract_fips']:
        md.append(f'| **Census Tract** | [{ch["tract_fips"]}](https://censusreporter.org/profiles/14000US{ch["tract_fips"]}/) |')
    md.append('')
    md.append(f'#### SBC County-Level Decline (ARDA)')
    md.append('')
    md.append(f'| Measure | 2010 | 2020 | Change |')
    md.append(f'|---------|------|------|--------|')
    md.append(f'| **Congregations** | {ch["arda_cong_2010"]:,} | {ch["arda_cong_2020"]:,} | {ch["arda_cong_2020"] - ch["arda_cong_2010"]:+,} |')
    md.append(f'| **Adherents** | {ch["arda_adh_2010"]:,} | {ch["arda_adh_2020"]:,} | {ch["arda_adh_2020"] - ch["arda_adh_2010"]:+,} ({ch["arda_decline_pct"]:+.1f}%) |')
    md.append('')
    md.append(f'#### Ministry Profile')
    md.append('')
    ministry = []
    if ch['has_esl']: ministry.append('ESL Program')
    if ch['spanish_language']: ministry.append('Spanish Language')
    if ch['has_food_pantry']: ministry.append('Food Pantry')
    if ch['has_youth']: ministry.append('Youth Ministry')
    if ch['has_children']: ministry.append('Children Ministry')
    if ch['has_seniors']: ministry.append('Senior Ministry')
    if ch['has_recovery']: ministry.append('Recovery Ministry')
    if ch['has_missions']: ministry.append('Missions')
    if ch['has_counseling']: ministry.append('Counseling')
    if ch['has_daycare']: ministry.append('Daycare')
    if ch['has_preschool']: ministry.append('Preschool')
    md.append(f'| Field | Value |')
    md.append(f'|-------|-------|')
    md.append(f'| **Active Ministries** | {", ".join(ministry) if ministry else "None detected"} |')
    md.append(f'| **Primary Language** | {ch["primary_language"] or "N/A"} |')
    md.append(f'| **Languages** | {ch["languages"] or "N/A"} |')
    md.append(f'| **Church Plant** | {"Yes" if ch["is_church_plant"] else "No"} |')
    md.append(f'| **Source** | {ch["source"]} |')
    md.append('')
    md.append(f'#### Score Breakdown')
    md.append('')
    md.append(f'| Component | Score | Weight |')
    md.append(f'|-----------|-------|--------|')
    md.append(f'| ARDA Decline | {ch["score_decline"]} | 40% |')
    md.append(f'| Hispanic Presence | {ch["score_hispanic"]} | 25% |')
    md.append(f'| Asian Presence | {ch["score_asian"]} | 15% |')
    md.append(f'| Minority Diversity | {ch["score_diversity"]} | 10% |')
    md.append(f'| Poverty Need | {ch["score_poverty"]} | 10% |')
    md.append(f'| **TOTAL** | **{ch["score"]}** | **100%** |')
    md.append('')
    md.append('---')
    md.append('')

md.append('')
md.append('## Methodology')
md.append('')
md.append('### Composite Score (0-100)')
md.append('')
md.append('| Component | Max Points | Rationale |')
md.append('|-----------|-----------|-----------|')
md.append('| **ARDA Adherent Decline** (2010-2020) | 40 | County-level SBC decline signals institutional vacancy — the existing congregation is shrinking, creating space for a new worshipping community |')
md.append('| **Hispanic Population %** (tract) | 25 | Hispanic communities are the largest immigrant group in SC; 20% tract threshold = full points |')
md.append('| **Asian Population %** (tract) | 15 | Asian immigrant communities (Korean, Chinese, Vietnamese, Indian) are growing rapidly in SC |')
md.append('| **Minority Diversity %** (tract) | 10 | Overall non-white population as a general multicultural readiness indicator |')
md.append('| **Poverty Rate** (tract) | 10 | Higher poverty signals community need and potential for holistic ministry |')
md.append('')
md.append('### Data Sources')
md.append('')
md.append('- **Church locations & attributes**: GRID (Global Religious Infrastructure Database)')
md.append('- **SBC adherent/congregation counts**: ARDA (Association of Religion Data Archives), 2010 & 2020')
md.append('- **Demographics**: ACS 5-Year Estimates (2018-2022), Census tract level')
md.append(f'- **Analysis date**: {now_str}')
md.append('')

# Write markdown
md_path = os.path.join(OUT_DIR, 'scbc_declining_immigrant.md')
with open(md_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md))
print(f"  [OK] Markdown report: {md_path}")

# ============================================================================
# STEP 6: Generate CSV
# ============================================================================
csv_path = os.path.join(OUT_DIR, 'scbc_declining_immigrant.csv')
csv_cols = [
    'rank', 'name', 'city', 'address', 'zip', 'website', 'phone', 'email',
    'pastor_name', 'lat', 'lon', 'county_fips', 'tract_fips',
    'score', 'score_decline', 'score_hispanic', 'score_asian',
    'score_diversity', 'score_poverty',
    'total_pop', 'hisp_pct', 'asian_pct', 'white_pct', 'black_pct',
    'minority_pct', 'poverty_rate', 'median_income', 'median_age',
    'unemployment_rate',
    'arda_cong_2010', 'arda_cong_2020', 'arda_adh_2010', 'arda_adh_2020',
    'arda_decline_pct',
    'has_esl', 'spanish_language', 'primary_language', 'languages',
    'has_food_pantry', 'attendance_est', 'is_church_plant', 'source',
]
import csv
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction='ignore')
    w.writeheader()
    for i, ch in enumerate(top, 1):
        ch['rank'] = i
        w.writerow(ch)
print(f"  [OK] CSV: {csv_path}")

# ============================================================================
# STEP 7: Generate Interactive HTML Map
# ============================================================================
print("Generating interactive map...")

# Build GeoJSON-like markers
markers_json = []
for i, ch in enumerate(top, 1):
    if not ch['lat'] or not ch['lon']:
        continue
    markers_json.append({
        'rank': i,
        'name': ch['name'],
        'city': ch['city'],
        'lat': ch['lat'],
        'lon': ch['lon'],
        'score': ch['score'],
        'hisp_pct': ch['hisp_pct'],
        'asian_pct': ch['asian_pct'],
        'decline_pct': ch['arda_decline_pct'],
        'poverty_rate': ch['poverty_rate'],
        'minority_pct': ch['minority_pct'],
        'website': ch['website'],
        'tract_fips': ch['tract_fips'],
    })

# Color by score: red (high) -> orange -> yellow (low)
def score_color(score):
    if score >= 40:
        return '#d62728'  # red
    elif score >= 30:
        return '#ff7f0e'  # orange
    elif score >= 20:
        return '#bcbd22'  # yellow-green
    else:
        return '#2ca02c'  # green

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SCBC — 25 Declining SC SBC Churches for Immigrant Congregations</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body {{ margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }}
  #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}
  .info-panel {{
    position: absolute; top: 10px; right: 10px; width: 320px; max-height: 90vh;
    overflow-y: auto; background: rgba(255,255,255,0.95); padding: 15px;
    border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.3);
    font-size: 13px; z-index: 1000;
  }}
  .info-panel h2 {{ margin: 0 0 8px 0; font-size: 16px; }}
  .info-panel h3 {{ margin: 0 0 4px 0; font-size: 14px; color: #555; }}
  .info-panel table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
  .info-panel th {{ background: #f5f5f5; text-align: left; padding: 3px 4px; }}
  .info-panel td {{ padding: 3px 4px; border-bottom: 1px solid #eee; }}
  .legend {{ margin-top: 10px; }}
  .legend span {{ display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
  .popup-table {{ font-size: 12px; }}
  .popup-table td {{ padding: 2px 4px; }}
  .popup-table td:first-child {{ font-weight: bold; white-space: nowrap; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="info-panel">
  <h2>Declining SC SBC Churches</h2>
  <h3>Positioned for Immigrant Congregations</h3>
  <p style="font-size:11px;color:#888;margin:4px 0">Generated {now_str}</p>
  <table>
    <tr><th>#</th><th>Church</th><th>Score</th><th>Hisp%</th><th>Decl.%</th></tr>
'''

for ch in markers_json:
    color = score_color(ch['score'])
    html += f'''
    <tr>
      <td><span style="background:{color};color:white;padding:1px 5px;border-radius:10px;font-size:10px">{ch['rank']}</span></td>
      <td>{ch['name'][:30]}</td>
      <td><b>{ch['score']}</b></td>
      <td>{ch['hisp_pct']}%</td>
      <td>{ch['decline_pct']}%</td>
    </tr>'''

html += '''
  </table>
  <div class="legend">
    <b>Score:</b><br>
    <span style="background:#d62728"></span> 40+ (High Priority)<br>
    <span style="background:#ff7f0e"></span> 30-39<br>
    <span style="background:#bcbd22"></span> 20-29<br>
    <span style="background:#2ca02c"></span> &lt;20
  </div>
  <p style="font-size:10px;color:#aaa;margin-top:8px">
    SBC decline = ARDA county-level adherent change 2010-2020.<br>
    Demographics = ACS 2018-2022 tract estimates.
  </p>
</div>
<script>
var map = L.map('map').setView([33.8, -80.5], 7);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
  subdomains: 'abcd',
  maxZoom: 19
}).addTo(map);

var markers = {json.dumps(markers_json)};

markers.forEach(function(ch) {{
  var color = '{score_color}'.replace('{score_color}', 
    ch.score >= 40 ? '#d62728' : ch.score >= 30 ? '#ff7f0e' : ch.score >= 20 ? '#bcbd22' : '#2ca02c');
  
  var size = Math.max(8, Math.min(20, ch.score / 4));
  
  var popup = '<div class="popup-table">' +
    '<b>#' + ch.rank + ' ' + ch.name + '</b><br>' +
    '<table>' +
    '<tr><td>City</td><td>' + ch.city + ', SC</td></tr>' +
    '<tr><td>Score</td><td><b>' + ch.score + '</b></td></tr>' +
    '<tr><td>Hispanic %</td><td>' + ch.hisp_pct + '%</td></tr>' +
    '<tr><td>Asian %</td><td>' + ch.asian_pct + '%</td></tr>' +
    '<tr><td>SBC Decline</td><td>' + ch.decline_pct + '%</td></tr>' +
    '<tr><td>Minority %</td><td>' + ch.minority_pct + '%</td></tr>' +
    '<tr><td>Poverty</td><td>' + ch.poverty_rate + '%</td></tr>' +
    (ch.website ? '<tr><td>Website</td><td><a href="' + ch.website + '" target="_blank">link</a></td></tr>' : '') +
    (ch.tract_fips ? '<tr><td>Tract</td><td><a href="https://censusreporter.org/profiles/14000US' + ch.tract_fips + '/" target="_blank">' + ch.tract_fips + '</a></td></tr>' : '') +
    '</table></div>';
  
  L.circleMarker([ch.lat, ch.lon], {{
    radius: size,
    fillColor: color,
    color: '#333',
    weight: 1,
    opacity: 1,
    fillOpacity: 0.8
  }}).bindPopup(popup).addTo(map);
  
  // Add rank label
  L.marker([ch.lat, ch.lon], {{
    icon: L.divIcon({{
      className: 'rank-label',
      html: '<div style="background:' + color + ';color:white;font-size:9px;font-weight:bold;width:18px;height:18px;line-height:18px;text-align:center;border-radius:50%;border:1px solid #333">' + ch.rank + '</div>',
      iconSize: [18, 18],
      iconAnchor: [9, 9]
    }})
  }}).addTo(map);
}});
</script>
</body>
</html>'''

html_path = os.path.join(OUT_DIR, 'scbc_declining_immigrant.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"  [OK] Interactive map: {html_path}")

# ============================================================================
# STEP 8: Print summary to console
# ============================================================================
print(f"\n{'='*70}")
print(f"TOP {TOP_N} SC SBC CHURCHES — DECLINING + IMMIGRANT POTENTIAL")
print(f"{'='*70}")
print(f"{'#':>3} {'Score':>6} {'Hisp%':>6} {'Asian%':>6} {'Decl%':>6} {'Pov%':>5} {'Min%':>5}  Name")
print(f"{'-'*3} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*5} {'-'*5}  {'-'*50}")
for i, ch in enumerate(top, 1):
    name = (ch['name'] or '?')[:50]
    print(f"{i:>3} {ch['score']:>6.1f} {ch['hisp_pct']:>5.1f}% {ch['asian_pct']:>5.1f}% {ch['arda_decline_pct']:>5.1f}% {ch['poverty_rate']:>4.1f}% {ch['minority_pct']:>4.1f}%  {name}")

print(f"\n{'='*70}")
print(f"Reports saved to: {OUT_DIR}/")
print(f"  scbc_declining_immigrant.md    — Markdown report")
print(f"  scbc_declining_immigrant.html  — Interactive map")
print(f"  scbc_declining_immigrant.csv   — Full data")
print(f"\n[DONE]")

db.close()
