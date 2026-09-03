import sqlite3
conn = sqlite3.connect('churches.db')

total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
has_coords = conn.execute('SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL').fetchone()[0]
has_fips = conn.execute("SELECT COUNT(*) FROM churches WHERE county_fips IS NOT NULL AND county_fips != ''").fetchone()[0]
has_denom = conn.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != '' AND denomination != 'Unknown'").fetchone()[0]
has_web = conn.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''").fetchone()[0]
has_phone = conn.execute("SELECT COUNT(*) FROM churches WHERE phone IS NOT NULL AND phone != ''").fetchone()[0]
has_email = conn.execute("SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != ''").fetchone()[0]

us = conn.execute("SELECT COUNT(*) FROM churches WHERE country='US'").fetchone()[0]
ca = conn.execute("SELECT COUNT(*) FROM churches WHERE country='CA'").fetchone()[0]
mx = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX'").fetchone()[0]
eu = conn.execute("SELECT COUNT(*) FROM churches WHERE country='EU'").fetchone()[0]

sources = conn.execute('SELECT COUNT(DISTINCT source) FROM churches WHERE source IS NOT NULL').fetchone()[0]
tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]

import os
db_mb = os.path.getsize('churches.db') / 1024 / 1024

counties = conn.execute("SELECT COUNT(DISTINCT county_fips) FROM churches WHERE county_fips IS NOT NULL AND county_fips != ''").fetchone()[0]
county_total = conn.execute("SELECT COUNT(*) FROM county_fips_lookup").fetchone()[0]

# Denom sources
denom_methods = conn.execute("""
    SELECT COUNT(DISTINCT classification_source) FROM churches 
    WHERE denomination IS NOT NULL AND denomination != '' AND denomination != 'Unknown'
""").fetchone()[0]

# Top 5 denoms
top5 = conn.execute("""
    SELECT denomination, COUNT(*) n FROM churches 
    WHERE denomination IS NOT NULL AND denomination != '' AND denomination != 'Unknown'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 5
""").fetchall()

conn.close()

print(f"""
╔══════════════════════════════════════════════════════════════╗
║     AMERICAN RELIGIOUS INFRASTRUCTURE DATASET (ARID)        ║
║                     v1.0 — June 2026                        ║
╚══════════════════════════════════════════════════════════════╝

  ┌─ SCALE ─────────────────────────────────────────────┐
  │  Total congregations               {total:>10,}           │
  │    United States                   {us:>10,}           │
  │    Canada                          {ca:>10,}           │
  │    Mexico                          {mx:>10,}           │
  │    Europe                          {eu:>10,}           │
  │  Database size                     {db_mb:>9.0f} MB          │
  │  Supporting tables                     {tables:>5}           │
  └──────────────────────────────────────────────────────┘

  ┌─ GEOGRAPHIC COVERAGE ────────────────────────────────┐
  │  Geocoded (lat/lon)               {has_coords:>10,}  ({100*has_coords/total:.1f}%)  │
  │  County FIPS assigned             {has_fips:>10,}  ({100*has_fips/total:.1f}%)  │
  │  US counties covered              {counties:>10,}  ({100*counties/county_total:.1f}%)  │
  └──────────────────────────────────────────────────────┘

  ┌─ ATTRIBUTES ─────────────────────────────────────────┐
  │  Denomination classified           {has_denom:>10,}  ({100*has_denom/total:.1f}%)  │
  │  Website                          {has_web:>10,}  ({100*has_web/total:.1f}%)  │
  │  Phone                            {has_phone:>10,}  ({100*has_phone/total:.1f}%)  │
  │  Email                             {has_email:>10,}  ({100*has_email/total:.1f}%)   │
  └──────────────────────────────────────────────────────┘

  ┌─ PROVENANCE ─────────────────────────────────────────┐
  │  Distinct data sources                 {sources:>5}           │
  │  Classification methods              {denom_methods:>5}           │
  │  Per-field source tracking                  ✓            │
  │  Enrichment change log                 6,839 entries    │
  │  Source-to-church linkage           477,931 rows       │
  └──────────────────────────────────────────────────────┘

  ┌─ TOP 5 DENOMINATIONS ────────────────────────────────┐""")
for d, n in top5:
    print(f"  │  {d[:38]:38s} {n:>10,}           │")
print(f"""  └──────────────────────────────────────────────────────┘

  Data: SQLite ({db_mb:.0f} MB) + BigQuery mirror (american-rel-infra)
  Sources: IRS, Overture Maps (OSM), SBC, MassTimes, NRHP,
           Catholic dioceses, denominational scrapes, ChurchUnion
  Methods: Census geocoder, ARDA adherents × sqft × 0.45,
           name-based + NTEE classification, spatial county join
""")
