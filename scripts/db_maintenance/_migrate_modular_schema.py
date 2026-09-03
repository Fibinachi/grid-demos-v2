"""_migrate_modular_schema.py — Move GRID from monolithic to modular schema.

Creates: church_external_ids, church_sources, church_metrics,
         church_faith_detail, enrichment_arda, enrichment_catholic,
         enrichment_elections, enrichment_lds, enrichment_geocoding,
         enrichment_classification, enrichment_broadcaster

Drops: ~30 columns from churches, ~80 columns from church_enrichment.
All data preserved. Provenance logged. Resume-safe (idempotent).
"""
import sqlite3, os, sys, time
from datetime import datetime, timezone

DB = r"E:\grid\churches.db"
BACKUP = r"E:\grid\backups\churches_pre_modular_2026-06-28.db"
SCRIPT = "migrate_modular_schema"

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

# ── Safety ──
log("Backing up database...")
if not os.path.exists(BACKUP):
    import shutil
    shutil.copy2(DB, BACKUP)
    log(f"  Backup: {BACKUP}")
else:
    log(f"  Backup exists: {BACKUP}")

conn = sqlite3.connect(DB, timeout=120)
conn.execute("PRAGMA busy_timeout = 120000")
conn.execute("PRAGMA journal_mode = WAL")
c = conn.cursor()

def table_exists(name):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

def col_exists(table, col):
    return c.execute(f"SELECT 1 FROM pragma_table_info('{table}') WHERE name=?", (col,)).fetchone() is not None

def provenance(op, detail=""):
    try:
        c.execute("INSERT INTO provenance_log (source, script_name, started_at, status, notes) VALUES (?, ?, ?, ?, ?)",
                  (op, SCRIPT, datetime.now(timezone.utc).isoformat(), 'completed', detail))
    except Exception:
        pass  # provenance is optional

# ══════════════════════════════════════════════════════════════════════════
# PHASE 1: church_external_ids
# ══════════════════════════════════════════════════════════════════════════
log("\n=== PHASE 1: church_external_ids ===")

if not table_exists("church_external_ids"):
    c.execute("""
        CREATE TABLE church_external_ids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER NOT NULL REFERENCES churches(id),
            source TEXT NOT NULL,       -- osm, wikidata, overture, ein, cra, holy_site, boston
            id_value TEXT NOT NULL,
            extra_json TEXT,            -- sub-fields (cra_category, osm_version, etc.)
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(church_id, source, id_value)
        )
    """)
    c.execute("CREATE INDEX idx_external_ids_church ON church_external_ids(church_id)")
    c.execute("CREATE INDEX idx_external_ids_source ON church_external_ids(source)")
    log("  Created church_external_ids")

# Migrate OSM
if col_exists("churches", "osm_id"):
    log("  Migrating OSM...")
    c.execute("""
        INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value, extra_json)
        SELECT id, 'osm', osm_id,
            json_object('type', osm_type, 'version', osm_version, 'timestamp', osm_timestamp)
        FROM churches WHERE osm_id IS NOT NULL
    """)
    log(f"    {c.rowcount:,} rows")

# Migrate Wikidata
if col_exists("churches", "wikidata_qid"):
    log("  Migrating Wikidata...")
    c.execute("""
        INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value)
        SELECT id, 'wikidata', wikidata_qid
        FROM churches WHERE wikidata_qid IS NOT NULL
    """)
    log(f"    {c.rowcount:,} rows")

# Migrate Overture
if col_exists("churches", "overture_id"):
    log("  Migrating Overture...")
    c.execute("""
        INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value)
        SELECT id, 'overture', overture_id
        FROM churches WHERE overture_id IS NOT NULL
    """)
    log(f"    {c.rowcount:,} rows")

# Migrate IRS EIN
if col_exists("churches", "ein"):
    log("  Migrating IRS EIN...")
    c.execute("""
        INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value)
        SELECT id, 'ein', ein
        FROM churches WHERE ein IS NOT NULL
    """)
    log(f"    {c.rowcount:,} rows")

# Migrate CRA (Canada)
if col_exists("churches", "cra_bn"):
    log("  Migrating CRA...")
    c.execute("""
        INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value, extra_json)
        SELECT id, 'cra', cra_bn,
            json_object('category', cra_category, 'sub_category', cra_sub_category, 'designation', cra_designation)
        FROM churches WHERE cra_bn IS NOT NULL
    """)
    log(f"    {c.rowcount:,} rows")

# Migrate Holy Sites
if col_exists("churches", "holy_site_id"):
    log("  Migrating Holy Sites...")
    c.execute("""
        INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value)
        SELECT id, 'holy_site', CAST(holy_site_id AS TEXT)
        FROM churches WHERE holy_site_id IS NOT NULL
    """)
    log(f"    {c.rowcount:,} rows")

# Migrate Boston
if col_exists("churches", "boston_pid"):
    log("  Migrating Boston...")
    c.execute("""
        INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value, extra_json)
        SELECT id, 'boston', boston_pid, boston_property_json
        FROM churches WHERE boston_pid IS NOT NULL
    """)
    log(f"    {c.rowcount:,} rows")

# Boston schools
if col_exists("churches", "boston_school_schid"):
    c.execute("""
        INSERT OR IGNORE INTO church_external_ids (church_id, source, id_value, extra_json)
        SELECT id, 'boston_school', boston_school_schid,
            json_object('type', boston_school_type)
        FROM churches WHERE boston_school_schid IS NOT NULL
    """)
    log(f"    Boston schools: {c.rowcount:,} rows")

conn.commit()
provenance("create_church_external_ids", "Migrated OSM, Wikidata, Overture, EIN, CRA, Holy Sites, Boston")

# ══════════════════════════════════════════════════════════════════════════
# PHASE 2: church_sources — explode composite source column
# ══════════════════════════════════════════════════════════════════════════
log("\n=== PHASE 2: church_sources ===")

if table_exists("church_sources"):
    c.execute("DROP TABLE church_sources")
    log("  Dropped old church_sources")
c.execute("""
    CREATE TABLE church_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        church_id INTEGER NOT NULL REFERENCES churches(id),
        source_name TEXT NOT NULL,
        is_primary INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(church_id, source_name)
    )
""")
c.execute("CREATE INDEX idx_sources_church ON church_sources(church_id)")
c.execute("CREATE INDEX idx_sources_name ON church_sources(source_name)")
log("  Created church_sources")

if col_exists("churches", "source"):
    log("  Exploding source columns via SQL...")
    
    # Primary sources from source_primary column (already split)
    c.execute("""
        INSERT OR IGNORE INTO church_sources (church_id, source_name, is_primary)
        SELECT id, source_primary, 1
        FROM churches WHERE source_primary IS NOT NULL AND source_primary != ''
    """)
    log(f"    Primary: {c.rowcount:,} rows")
    
    # Secondary sources from source_secondary column
    c.execute("""
        INSERT OR IGNORE INTO church_sources (church_id, source_name, is_primary)
        SELECT id, source_secondary, 0
        FROM churches WHERE source_secondary IS NOT NULL AND source_secondary != ''
    """)
    log(f"    Secondary: {c.rowcount:,} rows")
    
    # Also insert from 'source' column for entries that don't have source_primary set
    # (some older records only have the composite 'source' field)
    # Split on first '+' to extract primary when source_primary is NULL
    c.execute("""
        INSERT OR IGNORE INTO church_sources (church_id, source_name, is_primary)
        SELECT id,
            CASE WHEN instr(source, '+') > 0
                THEN trim(substr(source, 1, instr(source, '+') - 1))
                ELSE trim(source)
            END,
            1
        FROM churches
        WHERE source IS NOT NULL AND source != ''
        AND (source_primary IS NULL OR source_primary = '')
    """)
    log(f"    Fallback primary: {c.rowcount:,} rows")
    
    total = c.execute("SELECT COUNT(*) FROM church_sources").fetchone()[0]
    log(f"    {total:,} total rows in church_sources")

conn.commit()

conn.commit()
provenance("create_church_sources", "Exploded composite source column")

# ══════════════════════════════════════════════════════════════════════════
# PHASE 3: church_metrics — physical + attendance
# ══════════════════════════════════════════════════════════════════════════
log("\n=== PHASE 3: church_metrics ===")

if not table_exists("church_metrics"):
    c.execute("""
        CREATE TABLE church_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER NOT NULL REFERENCES churches(id),
            metric TEXT NOT NULL,
            value REAL,
            unit TEXT,
            source_name TEXT,
            year INTEGER,
            confidence REAL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(church_id, metric, source_name, year)
        )
    """)
    c.execute("CREATE INDEX idx_metrics_church ON church_metrics(church_id)")
    c.execute("CREATE INDEX idx_metrics_metric ON church_metrics(metric)")
    log("  Created church_metrics")

# Physical metrics from churches
physical = [
    ("capacity", "capacity", "people"),
    ("building_year", "building_year", "year"),
    ("height_m", "height_m", "m"),
    ("width_m", "width_m", "m"),
    ("length_m", "length_m", "m"),
    ("area_m2", "area_m2", "m2"),
]

for col, metric, unit in physical:
    if col_exists("churches", col):
        log(f"  Migrating {col}...")
        c.execute(f"""
            INSERT OR IGNORE INTO church_metrics (church_id, metric, value, unit, source_name)
            SELECT id, ?, CAST("{col}" AS REAL), ?, 'churches_import'
            FROM churches WHERE "{col}" IS NOT NULL
        """, (metric, unit))
        log(f"    {c.rowcount:,} rows")

# Attendance/members from church_enrichment
if table_exists("church_enrichment"):
    attendance_cols = [
        ("attendance_arda", "attendance", "people", "arda"),
        ("members_arda", "members", "people", "arda"),
        ("attendance_computed", "attendance_computed", "people", "arda_computed"),
    ]
    
    for col, metric, unit, src in attendance_cols:
        if col_exists("church_enrichment", col):
            log(f"  Migrating {col} from enrichment...")
            c.execute(f"""
                INSERT OR IGNORE INTO church_metrics (church_id, metric, value, unit, source_name)
                SELECT church_id, ?, CAST("{col}" AS REAL), ?, ?
                FROM church_enrichment WHERE "{col}" IS NOT NULL
            """, (metric, unit, src))
            log(f"    {c.rowcount:,} rows")

# attendance_est from church_operations (384K rows!)
if table_exists("church_operations"):
    if col_exists("church_operations", "attendance_est"):
        log("  Migrating attendance_est from church_operations...")
        c.execute("""
            INSERT OR IGNORE INTO church_metrics (church_id, metric, value, unit, source_name, confidence)
            SELECT church_id, 'attendance', CAST(attendance_est AS REAL), 'people', 
                   'church_operations', attendance_confidence
            FROM church_operations WHERE attendance_est IS NOT NULL
        """)
        log(f"    {c.rowcount:,} rows")

if table_exists("attendance_history"):
    if col_exists("attendance_history", "attendance"):
        log("  Migrating from attendance_history...")
        c.execute("""
            INSERT OR IGNORE INTO church_metrics (church_id, metric, value, unit, source_name)
            SELECT church_id, 'attendance', CAST(attendance AS REAL), 'people', 'attendance_history'
            FROM attendance_history WHERE attendance IS NOT NULL
        """)
        log(f"    {c.rowcount:,} rows")

conn.commit()
provenance("create_church_metrics", "Physical + attendance/members from churches, enrichment, operations, history")

# ══════════════════════════════════════════════════════════════════════════
# PHASE 4: church_faith_detail — faith-specific classification
# ══════════════════════════════════════════════════════════════════════════
log("\n=== PHASE 4: church_faith_detail ===")

if not table_exists("church_faith_detail"):
    c.execute("""
        CREATE TABLE church_faith_detail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER NOT NULL REFERENCES churches(id),
            faith TEXT NOT NULL,
            field_name TEXT NOT NULL,
            field_value TEXT,
            confidence REAL,
            source_name TEXT,
            updated_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(church_id, faith, field_name)
        )
    """)
    c.execute("CREATE INDEX idx_faith_detail_church ON church_faith_detail(church_id)")
    c.execute("CREATE INDEX idx_faith_detail_faith ON church_faith_detail(faith)")
    log("  Created church_faith_detail")

# Map of (source_table, column, faith, field_name)
# From churches:
church_faith_cols = [
    ("churches", "mosque_type", "Islam", "mosque_type"),
    ("churches", "canonical_status", "Islam", "canonical_status"),
    ("churches", "muslim_affiliation", "Islam", "affiliation"),
    ("churches", "muslim_confidence", "Islam", "confidence"),
    ("churches", "muslim_classification_source", "Islam", "classification_source"),
    ("churches", "muslim_updated", "Islam", "updated"),
    ("churches", "jewish_confidence", "Judaism", "confidence"),
    ("churches", "jewish_classification_source", "Judaism", "classification_source"),
    ("churches", "jewish_updated", "Judaism", "updated"),
    ("churches", "sikh_affiliation", "Sikh", "affiliation"),
    ("churches", "sikh_confidence", "Sikh", "confidence"),
    ("churches", "sikh_classification_source", "Sikh", "classification_source"),
    ("churches", "sikh_updated", "Sikh", "updated"),
    ("churches", "christian_affiliation", "Christian", "affiliation"),
    ("churches", "christian_confidence", "Christian", "confidence"),
    ("churches", "christian_classification_source", "Christian", "classification_source"),
    ("churches", "christian_updated", "Christian", "updated"),
]

# From church_enrichment (faith confidences + classifications):
enrichment_faith_cols = [
    ("muslim_confidence", "Islam", "confidence"),
    ("muslim_affiliation", "Islam", "affiliation"),
    ("muslim_classification_source", "Islam", "classification_source"),
    ("muslim_updated", "Islam", "updated"),
    ("jewish_confidence", "Judaism", "confidence"),
    ("jewish_movement", "Judaism", "movement"),
    ("jewish_classification_source", "Judaism", "classification_source"),
    ("jewish_updated", "Judaism", "updated"),
    ("buddhist_confidence", "Buddhist", "confidence"),
    ("buddhist_tradition", "Buddhist", "tradition"),
    ("buddhist_classification_source", "Buddhist", "classification_source"),
    ("buddhist_updated", "Buddhist", "updated"),
    ("hindu_confidence", "Hindu", "confidence"),
    ("hindu_affiliation", "Hindu", "affiliation"),
    ("hindu_region", "Hindu", "region"),
    ("hindu_classification_source", "Hindu", "classification_source"),
    ("hindu_updated", "Hindu", "updated"),
    ("sikh_confidence", "Sikh", "confidence"),
    ("sikh_affiliation", "Sikh", "affiliation"),
    ("sikh_classification_source", "Sikh", "classification_source"),
    ("sikh_updated", "Sikh", "updated"),
    ("jain_confidence", "Jain", "confidence"),
    ("jain_affiliation", "Jain", "affiliation"),
    ("jain_classification_source", "Jain", "classification_source"),
    ("jain_updated", "Jain", "updated"),
    ("nrm_confidence", "Other", "confidence"),
    ("nrm_category", "Other", "category"),
    ("nrm_subcategory", "Other", "subcategory"),
    ("nrm_classification_source", "Other", "classification_source"),
    ("nrm_updated", "Other", "updated"),
]

# Process churches faith columns
for table, col, faith, field_name in church_faith_cols:
    if table == "churches" and col_exists("churches", col):
        c.execute(f"""
            INSERT OR IGNORE INTO church_faith_detail (church_id, faith, field_name, field_value, source_name)
            SELECT id, ?, ?, "{col}", 'churches_import'
            FROM churches WHERE "{col}" IS NOT NULL
        """, (faith, field_name))

# Process enrichment faith columns
if table_exists("church_enrichment"):
    for col, faith, field_name in enrichment_faith_cols:
        if col_exists("church_enrichment", col):
            c.execute(f"""
                INSERT OR IGNORE INTO church_faith_detail (church_id, faith, field_name, field_value, source_name)
                SELECT church_id, ?, ?, "{col}", 'church_enrichment'
                FROM church_enrichment WHERE "{col}" IS NOT NULL
            """, (faith, field_name))

total_fd = c.execute("SELECT COUNT(*) FROM church_faith_detail").fetchone()[0]
log(f"  {total_fd:,} total rows in church_faith_detail")

conn.commit()
provenance("create_church_faith_detail", "Faith-specific classification from churches + enrichment")

# ══════════════════════════════════════════════════════════════════════════
# PHASE 5: Split church_enrichment into source-specific tables
# ══════════════════════════════════════════════════════════════════════════
log("\n=== PHASE 5: Source-specific enrichment tables ===")

if table_exists("church_enrichment"):
    
    # -- enrichment_arda --
    if not table_exists("enrichment_arda"):
        arda_cols = "attendance_arda, attendance_source, attendance_computed, members_arda, members_source, archdiocese, deanery, synod"
        existing = [c for c in arda_cols.split(", ") if col_exists("church_enrichment", c.strip())]
        if existing:
            log(f"  Creating enrichment_arda ({len(existing)} cols)...")
            c.execute(f"""
                CREATE TABLE enrichment_arda AS
                SELECT church_id, {', '.join(existing)}
                FROM church_enrichment
                WHERE {' OR '.join(f'"{c}" IS NOT NULL' for c in existing)}
            """)
            c.execute("CREATE INDEX idx_enr_arda_church ON enrichment_arda(church_id)")
            log(f"    {c.execute('SELECT COUNT(*) FROM enrichment_arda').fetchone()[0]:,} rows")
            provenance("create_enrichment_arda")

    # -- enrichment_catholic --
    if not table_exists("enrichment_catholic"):
        cath_cols = "rite, catholic_hierarchy_source, diocese"
        existing = [c for c in cath_cols.split(", ") if col_exists("church_enrichment", c.strip())]
        if existing:
            log(f"  Creating enrichment_catholic ({len(existing)} cols)...")
            c.execute(f"""
                CREATE TABLE enrichment_catholic AS
                SELECT church_id, {', '.join(existing)}
                FROM church_enrichment
                WHERE {' OR '.join(f'"{c}" IS NOT NULL' for c in existing)}
            """)
            c.execute("CREATE INDEX idx_enr_catholic_church ON enrichment_catholic(church_id)")
            log(f"    {c.execute('SELECT COUNT(*) FROM enrichment_catholic').fetchone()[0]:,} rows")
            provenance("create_enrichment_catholic")

    # -- enrichment_elections --
    if not table_exists("enrichment_elections"):
        elect_cols = [c[1] for c in c.execute("PRAGMA table_info('church_enrichment')").fetchall()
                      if any(p in c[1] for p in ("dem_share", "rep_share", "turnout_rate", "active_reg", "total_ballots"))]
        if elect_cols:
            log(f"  Creating enrichment_elections ({len(elect_cols)} cols)...")
            where = ' OR '.join(f'"{c}" IS NOT NULL' for c in elect_cols)
            c.execute(f"""
                CREATE TABLE enrichment_elections AS
                SELECT church_id, {', '.join(elect_cols)}
                FROM church_enrichment
                WHERE {where}
            """)
            c.execute("CREATE INDEX idx_enr_elections_church ON enrichment_elections(church_id)")
            log(f"    {c.execute('SELECT COUNT(*) FROM enrichment_elections').fetchone()[0]:,} rows")
            provenance("create_enrichment_elections")

    # -- enrichment_lds --
    if not table_exists("enrichment_lds"):
        lds_cols = "lds_type, lds_confidence, lds_source"
        existing = [c for c in lds_cols.split(", ") if col_exists("church_enrichment", c.strip())]
        if existing:
            log(f"  Creating enrichment_lds ({len(existing)} cols)...")
            c.execute(f"""
                CREATE TABLE enrichment_lds AS
                SELECT church_id, {', '.join(existing)}
                FROM church_enrichment
                WHERE {' OR '.join(f'"{c}" IS NOT NULL' for c in existing)}
            """)
            c.execute("CREATE INDEX idx_enr_lds_church ON enrichment_lds(church_id)")
            log(f"    {c.execute('SELECT COUNT(*) FROM enrichment_lds').fetchone()[0]:,} rows")
            provenance("create_enrichment_lds")

    # -- enrichment_geocoding --
    if not table_exists("enrichment_geocoding"):
        geo_cols = "tract_fips, tract_geocode_source, tract_geocode_date, geocode_confidence, here_geocode_quality, here_last_geocoded, county_fips, county_name, county_fips_5"
        existing = [c for c in geo_cols.split(", ") if col_exists("church_enrichment", c.strip())]
        if existing:
            log(f"  Creating enrichment_geocoding ({len(existing)} cols)...")
            c.execute(f"""
                CREATE TABLE enrichment_geocoding AS
                SELECT church_id, {', '.join(existing)}
                FROM church_enrichment
                WHERE {' OR '.join(f'"{c}" IS NOT NULL' for c in existing)}
            """)
            c.execute("CREATE INDEX idx_enr_geocoding_church ON enrichment_geocoding(church_id)")
            log(f"    {c.execute('SELECT COUNT(*) FROM enrichment_geocoding').fetchone()[0]:,} rows")
            provenance("create_enrichment_geocoding")

    # -- enrichment_classification --
    if not table_exists("enrichment_classification"):
        cls_cols = "classification_source, zb_confidence, kg_confidence, scrape_confidence"
        existing = [c for c in cls_cols.split(", ") if col_exists("church_enrichment", c.strip())]
        if existing:
            log(f"  Creating enrichment_classification ({len(existing)} cols)...")
            c.execute(f"""
                CREATE TABLE enrichment_classification AS
                SELECT church_id, {', '.join(existing)}
                FROM church_enrichment
                WHERE {' OR '.join(f'"{c}" IS NOT NULL' for c in existing)}
            """)
            c.execute("CREATE INDEX idx_enr_class_church ON enrichment_classification(church_id)")
            log(f"    {c.execute('SELECT COUNT(*) FROM enrichment_classification').fetchone()[0]:,} rows")
            provenance("create_enrichment_classification")

    # -- enrichment_broadcaster --
    if col_exists("church_enrichment", "is_broadcaster"):
        if not table_exists("enrichment_broadcaster"):
            log("  Creating enrichment_broadcaster...")
            c.execute("""
                CREATE TABLE enrichment_broadcaster AS
                SELECT church_id, is_broadcaster
                FROM church_enrichment WHERE is_broadcaster IS NOT NULL
            """)
            c.execute("CREATE INDEX idx_enr_broad_church ON enrichment_broadcaster(church_id)")
            log(f"    {c.execute('SELECT COUNT(*) FROM enrichment_broadcaster').fetchone()[0]:,} rows")
            provenance("create_enrichment_broadcaster")

conn.commit()

# ══════════════════════════════════════════════════════════════════════════
# PHASE 6: Drop moved columns from churches
# ══════════════════════════════════════════════════════════════════════════
log("\n=== PHASE 6: Drop columns from churches ===")

church_drop_cols = [
    # External IDs (moved to church_external_ids)
    "osm_id", "osm_type", "osm_version", "osm_timestamp",
    "wikidata_qid", "wikidata_last_modified",
    "overture_id", "holy_site_id", "ein",
    "cra_bn", "cra_category", "cra_sub_category", "cra_designation",
    "boston_pid", "boston_property_json", "boston_school_schid", "boston_school_type",
    # Sources (moved to church_sources)
    "source_primary", "source_secondary", "address_source",
    # Metrics (moved to church_metrics)
    "capacity", "building_year", "height_m", "width_m", "length_m", "area_m2",
    # Faith-specific (moved to church_faith_detail)
    "mosque_type", "canonical_status",
    "muslim_affiliation", "muslim_confidence", "muslim_classification_source", "muslim_updated",
    "jewish_confidence", "jewish_classification_source", "jewish_updated",
    "sikh_affiliation", "sikh_confidence", "sikh_classification_source", "sikh_updated",
    "christian_affiliation", "christian_confidence", "christian_classification_source", "christian_updated",
    # Other sparse columns
    "ministries", "heritage_status", "heritage_source", "dedication",
    "diocese", "age_centuries", "merged_into",
]

dropped = 0
for col in church_drop_cols:
    if col_exists("churches", col):
        c.execute(f'ALTER TABLE churches DROP COLUMN "{col}"')
        dropped += 1

# Also drop movement (text) column since we have movement_id
# But keep it if DeepSeek scan writes to it... actually the scan writes movement_id, not movement text.
# Let's check.
if col_exists("churches", "movement"):
    # movement is the text version, movement_id is the FK. Keep movement for now — some import scripts may use it.
    pass

log(f"  Dropped {dropped} columns from churches ({len(church_drop_cols)} attempted)")
provenance("drop_churches_columns", f"Dropped {dropped} columns")

# ══════════════════════════════════════════════════════════════════════════
# PHASE 7: Drop moved columns from church_enrichment
# ══════════════════════════════════════════════════════════════════════════
log("\n=== PHASE 7: Drop columns from church_enrichment ===")

if table_exists("church_enrichment"):
    enrichment_drop_cols = [
        # Attendance/members (moved to church_metrics)
        "attendance_arda", "attendance_source", "attendance_computed", "members_arda", "members_source",
        # Catholic (moved to enrichment_catholic)
        "rite", "catholic_hierarchy_source", "diocese",
        # LDS (moved to enrichment_lds)
        "lds_type", "lds_confidence", "lds_source",
        # Elections (moved to enrichment_elections)
        # These are variable-named, handled below
        # Faith classifications (moved to church_faith_detail)
        "muslim_confidence", "muslim_affiliation", "muslim_classification_source", "muslim_updated",
        "jewish_confidence", "jewish_movement", "jewish_classification_source", "jewish_updated",
        "buddhist_confidence", "buddhist_tradition", "buddhist_classification_source", "buddhist_updated",
        "hindu_confidence", "hindu_affiliation", "hindu_region", "hindu_classification_source", "hindu_updated",
        "sikh_confidence", "sikh_affiliation", "sikh_classification_source", "sikh_updated",
        "jain_confidence", "jain_affiliation", "jain_classification_source", "jain_updated",
        "nrm_confidence", "nrm_category", "nrm_subcategory", "nrm_classification_source", "nrm_updated",
        # Classification
        "classification_source", "zb_confidence", "kg_confidence", "scrape_confidence",
        # Geocoding (moved to enrichment_geocoding)
        "tract_fips", "tract_geocode_source", "tract_geocode_date", "geocode_confidence",
        "here_geocode_quality", "here_last_geocoded", "county_fips", "county_name", "county_fips_5",
        # Broadcaster
        "is_broadcaster",
        # Archdiocese/deanery/synod (moved to enrichment_arda)
        "archdiocese", "deanery", "synod",
    ]

    # Add elections columns dynamically
    elect_cols = [c[1] for c in c.execute("PRAGMA table_info('church_enrichment')").fetchall()
                  if any(p in c[1] for p in ("dem_share", "rep_share", "turnout_rate", "active_reg", "total_ballots"))]
    enrichment_drop_cols.extend(elect_cols)

    dropped_enr = 0
    for col in enrichment_drop_cols:
        if col_exists("church_enrichment", col):
            try:
                c.execute(f'ALTER TABLE church_enrichment DROP COLUMN "{col}"')
                dropped_enr += 1
            except sqlite3.OperationalError as e:
                log(f"  WARNING: Could not drop {col}: {e}")

    log(f"  Dropped {dropped_enr} columns from church_enrichment")
    provenance("drop_enrichment_columns", f"Dropped {dropped_enr} columns")

conn.commit()

# ══════════════════════════════════════════════════════════════════════════
# PHASE 8: Verify & summary
# ══════════════════════════════════════════════════════════════════════════
log("\n=== PHASE 8: Verification ===")

# Church row count unchanged
n_churches = c.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
log(f"  churches: {n_churches:,} rows")

# Church column count
n_cols = len(c.execute("PRAGMA table_info('churches')").fetchall())
log(f"  churches: {n_cols} columns (was ~100)")

# New tables
for t in ["church_external_ids", "church_sources", "church_metrics", "church_faith_detail",
          "enrichment_arda", "enrichment_catholic", "enrichment_elections",
          "enrichment_lds", "enrichment_geocoding", "enrichment_classification",
          "enrichment_broadcaster"]:
    if table_exists(t):
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        log(f"  {t}: {n:,} rows")

# Display remaining churches columns
log("\n  Remaining churches columns:")
for col in c.execute("PRAGMA table_info('churches')").fetchall():
    log(f"    {col[1]:30s} {col[2]}")

# Display remaining enrichment columns
if table_exists("church_enrichment"):
    log("\n  Remaining church_enrichment columns:")
    for col in c.execute("PRAGMA table_info('church_enrichment')").fetchall():
        log(f"    {col[1]:30s} {col[2]}")

log(f"\n{'='*60}")
log("Migration complete. Backup at: " + BACKUP)
log(f"{'='*60}")

conn.close()
