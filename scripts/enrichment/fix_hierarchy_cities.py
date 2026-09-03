"""
Fix all hierarchy tables: sync city/state from churches table.
The churches table just got 313K city fixes via zip_lookup_us.
Now propagate those corrected cities to all hierarchy tables.
"""
import sqlite3

DB = "E:/grid/churches.db"
CHUNK_SIZE = 500

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# Step 1: Fix city in all hierarchy tables from churches
HIERARCHY_TABLES = [
    "catholic_hierarchy",
    "anglican_hierarchy",
    "orthodox_hierarchy",
    "lutheran_hierarchy",
    "baptist_hierarchy",
    "lds_hierarchy",
    "jw_hierarchy",
    "sa_hierarchy",
    "moravian_hierarchy",
    "ahmadiyya_hierarchy",
    "chabad_hierarchy",
    "bahai_hierarchy",
]

total_fixes = 0

for table in HIERARCHY_TABLES:
    exists = db.execute("SELECT COUNT(1) FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
    if not exists:
        continue
    
    # Check if table has city and church_id columns
    cols = [c[1] for c in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if "church_id" not in cols or "city" not in cols:
        print(f"{table}: skipping (missing church_id or city)")
        continue
    
    # Count mismatches
    mismatches = db.execute(f"""
        SELECT COUNT(1) FROM {table} h
        JOIN churches c ON h.church_id = c.id
        WHERE h.city IS NOT NULL AND c.city IS NOT NULL AND h.city != c.city
    """).fetchone()[0]
    
    if mismatches == 0:
        print(f"{table}: 0 mismatches, skipping")
        continue
    
    # Get the fixes
    fixes = db.execute(f"""
        SELECT h.id, h.city as old_city, c.city as new_city, 
               h.state as old_state, c.state as new_state
        FROM {table} h
        JOIN churches c ON h.church_id = c.id
        WHERE h.city IS NOT NULL AND c.city IS NOT NULL AND h.city != c.city
    """).fetchall()
    
    # Show samples
    print(f"\n{table}: {len(fixes):,} mismatches")
    for f in fixes[:5]:
        print(f"  id={f['id']} | {f['old_city']} → {f['new_city']} | {f['old_state']} → {f['new_state']}")
    
    # Batch update
    for i in range(0, len(fixes), CHUNK_SIZE):
        batch = fixes[i:i+CHUNK_SIZE]
        db.executemany(f"UPDATE {table} SET city=?, state=? WHERE id=?",
                       [(f["new_city"], f["new_state"] if f["new_state"] else f["old_state"], f["id"]) for f in batch])
    db.commit()
    
    total_fixes += len(fixes)
    print(f"  → {len(fixes):,} fixed")

print(f"\n{'='*50}")
print(f"TOTAL: {total_fixes:,} hierarchy city/state fixes across all tables")

# Step 2: Now link unlinked US Catholic churches to hierarchy
# Count how many need linking
unlinked = db.execute("""
    SELECT COUNT(1) FROM churches c
    WHERE c.country='US' AND c.taxonomy_id IN (14,86,92,100)
      AND c.id NOT IN (SELECT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL)
""").fetchone()[0]
print(f"\nUS Catholic churches not in hierarchy: {unlinked:,}")

# Check: how many dioceses do we have?
dioceses = db.execute("""
    SELECT id, name, city, state FROM catholic_hierarchy WHERE cath_type='diocese'
""").fetchall()
print(f"Dioceses in hierarchy: {len(dioceses)}")

# Check: how many archdioceses?
archdioceses = db.execute("""
    SELECT id, name FROM catholic_hierarchy WHERE cath_type='archdiocese'
""").fetchall()
print(f"Archdioceses: {len(archdioceses)}")

db.close()
