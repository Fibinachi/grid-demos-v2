#!/usr/bin/env python3
"""
===========================================================
Migration: Normalize Census Data into Geography-Centric Schema
===========================================================

Creates:
  1. census_geographies  — master geography reference (counties, tracts, ZIPs, countries)
  2. church_geographies  — links church_id → geography_id

Populates from existing normalized tables + churches table.
Drops empty county_* demo columns from church_enrichment.

Usage:
    python scripts/db_maintenance/migrate_census_geo.py [--dry-run]

Run with --dry-run first, then without to apply.
===========================================================
"""
import sqlite3, sys, os, time
from datetime import datetime

DB = r'E:\grid\churches.db'

DRY_RUN = '--dry-run' in sys.argv
if DRY_RUN:
    print("=" * 60)
    print("DRY RUN — no changes will be made")
    print("=" * 60)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {"[DRY-RUN] " if DRY_RUN else ""}{msg}')

def run(db, sql, params=None):
    if DRY_RUN:
        log(f'  SQL: {sql[:120]}...')
        return []
    if params:
        return db.execute(sql, params).fetchall()
    return db.execute(sql).fetchall()

def run_many(db, sql, rows):
    if DRY_RUN:
        log(f'  Would insert {len(rows):,} rows via executemany')
        return
    db.executemany(sql, rows)

# ────────────────────────────────────────────────────────────────
# Step 0: Connect
# ────────────────────────────────────────────────────────────────
log("Connecting...")
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA foreign_keys=OFF")
t0 = time.time()

# ────────────────────────────────────────────────────────────────
# Step 1: Create census_geographies
# ────────────────────────────────────────────────────────────────
log("\n[1] Creating census_geographies table...")
run(db, """
    CREATE TABLE IF NOT EXISTS census_geographies (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        geo_type        TEXT NOT NULL,   -- 'county_fips_5', 'tract_fips_11', 'zip5', 'country_code_2'
        geo_code        TEXT NOT NULL,   -- e.g., '06037', '06037201000', '90210', 'US'
        geo_name        TEXT,            -- e.g., 'Los Angeles County', 'United States'
        parent_code     TEXT,            -- e.g., state FIPS for a county
        meta            TEXT,            -- JSON blob for extra metadata
        created_at      TEXT DEFAULT (datetime('now')),
        UNIQUE(geo_type, geo_code)
    )
""")
log("  Created census_geographies")

# Count existing
n = db.execute("SELECT COUNT(*) FROM census_geographies").fetchone()[0]
log(f"  Already has {n:,} rows" if n else "  Empty table — will populate")

if n == 0 or DRY_RUN:
    # ── 1a: Counties from county_fips_lookup ──
    log("  1a: Inserting counties from county_fips_lookup...")
    rows = db.execute("""
        SELECT county_fips, county_name, state_fips 
        FROM county_fips_lookup
        WHERE county_fips IS NOT NULL AND county_fips != ''
    """).fetchall()
    run_many(db, """
        INSERT OR IGNORE INTO census_geographies (geo_type, geo_code, geo_name, parent_code)
        VALUES ('county_fips_5', ?, ?, ?)
    """, [(r[0], r[1], r[2]) for r in rows])
    log(f"    {len(rows):,} county FIPS codes")

    # ── 1b: Extra counties from churches.fips (not in lookup) ──
    log("  1b: Inserting extra county FIPS from churches.fips...")
    rows = db.execute("""
        SELECT DISTINCT substr('00000' || fips, -5, 5) as padded_fips
        FROM churches 
        WHERE fips IS NOT NULL AND fips != '' AND fips != '0'
        AND padded_fips NOT IN (
            SELECT geo_code FROM census_geographies WHERE geo_type = 'county_fips_5'
        )
    """).fetchall()
    run_many(db, """
        INSERT OR IGNORE INTO census_geographies (geo_type, geo_code)
        VALUES ('county_fips_5', ?)
    """, rows)
    log(f"    {len(rows):,} extra county FIPS codes")

    # ── 1c: Tracts from tract_lookup_us ──
    log("  1c: Inserting tracts from tract_lookup_us...")
    rows = db.execute("""
        SELECT tract_fips, county_fips 
        FROM tract_lookup_us
        WHERE tract_fips IS NOT NULL AND tract_fips != ''
    """).fetchall()
    run_many(db, """
        INSERT OR IGNORE INTO census_geographies (geo_type, geo_code, parent_code)
        VALUES ('tract_fips_11', ?, ?)
    """, [(r[0], r[1]) for r in rows])
    log(f"    {len(rows):,} tract FIPS codes")

    # ── 1d: Extra tracts from church_enrichment (not in lookup) ──
    log("  1d: Inserting extra tracts from church_enrichment...")
    rows = db.execute("""
        SELECT DISTINCT tract_fips, county_fips
        FROM church_enrichment 
        WHERE tract_fips IS NOT NULL AND tract_fips != ''
        AND tract_fips NOT IN (
            SELECT geo_code FROM census_geographies WHERE geo_type = 'tract_fips_11'
        )
    """).fetchall()
    run_many(db, """
        INSERT OR IGNORE INTO census_geographies (geo_type, geo_code, parent_code)
        VALUES ('tract_fips_11', ?, ?)
    """, rows)
    log(f"    {len(rows):,} extra tract FIPS codes")

    # ── 1e: ZIP5 from census_zip_data ──
    log("  1e: Inserting ZIP5 from census_zip_data...")
    rows = db.execute("""
        SELECT DISTINCT zip5 FROM census_zip_data 
        WHERE zip5 IS NOT NULL AND zip5 != ''
    """).fetchall()
    run_many(db, """
        INSERT OR IGNORE INTO census_geographies (geo_type, geo_code)
        VALUES ('zip5', ?)
    """, rows)
    log(f"    {len(rows):,} ZIP5 codes")

    # ── 1f: Countries from churches table ──
    log("  1f: Inserting countries from churches table...")
    # Built-in country name mapping (ISO 3166-1 alpha-2)
    COUNTRY_NAMES = {
        "US":"United States","CA":"Canada","GB":"United Kingdom","DE":"Germany",
        "FR":"France","IT":"Italy","ES":"Spain","BR":"Brazil","IN":"India",
        "JP":"Japan","CN":"China","RU":"Russia","AU":"Australia","MX":"Mexico",
        "ID":"Indonesia","NL":"Netherlands","CH":"Switzerland","SE":"Sweden",
        "NO":"Norway","DK":"Denmark","FI":"Finland","BE":"Belgium","AT":"Austria",
        "PT":"Portugal","GR":"Greece","IE":"Ireland","PL":"Poland","CZ":"Czechia",
        "HU":"Hungary","RO":"Romania","BG":"Bulgaria","SK":"Slovakia","SI":"Slovenia",
        "HR":"Croatia","RS":"Serbia","BA":"Bosnia and Herzegovina","AL":"Albania",
        "MK":"North Macedonia","ME":"Montenegro","LT":"Lithuania","LV":"Latvia",
        "EE":"Estonia","IS":"Iceland","LU":"Luxembourg","MT":"Malta","CY":"Cyprus",
        "TR":"Turkey","IL":"Israel","SA":"Saudi Arabia","AE":"United Arab Emirates",
        "QA":"Qatar","KW":"Kuwait","OM":"Oman","BH":"Bahrain","JO":"Jordan",
        "LB":"Lebanon","EG":"Egypt","ZA":"South Africa","NG":"Nigeria",
        "KE":"Kenya","GH":"Ghana","TZ":"Tanzania","UG":"Uganda","ET":"Ethiopia",
        "MA":"Morocco","DZ":"Algeria","TN":"Tunisia","LY":"Libya","SD":"Sudan",
        "AR":"Argentina","CL":"Chile","CO":"Colombia","PE":"Peru","VE":"Venezuela",
        "PH":"Philippines","TH":"Thailand","VN":"Vietnam","MY":"Malaysia",
        "KR":"South Korea","TW":"Taiwan","HK":"Hong Kong","SG":"Singapore",
        "PK":"Pakistan","BD":"Bangladesh","LK":"Sri Lanka","NP":"Nepal",
        "MM":"Myanmar","KH":"Cambodia","LA":"Laos","MN":"Mongolia",
        "NZ":"New Zealand","FJ":"Fiji","PG":"Papua New Guinea",
        "CU":"Cuba","DO":"Dominican Republic","PR":"Puerto Rico",
        "GT":"Guatemala","HN":"Honduras","SV":"El Salvador","NI":"Nicaragua",
        "CR":"Costa Rica","PA":"Panama","HT":"Haiti","JM":"Jamaica",
        "BO":"Bolivia","EC":"Ecuador","UY":"Uruguay","PY":"Paraguay","GY":"Guyana",
        "IR":"Iran","IQ":"Iraq","AF":"Afghanistan","SY":"Syria","YE":"Yemen",
        "BY":"Belarus","UA":"Ukraine","KZ":"Kazakhstan","UZ":"Uzbekistan",
        "AM":"Armenia","GE":"Georgia","AZ":"Azerbaijan","MD":"Moldova",
        "ZW":"Zimbabwe","ZM":"Zambia","MW":"Malawi","MZ":"Mozambique",
        "AO":"Angola","CM":"Cameroon","CI":"Cote d'Ivoire","SN":"Senegal",
        "ML":"Mali","BF":"Burkina Faso","NE":"Niger","TD":"Chad","SO":"Somalia",
        "MG":"Madagascar","CD":"DR Congo","CG":"Congo","GA":"Gabon",
        "MU":"Mauritius","SC":"Seychelles","RE":"Reunion","YT":"Mayotte",
        "PF":"French Polynesia","NC":"New Caledonia","WF":"Wallis and Futuna",
        "VA":"Vatican City","MC":"Monaco","LI":"Liechtenstein","SM":"San Marino",
        "AD":"Andorra","GI":"Gibraltar","FO":"Faroe Islands","IM":"Isle of Man",
        "JE":"Jersey","GG":"Guernsey","GL":"Greenland","BM":"Bermuda",
        "BS":"Bahamas","BB":"Barbados","TT":"Trinidad and Tobago","AW":"Aruba",
        "CW":"Curacao","SX":"Sint Maarten","BZ":"Belize","SR":"Suriname",
        "MV":"Maldives","BN":"Brunei","MO":"Macao","BT":"Bhutan",
        "TL":"Timor-Leste","SB":"Solomon Islands","VU":"Vanuatu","WS":"Samoa",
        "TO":"Tonga","KI":"Kiribati","MH":"Marshall Islands","FM":"Micronesia",
        "PW":"Palau","TV":"Tuvalu","NR":"Nauru","MV":"Maldives",
        "KP":"North Korea","SS":"South Sudan","EH":"Western Sahara",
        "CF":"Central African Republic","GQ":"Equatorial Guinea",
        "GW":"Guinea-Bissau","SL":"Sierra Leone","LR":"Liberia",
        "TG":"Togo","BJ":"Benin","GM":"Gambia","GN":"Guinea","CV":"Cape Verde",
        "ST":"Sao Tome and Principe","KM":"Comoros","DJ":"Djibouti",
        "ER":"Eritrea","RW":"Rwanda","BI":"Burundi","LS":"Lesotho",
        "SZ":"Eswatini","NA":"Namibia","BW":"Botswana",
        "MP":"Northern Mariana Islands","GU":"Guam","VI":"US Virgin Islands",
        "AS":"American Samoa","AX":"Aland Islands","PS":"Palestine",
        "BL":"Saint Barthelemy","MF":"Saint Martin","PM":"Saint Pierre and Miquelon",
        "SH":"Saint Helena","TF":"French Southern Territories","SJ":"Svalbard",
        "XK":"Kosovo","BQ":"Bonaire","CK":"Cook Islands","FK":"Falkland Islands",
        "NF":"Norfolk Island","NU":"Niue","TK":"Tokelau","CC":"Cocos Islands",
        "CX":"Christmas Island","MS":"Montserrat","IO":"British Indian Ocean Territory",
        "PN":"Pitcairn Islands","GS":"South Georgia","UM":"US Outlying Islands",
        "VG":"British Virgin Islands","KY":"Cayman Islands","AI":"Anguilla",
        "TC":"Turks and Caicos Islands","KN":"Saint Kitts and Nevis",
        "AG":"Antigua and Barbuda","DM":"Dominica","LC":"Saint Lucia",
        "VC":"Saint Vincent and the Grenadines","GD":"Grenada",
        "SA":"Saudi Arabia","QA":"Qatar","YE":"Yemen","AE":"UAE",
    }
    rows = db.execute("""
        SELECT DISTINCT country FROM churches 
        WHERE country IS NOT NULL AND country != ''
        ORDER BY country
    """).fetchall()
    inserts = []
    for r in rows:
        code = r[0]
        name = COUNTRY_NAMES.get(code.upper(), None)
        inserts.append((code, name))
    run_many(db, """
        INSERT OR IGNORE INTO census_geographies (geo_type, geo_code, geo_name)
        VALUES ('country_code_2', ?, ?)
    """, inserts)
    log(f"    {len(inserts):,} country codes")

    # ── 1g: County FIPS from church_enrichment (any extras) ──
    log("  1g: Inserting extra county FIPS from enrichment...")
    rows = db.execute("""
        SELECT DISTINCT county_fips FROM church_enrichment
        WHERE county_fips IS NOT NULL AND county_fips != ''
        AND county_fips NOT IN (
            SELECT geo_code FROM census_geographies WHERE geo_type = 'county_fips_5'
        )
    """).fetchall()
    run_many(db, """
        INSERT OR IGNORE INTO census_geographies (geo_type, geo_code)
        VALUES ('county_fips_5', ?)
    """, rows)
    log(f"    {len(rows):,} extra county FIPS from enrichment")

    db.commit()
    geo_count = db.execute("SELECT COUNT(*) FROM census_geographies").fetchone()[0]
    log(f"  Total geographies: {geo_count:,}")
    for gt in db.execute("SELECT geo_type, COUNT(*) FROM census_geographies GROUP BY geo_type ORDER BY geo_type").fetchall():
        log(f"    {gt[0]}: {gt[1]:,}")

# ────────────────────────────────────────────────────────────────
# Step 2: Create church_geographies
# ────────────────────────────────────────────────────────────────
log("\n[2] Creating church_geographies table...")
run(db, """
    CREATE TABLE IF NOT EXISTS church_geographies (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        church_id       INTEGER NOT NULL REFERENCES churches(id),
        geography_id    INTEGER NOT NULL REFERENCES census_geographies(id),
        geo_type        TEXT NOT NULL,   -- denormalized for fast filtering
        confidence      TEXT DEFAULT 'auto',  -- 'exact_match', 'spatial_join', 'manual'
        source          TEXT DEFAULT 'migration',
        created_at      TEXT DEFAULT (datetime('now')),
        UNIQUE(church_id, geography_id)
    )
""")
log("  Created church_geographies")

# Check if already populated
cg_count = db.execute("SELECT COUNT(*) FROM church_geographies").fetchone()[0]
log(f"  Already has {cg_count:,} links" if cg_count else "  Empty — will populate")

if cg_count == 0 or DRY_RUN:
    batch_size = 50000
    
    # ── 2a: County links from church_enrichment ──
    log("  2a: Linking churches to counties (from church_enrichment)...")
    total = db.execute("""
        SELECT COUNT(*) FROM church_enrichment ce
        JOIN census_geographies cg ON cg.geo_type = 'county_fips_5' 
            AND cg.geo_code = ce.county_fips
        WHERE ce.county_fips IS NOT NULL AND ce.county_fips != ''
    """).fetchone()[0]
    log(f"    {total:,} links to create")
    
    if not DRY_RUN and total > 0:
        offset = 0
        while offset < total:
            rows = db.execute("""
                SELECT ce.church_id, cg.id, 'county_fips_5'
                FROM church_enrichment ce
                JOIN census_geographies cg ON cg.geo_type = 'county_fips_5' 
                    AND cg.geo_code = ce.county_fips
                WHERE ce.county_fips IS NOT NULL AND ce.county_fips != ''
                LIMIT ? OFFSET ?
            """, (batch_size, offset)).fetchall()
            run_many(db, """
                INSERT OR IGNORE INTO church_geographies (church_id, geography_id, geo_type, source)
                VALUES (?, ?, ?, 'migration:enrichment')
            """, rows)
            db.commit()
            offset += len(rows)
            log(f"      {offset:,}/{total:,}")
    
    # ── 2b: Tract links from church_enrichment ──
    log("  2b: Linking churches to tracts (from church_enrichment)...")
    total = db.execute("""
        SELECT COUNT(*) FROM church_enrichment ce
        JOIN census_geographies cg ON cg.geo_type = 'tract_fips_11' 
            AND cg.geo_code = ce.tract_fips
        WHERE ce.tract_fips IS NOT NULL AND ce.tract_fips != ''
    """).fetchone()[0]
    log(f"    {total:,} links to create")
    
    if not DRY_RUN and total > 0:
        offset = 0
        while offset < total:
            rows = db.execute("""
                SELECT ce.church_id, cg.id, 'tract_fips_11'
                FROM church_enrichment ce
                JOIN census_geographies cg ON cg.geo_type = 'tract_fips_11' 
                    AND cg.geo_code = ce.tract_fips
                WHERE ce.tract_fips IS NOT NULL AND ce.tract_fips != ''
                LIMIT ? OFFSET ?
            """, (batch_size, offset)).fetchall()
            run_many(db, """
                INSERT OR IGNORE INTO church_geographies (church_id, geography_id, geo_type, source)
                VALUES (?, ?, ?, 'migration:enrichment')
            """, rows)
            db.commit()
            offset += len(rows)
            log(f"      {offset:,}/{total:,}")

    # ── 2c: FIPS links from churches table ──
    log("  2c: Linking churches to FIPS (from churches table)...")
    total = db.execute("""
        SELECT COUNT(*) FROM churches ch
        JOIN census_geographies cg ON cg.geo_type = 'county_fips_5' 
            AND cg.geo_code = substr('00000' || ch.fips, -5, 5)
        WHERE ch.fips IS NOT NULL AND ch.fips != '' AND ch.fips != '0'
        AND ch.id NOT IN (
            SELECT church_id FROM church_geographies WHERE geo_type = 'county_fips_5'
        )
    """).fetchone()[0]
    log(f"    {total:,} new links to create")
    
    if not DRY_RUN and total > 0:
        offset = 0
        while offset < total:
            rows = db.execute("""
                SELECT ch.id, cg.id, 'county_fips_5'
                FROM churches ch
                JOIN census_geographies cg ON cg.geo_type = 'county_fips_5' 
                    AND cg.geo_code = substr('00000' || ch.fips, -5, 5)
                WHERE ch.fips IS NOT NULL AND ch.fips != '' AND ch.fips != '0'
                AND ch.id NOT IN (
                    SELECT church_id FROM church_geographies WHERE geo_type = 'county_fips_5'
                )
                LIMIT ? OFFSET ?
            """, (batch_size, offset)).fetchall()
            run_many(db, """
                INSERT OR IGNORE INTO church_geographies (church_id, geography_id, geo_type, source)
                VALUES (?, ?, ?, 'migration:churches_fips')
            """, rows)
            db.commit()
            offset += len(rows)
            log(f"      {offset:,}/{total:,}")

    # ── 2d: ZIP5 links from churches table ──
    log("  2d: Linking churches to ZIP5 (from churches.zip5)...")
    total = db.execute("""
        SELECT COUNT(*) FROM churches ch
        JOIN census_geographies cg ON cg.geo_type = 'zip5' AND cg.geo_code = ch.zip5
        WHERE ch.zip5 IS NOT NULL AND ch.zip5 != ''
    """).fetchone()[0]
    log(f"    {total:,} links to create")
    
    if not DRY_RUN and total > 0:
        offset = 0
        while offset < total:
            rows = db.execute("""
                SELECT ch.id, cg.id, 'zip5'
                FROM churches ch
                JOIN census_geographies cg ON cg.geo_type = 'zip5' AND cg.geo_code = ch.zip5
                WHERE ch.zip5 IS NOT NULL AND ch.zip5 != ''
                LIMIT ? OFFSET ?
            """, (batch_size, offset)).fetchall()
            run_many(db, """
                INSERT OR IGNORE INTO church_geographies (church_id, geography_id, geo_type, source)
                VALUES (?, ?, ?, 'migration:churches_zip5')
            """, rows)
            db.commit()
            offset += len(rows)
            log(f"      {offset:,}/{total:,}")

    # ── 2e: Country links from churches table ──
    log("  2e: Linking churches to countries...")
    total = db.execute("""
        SELECT COUNT(*) FROM churches ch
        JOIN census_geographies cg ON cg.geo_type = 'country_code_2' AND cg.geo_code = ch.country
        WHERE ch.country IS NOT NULL AND ch.country != ''
    """).fetchone()[0]
    log(f"    {total:,} links to create")
    
    if not DRY_RUN and total > 0:
        offset = 0
        while offset < total:
            rows = db.execute("""
                SELECT ch.id, cg.id, 'country_code_2'
                FROM churches ch
                JOIN census_geographies cg ON cg.geo_type = 'country_code_2' AND cg.geo_code = ch.country
                WHERE ch.country IS NOT NULL AND ch.country != ''
                LIMIT ? OFFSET ?
            """, (batch_size, offset)).fetchall()
            run_many(db, """
                INSERT OR IGNORE INTO church_geographies (church_id, geography_id, geo_type, source)
                VALUES (?, ?, ?, 'migration:churches_country')
            """, rows)
            db.commit()
            offset += len(rows)
            log(f"      {offset:,}/{total:,}")

    db.commit()
    final_count = db.execute("SELECT COUNT(*) FROM church_geographies").fetchone()[0]
    log(f"  Total church-geography links: {final_count:,}")
    for gt in db.execute("""
        SELECT geo_type, COUNT(*) FROM church_geographies 
        GROUP BY geo_type ORDER BY COUNT(*) DESC
    """).fetchall():
        log(f"    {gt[0]}: {gt[1]:,}")

# ────────────────────────────────────────────────────────────────
# Step 3: Create indices
# ────────────────────────────────────────────────────────────────
log("\n[3] Creating indices...")
run(db, "CREATE INDEX IF NOT EXISTS idx_cg_type_code ON census_geographies(geo_type, geo_code)")
run(db, "CREATE INDEX IF NOT EXISTS idx_cg_parent ON census_geographies(parent_code)")
run(db, "CREATE INDEX IF NOT EXISTS idx_chg_church ON church_geographies(church_id)")
run(db, "CREATE INDEX IF NOT EXISTS idx_chg_geo ON church_geographies(geography_id)")
run(db, "CREATE INDEX IF NOT EXISTS idx_chg_type ON church_geographies(geo_type)")
db.commit()

# ────────────────────────────────────────────────────────────────
# Step 4: Drop empty county_* columns from church_enrichment
# ────────────────────────────────────────────────────────────────
log("\n[4] Cleaning up empty columns from church_enrichment...")

# These county_* columns are all NULL — they were schema placeholders
# that were never populated. They waste space in a 735K-row table.
empty_cols = [
    'county_total_pop', 'county_median_hh_income', 'county_poverty_rate',
    'county_unemployment_rate', 'county_bachelors_25_64', 'county_graduate_degree',
    'county_white_pct', 'county_black_pct', 'county_asian_pct', 'county_hispanic_pct',
    'county_median_home_value', 'county_median_gross_rent', 'county_owner_pct',
    'county_mean_commute_min', 'county_drove_alone_pct', 'county_wfh_pct',
    'county_gini_index', 'county_income_per_capita', 'county_median_age',
]

for col in empty_cols:
    cnt = db.execute(f"SELECT COUNT(*) FROM church_enrichment WHERE {col} IS NOT NULL AND {col} != '' AND {col} != 0").fetchone()[0]
    log(f"  {col}: {cnt:,} non-null values")
    if cnt == 0:
        if DRY_RUN:
            log(f"    Would DROP column {col}")
        else:
            try:
                db.execute(f"ALTER TABLE church_enrichment DROP COLUMN {col}")
                log(f"    DROPPED {col}")
            except Exception as e:
                log(f"    FAILED to drop {col}: {e}")

db.commit()

# ────────────────────────────────────────────────────────────────
# Step 5: Log provenance
# ────────────────────────────────────────────────────────────────
log("\n[5] Logging provenance...")
if not DRY_RUN:
    geo = db.execute("SELECT COUNT(*) FROM census_geographies").fetchone()[0]
    chg = db.execute("SELECT COUNT(*) FROM church_geographies").fetchone()[0]
    run(db, """
        INSERT INTO provenance_log (source, action, timestamp, details)
        VALUES (?, ?, datetime('now'), ?)
    """, ('migration', 'migrate_census_geo.py', 
          f'Created census_geographies ({geo:,} rows) and church_geographies ({chg:,} links). Dropped empty county_* columns.'))
    db.commit()

# ────────────────────────────────────────────────────────────────
# Done
# ────────────────────────────────────────────────────────────────
elapsed = time.time() - t0
log(f"\n{'='*60}")
log(f"Migration complete in {elapsed/60:.1f} minutes")
log(f"{'='*60}")

# Summary
geo = db.execute("SELECT COUNT(*) FROM census_geographies").fetchone()[0]
chg = db.execute("SELECT COUNT(*) FROM church_geographies").fetchone()[0]
log(f"\nFinal summary:")
log(f"  census_geographies:    {geo:,} rows")
for gt in db.execute("SELECT geo_type, COUNT(*) FROM census_geographies GROUP BY geo_type ORDER BY geo_type").fetchall():
    log(f"    {gt[0]}: {gt[1]:,}")
log(f"  church_geographies:   {chg:,} links")
for gt in db.execute("SELECT geo_type, COUNT(*) FROM church_geographies GROUP BY geo_type ORDER BY COUNT(*) DESC").fetchall():
    log(f"    {gt[0]}: {gt[1]:,}")

db.close()
