#!/usr/bin/env python3
"""
Healthcare Access for Rural Congregations — Full Analysis
Generates data for the report notebook.
Outputs: JSON data files + summary stats for the report.
"""
import sqlite3
import json
import os

DB = 'e:/grid/churches.db'
OUT = 'outputs/healthcare_access'
os.makedirs(OUT, exist_ok=True)

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

def query(sql, params=None):
    return [dict(r) for r in db.execute(sql, params or [])]

# ============================================================
# 1. OVERALL SUMMARY
# ============================================================
print("=== 1. OVERALL SUMMARY ===")

total_churches = db.execute('SELECT COUNT(*) as n FROM churches').fetchone()['n']
total_us = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US'").fetchone()['n']
total_us_gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US' AND latitude IS NOT NULL AND latitude != 0").fetchone()['n']

has_hosp = db.execute('SELECT COUNT(*) as n FROM churches WHERE nearest_hospital_km IS NOT NULL').fetchone()['n']
has_clinic = db.execute('SELECT COUNT(*) as n FROM churches WHERE nearest_clinic_km IS NOT NULL').fetchone()['n']

hosp_stats = dict(db.execute('SELECT MIN(nearest_hospital_km) as min_h, AVG(nearest_hospital_km) as avg_h, MAX(nearest_hospital_km) as max_h FROM churches WHERE nearest_hospital_km IS NOT NULL').fetchone())
clinic_stats = dict(db.execute('SELECT MIN(nearest_clinic_km) as min_c, AVG(nearest_clinic_km) as avg_c, MAX(nearest_clinic_km) as max_c FROM churches WHERE nearest_clinic_km IS NOT NULL').fetchone())

summary = {
    'total_churches': total_churches,
    'total_us_churches': total_us,
    'total_us_with_gps': total_us_gps,
    'churches_with_hospital_distance': has_hosp,
    'churches_with_clinic_distance': has_clinic,
    'hospital_km': hosp_stats,
    'clinic_km': clinic_stats,
    'healthcare_source': 'OSM Overpass API — 7,541 hospitals + 23,352 clinics (US only)',
    'data_date': '2026-07-10',
}
print(json.dumps(summary, indent=2))

# ============================================================
# 2. RUCC BREAKDOWN
# ============================================================
print("\n=== 2. RUCC BREAKDOWN ===")

rucc_breakdown = query('''
    SELECT 
        CASE 
            WHEN rc.rucc_code = 1 THEN 'Metro — 1M+'
            WHEN rc.rucc_code = 2 THEN 'Metro — 250K-1M'
            WHEN rc.rucc_code = 3 THEN 'Metro — <250K'
            WHEN rc.rucc_code = 4 THEN 'Non-metro — 20K+, adj metro'
            WHEN rc.rucc_code = 5 THEN 'Non-metro — 20K+, not adj'
            WHEN rc.rucc_code = 6 THEN 'Non-metro — 5K-20K, adj metro'
            WHEN rc.rucc_code = 7 THEN 'Non-metro — 5K-20K, not adj'
            WHEN rc.rucc_code = 8 THEN 'Rural — <5K, adj metro'
            WHEN rc.rucc_code = 9 THEN 'Rural — <5K, not adj'
            ELSE 'Unknown'
        END as rucc_label,
        rc.rucc_code,
        COUNT(*) as churches,
        ROUND(AVG(c.nearest_hospital_km), 1) as avg_hospital_km,
        ROUND(AVG(c.nearest_clinic_km), 1) as avg_clinic_km,
        ROUND(AVG(c.nearest_fire_km), 1) as avg_fire_km,
        ROUND(AVG(c.nearest_police_km), 1) as avg_police_km,
        COUNT(CASE WHEN c.nearest_hospital_km > 15 THEN 1 END) as over_15km,
        COUNT(CASE WHEN c.nearest_hospital_km > 30 THEN 1 END) as over_30km,
        COUNT(CASE WHEN c.nearest_hospital_km > 50 THEN 1 END) as over_50km,
        COUNT(CASE WHEN c.nearest_hospital_km > 100 THEN 1 END) as over_100km
    FROM churches c
    JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.latitude != 0
      AND c.nearest_hospital_km IS NOT NULL
    GROUP BY rc.rucc_code
    ORDER BY rc.rucc_code
''')

for r in rucc_breakdown:
    r['pct_over_15km'] = round(r['over_15km'] / r['churches'] * 100, 1) if r['churches'] else 0
    r['pct_over_30km'] = round(r['over_30km'] / r['churches'] * 100, 1) if r['churches'] else 0
    print(f"  RUCC {r['rucc_code']}: {r['rucc_label']} — {r['churches']:,} churches, avg hospital={r['avg_hospital_km']}km, >30km={r['over_30km']:,} ({r['pct_over_30km']}%)")

with open(f'{OUT}/rucc_breakdown.json', 'w') as f:
    json.dump(rucc_breakdown, f, indent=2)

# ============================================================
# 3. RURAL AGGREGATED STATS
# ============================================================
print("\n=== 3. RURAL (RUCC 8-9) AGGREGATED ===")

rural_agg = query('''
    SELECT 
        COUNT(*) as total_rural_churches,
        ROUND(AVG(c.nearest_hospital_km), 1) as avg_hospital_km,
        ROUND(AVG(c.nearest_clinic_km), 1) as avg_clinic_km,
        ROUND(AVG(c.nearest_fire_km), 1) as avg_fire_km,
        ROUND(AVG(c.nearest_police_km), 1) as avg_police_km,
        COUNT(CASE WHEN c.nearest_hospital_km > 15 THEN 1 END) as over_15km,
        COUNT(CASE WHEN c.nearest_hospital_km > 30 THEN 1 END) as over_30km,
        COUNT(CASE WHEN c.nearest_hospital_km > 50 THEN 1 END) as over_50km,
        COUNT(CASE WHEN c.nearest_hospital_km > 100 THEN 1 END) as over_100km
    FROM churches c
    JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.latitude != 0
      AND rc.rucc_code IN (8, 9)
      AND c.nearest_hospital_km IS NOT NULL
''')
print(json.dumps(rural_agg, indent=2))

# Metro comparison
metro_agg = query('''
    SELECT 
        COUNT(*) as total_metro_churches,
        ROUND(AVG(c.nearest_hospital_km), 1) as avg_hospital_km,
        ROUND(AVG(c.nearest_clinic_km), 1) as avg_clinic_km,
        COUNT(CASE WHEN c.nearest_hospital_km > 30 THEN 1 END) as over_30km
    FROM churches c
    JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.latitude != 0
      AND rc.rucc_code IN (1, 2, 3)
      AND c.nearest_hospital_km IS NOT NULL
''')
print("Metro comparison:")
print(json.dumps(metro_agg, indent=2))

# ============================================================
# 4. STATE-LEVEL RURAL HEALTHCARE DESERTS
# ============================================================
print("\n=== 4. STATE-LEVEL RURAL HEALTHCARE DESERTS ===")

state_rural = query('''
    SELECT c.state,
           COUNT(*) as rural_churches,
           ROUND(AVG(c.nearest_hospital_km), 1) as avg_hospital_km,
           ROUND(AVG(c.nearest_clinic_km), 1) as avg_clinic_km,
           COUNT(CASE WHEN c.nearest_hospital_km > 30 THEN 1 END) as over_30km,
           COUNT(CASE WHEN c.nearest_hospital_km > 50 THEN 1 END) as over_50km,
           COUNT(CASE WHEN c.nearest_hospital_km > 100 THEN 1 END) as over_100km,
           ROUND(COUNT(CASE WHEN c.nearest_hospital_km > 30 THEN 1 END) * 100.0 / COUNT(*), 1) as pct_over_30km
    FROM churches c
    JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.latitude != 0
      AND rc.rucc_code IN (8, 9)
      AND c.nearest_hospital_km IS NOT NULL
    GROUP BY c.state
    ORDER BY avg_hospital_km DESC
''')

print(f"  Top 20 states by avg rural hospital distance:")
for r in state_rural[:20]:
    print(f"    {r['state']}: {r['rural_churches']:,} rural churches, avg={r['avg_hospital_km']}km, >30km={r['over_30km']:,} ({r['pct_over_30km']}%)")

with open(f'{OUT}/state_rural_healthcare.json', 'w') as f:
    json.dump(state_rural, f, indent=2)

# ============================================================
# 5. FAITH BREAKDOWN FOR RURAL
# ============================================================
print("\n=== 5. FAITH BREAKDOWN ===")

faith_rural = query('''
    SELECT c.faith,
           COUNT(*) as churches,
           ROUND(AVG(c.nearest_hospital_km), 1) as avg_hospital_km,
           COUNT(CASE WHEN c.nearest_hospital_km > 30 THEN 1 END) as over_30km,
           COUNT(CASE WHEN c.nearest_hospital_km > 50 THEN 1 END) as over_50km
    FROM churches c
    JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.latitude != 0
      AND rc.rucc_code IN (8, 9)
      AND c.nearest_hospital_km IS NOT NULL
    GROUP BY c.faith
    ORDER BY churches DESC
''')
for r in faith_rural:
    print(f"  {r['faith']}: {r['churches']:,} churches, avg={r['avg_hospital_km']}km, >30km={r['over_30km']:,}")

with open(f'{OUT}/faith_rural_healthcare.json', 'w') as f:
    json.dump(faith_rural, f, indent=2)

# ============================================================
# 6. TRADITION BREAKDOWN (TOP 25)
# ============================================================
print("\n=== 6. TRADITION BREAKDOWN (Top 25 by rural count) ===")

denom_rural = query('''
    SELECT c.tradition,
           COUNT(*) as churches,
           ROUND(AVG(c.nearest_hospital_km), 1) as avg_hospital_km,
           COUNT(CASE WHEN c.nearest_hospital_km > 30 THEN 1 END) as over_30km,
           COUNT(CASE WHEN c.nearest_hospital_km > 50 THEN 1 END) as over_50km
    FROM churches c
    JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.latitude != 0
      AND rc.rucc_code IN (8, 9)
      AND c.nearest_hospital_km IS NOT NULL
      AND c.tradition IS NOT NULL
    GROUP BY c.tradition
    ORDER BY churches DESC
    LIMIT 25
''')
for r in denom_rural:
    print(f"  {r['tradition']}: {r['churches']:,} churches, avg={r['avg_hospital_km']}km, >30km={r['over_30km']:,}")

with open(f'{OUT}/tradition_rural_healthcare.json', 'w') as f:
    json.dump(denom_rural, f, indent=2)

# ============================================================
# 7. COUNTY-LEVEL HOTSPOTS (worst counties for rural access)
# ============================================================
print("\n=== 7. WORST COUNTIES FOR RURAL HEALTHCARE ACCESS ===")

county_hotspots = query('''
    SELECT c.county, c.state,
           rc.county_name,
           rc.rucc_code,
           rc.description as rucc_desc,
           COUNT(*) as churches,
           ROUND(AVG(c.nearest_hospital_km), 1) as avg_hospital_km,
           ROUND(AVG(c.nearest_clinic_km), 1) as avg_clinic_km,
           COUNT(CASE WHEN c.nearest_hospital_km > 30 THEN 1 END) as over_30km,
           COUNT(CASE WHEN c.nearest_hospital_km > 50 THEN 1 END) as over_50km,
           COUNT(CASE WHEN c.nearest_hospital_km > 100 THEN 1 END) as over_100km
    FROM churches c
    JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.latitude != 0
      AND rc.rucc_code IN (8, 9)
      AND c.nearest_hospital_km IS NOT NULL
      AND c.county IS NOT NULL
    GROUP BY c.county_fips_5
    HAVING churches >= 5
    ORDER BY avg_hospital_km DESC
    LIMIT 30
''')
for r in county_hotspots:
    print(f"  {r['county']}, {r['state']} (RUCC {r['rucc_code']}): {r['churches']} churches, avg={r['avg_hospital_km']}km, >50km={r['over_50km']}")

with open(f'{OUT}/county_hotspots.json', 'w') as f:
    json.dump(county_hotspots, f, indent=2)

# ============================================================
# 8. HOSPITAL VS CLINIC GAP ANALYSIS
# ============================================================
print("\n=== 8. HOSPITAL VS CLINIC GAP ===")

# For rural churches, clinic is closer than hospital? Or further?
gap_data = query('''
    SELECT 
        CASE 
            WHEN c.nearest_clinic_km < c.nearest_hospital_km THEN 'Clinic closer'
            WHEN c.nearest_clinic_km > c.nearest_hospital_km THEN 'Hospital closer'
            ELSE 'Same distance'
        END as closer,
        COUNT(*) as n,
        ROUND(AVG(c.nearest_hospital_km - c.nearest_clinic_km), 2) as avg_diff_km
    FROM churches c
    JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.latitude != 0
      AND rc.rucc_code IN (8, 9)
      AND c.nearest_hospital_km IS NOT NULL
      AND c.nearest_clinic_km IS NOT NULL
    GROUP BY closer
    ORDER BY n DESC
''')
for r in gap_data:
    print(f"  {r['closer']}: {r['n']:,} churches, avg diff={r['avg_diff_km']}km")

with open(f'{OUT}/gap_analysis.json', 'w') as f:
    json.dump(gap_data, f, indent=2)

# ============================================================
# 9. EXTREME HEALTHCARE DESERTS (>100km)
# ============================================================
print("\n=== 9. EXTREME HEALTHCARE DESERTS (>100km) ===")

extreme = query('''
    SELECT c.state,
           COUNT(*) as churches,
           ROUND(AVG(c.nearest_hospital_km), 1) as avg_km,
           MAX(c.nearest_hospital_km) as max_km
    FROM churches c
    JOIN rucc_codes rc ON c.county_fips_5 = rc.fips
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.latitude != 0
      AND rc.rucc_code IN (8, 9)
      AND c.nearest_hospital_km > 100
    GROUP BY c.state
    ORDER BY churches DESC
''')
print(f"  Total rural churches >100km from hospital: {sum(r['churches'] for r in extreme)}")
for r in extreme:
    print(f"    {r['state']}: {r['churches']} churches, avg={r['avg_km']}km, max={r['max_km']}km")

with open(f'{OUT}/extreme_deserts.json', 'w') as f:
    json.dump(extreme, f, indent=2)

# ============================================================
# 10. COMPREHENSIVE SUMMARY JSON
# ============================================================
print("\n=== 10. Saving comprehensive summary ===")

full_summary = {
    'summary': summary,
    'rucc_breakdown': rucc_breakdown,
    'rural_aggregated': rural_agg,
    'metro_comparison': metro_agg,
    'state_rural': state_rural,
    'faith_rural': faith_rural,
    'denom_rural': denom_rural,
    'county_hotspots': county_hotspots,
    'gap_analysis': gap_data,
    'extreme_deserts': extreme,
}

with open(f'{OUT}/full_summary.json', 'w') as f:
    json.dump(full_summary, f, indent=2)

print(f"All data saved to {OUT}/")
print("Done.")
db.close()
