"""
Match Catholic diocese nodes to their cathedrals in GRID by name.
Load all data into memory first, then match in Python (fast).
"""
import sqlite3, re
from collections import defaultdict

DB = "E:/grid/churches.db"
CHUNK_SIZE = 500

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# ── Load all diocese nodes without GPS ──
print("Loading dioceses...", end=" ", flush=True)
dioceses = db.execute("""
    SELECT id, name, cath_type, country, city, lat, lon
    FROM catholic_hierarchy
    WHERE cath_type IN ('diocese','archdiocese')
      AND (lat IS NULL OR lat = 0)
""").fetchall()
print(f"{len(dioceses):,}")

# ── Load all Catholic cathedrals from GRID once ──
print("Loading cathedrals from GRID...", end=" ", flush=True)
cathedrals = db.execute("""
    SELECT id, name, city, country, latitude, longitude
    FROM churches
    WHERE name LIKE '%Cathedral%'
      AND taxonomy_id IN (14,86,92,100)
      AND latitude IS NOT NULL
""").fetchall()
print(f"{len(cathedrals):,}")

# Index cathedrals by country
cath_by_country = defaultdict(list)
for c in cathedrals:
    cath_by_country[c["country"] or ""].append(c)

# ── Match ──
print("Matching...", flush=True)
matches = []
no_match = 0

for i, d in enumerate(dioceses):
    if i % 500 == 0:
        print(f"  {i:,}/{len(dioceses):,}...")
    
    name = d["name"]
    country = d["country"] or ""
    
    # Extract see city
    see_city = re.sub(r'^(Archdiocese|Diocese|Archbishop|Metropolitan|Eparchy)\s+(of\s+)?', '', name, flags=re.IGNORECASE).strip()
    
    # Get cathedrals in same country
    candidates = cath_by_country.get(country, cathedrals)
    
    best_score = 0
    best_match = None
    
    for ch in candidates:
        score = 0
        ch_name = ch["name"].upper()
        ch_city = (ch["city"] or "").upper()
        see_upper = see_city.upper()
        
        if f"CATHEDRAL OF {see_upper}" in ch_name:
            score += 200
        elif see_upper in ch_name:
            score += 50
        if see_upper == ch_city:
            score += 100
        elif see_upper in ch_city:
            score += 30
        if ch["country"] == country:
            score += 10
        
        if score > best_score:
            best_score = score
            best_match = ch
    
    if best_match and best_score >= 50:
        matches.append((d["id"], best_match["id"], best_match["name"],
                       best_match["latitude"], best_match["longitude"],
                       best_score, see_city))
    else:
        no_match += 1

print(f"\nMatched: {len(matches):,}")
print(f"No match: {no_match:,}")

print("\n=== SAMPLE MATCHES ===")
for m in matches[:15]:
    d = next(d for d in dioceses if d["id"] == m[0])
    print(f"  {d['name'][:50]} ({d['country']}) -> {m[2][:50]} (score={m[5]})")

# ── Update diocese nodes ──
print(f"\nUpdating {len(matches):,} diocese nodes...")
for i in range(0, len(matches), CHUNK_SIZE):
    batch = matches[i:i+CHUNK_SIZE]
    db.executemany("""
        UPDATE catholic_hierarchy 
        SET lat=?, lon=?, church_id=?, 
            city=(SELECT city FROM churches WHERE id=?),
            notes=COALESCE(notes,'') || ' | Cathedral: ' || ?
        WHERE id=?
    """, [(m[3], m[4], m[1], m[1], m[2], m[0]) for m in batch])
    db.commit()

# ── Create cathedral child nodes ──
print("Creating cathedral child nodes...")
for i in range(0, len(matches), CHUNK_SIZE):
    batch = matches[i:i+CHUNK_SIZE]
    inserts = [(m[0], m[1], m[2], m[2], "cathedral",
               None, None, None, None, None, m[3], m[4],
               "diocese", "cathedral_of", f"Auto-matched (score={m[5]})") for m in batch]
    db.executemany("""
        INSERT INTO catholic_hierarchy
        (parent_id, church_id, name, original_name, cath_type, diocese, archdiocese,
         city, state, country, lat, lon, parent_cath_type, relationship, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, inserts)
    db.commit()

with_gps = db.execute("""
    SELECT COUNT(1) FROM catholic_hierarchy
    WHERE cath_type IN ('diocese','archdiocese') AND lat IS NOT NULL AND lat != 0
""").fetchone()[0]
total = db.execute("SELECT COUNT(1) FROM catholic_hierarchy WHERE cath_type IN ('diocese','archdiocese')").fetchone()[0]
print(f"\nDioceses with GPS: {with_gps:,} / {total:,} ({with_gps*100/total:.1f}%)")
db.close()
