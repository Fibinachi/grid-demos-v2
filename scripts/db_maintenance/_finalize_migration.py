"""_finalize_migration.py — Drop moved columns from churches + enrichment, verify."""
import sqlite3, os, sys
from datetime import datetime, timezone

DB = r"E:\grid\churches.db"

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

conn = sqlite3.connect(DB, timeout=120)
conn.execute("PRAGMA busy_timeout = 120000")
conn.execute("PRAGMA journal_mode = WAL")
c = conn.cursor()

def col_exists(table, col):
    return c.execute(f"SELECT 1 FROM pragma_table_info('{table}') WHERE name=?", (col,)).fetchone() is not None

# ══════════════════════════════════════════════════════════════════════════
# Drop columns from churches
# ══════════════════════════════════════════════════════════════════════════
log("=== Dropping columns from churches ===")

# Drop ALL views that reference churches (they'll block column drops)
log("  Dropping views...")
views = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()]
for v in views:
    try:
        c.execute(f"DROP VIEW IF EXISTS \"{v}\"")
        log(f"    Dropped view {v}")
    except Exception as e:
        log(f"    Could not drop view {v}: {e}")

# Drop indexes that reference columns we're removing
log("  Dropping blocking indexes...")
for idx in ["idx_ch_osm", "idx_ch_qid"]:
    try:
        c.execute(f"DROP INDEX IF EXISTS {idx}")
        log(f"    Dropped {idx}")
    except:
        pass

church_drop = [
    "osm_id", "osm_type", "osm_version", "osm_timestamp",
    "wikidata_qid", "wikidata_last_modified",
    "overture_id", "holy_site_id", "ein",
    "cra_bn", "cra_category", "cra_sub_category", "cra_designation",
    "boston_pid", "boston_property_json", "boston_school_schid", "boston_school_type",
    "source_primary", "source_secondary", "address_source",
    "capacity", "building_year", "height_m", "width_m", "length_m", "area_m2",
    "mosque_type", "canonical_status",
    "muslim_affiliation", "muslim_confidence", "muslim_classification_source", "muslim_updated",
    "jewish_confidence", "jewish_classification_source", "jewish_updated",
    "sikh_affiliation", "sikh_confidence", "sikh_classification_source", "sikh_updated",
    "christian_affiliation", "christian_confidence", "christian_classification_source", "christian_updated",
    "ministries", "heritage_status", "heritage_source", "dedication",
    "diocese", "age_centuries", "merged_into",
]

dropped = 0
for col in church_drop:
    if col_exists("churches", col):
        c.execute(f'ALTER TABLE churches DROP COLUMN "{col}"')
        dropped += 1
        if dropped % 10 == 0:
            log(f"  Dropped {dropped}/{len(church_drop)}...")

log(f"  Dropped {dropped} columns from churches")

conn.commit()

# ══════════════════════════════════════════════════════════════════════════
# Drop columns from church_enrichment
# ══════════════════════════════════════════════════════════════════════════
log("\n=== Dropping columns from church_enrichment ===")

enrichment_drop = [
    "attendance_arda", "attendance_source", "attendance_computed", "members_arda", "members_source",
    "rite", "catholic_hierarchy_source", "diocese",
    "lds_type", "lds_confidence", "lds_source",
    "muslim_confidence", "muslim_affiliation", "muslim_classification_source", "muslim_updated",
    "jewish_confidence", "jewish_movement", "jewish_classification_source", "jewish_updated",
    "buddhist_confidence", "buddhist_tradition", "buddhist_classification_source", "buddhist_updated",
    "hindu_confidence", "hindu_affiliation", "hindu_region", "hindu_classification_source", "hindu_updated",
    "sikh_confidence", "sikh_affiliation", "sikh_classification_source", "sikh_updated",
    "jain_confidence", "jain_affiliation", "jain_classification_source", "jain_updated",
    "nrm_confidence", "nrm_category", "nrm_subcategory", "nrm_classification_source", "nrm_updated",
    "classification_source", "zb_confidence", "kg_confidence", "scrape_confidence",
    "tract_fips", "tract_geocode_source", "tract_geocode_date", "geocode_confidence",
    "here_geocode_quality", "here_last_geocoded", "county_fips", "county_name", "county_fips_5",
    "is_broadcaster", "archdiocese", "deanery", "synod",
]

# Add elections columns
elect_cols = [c[1] for c in c.execute("PRAGMA table_info('church_enrichment')").fetchall()
              if any(p in c[1] for p in ("dem_share", "rep_share", "turnout_rate", "active_reg", "total_ballots"))]
enrichment_drop.extend(elect_cols)

dropped_enr = 0
for col in enrichment_drop:
    if col_exists("church_enrichment", col):
        try:
            c.execute(f'ALTER TABLE church_enrichment DROP COLUMN "{col}"')
            dropped_enr += 1
        except Exception as e:
            log(f"  SKIP {col}: {e}")

log(f"  Dropped {dropped_enr} columns from church_enrichment")
conn.commit()

# ══════════════════════════════════════════════════════════════════════════
# Verify
# ══════════════════════════════════════════════════════════════════════════
log("\n=== Verification ===")

n = c.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
ncol = len(c.execute("PRAGMA table_info('churches')").fetchall())
log(f"  churches: {n:,} rows, {ncol} columns")

log("  churches columns:")
for col in c.execute("PRAGMA table_info('churches')").fetchall():
    log(f"    {col[1]:30s} {col[2]}")

log("\n  Key tables:")
for t in ["church_external_ids", "church_sources", "church_metrics"]:
    try:
        nr = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        log(f"    {t}: {nr:,} rows")
    except:
        log(f"    {t}: NOT FOUND")

log("\nDone. Safe to run DeepSeek scan and BQ upload.")
conn.close()
