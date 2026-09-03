"""
Collapse Judaism entries sharing the same GPS coordinates into a JSON
'ministries' column on the primary entry.

Many synagogues host multiple congregations, minyanim, kollels, and services
in the same building. These are stored as separate church entries but should
be consolidated — the building is the physical entity; the rest are ministries.

Strategy:
1. Add `ministries` TEXT column (JSON array) and `merged_into` INTEGER to churches
2. Find clusters by ROUND(lat,5) + ROUND(lon,5) + city + country
3. Pick the best "primary" per cluster (prefer 'synagogue' type, most complete contact data)
4. Serialize secondary entries as JSON ministries on the primary row
5. Mark secondary entries with merged_into pointing to primary

Usage:
    python scripts/db_maintenance/collapse_shared_jewish.py          # run for real
    python scripts/db_maintenance/collapse_shared_jewish.py --dry-run  # preview
"""
import sqlite3, json, sys
from datetime import datetime, timezone

dry_run = '--dry-run' in sys.argv

conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()

TYPE_PREFERENCE = ['synagogue', 'chabad_house', 'yeshiva', 'community_center',
                   'kollel', 'school', 'organization', 'hillel', 'mikveh',
                   'cemetery', 'museum', 'retail', 'food', 'senior_home', None]

def score_entry(row):
    """Score an entry for primacy. Higher is better primary candidate."""
    id_, name, city, state, country, lat, lon, landmark_type, tradition = row[:9]
    name_str = str(name or '')
    score = 0
    # Prefer 'synagogue' type as primary
    lt = landmark_type or ''
    type_rank = TYPE_PREFERENCE.index(lt) if lt in TYPE_PREFERENCE else len(TYPE_PREFERENCE)
    score += (len(TYPE_PREFERENCE) - type_rank) * 10
    # Prefer entries with more complete names
    if name_str and len(name_str) > 10:
        score += 5
    # Prefer entries with a tradition set
    if tradition and tradition not in ('', 'Rabbinic'):
        score += 3
    # Prefer shorter, cleaner names (likely the building name, not a specific service)
    if name_str and not any(x in name_str.upper() for x in ['CONGREGATION', 'CONG ', 'MINYAN', 'KOLLEL']):
        score += 2
    return score

def make_ministry_json(row):
    """Serialize a secondary entry into a ministry dict."""
    id_, name, city, state, country, lat, lon, landmark_type, tradition = row[:9]
    ministry = {'church_id': id_}
    if name: ministry['name'] = name
    if landmark_type: ministry['type'] = landmark_type
    if tradition and tradition not in ('', 'Rabbinic'): ministry['tradition'] = tradition
    return ministry

print("=" * 60)
print("Jewish Shared-Location Collapse — Ministries JSON")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# ── Step 1: Add columns ──
print("\n[1/4] Adding columns to churches...")
cols = [r[1] for r in c.execute("PRAGMA table_info(churches)").fetchall()]
additions = []
if 'ministries' not in cols:
    additions.append("ALTER TABLE churches ADD COLUMN ministries TEXT")
if 'merged_into' not in cols:
    additions.append("ALTER TABLE churches ADD COLUMN merged_into INTEGER REFERENCES churches(id)")
for stmt in additions:
    print(f"  {stmt}")
    if not dry_run:
        c.execute(stmt)
if not dry_run:
    conn.commit()

# ── Step 2: Find clusters ──
print("\n[2/4] Finding shared-location clusters...")
c.execute("""
    SELECT ROUND(latitude,5), ROUND(longitude,5), city, country, COUNT(*) as cnt
    FROM churches 
    WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY ROUND(latitude,5), ROUND(longitude,5), city, country
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
""")
clusters = c.fetchall()
print(f"  Found {len(clusters)} clusters with {sum(r[4] for r in clusters)} entries")

# ── Step 3: Process each cluster ──
print("\n[3/4] Processing clusters...")

total_primary = 0
total_merged = 0
problems = []

for ci, (lat, lon, city, country, cnt) in enumerate(clusters):
    c.execute("""
        SELECT id, name, city, state, country, latitude, longitude,
               landmark_type, tradition
        FROM churches 
        WHERE faith='Judaism' 
          AND ROUND(latitude,5)=? AND ROUND(longitude,5)=?
          AND city=? AND country=?
        ORDER BY id
    """, (lat, lon, city, country))
    entries = c.fetchall()
    
    if len(entries) < 2:
        continue
    
    # Score and pick primary
    scored = [(score_entry(e), e) for e in entries]
    scored.sort(key=lambda x: -x[0])
    primary = scored[0][1]
    secondaries = [s[1] for s in scored[1:]]
    
    primary_id = primary[0]
    ministries = [make_ministry_json(s) for s in secondaries]
    
    # Log what's happening
    print(f"\n  [{ci+1}/{len(clusters)}] {city or 'N/A'}, {country} @ ({lat:.5f}, {lon:.5f})")
    print(f"    PRIMARY: #{primary_id} {str(primary[1] or '')[:50]} [{primary[7] or ''}]")
    for s in secondaries:
        print(f"      -> #{s[0]} {str(s[1] or '')[:45]} [{s[7] or ''}]")
    print(f"    Merging {len(secondaries)} -> {primary_id}")
    
    if not dry_run:
        # Store ministries JSON on primary
        existing = c.execute("SELECT ministries FROM churches WHERE id=?", (primary_id,)).fetchone()
        existing_json = json.loads(existing[0]) if existing and existing[0] else []
        existing_json.extend(ministries)
        c.execute("UPDATE churches SET ministries=? WHERE id=?", (json.dumps(existing_json), primary_id))
        
        # Mark secondaries with merged_into
        for s in secondaries:
            c.execute("UPDATE churches SET merged_into=? WHERE id=?", (primary_id, s[0]))
            # Log to provenance
            c.execute("""INSERT INTO enrichment_change_log 
                (church_id, field_name, old_value, new_value, change_source)
                VALUES (?, 'merged_into', NULL, ?, 'collapse_shared_jewish')""",
                (s[0], str(primary_id)))
    
    total_primary += 1
    total_merged += len(secondaries)

if not dry_run:
    conn.commit()

print(f"\n[3/4] Done: {total_primary} primaries, {total_merged} merged entries")

# ── Step 4: Summary ──
print(f"\n[4/4] Summary")
print(f"  Clusters processed: {len(clusters)}")
print(f"  Primary entries kept: {total_primary}")
print(f"  Entries merged into JSON ministries: {total_merged}")
print(f"  Entries saved (not deleted): {total_primary + total_merged}")

# Verify
if not dry_run:
    c.execute("SELECT COUNT(*) FROM churches WHERE merged_into IS NOT NULL")
    merged_count = c.fetchone()[0]
    print(f"\n  Churches with merged_into set: {merged_count}")
    
    c.execute("SELECT COUNT(*) FROM churches WHERE ministries IS NOT NULL AND ministries != '[]'")
    ministries_count = c.fetchone()[0]
    print(f"  Churches with ministries JSON: {ministries_count}")

conn.close()
print("\nDone!")
