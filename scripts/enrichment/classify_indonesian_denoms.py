"""Classify Indonesian Protestant denominations hiding under generic 'Christian'."""
import sqlite3

DB = "E:/grid/churches.db"

DENOMS = [
    ("GBI", "Gereja Bethel Indonesia", "Pentecostal"),
    ("GPdI", "Gereja Pentekosta di Indonesia", "Pentecostal"),
    ("HKBP", "Huria Kristen Batak Protestan", "Lutheran"),
    ("GMIM", "Gereja Masehi Injili di Minahasa", "Reformed"),
    ("GKI", "Gereja Kristen Indonesia", "Reformed"),
    ("GPIB", "Gereja Protestan di Indonesia bagian Barat", "Reformed"),
    ("GKJ", "Gereja Kristen Jawa", "Reformed"),
    ("GMIT", "Gereja Masehi Injili di Timor", "Reformed"),
    ("GKE", "Gereja Kalimantan Evangelis", "Reformed"),
    ("GKPB", "Gereja Kristen Protestan Bali", "Protestant"),
    ("GPM", "Gereja Protestan Maluku", "Reformed"),
]

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# Find parent taxonomy nodes
print("Parent taxonomy nodes:")
parent_ids = {}
for parent_name in set(d[2] for d in DENOMS):
    r = db.execute("SELECT id FROM taxonomy WHERE name=? LIMIT 1", (parent_name,)).fetchone()
    if r:
        parent_ids[parent_name] = r["id"]
        print(f"  {parent_name}: id={r['id']}")
    else:
        print(f"  {parent_name}: NOT FOUND!")

# Classify
total = 0
for prefix, full_name, parent_name in DENOMS:
    pid = parent_ids[parent_name]
    
    # Check existing taxonomy
    r = db.execute("SELECT id FROM taxonomy WHERE name=? AND parent_id=?", (full_name, pid)).fetchone()
    if r:
        tax_id = r["id"]
    else:
        parent = db.execute("SELECT * FROM taxonomy WHERE id=?", (pid,)).fetchone()
        max_id = db.execute("SELECT MAX(id) FROM taxonomy").fetchone()[0]
        tax_id = max_id + 1
        db.execute("""
            INSERT INTO taxonomy (id, name, parent_id, full_path, depth, root_id, tradition_id, family_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (tax_id, full_name, pid, parent["full_path"] + "/" + full_name,
              parent["depth"] + 1, parent["root_id"], parent["tradition_id"], parent["family_id"]))
    
    before = db.total_changes
    db.execute("""
        UPDATE churches SET taxonomy_id=?, last_updated=datetime('now')
        WHERE country='ID' AND name LIKE ? AND taxonomy_id IN (2,6)
    """, (tax_id, f"{prefix} %"))
    count = db.total_changes - before
    total += count
    print(f"  {prefix}: {count:,} -> {full_name} (tax={tax_id})")

db.commit()

# Verify no stragglers
print("\nVerification:")
for prefix, full_name, _ in DENOMS:
    r = db.execute("SELECT COUNT(1) FROM churches WHERE country='ID' AND name LIKE ? AND taxonomy_id IN (2,6)", (f"{prefix} %",)).fetchone()
    if r[0] > 0:
        print(f"  ⚠️ {prefix}: {r[0]} still generic")

print(f"\nTotal classified: {total:,}")
db.close()
