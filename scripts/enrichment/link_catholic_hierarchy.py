"""
Church Hierarchy Linking — Phase 2: Link Catholic parishes to their diocese using sitemap data
"""
import sqlite3, csv, json, re

DB = "churches.db"

def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# Load diocese data with province mapping
dioceses = json.load(open("data/catholic_dioceses.json"))
diocese_by_name = {}
for d in dioceses:
    key = d["name"].upper().replace("ARCHDIOCESE", "ARCHDIOCESE").replace("DIOCESE", "DIOCESE")
    diocese_by_name[key] = d

print(f"Loaded {len(dioceses)} Catholic dioceses")

# Load parish sitemap data
parish_rows = list(csv.DictReader(open("data/diocese_parishes.csv", encoding="utf-8")))
print(f"Loaded {len(parish_rows)} parish URLs from {len(set(r['diocese'] for r in parish_rows))} dioceses")

conn = get_conn()
cur = conn.cursor()

# Build a lookup: diocese name -> (archdiocese/province info)
diocese_info = {}
for d in dioceses:
    name = d["name"]
    province = d.get("province", "")
    diotype = d.get("type", "")
    state = d.get("state", "")
    # Extract the archdiocese from province name
    archdiocese = province.replace("Province of ", "") if province.startswith("Province of") else ""
    diocese_info[name.upper()] = {
        "diocese": name,
        "archdiocese": archdiocese if diotype == "Archdiocese" else "",
        "province": province,
        "diocese_type": diotype,
        "state": state,
    }

# For each parish record, try to match to a church in the DB
matched = 0
parish_count = 0
for row in parish_rows:
    parish_name = row.get("parish_name", "").strip()
    parish_url = row.get("parish_url", "").strip()
    diocese_name = row.get("diocese", "").strip()
    state = row.get("state", "").strip()
    
    if not parish_name:
        continue
    
    parish_count += 1
    info = diocese_info.get(diocese_name.upper())
    if not info:
        continue
    
    # Try to match parish to a church in the same city/state by name similarity
    # First try exact name match
    cur.execute(
        "SELECT id, name, city FROM churches WHERE UPPER(name)=? AND state=? LIMIT 1",
        (parish_name.upper(), state if state else info["state"])
    )
    church = cur.fetchone()
    
    if not church:
        # Try LIKE match with first significant word
        first_word = parish_name.upper().split()[0] if parish_name.split() else ""
        if len(first_word) > 3:
            cur.execute(
                "SELECT id, name, city FROM churches WHERE UPPER(name) LIKE ? AND state=? LIMIT 1",
                (f"{first_word}%", state if state else info["state"])
            )
            church = cur.fetchone()
    
    if church:
        # Update the church's diocese fields
        updates = []
        if info["diocese"]:
            updates.append(("diocese", info["diocese"]))
        if info["archdiocese"]:
            updates.append(("archdiocese", info["archdiocese"]))
        if info["province"]:
            updates.append(("province", info["province"]))
        
        for field, value in updates:
            cur.execute(f"UPDATE churches SET {field}=? WHERE id=? AND ({field} IS NULL OR {field}='')", (value, church["id"]))
        
        matched += 1
        if matched <= 10 or matched % 500 == 0:
            print(f"  {parish_name[:50]:50s} -> {church['name'][:40]:40s} | diocese={info['diocese'][:30]}")

conn.commit()
conn.close()

print(f"\n=== RESULTS ===")
print(f"Parish records processed: {parish_count}")
print(f"Churches matched to diocese: {matched}")
