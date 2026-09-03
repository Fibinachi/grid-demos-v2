"""
Merge Mapping Saints dataset into churches.db.

Source: saints.dh.gu.se — 3,773 medieval religious places (CC-BY-SA 4.0)
Mostly Nordic: Sweden 3,248, Finland 277, Norway 133, others.

Strategy:
  1. Populate mapping_saints_* columns via SQL JOIN with mapping_saints table
  2. Add mapping_saints_wikidata column to churches table
  3. Log provenance
"""
import sqlite3, sys, os, json
from datetime import datetime, timezone

DB = 'churches.db'
DRY_RUN = '--dry-run' in sys.argv
CHUNK = 500

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
SOURCE = 'merge_mapping_saints'

print("=" * 70)
print("MERGE MAPPING SAINTS")
print("=" * 70)
print(f"DRY RUN: {DRY_RUN}")

# ================================================================
# Phase 0: Check if mapping_saints_wikidata column exists
# ================================================================
c.execute("PRAGMA table_info(churches)")
churches_cols = {r[1] for r in c.fetchall()}

if 'mapping_saints_wikidata' not in churches_cols:
    print("\n--- Adding mapping_saints_wikidata column ---")
    if not DRY_RUN:
        c.execute("ALTER TABLE churches ADD COLUMN mapping_saints_wikidata TEXT")
        db.commit()
        print("  ✅ Column added")
else:
    print("\n  Column mapping_saints_wikidata already exists")

# ================================================================
# Phase 1: Populate mapping_saints columns from mapping_saints table
# ================================================================
print("\n--- Phase 1: Populate mapping_saints columns ---")

# Check mapping_saints table exists and has data
c.execute("SELECT COUNT(*) FROM mapping_saints")
ms_count = c.fetchone()[0]
print(f"  mapping_saints table: {ms_count:,} rows")

# Count churches with mapping_saints_id but unpopulated columns
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE mapping_saints_id IS NOT NULL 
      AND (mapping_saints_matched IS NULL OR mapping_saints_matched = '')
""")
to_update = c.fetchone()[0]
print(f"  Churches with mapping_saints_id to populate: {to_update:,}")

if to_update > 0 and not DRY_RUN:
    # Use a single UPDATE FROM JOIN pattern
    # SQLite doesn't support UPDATE FROM directly, so we'll use a temp table approach
    
    # Create temp table with mapping_saints data joined on ms_id
    c.execute("""
        CREATE TEMP TABLE ms_merge AS
        SELECT ch.rowid as church_rowid,
               ms.place_type,
               ms.diocese,
               ms.cults_json,
               ms.wikidata,
               ms.lat,
               ms.lon
        FROM churches ch
        JOIN mapping_saints ms ON ch.mapping_saints_id = ms.ms_id
        WHERE ch.mapping_saints_id IS NOT NULL
          AND (ch.mapping_saints_matched IS NULL OR ch.mapping_saints_matched = '')
    """)
    temp_count = c.execute("SELECT COUNT(*) FROM ms_merge").fetchone()[0]
    print(f"  Temp table created: {temp_count:,} rows")
    
    # Update place_type
    c.execute("""
        UPDATE churches SET mapping_saints_place_type = (
            SELECT place_type FROM ms_merge WHERE ms_merge.church_rowid = churches.rowid
        ) WHERE rowid IN (SELECT church_rowid FROM ms_merge WHERE place_type IS NOT NULL)
    """)
    print(f"  Updated place_type")
    
    # Update diocese
    c.execute("""
        UPDATE churches SET mapping_saints_diocese = (
            SELECT diocese FROM ms_merge WHERE ms_merge.church_rowid = churches.rowid
        ) WHERE rowid IN (SELECT church_rowid FROM ms_merge WHERE diocese IS NOT NULL)
    """)
    print(f"  Updated diocese")
    
    # Update saints (cults_json)
    c.execute("""
        UPDATE churches SET mapping_saints_saints = (
            SELECT cults_json FROM ms_merge WHERE ms_merge.church_rowid = churches.rowid
        ) WHERE rowid IN (SELECT church_rowid FROM ms_merge WHERE cults_json IS NOT NULL)
    """)
    print(f"  Updated saints")
    
    # Update wikidata
    c.execute("""
        UPDATE churches SET mapping_saints_wikidata = (
            SELECT wikidata FROM ms_merge WHERE ms_merge.church_rowid = churches.rowid
        ) WHERE rowid IN (SELECT church_rowid FROM ms_merge WHERE wikidata IS NOT NULL)
    """)
    print(f"  Updated wikidata")
    
    # Update matched flag and timestamp
    c.execute("""
        UPDATE churches SET 
            mapping_saints_matched = 'matched',
            mapping_saints_updated = ?
        WHERE rowid IN (SELECT church_rowid FROM ms_merge)
    """, (NOW,))
    print(f"  Updated matched flag")
    
    # Update GPS from mapping_saints if churches have NULL coordinates
    c.execute("""
        UPDATE churches SET 
            latitude = (SELECT lat FROM ms_merge WHERE ms_merge.church_rowid = churches.rowid),
            longitude = (SELECT lon FROM ms_merge WHERE ms_merge.church_rowid = churches.rowid)
        WHERE rowid IN (SELECT church_rowid FROM ms_merge WHERE lat IS NOT NULL AND lon IS NOT NULL)
          AND (latitude IS NULL OR longitude IS NULL)
    """)
    updated_gps = c.execute("""
        SELECT COUNT(*) FROM churches WHERE rowid IN (
            SELECT church_rowid FROM ms_merge WHERE lat IS NOT NULL AND lon IS NOT NULL
        ) AND latitude IS NOT NULL AND longitude IS NOT NULL
    """).fetchone()[0]
    print(f"  Updated GPS for {updated_gps} churches")
    
    # Drop temp table
    c.execute("DROP TABLE IF EXISTS ms_merge")
    
    db.commit()
    print(f"  ✅ Phase 1 complete")

# ================================================================
# Phase 2: Update taxonomy/faith for Mapping Saints churches
# ================================================================
print("\n--- Phase 2: Set faith/taxonomy for MS churches ---")

# Mapping Saints places are medieval Christian churches
c.execute("""
    UPDATE churches SET faith = 'Christian' 
    WHERE mapping_saints_id IS NOT NULL 
      AND mapping_saints_matched = 'matched'
      AND (faith IS NULL OR faith = '')
""")
updated_faith = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE mapping_saints_id IS NOT NULL AND mapping_saints_matched = 'matched' 
    AND faith = 'Christian'
""").fetchone()[0]
print(f"  Churches set to Christian faith: {updated_faith:,}")

# ================================================================
# Phase 3: Handle the 21 unmatched places
# ================================================================
print("\n--- Phase 3: Unmatched places ---")

# Get IDs already in DB
cur = c.execute("SELECT DISTINCT mapping_saints_id FROM churches WHERE mapping_saints_id IS NOT NULL")
existing_ids = {r[0] for r in cur.fetchall()}

# Load JSON to find unmatched
import json as _json
with open('data/sources/mapping_saints_places.json', encoding='utf-8') as f:
    data = _json.load(f)
json_places = data['results']

unmatched_ids = [p for p in json_places if p['id'] not in existing_ids]
print(f"  Unmatched JSON places: {len(unmatched_ids)}")

# Most are "Unknown" or generic sea locations — log them but don't create records
for p in unmatched_ids:
    name = p.get('name', '?')
    country = p.get('country', '?')
    wd = p.get('wikidata', '?')
    print(f"    ⚠ Skipping: id={p['id']} '{name}' ({country}) wikidata={wd}")

# ================================================================
# Log provenance
# ================================================================
if not DRY_RUN:
    updated_total = c.execute("""
        SELECT COUNT(*) FROM churches WHERE mapping_saints_matched = 'matched'
    """).fetchone()[0]
    
    db.execute("""
        INSERT INTO provenance_log 
        (source, script_name, started_at, completed_at, churches_updated, 
         churches_inserted, fields_populated, records_attempted, records_matched, 
         status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (SOURCE, 'scripts/enrichment/merge_mapping_saints.py', NOW, NOW,
          updated_total, 0,
          'mapping_saints_place_type,mapping_saints_diocese,mapping_saints_saints,mapping_saints_wikidata,mapping_saints_matched,mapping_saints_updated',
          ms_count, updated_total,
          'completed',
          f'Merged Mapping Saints: {updated_total} matched from mapping_saints table. Source: saints.dh.gu.se (CC-BY-SA 4.0). 21 unmatchable places skipped.'))
    db.commit()
    
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    print("\n  ✅ Provenance logged and WAL checkpointed")

# ================================================================
# Summary
# ================================================================
print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
print(f"  Churches updated: {to_update if not DRY_RUN else '? (dry run)'}")
matched_count = c.execute("SELECT COUNT(*) FROM churches WHERE mapping_saints_matched = 'matched'").fetchone()[0]
print(f"  Total confirmed matched: {matched_count:,}")
ms_id_count = c.execute("SELECT COUNT(*) FROM churches WHERE mapping_saints_id IS NOT NULL").fetchone()[0]
print(f"  Total with mapping_saints_id: {ms_id_count:,}")
print(f"  Unmatched places skipped: {len(unmatched_ids)}")
print(f"  DRY RUN: {DRY_RUN}")

db.close()
print("\nDone!")
