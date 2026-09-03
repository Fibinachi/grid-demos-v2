"""Classify La Luz del Mundo, IURD, and Foursquare churches."""
import sqlite3

DB = "E:/grid/churches.db"
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

def get_or_create_taxon(name, parent_name, parent_id=None):
    """Get or create a taxonomy node. Returns tax_id."""
    if parent_id:
        r = db.execute("SELECT id FROM taxonomy WHERE name=? AND parent_id=?", (name, parent_id)).fetchone()
    else:
        r = db.execute("SELECT id FROM taxonomy WHERE name=?", (name,)).fetchone()
    if r:
        return r["id"]
    
    # Find parent
    if not parent_id:
        pid = db.execute("SELECT id FROM taxonomy WHERE name=?", (parent_name,)).fetchone()
        if not pid:
            print(f"  ERROR: parent '{parent_name}' not found!")
            return None
        parent_id = pid["id"]
    
    parent = db.execute("SELECT * FROM taxonomy WHERE id=?", (parent_id,)).fetchone()
    max_id = db.execute("SELECT MAX(id) FROM taxonomy").fetchone()[0]
    tax_id = max_id + 1
    db.execute("""
        INSERT INTO taxonomy (id, name, parent_id, full_path, depth, root_id, tradition_id, family_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (tax_id, name, parent_id, parent["full_path"] + "/" + name,
          parent["depth"] + 1, parent["root_id"], parent["tradition_id"], parent["family_id"]))
    return tax_id

def classify(name_patterns, tax_id, countries=None, extra_where=""):
    """Classify churches matching patterns."""
    total = 0
    for pattern in name_patterns:
        where = f"name LIKE ? {extra_where}"
        params = [pattern]
        if countries:
            placeholders = ",".join("?" * len(countries))
            where += f" AND country IN ({placeholders})"
            params.extend(countries)
        sql = f"SELECT COUNT(1) FROM churches WHERE {where} AND taxonomy_id IN (2,6)"
        count = db.execute(sql, params).fetchone()[0]
        if count:
            before = db.total_changes
            db.execute(f"UPDATE churches SET taxonomy_id=?, last_updated=datetime('now') WHERE {where} AND taxonomy_id IN (2,6)", [tax_id] + params)
            total += db.total_changes - before
    return total

# ── 1. La Luz del Mundo (Nontrinitarian Restorationist) ──
print("=== LA LUZ DEL MUNDO ===")
# Create under Christian/Other (id=6 has Other as parent, let me find right spot)
other_christian = db.execute("SELECT id FROM taxonomy WHERE name='Other' AND parent_id=(SELECT id FROM taxonomy WHERE name='Christian')").fetchone()
if not other_christian:
    other_christian = db.execute("SELECT id FROM taxonomy WHERE name='Other' LIMIT 1").fetchone()
lldm_tax = get_or_create_taxon("La Luz del Mundo", "Other", other_christian["id"] if other_christian else 15)
print(f"  Taxonomy: {lldm_tax}")

n = classify(["%Luz del Mundo%", "%LLDM%", "%Iglesia del Dios Vivo%"], lldm_tax)
print(f"  Classified: {n:,}")

# ── 2. IURD (Universal Church of the Kingdom of God) - Neo-Pentecostal ──
print("\n=== IURD (UNIVERSAL CHURCH) ===")
pentecostal = db.execute("SELECT id FROM taxonomy WHERE name='Pentecostal' LIMIT 1").fetchone()
iurd_tax = get_or_create_taxon("Igreja Universal do Reino de Deus", "Pentecostal", pentecostal["id"])
print(f"  Taxonomy: {iurd_tax}")

n = classify(["%Universal del Reino de Dios%", "%IURD%", "%Pare de Sufrir%", 
              "%Universal Church of the Kingdom of God%"], iurd_tax)
print(f"  Classified: {n:,}")

# ── 3. Foursquare ──
print("\n=== FOURSQUARE ===")
# Find existing Foursquare taxonomy
fsq = db.execute("SELECT id FROM taxonomy WHERE name LIKE '%Foursquare%' OR name LIKE '%Cuadrangular%' LIMIT 1").fetchone()
if fsq:
    fsq_tax = fsq["id"]
    print(f"  Existing taxonomy: {fsq_tax} ({fsq['name'] if 'name' in fsq.keys() else ''})")
else:
    fsq_tax = get_or_create_taxon("Iglesia Cuadrangular (Foursquare)", "Pentecostal", pentecostal["id"])
    print(f"  Created taxonomy: {fsq_tax}")

n = classify(["%Cuadrangular%", "%Foursquare Gospel%", "%Foursquare Church%", 
              "%Iglesia Cuadrangular%"], fsq_tax)
print(f"  Classified: {n:,}")

db.commit()

# ── Verify ──
print("\n=== VERIFICATION ===")
for name, patterns in [
    ("Luz del Mundo", ["%Luz del Mundo%", "%LLDM%"]),
    ("IURD", ["%IURD%", "%Universal del Reino%"]),  
    ("Foursquare", ["%Cuadrangular%", "%Foursquare%"]),
]:
    stragglers = 0
    for p in patterns:
        r = db.execute("SELECT COUNT(1) FROM churches WHERE name LIKE ? AND taxonomy_id IN (2,6)", (p,)).fetchone()
        stragglers += r[0]
    if stragglers:
        print(f"  ⚠️ {name}: {stragglers} still generic")

print("\nDone!")
db.close()
