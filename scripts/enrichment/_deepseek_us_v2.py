"""DeepSeek US state-by-state review v2 - fixed faith/type logic."""
import sqlite3, os, json, requests, sys
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# Get states we haven't done yet (states with fewer than expected processed entries)
# States already processed: AK, AL, AR, AZ, 'Alabama', 'Alaska', 'Arizona', 'Arkansas', CA, CO, CT, 'California' (partial)
c.execute("""
    SELECT DISTINCT state FROM churches 
    WHERE faith='Judaism' AND country='US' AND state IS NOT NULL AND state != ''
    ORDER BY state
""")
all_states = [r[0] for r in c.fetchall()]
print(f"Total US states/territories: {len(all_states)}")

CHUNK_SIZE = 20

def classify_chunk(chunk):
    items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[4] or ''), "state": str(e[5] or '')} for e in chunk]
    prompt = f"""For each US religious site, classify it. Rules:
- If it's a Jewish site (synagogue, Chabad, yeshiva, Hillel, mikvah, JCC, etc): classification=JEWISH
- If the name contains church/cathedral/chapel/abbey/mosque/mission/saint/bishop/pastor/etc: classification=CHRISTIAN
- If it's a school, university, college, library, museum, foundation, society, or similar non-religious entity: classification=OTHER
- If it's a Hindu, Buddhist, Islamic site: use those labels

Facility types: SYNAGOGUE, CHABAD, YESHIVA, KOLLEL, SCHOOL, COMMUNITY_CENTER, MIKVEH, HILLEL, CEMETERY, MUSEUM, ORGANIZATION, FOOD, RETAIL, SENIOR_HOME, CHURCH (for Christian), MOSQUE (for Islam), TEMPLE (for Hindu/Buddhist)

Return ONLY JSON array: [{{"id": N, "classification": "JEWISH|CHRISTIAN|HINDU|BUDDHIST|ISLAM|OTHER", "type": "SYNAGOGUE|...|null"}}]

{json.dumps(items, indent=2)}"""
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
            "model": "deepseek-chat", "messages": [{"role":"user","content":prompt}],
            "temperature": 0.1, "max_tokens": 2000
        }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=60)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            import re; jm = re.search(r'\[.*?\]', content, re.DOTALL)
            if jm: return json.loads(jm.group())
    except Exception as e: print(f"  Error: {e}")
    return []

# Faith map for non-Jewish types
TYPE_TO_FAITH = {
    'CHURCH': ('Christian', 'Protestant'),
    'CATHEDRAL': ('Christian', 'Catholic'),
    'CHAPEL': ('Christian', 'Protestant'),
    'ABBEY': ('Christian', 'Catholic'),
    'MOSQUE': ('Islam', 'Sunni'),
    'TEMPLE': None,  # Ambiguous - check classification
}

total_entries = 0
total_moved = 0
total_retyped = 0

for st in all_states:
    c.execute("""
        SELECT id, name, name_transliterated, tradition, city, state, country, landmark_type
        FROM churches WHERE faith='Judaism' AND country='US' AND state=?
        ORDER BY name
    """, (st,))
    entries = c.fetchall()
    if not entries: continue
    
    print(f"\n=== {st} ({len(entries):,} entries) ===")
    
    for cs in range(0, len(entries), CHUNK_SIZE):
        chunk = entries[cs:cs+CHUNK_SIZE]
        print(f"  {cs//CHUNK_SIZE+1}/{(len(entries)-1)//CHUNK_SIZE+1}...", end="")
        sys.stdout.flush()
        
        results = classify_chunk(chunk)
        if not results: print("FAIL"); continue
        
        for r in results:
            id_ = r.get("id")
            cls = r.get("classification","").upper()
            ftype = (r.get("type") or "").upper()
            
            moved = False
            # Determine correct faith based on type first
            if ftype in TYPE_TO_FAITH:
                faith_map = TYPE_TO_FAITH[ftype]
                if faith_map:
                    c.execute("UPDATE churches SET faith=?, tradition=?, landmark_type=? WHERE id=?", 
                              (faith_map[0], faith_map[1], ftype.lower(), id_))
                    moved = True
            elif cls == "CHRISTIAN":
                c.execute("UPDATE churches SET faith='Christian', tradition='Protestant', landmark_type=COALESCE(?, 'church') WHERE id=?", (ftype.lower() if ftype else None, id_))
                moved = True
            elif cls == "HINDU":
                c.execute("UPDATE churches SET faith='Hindu', tradition='Other', landmark_type=COALESCE(?, 'temple') WHERE id=?", (ftype.lower() if ftype else None, id_))
                moved = True
            elif cls == "BUDDHIST":
                c.execute("UPDATE churches SET faith='Buddhist', tradition='Mahayana', landmark_type=COALESCE(?, 'temple') WHERE id=?", (ftype.lower() if ftype else None, id_))
                moved = True
            elif cls == "ISLAM":
                c.execute("UPDATE churches SET faith='Islam', tradition='Sunni', landmark_type=COALESCE(?, 'mosque') WHERE id=?", (ftype.lower() if ftype else None, id_))
                moved = True
            elif cls == "OTHER":
                c.execute("UPDATE churches SET faith='Other', tradition='New Age', landmark_type=COALESCE(?, 'organization') WHERE id=?", (ftype.lower() if ftype else None, id_))
                moved = True
            
            if moved:
                total_moved += 1
            elif ftype and ftype not in ('SYNAGOGUE', 'TEMPLE'):
                # Still Jewish but has a specific facility type
                mapped_type = ftype.lower().replace('_', ' ')
                if mapped_type != 'synagogue':
                    c.execute("UPDATE churches SET landmark_type=? WHERE id=? AND (landmark_type IS NULL OR landmark_type='synagogue')", (mapped_type, id_))
                    total_retyped += 1
        
        conn.commit()
        print(f"{len(results)} done")
    
    moved_here = sum(1 for r in results if r.get("classification","").upper() != "JEWISH") if results else 0
    print(f"  -> cumulative: {total_moved} moved, {total_retyped} retyped")

print(f"\n\n=== FINAL ===")
print(f"States processed: {len(all_states)}")
print(f"Entries moved out of Judaism: {total_moved}")
print(f"Facility types corrected: {total_retyped}")
conn.close()
