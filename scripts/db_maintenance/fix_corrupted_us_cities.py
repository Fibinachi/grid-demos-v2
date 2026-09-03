"""
Fix US records with corrupted (non-ASCII / foreign) city names.
Strategy: ZIP5 lookup from clean records -> extract ZIP5 from full ZIP -> skip unfixable.
"""
import sqlite3, sys, os
from datetime import datetime
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, log_change

db = connect()
cur = db.cursor()

print("=" * 60)
print("FIXING CORRUPTED US CITY NAMES")
print("=" * 60)

# Step 1: Build ZIP5 -> city lookup
print("\n[1/3] Building ZIP5 -> city lookup...")
cur.execute("""
    SELECT zip5, city, COUNT(*) as cnt
    FROM churches
    WHERE country='US'
      AND zip5 IS NOT NULL AND zip5 != ''
      AND city NOT GLOB '*[^ -~]*'
      AND city != ''
    GROUP BY zip5, city
""")
zip_city_counts = {}
for zip5, city, cnt in cur.fetchall():
    if zip5 not in zip_city_counts:
        zip_city_counts[zip5] = Counter()
    zip_city_counts[zip5][city] += cnt

zip_to_city = {z: c.most_common(1)[0][0] for z, c in zip_city_counts.items()}
print(f"  {len(zip_to_city):,} unique ZIP5 -> city mappings")

# Step 2: Find and fix
print("\n[2/3] Finding and fixing corrupted records...")
cur.execute("""
    SELECT id, name, city, state, zip5, zip
    FROM churches
    WHERE country='US' AND city GLOB '*[^ -~]*'
""")
bad_rows = cur.fetchall()
print(f"  {len(bad_rows):,} records with non-ASCII city names")

now = datetime.now().isoformat()
fixed = 0
skipped = 0

for i, row in enumerate(bad_rows):
    cid, name, old_city, state, zip5, zip_full = row
    
    zip_key = None
    if zip5 and zip5.strip():
        zip_key = zip5.strip()
    elif zip_full and len(zip_full.strip()) >= 5:
        zip_key = zip_full.strip()[:5]
    
    if zip_key and zip_key in zip_to_city:
        new_city = zip_to_city[zip_key]
        if new_city != old_city:
            cur.execute("UPDATE churches SET city=?, last_updated=? WHERE id=?", 
                       (new_city, now, cid))
            log_change(db, church_id=cid, field_name="city", old_value=old_city, 
                      new_value=new_city, source=f"zip5_lookup:{zip_key}")
            fixed += 1
        else:
            skipped += 1
    else:
        skipped += 1
    
    if (i + 1) % 1000 == 0:
        db.commit()
        print(f"  Progress: {i+1:,} / {len(bad_rows):,} — fixed {fixed:,} so far...")

db.commit()

# Step 3: Verify
print(f"\n[3/3] Verifying...")
cur.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND city GLOB '*[^ -~]*'")
remaining = cur.fetchone()[0]

print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"  Total corrupted:  {len(bad_rows):>8,}")
print(f"  Fixed:            {fixed:>8,}")
print(f"  Could not fix:    {skipped:>8,}")
print(f"  Remaining:        {remaining:>8,}")

# Show some examples
print(f"\n  Sample fixes:")
cur.execute("""
    SELECT c.name, c.city, c.state, e.old_value
    FROM enrichment_change_log e
    JOIN churches c ON e.church_id = c.id
    WHERE e.field_name='city' AND e.change_source LIKE 'zip5_lookup%'
    ORDER BY e.changed_at DESC LIMIT 10
""")
for r in cur.fetchall():
    print(f"    {str(r[0])[:40]:40s} | {str(r[3])[:20]:20s} -> {str(r[1])[:20]:20s} | {r[2]}")

db.close()
print("\nDone.")
