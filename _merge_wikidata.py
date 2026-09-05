"""
_merge_wikidata.py
Merge 780,737 wikidata_staging rows into churches.db.

Key decisions:
  - 100% of rows have GPS (verified)
  - Skip coordinate clusters where 20+ QIDs share identical coords (admin centroids, not churches)
  - One row per wikidata_qid (dedup by QID, best data wins)
  - Insert bare churches record + church_location (country from staging)
  - Admin0/1/2 codes left NULL (require spatial join pipeline)

780,737 rows -> after coord-filter + dedup -> ~270-350K actual churches to insert
"""

import sqlite3, sys
from datetime import datetime, timezone

DB = 'E:/grid/churches.db'
STAGING = 'E:/grid/data/wikidata_staging/wikidata_staging.db'
DRY_RUN = '--write' not in sys.argv

# Coord cluster threshold: if N+ QIDs share identical coords, skip those coords
# (likely Wikidata admin boundary centroids, not real church locations)
COORD_CLUSTER_THRESHOLD = 20

conn = sqlite3.connect(DB)
conn.execute('PRAGMA journal_mode=WAL')
c = conn.cursor()

conn_s = sqlite3.connect(STAGING)
cs = conn_s.cursor()

print('DRY RUN' if DRY_RUN else 'LIVE RUN')
print('Coord cluster threshold: %d' % COORD_CLUSTER_THRESHOLD)
print()

# ── Taxonomy map: (faith, landmark_type) -> (taxonomy_id, tradition) ────────────
FAITH_LANDMARK_TAX = {
    ('Shinto',   'shrine'):   (534, 'Shinto Shrine'),
    ('Christian', 'church'):   (2,   'Christian'),
    ('Christian', 'abbey'):    (120, 'Christian/Monastic/Abbey'),
    ('Christian', 'cathedral'):(79,  'Episcopal/Anglican'),
    ('Hindu',     'temple'):  (67,  'Hindu Temple'),
    ('Islam',     'mosque'):  (4,   'Islam'),
    ('Jewish',    'synagogue'):(242, 'Judaism/Rabbinic'),
    ('Buddhist',  'temple'):  (65,  'Buddhist Temple'),
    ('Buddhist',  'shrine'):  (9,   'Buddhist'),
}

def get_taxonomy(faith, landmark_type):
    key = (faith.strip().title() if faith else '',
           landmark_type.strip().lower() if landmark_type else '')
    return FAITH_LANDMARK_TAX.get(key, (None, None))

# ── Step 1: Total staging counts ───────────────────────────────────────────────
total = cs.execute("SELECT COUNT(*) FROM holy_sites_staging").fetchone()[0]
unique_qids = cs.execute("SELECT COUNT(DISTINCT wikidata_qid) FROM holy_sites_staging").fetchone()[0]
print('[1] Staging: %d rows, %d unique QIDs' % (total, unique_qids))

# ── Step 2: Find coordinate clusters to exclude ────────────────────────────────
# These are coords where 20+ distinct QIDs share the same point
# (Wikidata admin boundary centroids, not real church locations)
print()
print('[2] Finding coordinate clusters (threshold >= %d QIDs)...' % COORD_CLUSTER_THRESHOLD)
cluster_sql = """
    SELECT lat, lon, COUNT(DISTINCT wikidata_qid) as qid_count
    FROM holy_sites_staging
    WHERE lat IS NOT NULL AND lon IS NOT NULL AND abs(lat) > 0.001 AND abs(lon) > 0.001
    GROUP BY lat, lon
    HAVING COUNT(DISTINCT wikidata_qid) >= :threshold
    ORDER BY qid_count DESC
"""
coord_clusters = cs.execute(cluster_sql, {'threshold': COORD_CLUSTER_THRESHOLD}).fetchall()
print('    Clusters found: %d' % len(coord_clusters))
if coord_clusters:
    top_clusters = coord_clusters[:10]
    total_cluster_rows = sum(r[2] for r in coord_clusters)
    print('    Top clusters:')
    for lat, lon, cnt in top_clusters:
        print('      lat=%.6f lon=%.6f  ->  %d QIDs' % (lat, lon, cnt))
    print('    Total rows in all clusters: %d' % total_cluster_rows)

# Build set of excluded coords
excluded_coords = set()
for lat, lon, cnt in coord_clusters:
    excluded_coords.add((round(lat, 6), round(lon, 6)))

# Count rows affected by coord filter
if excluded_coords:
    affected = cs.execute("""
        SELECT COUNT(DISTINCT wikidata_qid)
        FROM holy_sites_staging
        WHERE lat IS NOT NULL AND lon IS NOT NULL
        AND abs(lat) > 0.001 AND abs(lon) > 0.001
        AND ROUND(lat, 6) IN (%s) AND ROUND(lon, 6) IN (%s)
    """ % (','.join(str(c[0]) for c in excluded_coords),
           ','.join(str(c[1]) for c in excluded_coords))).fetchone()[0]
    print('    QIDs affected by coord filter: %d' % affected)

# ── Step 3: QID dedup with coord filter ───────────────────────────────────────
# One row per QID, best data wins (GPS completeness > name > faith),
# but skip QIDs whose best row is at an excluded coord cluster
print()
print('[3] Deduplicating by QID...')

dedup_sql = """
    SELECT
        w.wikidata_qid,
        w.name,
        w.lat,
        w.lon,
        w.country,
        w.landmark_type,
        w.faith,
        w.tradition,
        w.batch_id,
        ROW_NUMBER() OVER (
            PARTITION BY w.wikidata_qid
            ORDER BY
                CASE WHEN w.lat IS NOT NULL AND w.lon IS NOT NULL
                     AND abs(w.lat) > 0.001 AND abs(w.lon) > 0.001
                     AND ROUND(w.lat,6) NOT IN (%s)
                     AND ROUND(w.lon,6) NOT IN (%s)
                THEN 1 ELSE 0 END DESC,
                CASE WHEN w.name IS NOT NULL AND w.name != '' THEN 1 ELSE 0 END DESC,
                CASE WHEN w.faith IS NOT NULL AND w.faith != '' THEN 1 ELSE 0 END DESC,
                w.name ASC
        ) AS rn
    FROM holy_sites_staging w
""" % (','.join(str(c[0]) for c in excluded_coords),
       ','.join(str(c[1]) for c in excluded_coords))

deduped = cs.execute(dedup_sql).fetchall()
# Only keep rn=1 AND that row must have passed coord filter (lat/lon not in excluded set)
coord_excluded_dedup = 0
rows_to_insert = []
for row in deduped:
    qid, name, lat, lon, country, landmark_type, faith, tradition, batch_id, rn = row
    if rn == 1:
        if lat is not None and lon is not None and abs(lat) > 0.001 and abs(lon) > 0.001:
            coord_key = (round(lat, 6), round(lon, 6))
            if coord_key in excluded_coords:
                coord_excluded_dedup += 1
                continue
        rows_to_insert.append(row)

print('    After coord-filter + dedup: %d unique QIDs to insert' % len(rows_to_insert))
print('    Dedup rows excluded due to coord cluster: %d' % coord_excluded_dedup)

# ── Step 4: Faith/landmark breakdown for the full staging set ─────────────────
# (informational only - the deduped set has the same distribution)
print()
print('[4] Faith/landmark breakdown (full staging, informational):')
auto_map = 0
need_manual = 0
breakdown = cs.execute("""
    SELECT faith, landmark_type, COUNT(*) n
    FROM holy_sites_staging
    GROUP BY faith, landmark_type
    ORDER BY n DESC
""").fetchall()
for faith, lt, n in breakdown:
    tax_id, tax_name = get_taxonomy(faith, lt)
    status = 'AUTO' if tax_id else 'NEED'
    if tax_id:
        auto_map += n
    else:
        need_manual += n
    print('  %s %-10s/%-12s: %7d rows  -> tax_id=%s' % (status, str(faith)[:10], str(lt)[:12], n, tax_id))
print('  Auto-mapped: %d (%.1f%%)' % (auto_map, auto_map*100.0/(auto_map+need_manual) if (auto_map+need_manual) > 0 else 0))

if DRY_RUN:
    print()
    print('*** DRY RUN - re-run with --write to apply ***')
    conn.close()
    conn_s.close()
    sys.exit(0)

# ── [LIVE RUN] ────────────────────────────────────────────────────────────────
print()
print('[LIVE] Starting insert at %s' % datetime.now().strftime('%H:%M:%S'))

inserted = 0
start_time = datetime.now(timezone.utc).isoformat()
BATCH = 500

for i in range(0, len(rows_to_insert), BATCH):
    batch = rows_to_insert[i:i+BATCH]
    for row in batch:
        qid, name, lat, lon, country, landmark_type, faith, tradition, batch_id, rn = row
        tax_id, tax_name = get_taxonomy(faith, landmark_type)
        normalized = name.lower().strip() if name else ''

        # Insert into churches
        c.execute("""
            INSERT INTO churches (id, name, normalized_name, latitude, longitude,
                source, landmark_type, faith, taxonomy_id, status, holy_site_id, last_updated)
            VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, datetime('now'))
        """, (name, normalized, lat, lon,
              'wikidata_holy_sites:%s' % batch_id,
              landmark_type, faith, tax_id, qid))

        church_id = c.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Insert into church_location (country from staging, admin codes NULL - spatial join needed)
        if country:
            c.execute("""
                INSERT INTO church_location (church_id, country)
                VALUES (?, ?)
            """, (church_id, country))

        inserted += 1

    conn.commit()
    if (i + BATCH) % 50000 == 0:
        print('    %d / %d done...' % (inserted, len(rows_to_insert)))

print()
print('[LIVE] Inserted: %d churches + church_location rows' % inserted)

# Provenance log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_inserted, churches_updated, fields_populated, records_attempted,
        status, notes)
    VALUES (
        'merge_wikidata_staging', '_merge_wikidata.py',
        ?, datetime('now'),
        ?, 0,
        'taxonomy_id,faith,landmark_type,holy_site_id,country,church_location',
        ?,
        'completed',
        ?
    )
""", (start_time, inserted, len(rows_to_insert),
     'Deduped %d->%d by QID; coord-filter excluded %d clusters (%d dedup rows); '
     'auto-tax %.1f%%; church_location.country set; admin0/1/2 NULL'
     % (total, inserted, len(coord_clusters), coord_excluded_dedup,
        auto_map*100.0/(auto_map+need_manual) if (auto_map+need_manual) > 0 else 0)))
conn.commit()

max_id = c.execute('SELECT MAX(id) FROM churches').fetchone()[0]
print()
print('Done at %s' % datetime.now().strftime('%H:%M:%S'))
print('ID range: %d - %d' % (max_id - inserted + 1, max_id))

conn.close()
conn_s.close()
