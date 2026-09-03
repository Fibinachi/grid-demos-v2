"""
Link ALL unlinked Catholic churches using state/country boundary logic.
Diocese boundaries rarely cross borders → use state first, then country.
"""
import sqlite3
from collections import defaultdict

DB = "E:/grid/churches.db"
CHUNK_SIZE = 500

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# ── Build ALL existing parish links into state→diocese map ──
print("Building state→diocese map from ALL existing parish links...")
all_links = db.execute("""
    SELECT c.county_fips_5, c.state, c.country, 
           ch.parent_id, ch.diocese, ch.archdiocese
    FROM catholic_hierarchy ch
    JOIN churches c ON ch.church_id = c.id
    WHERE ch.cath_type='parish' AND ch.parent_id IS NOT NULL
""").fetchall()
print(f"Existing parish links: {len(all_links):,}")

# County → most common parent
county_map = defaultdict(lambda: defaultdict(int))
# State+country → most common parent  
state_map = defaultdict(lambda: defaultdict(int))
# Country → most common parent
country_map = defaultdict(lambda: defaultdict(int))

for row in all_links:
    pid = row["parent_id"]
    if row["county_fips_5"]:
        county_map[row["county_fips_5"]][pid] += 1
    state_key = f"{row['state']}|{row['country']}"
    state_map[state_key][pid] += 1
    if row["country"]:
        country_map[row["country"]][pid] += 1

# Resolve to single parent per key
def best_parent(d):
    return max(d, key=d.get) if d else None

county_diocese = {k: best_parent(v) for k, v in county_map.items()}
state_diocese = {k: best_parent(v) for k, v in state_map.items()}
country_diocese = {k: best_parent(v) for k, v in country_map.items()}

print(f"County mappings: {len(county_diocese):,}")
print(f"State mappings:  {len(state_diocese):,}")
print(f"Country mappings: {len(country_diocese):,}")

# ── Get parent info ──
all_parents = set()
all_parents.update(county_diocese.values(), state_diocese.values(), country_diocese.values())
all_parents.discard(None)

parent_info = {}
for p in db.execute(f"SELECT id, name, cath_type, archdiocese, diocese, city, state, country FROM catholic_hierarchy WHERE id IN ({','.join('?' for _ in all_parents)})", list(all_parents)).fetchall():
    parent_info[p["id"]] = dict(p)
print(f"Unique parent dioceses/archdioceses: {len(parent_info)}")

# ── Get ALL unlinked Catholic churches ──
print("\nLoading unlinked Catholic churches...")
unlinked = db.execute("""
    SELECT c.id, c.name, c.city, c.state, c.country, c.latitude, c.longitude,
           c.county_fips_5, c.zip5
    FROM churches c
    WHERE c.taxonomy_id IN (14,86,92,100)
      AND c.id NOT IN (SELECT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL)
      AND c.latitude IS NOT NULL
""").fetchall()
print(f"Unlinked Catholic churches worldwide: {len(unlinked):,}")

# ── Assign using county→state→country fallback ──
inserts = []
stats = {"county": 0, "state": 0, "country": 0, "none": 0}

for ch in unlinked:
    parent_id = None
    level = "none"
    
    # Try county first
    if ch["county_fips_5"]:
        parent_id = county_diocese.get(ch["county_fips_5"])
        if parent_id:
            level = "county"
    
    # Then state+country
    if not parent_id:
        state_key = f"{ch['state']}|{ch['country']}"
        parent_id = state_diocese.get(state_key)
        if parent_id:
            level = "state"
    
    # Then country only
    if not parent_id and ch["country"]:
        parent_id = country_diocese.get(ch["country"])
        if parent_id:
            level = "country"
    
    if not parent_id:
        stats["none"] += 1
        continue
    
    stats[level] += 1
    pinfo = parent_info[parent_id]
    
    if pinfo["cath_type"] == "archdiocese":
        dname = aname = pinfo["name"]
    elif pinfo["cath_type"] == "diocese":
        dname = pinfo["name"]
        aname = pinfo["archdiocese"] or pinfo["name"]
    else:
        dname = pinfo["diocese"] or pinfo["name"]
        aname = pinfo["archdiocese"] or dname
    
    inserts.append((
        parent_id, ch["id"], ch["name"], ch["name"], "parish",
        dname, aname,
        ch["city"], ch["state"], ch["country"],
        ch["latitude"], ch["longitude"],
        pinfo["cath_type"], "belongs_to_diocese",
        f"{level}: {ch['county_fips_5'] or ''} {ch['state']} {ch['country']} -> {pinfo['name']}"
    ))

print(f"\nAssignment breakdown:")
print(f"  County match:  {stats['county']:,}")
print(f"  State match:   {stats['state']:,}")
print(f"  Country match: {stats['country']:,}")
print(f"  No match:      {stats['none']:,}")
print(f"  TO INSERT:     {len(inserts):,}")

if not inserts:
    print("Nothing to insert!")
    db.close()
    exit()

# ── Insert ──
print(f"\nInserting {len(inserts):,} parish links...")
for i in range(0, len(inserts), CHUNK_SIZE):
    batch = inserts[i:i+CHUNK_SIZE]
    db.executemany("""
        INSERT INTO catholic_hierarchy 
        (parent_id, church_id, name, original_name, cath_type, diocese, archdiocese,
         city, state, country, lat, lon, parent_cath_type, relationship, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    if (i + CHUNK_SIZE) % 5000 == 0:
        print(f"  {min(i+CHUNK_SIZE, len(inserts)):,}/{len(inserts):,}")

# ── Final stats ──
total = db.execute("SELECT COUNT(1) FROM catholic_hierarchy WHERE cath_type='parish'").fetchone()[0]
us_linked = db.execute("""
    SELECT COUNT(DISTINCT ch.church_id) FROM catholic_hierarchy ch
    JOIN churches c ON ch.church_id = c.id
    WHERE ch.cath_type='parish' AND c.country='US'
""").fetchone()[0]
us_total = db.execute("SELECT COUNT(1) FROM churches WHERE country='US' AND taxonomy_id IN (14,86,92,100)").fetchone()[0]

print(f"\n=== FINAL ===")
print(f"Total parishes in hierarchy: {total:,}")
print(f"US: {us_linked:,} / {us_total:,} ({us_linked*100/max(us_total,1):.1f}%)")

# Global
global_linked = db.execute("""
    SELECT COUNT(DISTINCT church_id) FROM catholic_hierarchy WHERE cath_type='parish' AND church_id IS NOT NULL
""").fetchone()[0]
global_total = db.execute("SELECT COUNT(1) FROM churches WHERE taxonomy_id IN (14,86,92,100)").fetchone()[0]
print(f"Global: {global_linked:,} / {global_total:,} ({global_linked*100/max(global_total,1):.1f}%)")

still = db.execute("""
    SELECT COUNT(1) FROM churches WHERE taxonomy_id IN (14,86,92,100)
      AND id NOT IN (SELECT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL)
""").fetchone()[0]
print(f"Still unlinked: {still:,}")

db.close()
