"""Step 2 v2: Backfill holy_site_id + enrich with indexes for speed."""
import sqlite3, time

db = sqlite3.connect('E:/grid/churches.db')
R = 3

# --- Create temp: holy_sites grid ---
t0 = time.time()
db.execute("DROP TABLE IF EXISTS _hs_grid")
db.execute(f"""
    CREATE TEMP TABLE _hs_grid AS
    SELECT site_id, ROUND(lat,{R}) as glat, ROUND(lon,{R}) as glon,
           faith, tradition, denomination as hs_denom,
           landmark_type, is_landmark, heritage_status,
           height_m, width_m, length_m, area_m2, capacity,
           construction_year, website as hs_website,
           source_primary, source_secondary,
           osm_id, osm_type, osm_version, osm_timestamp,
           wikidata_qid, wikidata_last_modified,
           overture_id, confidence_score,
           diocese as hs_diocese
    FROM holy_sites WHERE lat IS NOT NULL
""")
db.execute("CREATE INDEX idx_hs_gl ON _hs_grid(glat, glon)")
print(f"holy_sites grid: {db.execute('SELECT COUNT(*) FROM _hs_grid').fetchone()[0]:,} rows in {time.time()-t0:.1f}s")

# --- Create temp: churches grid ---
t0 = time.time()
db.execute("DROP TABLE IF EXISTS _ch_grid")
db.execute(f"""
    CREATE TEMP TABLE _ch_grid AS
    SELECT id, ROUND(latitude,{R}) as glat, ROUND(longitude,{R}) as glon
    FROM churches WHERE latitude IS NOT NULL AND holy_site_id IS NULL
""")
db.execute("CREATE INDEX idx_ch_gl ON _ch_grid(glat, glon)")
print(f"churches grid: {db.execute('SELECT COUNT(*) FROM _ch_grid').fetchone()[0]:,} rows in {time.time()-t0:.1f}s")

# --- Create mapping: church_id -> MIN(site_id) ---
t0 = time.time()
db.execute("DROP TABLE IF EXISTS _ch_hs_map")
db.execute("""
    CREATE TEMP TABLE _ch_hs_map AS
    SELECT c.id as church_id, MIN(h.site_id) as site_id
    FROM _ch_grid c
    INNER JOIN _hs_grid h ON h.glat = c.glat AND h.glon = c.glon
    GROUP BY c.id
""")
db.execute("CREATE INDEX idx_map_ch ON _ch_hs_map(church_id)")
map_count = db.execute("SELECT COUNT(*) FROM _ch_hs_map").fetchone()[0]
print(f"Mapping table: {map_count:,} matches in {time.time()-t0:.1f}s")

# --- UPDATE holy_site_id ---
t0 = time.time()
db.execute("""
    UPDATE churches SET holy_site_id = (
        SELECT m.site_id FROM _ch_hs_map m WHERE m.church_id = churches.id
    )
    WHERE EXISTS (SELECT 1 FROM _ch_hs_map m WHERE m.church_id = churches.id)
""")
print(f"Backfilled holy_site_id: {db.execute('SELECT changes()').fetchone()[0]:,} in {time.time()-t0:.1f}s")

# --- Bulk enrich matched churches ---
t0 = time.time()
enrichments = [
    ("faith", "h.faith"),
    ("tradition", "h.tradition"),
    ("landmark_type", "h.landmark_type"),
    ("is_landmark", "h.is_landmark"),
    ("heritage_status", "h.heritage_status"),
    ("height_m", "h.height_m"),
    ("width_m", "h.width_m"),
    ("length_m", "h.length_m"),
    ("area_m2", "h.area_m2"),
    ("capacity", "h.capacity"),
    ("source_primary", "h.source_primary"),
    ("source_secondary", "h.source_secondary"),
    ("osm_id", "h.osm_id"),
    ("osm_type", "h.osm_type"),
    ("osm_version", "h.osm_version"),
    ("osm_timestamp", "h.osm_timestamp"),
    ("wikidata_qid", "h.wikidata_qid"),
    ("wikidata_last_modified", "h.wikidata_last_modified"),
    ("overture_id", "h.overture_id"),
    ("confidence_score", "h.confidence_score"),
]

for ch_col, hs_expr in enrichments:
    db.execute(f"""
        UPDATE churches SET {ch_col} = (
            SELECT {hs_expr} FROM _hs_grid h
            INNER JOIN _ch_hs_map m ON m.site_id = h.site_id
            WHERE m.church_id = churches.id
        )
        WHERE holy_site_id IS NOT NULL AND {ch_col} IS NULL
    """)
    n = db.execute("SELECT changes()").fetchone()[0]
    if n: print(f"  {ch_col}: {n:,}")

# building_year
db.execute("""
    UPDATE churches SET building_year = (
        SELECT h.construction_year FROM _hs_grid h
        INNER JOIN _ch_hs_map m ON m.site_id = h.site_id
        WHERE m.church_id = churches.id
    )
    WHERE holy_site_id IS NOT NULL AND building_year IS NULL
""")
print(f"  building_year: {db.execute('SELECT changes()').fetchone()[0]:,}")

# diocese
db.execute("""
    UPDATE churches SET diocese = (
        SELECT h.hs_diocese FROM _hs_grid h
        INNER JOIN _ch_hs_map m ON m.site_id = h.site_id
        WHERE m.church_id = churches.id
    )
    WHERE holy_site_id IS NOT NULL AND diocese IS NULL
""")
print(f"  diocese: {db.execute('SELECT changes()').fetchone()[0]:,}")

# Tag source
db.execute("""
    UPDATE churches SET source = COALESCE(source || '+holy_sites_enrichment', 'holy_sites_enrichment')
    WHERE holy_site_id IS NOT NULL AND source NOT LIKE '%holy_sites%'
""")
print(f"  source: {db.execute('SELECT changes()').fetchone()[0]:,}")

print(f"\nEnrichment done in {time.time()-t0:.1f}s")
total = db.execute("SELECT COUNT(*) FROM churches WHERE holy_site_id IS NOT NULL").fetchone()[0]
print(f"Churches linked to holy_sites: {total:,}")

db.execute("DROP TABLE IF EXISTS _hs_grid")
db.execute("DROP TABLE IF EXISTS _ch_grid")
db.execute("DROP TABLE IF EXISTS _ch_hs_map")
db.commit()
db.close()
