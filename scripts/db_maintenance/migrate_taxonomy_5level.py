"""Migration: Restructure taxonomy into 5 level-specific tables + fix LDS depth.

Phase 1: Fix LDS subtree depth (reparent d=5 nodes to d=4)
Phase 2: Create 5 locked tables (culture, faith, legacy, tradition, movement)
Phase 3: Backfill from existing taxonomy
Phase 4: Add FK columns to churches and populate
Phase 5: Add constraints

Run with: python scripts/db_maintenance/migrate_taxonomy_5level.py
"""
import sqlite3, sys, os
from datetime import datetime, timezone

DB = r"E:\grid\churches.db"
conn = sqlite3.connect(DB, timeout=60)
conn.execute("PRAGMA busy_timeout = 60000")
c = conn.cursor()

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

def checkpoint():
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

# ═══════════════════════════════════════════════
# PHASE 1: Fix LDS subtree depth
# ═══════════════════════════════════════════════
log("=" * 60)
log("PHASE 1: Fix LDS subtree depth")
log("=" * 60)

# Reparent all children of id=460 (Other LDS) under id=17 (Latter-day Saints)
log("  Reparenting 460's children under 17...")
c.execute("UPDATE taxonomy SET parent_id=17 WHERE parent_id=460")
cnt = c.rowcount
log(f"    {cnt} nodes reparented")

# Reparent id=459 (LDS) under id=17 (it's under 168 currently)
log("  Reparenting 459 under 17...")
c.execute("UPDATE taxonomy SET parent_id=17 WHERE id=459")
log(f"    1 node reparented")

# Reparent children of 588 under 17 (d=6→d=4)
log("  Reparenting 588's children under 17...")
c.execute("UPDATE taxonomy SET parent_id=17 WHERE parent_id=588")
cnt = c.rowcount
log(f"    {cnt} nodes reparented")

conn.commit()

# Verify: no more depth-5+ nodes
c.execute("""
    WITH RECURSIVE t AS (
        SELECT id, parent_id, 0 as depth FROM taxonomy WHERE parent_id IS NULL
        UNION ALL
        SELECT tax.id, tax.parent_id, t.depth + 1
        FROM taxonomy tax JOIN t ON tax.parent_id = t.id
    )
    SELECT MAX(depth) FROM t
""")
max_depth = c.fetchone()[0]
log(f"  Max depth after fix: {max_depth}")

log("  PHASE 1 complete")

# Orphaned Jewish tradition nodes (ids 32-243, 0 churches) are skipped.
# They need manual cleanup but don't affect the migration.

# ═══════════════════════════════════════════════
# PHASE 2: Create level-specific tables
# ═══════════════════════════════════════════════
log("=" * 60)
log("PHASE 2: Create level tables")
log("=" * 60)

conn.executescript("""
    CREATE TABLE IF NOT EXISTS culture (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT
    );
    CREATE TABLE IF NOT EXISTS faith (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        culture_id INTEGER NOT NULL REFERENCES culture(id),
        description TEXT,
        UNIQUE(name, culture_id)
    );
    CREATE TABLE IF NOT EXISTS legacy (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        faith_id INTEGER NOT NULL REFERENCES faith(id),
        description TEXT,
        UNIQUE(name, faith_id)
    );
    CREATE TABLE IF NOT EXISTS tradition (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        legacy_id INTEGER NOT NULL REFERENCES legacy(id),
        description TEXT,
        UNIQUE(name, legacy_id)
    );
    CREATE TABLE IF NOT EXISTS movement (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        tradition_id INTEGER NOT NULL REFERENCES tradition(id),
        description TEXT,
        UNIQUE(name, tradition_id)
    );
""")
log("  Tables created")

# ═══════════════════════════════════════════════
# PHASE 3: Populate from existing taxonomy
# ═══════════════════════════════════════════════
log("=" * 60)
log("PHASE 3: Populate from taxonomy tree")
log("=" * 60)

# Get all root nodes (culture level)
c.execute("SELECT id, name FROM taxonomy WHERE parent_id IS NULL ORDER BY id")
roots = {r[0]: r[1] for r in c.fetchall()}

# 4 cultures we care about
culture_map = {}
for cid, cname in [(555,'Abrahamic'), (556,'Dharmic'), (557,'Taoic'), (6,'Other')]:
    if cid in roots:
        c.execute("INSERT OR IGNORE INTO culture (id, name) VALUES (?, ?)", (cid, cname))
        culture_map[cid] = cname
        log(f"  Culture: {cname} (id={cid})")

conn.commit()
log(f"  {len(culture_map)} cultures populated")

# Faith level (d=1): direct children of cultures
faith_map = {}  # faith_id -> culture_id
for cid in culture_map:
    rows = c.execute("SELECT id, name FROM taxonomy WHERE parent_id=?", (cid,)).fetchall()
    for fid, fname in rows:
        c.execute("INSERT OR IGNORE INTO faith (id, name, culture_id) VALUES (?, ?, ?)", (fid, fname, cid))
        faith_map[fid] = cid
        log(f"  Faith: {fname} (id={fid}) under {culture_map[cid]}")

conn.commit()
log(f"  {len(faith_map)} faiths populated")

# Legacy level (d=2): children of faith nodes
legacy_map = {}  # legacy_id -> faith_id
for fid in faith_map:
    rows = c.execute("SELECT id, name FROM taxonomy WHERE parent_id=?", (fid,)).fetchall()
    for lid, lname in rows:
        c.execute("INSERT OR IGNORE INTO legacy (id, name, faith_id) VALUES (?, ?, ?)", (lid, lname, fid))
        legacy_map[lid] = fid

conn.commit()
log(f"  {len(legacy_map)} legacies populated")

# Tradition level (d=3): children of legacy nodes
tradition_map = {}  # tradition_id -> legacy_id
for lid in legacy_map:
    rows = c.execute("SELECT id, name FROM taxonomy WHERE parent_id=?", (lid,)).fetchall()
    for tid, tname in rows:
        c.execute("INSERT OR IGNORE INTO tradition (id, name, legacy_id) VALUES (?, ?, ?)", (tid, tname, lid))
        tradition_map[tid] = lid

conn.commit()
log(f"  {len(tradition_map)} traditions populated")

# Movement level (d=4): children of tradition nodes
movement_map = {}  # movement_id -> tradition_id
for tid in tradition_map:
    rows = c.execute("SELECT id, name FROM taxonomy WHERE parent_id=?", (tid,)).fetchall()
    for mid, mname in rows:
        c.execute("INSERT OR IGNORE INTO movement (id, name, tradition_id) VALUES (?, ?, ?)", (mid, mname, tid))
        movement_map[mid] = tid

conn.commit()
log(f"  {len(movement_map)} movements populated")

log("  PHASE 3 complete")

# ═══════════════════════════════════════════════
# PHASE 4: Add FK columns to churches
# ═══════════════════════════════════════════════
log("=" * 60)
log("PHASE 4: Add taxonomy columns to churches")
log("=" * 60)

existing = {r[1] for r in c.execute('PRAGMA table_info(churches)').fetchall()}
for col, dtype in [
    ('culture_id', 'INTEGER'),
    ('faith_id', 'INTEGER'),
    ('legacy_id', 'INTEGER'),
    ('tradition_id', 'INTEGER'),
    ('movement_id', 'INTEGER'),
]:
    if col not in existing:
        c.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')
        log(f"  Added column: {col}")

conn.commit()

# Build lookup: taxonomy_id -> (culture_id, faith_id, legacy_id, tradition_id, movement_id)
log("  Building taxonomy path lookup...")
c.execute("""
    WITH RECURSIVE t AS (
        SELECT id, parent_id, id as self FROM taxonomy
        UNION ALL
        SELECT tax.id, tax.parent_id, t.self
        FROM taxonomy tax JOIN t ON tax.id = t.parent_id
    )
    SELECT t.self, t.id FROM t ORDER BY t.self
""")
# This will give us (ancestor_id, descendant_id) pairs
# We need to organize by depth for each descendant

# Simpler approach: walk each taxonomy node up to root
taxonomy_paths = {}  # taxonomy_id -> [id from root to leaf]

c.execute("SELECT id FROM taxonomy")
all_ids = [r[0] for r in c.fetchall()]

for tid in all_ids:
    path = []
    pid = tid
    while pid:
        path.append(pid)
        next_pid = c.execute("SELECT parent_id FROM taxonomy WHERE id=?", (pid,)).fetchone()
        pid = next_pid[0] if next_pid else None
    path.reverse()  # now root -> leaf
    taxonomy_paths[tid] = path

log(f"  Built paths for {len(taxonomy_paths)} taxonomy nodes")

# Backfill churches — one taxonomy_id at a time to avoid massive WAL growth
log("  Backfilling churches in chunks...")
total = c.execute("SELECT COUNT(id) FROM churches").fetchone()[0]
done = 0

# Get all unique taxonomy_ids used by churches, sorted by count descending
# (process largest groups first)
c.execute("""
    SELECT taxonomy_id, COUNT(id) as cnt FROM churches 
    WHERE taxonomy_id IS NOT NULL 
    GROUP BY taxonomy_id ORDER BY cnt DESC
""")
tax_ids_used = c.fetchall()
log(f"  {len(tax_ids_used)} unique taxonomy_ids found")

for tid, cnt in tax_ids_used:
    path = taxonomy_paths.get(tid, [])
    culture_id = next((x for x in path if x in culture_map), None)
    faith_id = next((x for x in path if x in faith_map), None)
    legacy_id = next((x for x in path if x in legacy_map), None)
    tradition_id = next((x for x in path if x in tradition_map), None)
    movement_id = next((x for x in path if x in movement_map), None)
    
    c.execute("""
        UPDATE churches SET culture_id=?, faith_id=?, legacy_id=?, tradition_id=?, movement_id=?
        WHERE taxonomy_id=?
    """, (culture_id, faith_id, legacy_id, tradition_id, movement_id, tid))
    conn.commit()
    done += cnt
    log(f"    {done:,} / {total:,} churches done (tid={tid}, cnt={cnt:,})")

log("  PHASE 4 complete")

# ═══════════════════════════════════════════════
# PHASE 5: Verify and report
# ═══════════════════════════════════════════════
log("=" * 60)
log("PHASE 5: Verification")
log("=" * 60)

with_culture = c.execute("SELECT COUNT(id) FROM churches WHERE culture_id IS NOT NULL").fetchone()[0]
with_faith = c.execute("SELECT COUNT(id) FROM churches WHERE faith_id IS NOT NULL").fetchone()[0]
with_legacy = c.execute("SELECT COUNT(id) FROM churches WHERE legacy_id IS NOT NULL").fetchone()[0]
with_tradition = c.execute("SELECT COUNT(id) FROM churches WHERE tradition_id IS NOT NULL").fetchone()[0]
with_movement = c.execute("SELECT COUNT(id) FROM churches WHERE movement_id IS NOT NULL").fetchone()[0]
total = c.execute("SELECT COUNT(id) FROM churches").fetchone()[0]

log(f"  Total churches: {total:,}")
log(f"  With culture_id:  {with_culture:,} ({with_culture/total*100:.1f}%)")
log(f"  With faith_id:    {with_faith:,} ({with_faith/total*100:.1f}%)")
log(f"  With legacy_id:   {with_legacy:,} ({with_legacy/total*100:.1f}%)")
log(f"  With tradition_id:{with_tradition:,} ({with_tradition/total*100:.1f}%)")
log(f"  With movement_id: {with_movement:,} ({with_movement/total*100:.1f}%)")

# Count by culture
log(f"\n  Churches by culture:")
for cid, cname in [(555,'Abrahamic'), (556,'Dharmic'), (557,'Taoic'), (6,'Other')]:
    cnt = c.execute("SELECT COUNT(id) FROM churches WHERE culture_id=?", (cid,)).fetchone()[0]
    log(f"    {cname:30s} {cnt:>10,}")

# Cross-culture violations (should be 0!)
log(f"\n  Cross-culture integrity check:")
bad = c.execute("""
    SELECT COUNT(id) FROM churches c
    WHERE c.faith_id IS NOT NULL 
    AND (SELECT culture_id FROM faith WHERE id=c.faith_id) != c.culture_id
""").fetchone()[0]
log(f"    Faith/culture mismatches: {bad:,}")

log("=" * 60)
log("MIGRATION COMPLETE")
log("=" * 60)

conn.close()
