"""
Link unlinked US Catholic churches to the Catholic hierarchy.
Strategy: build county_fips → diocese mapping from existing parishes,
then assign unlinked churches to the right diocese.
"""
import sqlite3
from collections import defaultdict

DB = "E:/grid/churches.db"
CHUNK_SIZE = 500

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# ── Step 1: Build county → diocese mapping from clean existing links ──
print("Building county→diocese map from existing clean parish links...")

# Get parishes where hierarchy city matches church city (clean links)
clean = db.execute("""
    SELECT c.county_fips_5, ch.archdiocese, ch.diocese, 
           ch.id as hier_id, ch.parent_id, c.state
    FROM catholic_hierarchy ch
    JOIN churches c ON ch.church_id = c.id
    WHERE ch.cath_type='parish' 
      AND c.country='US'
      AND c.county_fips_5 IS NOT NULL
      AND ch.city = c.city
""").fetchall()
print(f"Clean existing parish links: {len(clean):,}")

# Build county → diocese mapping
county_to_parent = defaultdict(lambda: defaultdict(int))
for row in clean:
    fips = row["county_fips_5"]
    parent = row["parent_id"]
    county_to_parent[fips][parent] += 1

# Take the most common parent_id for each county
county_diocese = {}
for fips, parents in county_to_parent.items():
    best_parent = max(parents, key=parents.get)
    county_diocese[fips] = best_parent

print(f"County→diocese mappings: {len(county_diocese):,}")

# ── Step 2: Find diocese info for each parent_id ──
unique_parents = list(set(county_diocese.values()))
print(f"Unique diocese/archdiocese parents: {len(unique_parents)}")

parent_info = {}
parents = db.execute(f"""
    SELECT id, name, cath_type, archdiocese, diocese, city, state
    FROM catholic_hierarchy 
    WHERE id IN ({','.join('?' for _ in unique_parents)})
""", unique_parents).fetchall()
for p in parents:
    parent_info[p["id"]] = {
        "name": p["name"],
        "cath_type": p["cath_type"],
        "archdiocese": p["archdiocese"],
        "diocese": p["diocese"],
        "city": p["city"],
        "state": p["state"]
    }

# ── Step 3: Get unlinked US Catholic churches ──
print("Loading unlinked US Catholic churches...")
unlinked = db.execute("""
    SELECT c.id, c.name, c.city, c.state, c.latitude, c.longitude,
           c.county_fips_5, c.zip5
    FROM churches c
    WHERE c.country='US' 
      AND c.taxonomy_id IN (14,86,92,100)
      AND c.id NOT IN (SELECT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL)
      AND c.latitude IS NOT NULL
""").fetchall()
print(f"Unlinked US Catholic churches: {len(unlinked):,}")

# ── Step 4: Assign and insert ──
linked = 0
no_county = 0
no_mapping = 0
inserts = []

for ch in unlinked:
    fips = ch["county_fips_5"]
    if not fips:
        no_county += 1
        continue
    
    parent_id = county_diocese.get(fips)
    if not parent_id:
        no_mapping += 1
        continue
    
    pinfo = parent_info[parent_id]
    
    # Determine diocese and archdiocese names
    if pinfo["cath_type"] == "archdiocese":
        diocese_name = pinfo["name"]
        archdiocese_name = pinfo["name"]
    elif pinfo["cath_type"] == "diocese":
        diocese_name = pinfo["name"]
        archdiocese_name = pinfo["archdiocese"] or pinfo["name"]
    else:
        diocese_name = pinfo["diocese"] or pinfo["name"]
        archdiocese_name = pinfo["archdiocese"] or diocese_name
    
    inserts.append((
        parent_id,
        ch["id"],
        ch["name"],
        ch["name"],
        "parish",
        diocese_name,
        archdiocese_name,
        ch["city"],
        ch["state"],
        "US",
        ch["latitude"],
        ch["longitude"],
        pinfo["cath_type"],
        "belongs_to_diocese",
        f"county_fips={fips} → {pinfo['name']}"
    ))
    linked += 1

print(f"\nAssignable: {linked:,}")
print(f"No county_fips: {no_county:,}")
print(f"No county→diocese mapping: {no_mapping:,}")

if not inserts:
    print("Nothing to insert!")
    db.close()
    exit()

# ── Step 5: Batch insert ──
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
    print(f"  {min(i+CHUNK_SIZE, len(inserts)):,}/{len(inserts):,}")

# ── Step 6: Final stats ──
total = db.execute("SELECT COUNT(1) FROM catholic_hierarchy WHERE cath_type='parish'").fetchone()[0]
la_parishes = db.execute("""
    SELECT COUNT(DISTINCT ch.church_id) FROM catholic_hierarchy ch
    JOIN churches c ON ch.church_id = c.id
    WHERE ch.cath_type='parish' AND c.county_fips_5='06037'
""").fetchone()
print(f"\n=== FINAL STATE ===")
print(f"Total parishes in hierarchy: {total:,}")
print(f"LA County parishes: {la_parishes[0]} (was 37)")

us_in_hier = db.execute("""
    SELECT COUNT(DISTINCT ch.church_id) FROM catholic_hierarchy ch
    JOIN churches c ON ch.church_id = c.id
    WHERE ch.cath_type='parish' AND c.country='US'
""").fetchone()
us_total = db.execute("""
    SELECT COUNT(1) FROM churches WHERE country='US' AND taxonomy_id IN (14,86,92,100)
""").fetchone()
print(f"US parishes in hierarchy: {us_in_hier[0]:,} / {us_total[0]:,} ({us_in_hier[0]*100/us_total[0]:.1f}%)")

db.close()
