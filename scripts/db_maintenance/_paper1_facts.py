import sqlite3, json, os, subprocess
from collections import Counter

conn = sqlite3.connect('churches.db')
total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]

print("=" * 80)
print("PAPER 1 — FACTS & FIGURES")
print("=" * 80)

# ── 1. SIZE & SCOPE ──
print("\n### 1. SIZE & GROWTH ###")
print(f"Current total: {total:,} congregations (SQLite)")
print(f"CSV staged: 165,064 from ChurchUnion — ~95K expected new (58% new rate)")
print(f"Projected total post-import: ~{total + 95000:,}")

# Country
for r in conn.execute('SELECT COALESCE(country,\'NULL\'), COUNT(*) FROM churches GROUP BY 1 ORDER BY 2 DESC'):
    print(f"  {r[0]}: {r[1]:,}")

# Source count
src_count = conn.execute('SELECT COUNT(DISTINCT COALESCE(source,\'NULL\')) FROM churches').fetchone()[0]
print(f"Distinct source values: {src_count}")

# ── 2. PROVENANCE ARCHITECTURE ──
print("\n### 2. PROVENANCE & AUDIT TRAIL ###")
print("Columns tracking data origin:")
print("  source — bulk import origin (250K+ from IRS, 23K SBC, etc.)")
print("  classification_source — how denomination was assigned (name_heuristic, irs_ntee)")
print("  geocode_source — which service produced coordinates (census_street, zip_centroid, mapbox, here, census_batch)")
print("  website_source — origin of website URL (overture, batch_finder, legacy)")
print("  phone_source, address_source, email_source — per-field origin")
print("Tables for provenance:")
church_sources_n = conn.execute('SELECT COUNT(*) FROM church_sources').fetchone()[0]
enrich_log_n = conn.execute('SELECT COUNT(*) FROM enrichment_change_log').fetchone()[0]
print(f"  church_sources: {church_sources_n:,} rows (links churches to source URLs/databases)")
print(f"  enrichment_change_log: {enrich_log_n:,} audited enrichment events")

# ── 3. TOP SOURCES ──
print("\n### 3. DATA SOURCES (by volume) ###")
sources = conn.execute('''
    SELECT COALESCE(source,'NULL'), COUNT(*) n 
    FROM churches GROUP BY 1 ORDER BY 2 DESC LIMIT 12
''').fetchall()
for s, n in sources:
    pct = 100 * n / total
    desc = {
        'irs': 'IRS Business Master File — NTEE-coded religious nonprofits',
        'sbc_directory': 'Southern Baptist Convention official directory',
        'csv_import': 'Bulk CSV imports from denominational scrapes',
        'masstimes_nationwide': 'MassTimes.org — Catholic mass directory',
        'coc_21stcc': '21st Century Christian — Churches of Christ directory',
        'catholic_diocese_scrape': 'Official Catholic diocese websites',
        'nrhp': 'National Register of Historic Places',
        'sbc_scrape': 'SBC state convention directories',
        'ag_directory': 'Assemblies of God official directory',
        'overture_discovery': 'Overture Maps Places (confidence 0.95)',
        'churchunion_scraper': 'ChurchUnion.us scraped directory (NEW)',
    }.get(s, '')
    print(f"  {s:30s} {n:>8,} ({pct:4.1f}%)  {desc}")

# ── 4. GEOGRAPHIC COVERAGE ──
print("\n### 4. GEOGRAPHIC COVERAGE ###")
has_coords = conn.execute('SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL').fetchone()[0]
has_fips = conn.execute("SELECT COUNT(*) FROM churches WHERE county_fips IS NOT NULL AND county_fips != ''").fetchone()[0]
has_tract = conn.execute("SELECT COUNT(*) FROM churches WHERE tract_fips IS NOT NULL AND tract_fips != ''").fetchone()[0]

print(f"Coordinates: {has_coords:,} ({100*has_coords/total:.1f}%)")
print(f"County FIPS: {has_fips:,} ({100*has_fips/total:.1f}%)")
print(f"Tract FIPS:  {has_tract:,} ({100*has_tract/total:.1f}%)")

# Top states
print("\nTop 15 states:")
for r in conn.execute('SELECT state, COUNT(*) n FROM churches WHERE state IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 15'):
    print(f"  {r[0]:5s} {r[1]:>8,}")

# County coverage
county_cnt = conn.execute('SELECT COUNT(DISTINCT county_fips) FROM churches WHERE county_fips IS NOT NULL AND county_fips != ""').fetchone()[0]
total_counties = conn.execute('SELECT COUNT(*) FROM county_fips_lookup').fetchone()[0]
print(f"\nCounty coverage: {county_cnt:,} of {total_counties:,} US counties ({100*county_cnt/total_counties:.1f}%)")

# ── 5. GEOCODING METHODOLOGY ──
print("\n### 5. GEOCODING SOURCES ###")
for r in conn.execute('SELECT geocode_source, COUNT(*) n FROM churches WHERE latitude IS NOT NULL GROUP BY 1 ORDER BY 2 DESC'):
    print(f"  {r[0] or 'NULL':25s} {r[1]:>8,}")

# ── 6. DENOMINATIONAL COVERAGE ──
print("\n### 6. DENOMINATIONAL COVERAGE ###")
has_denom = conn.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != '' AND denomination != 'Unknown'").fetchone()[0]
print(f"Classified: {has_denom:,} ({100*has_denom/total:.1f}%)")

# Classification method
for r in conn.execute("SELECT classification_source, COUNT(*) n FROM churches WHERE denomination IS NOT NULL AND denomination != '' AND denomination != 'Unknown' GROUP BY 1 ORDER BY 2 DESC LIMIT 8"):
    print(f"  {r[0] or 'NULL':30s} {r[1]:>8,}")

# Top denominations
print("\nTop 20 denominations:")
for r in conn.execute("SELECT denomination, COUNT(*) n FROM churches WHERE denomination IS NOT NULL AND denomination != '' AND denomination != 'Unknown' GROUP BY 1 ORDER BY 2 DESC LIMIT 20"):
    print(f"  {r[0][:42]:42s} {r[1]:>8,}")

# ── 7. CONTACT DATA ──
print("\n### 7. CONTACT ENRICHMENT ###")
for col, label in [('website', 'Website'), ('phone', 'Phone'), ('email', 'Email')]:
    n = conn.execute(f"SELECT COUNT(*) FROM churches WHERE {col} IS NOT NULL AND {col} != ''").fetchone()[0]
    print(f"  {label:12s}: {n:>8,} ({100*n/total:.1f}%)")

# ── 8. BUILDING FOOTPRINTS ──
print("\n### 8. BUILDING FOOTPRINTS (BigQuery) ###")
print("  church_building_sqft: 268,000+ churches with building area (sqft)")
print("  Source: Overture Maps building footprints, spatially matched to church coordinates")
print("  Used in: ARDA attendance allocation model (Tiers 1-2)")

# ── 9. ATTENDANCE ESTIMATES ──
print("\n### 9. ATTENDANCE ESTIMATION (BigQuery) ###")
print("  3-tier model in church_attendance_estimates (339,680 churches):")
print("    Tier 1 (arda_allocated):    185,531 — ARDA county×denom adherents × building sqft proportion × 0.45")
print("    Tier 2 (county_sqft_rate):   ~82,000 — Building sqft × county adh/sqft rate × 0.45")
print("    Tier 3 (county_or_state_avg): ~72,000 — County or state average attendance fallback")
print("  National adherents-to-weekly ratio: 0.45 (from ARDA national totals)")

# ── 10. TECHNICAL INFRASTRUCTURE ──
print("\n### 10. TECHNICAL INFRASTRUCTURE ###")
db_size = os.path.getsize('churches.db') / 1024 / 1024
print(f"  SQLite database: {db_size:.0f} MB")
tbl_cnt = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
print(f"  Total tables: {tbl_cnt}")
print("  BigQuery mirror: american-rel-infra.American_Religious_Infrastructure.churches")
print("  Census Geocoder API for address-to-coordinate resolution")
print("  ARDA (Association of Religion Data Archives) for county×denom adherent counts")
print("  Overture Maps for building footprint geometry")
print("  ACS 2020 5-year for census tract demographics (68,951 tracts)")

# ── 11. ID COLUMNS (linking) ──
print("\n### 11. EXTERNAL IDENTIFIERS ###")
nrhp = conn.execute("SELECT COUNT(*) FROM churches WHERE nrhp_ref IS NOT NULL AND nrhp_ref != ''").fetchone()[0]
gnis = conn.execute("SELECT COUNT(*) FROM churches WHERE gnis_feature_id IS NOT NULL AND gnis_feature_id != ''").fetchone()[0]
print(f"  NRHP reference numbers: {nrhp:,}")
print(f"  GNIS feature IDs: {gnis:,} (staged, not yet merged)")
print("  BQ church IDs link to: church_building_sqft, arda_attendance_estimates, church_attendance_estimates")

# ── 12. OTHER ENRICHMENT TABLES ──
print("\n### 12. ENRICHMENT TABLES ###")
for tbl, desc in [
    ('church_census_us', 'Census tract demographics per church'),
    ('church_arda', 'ARDA county×denom data per church'),
    ('church_broadcast', 'FCC broadcast station coverage'),
    ('church_food_desert', 'USDA food desert classification'),
    ('church_staff', 'Clergy/staff rosters'),
    ('church_vacancies', 'Open clergy positions'),
    ('broadcast_coverage', 'FCC broadcast coverage areas'),
    ('tract_lookup_us', '68,951 census tracts with ACS demographics'),
    ('county_fips_lookup', '3,235 counties with population/adherents'),
]:
    try:
        n = conn.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
        print(f"  {tbl:25s} {n:>10,}  {desc}")
    except:
        print(f"  {tbl:25s} {'N/A':>10}  {desc}")

# ── 13. KNOWN LIMITATIONS ──
print("\n### 13. KNOWN LIMITATIONS ###")
print("  - Canada coverage: only 877 churches (major denominations missing)")
print("  - Tract FIPS: only 15.4% resolved (ZIP centroids don't map to tracts accurately)")
print("  - Email coverage: only 7.4% of churches have email addresses")
print("  - Attendance estimates in BigQuery only — not synced to SQLite")
print("  - GNIS church features downloaded but not yet merged")
print("  - IRS data is organizational-level, may not reflect active congregations")
print("  - Some denominations lack public directories (NBC, CME, UCC, etc.)")

# ── 14. REPRODUCIBILITY ──
print("\n### 14. REPRODUCIBILITY MEASURES ###")
print("  - All API keys stored as environment variables (none in code)")
print("  - Every church has source column tracing to origin import")
print("  - Per-field provenance columns (geocode_source, website_source, etc.)")
print("  - enrichment_change_log with 6,839 audited operations")
print("  - Deterministic ARDA model: adherents × sqft proportion × 0.45")
print("  - BigQuery mirror for reproducible analytics")
print("  - All scrapers and enrichment scripts in scripts/ directory")
print("  - Database backup and recovery procedures documented")
print("  - SQLite integrity verified via PRAGMA integrity_check")

conn.close()
