"""DeepSeek US state-by-state review - classify facility types."""
import sqlite3, os, json, requests, sys
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# Get US states with Jewish entries
c.execute("""
    SELECT DISTINCT state FROM churches 
    WHERE faith='Judaism' AND country='US' AND state IS NOT NULL AND state != ''
    ORDER BY state
""")
states = [r[0] for r in c.fetchall()]
print(f"US states with Jewish entries: {len(states)}\n")

CHUNK_SIZE = 20

TYPE_MAP = {
    'SYNAGOGUE': 'synagogue',
    'CHABAD': 'chabad_house',
    'YESHIVA': 'yeshiva',
    'KOLLEL': 'kollel',
    'SCHOOL': 'school',
    'DAY SCHOOL': 'school',
    'HEBREW SCHOOL': 'school',
    'COMMUNITY CENTER': 'community_center',
    'JCC': 'community_center',
    'MIKVEH': 'mikveh',
    'MIKVAH': 'mikveh',
    'HILLEL': 'hillel',
    'CEMETERY': 'cemetery',
    'CEMETARY': 'cemetery',
    'ORGANIZATION': 'organization',
    'OFFICE': 'organization',
    'FOUNDATION': 'organization',
    'MUSEUM': 'museum',
    'RESTAURANT': 'food',
    'BAKERY': 'food',
    'KOSHER': 'food',
    'STORE': 'retail',
    'SHOP': 'retail',
    'BOOKSTORE': 'retail',
    'SENIOR': 'senior_home',
    'NURSING': 'senior_home',
    'CHURCH': 'church',
    'CHRISTIAN': 'church',
    'TEMPLE': 'synagogue',  # default temple->synagogue unless context says otherwise
}

def classify_chunk(chunk):
    items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[4] or ''), "state": str(e[5] or '')} for e in chunk]
    prompt = f"""For each US religious site, determine: (1) is it JEWISH or NOT? (2) what facility type?

Facility types: SYNAGOGUE, CHABAD, YESHIVA, KOLLEL, SCHOOL, COMMUNITY_CENTER, MIKVEH, HILLEL, CEMETERY, MUSEUM, ORGANIZATION, FOOD, RETAIL, SENIOR_HOME

If NOT Jewish, classify as: CHRISTIAN, HINDU, BUDDHIST, ISLAM, or OTHER.

Return ONLY JSON array: [{{"id": N, "classification": "JEWISH|CHRISTIAN|HINDU|BUDDHIST|ISLAM|OTHER", "type": "SYNAGOGUE|CHABAD|...|null"}}]

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

total_entries = 0
total_fixed_faith = 0
total_fixed_type = 0
state_stats = {}

for st in states:
    c.execute("""
        SELECT id, name, name_transliterated, tradition, city, state, country, landmark_type
        FROM churches WHERE faith='Judaism' AND country='US' AND state=?
        ORDER BY name
    """, (st,))
    entries = c.fetchall()
    if not entries: continue
    
    print(f"\n=== {st} ({len(entries):,} entries) ===")
    state_stats[st] = {"total": len(entries), "moved": 0, "retyped": 0}
    
    for cs in range(0, len(entries), CHUNK_SIZE):
        chunk = entries[cs:cs+CHUNK_SIZE]
        print(f"  {cs//CHUNK_SIZE+1}/{(len(entries)-1)//CHUNK_SIZE+1}...", end="")
        sys.stdout.flush()
        
        results = classify_chunk(chunk)
        if not results: print("FAIL"); continue
        
        for r in results:
            id_ = r.get("id")
            cls = r.get("classification","").upper()
            ftype = r.get("type","")
            
            if cls != "JEWISH":
                if cls == "CHRISTIAN":
                    c.execute("UPDATE churches SET faith='Christian', tradition='Protestant', landmark_type='church' WHERE id=?", (id_,))
                elif cls == "HINDU":
                    c.execute("UPDATE churches SET faith='Hindu', tradition='Other', landmark_type='temple' WHERE id=?", (id_,))
                elif cls == "BUDDHIST":
                    c.execute("UPDATE churches SET faith='Buddhist', tradition='Mahayana', landmark_type='temple' WHERE id=?", (id_,))
                elif cls == "ISLAM":
                    c.execute("UPDATE churches SET faith='Islam', tradition='Sunni', landmark_type='mosque' WHERE id=?", (id_,))
                else:
                    c.execute("UPDATE churches SET faith='Other', tradition='New Age', landmark_type='organization' WHERE id=?", (id_,))
                state_stats[st]["moved"] += 1
                total_fixed_faith += 1
            elif ftype:
                # Map the type string
                mapped = TYPE_MAP.get(ftype.upper())
                if mapped and mapped != 'synagogue':  # Only update if it's a specific type
                    c.execute("UPDATE churches SET landmark_type=? WHERE id=? AND (landmark_type IS NULL OR landmark_type='synagogue')", (mapped, id_))
                    state_stats[st]["retyped"] += 1
                    total_fixed_type += 1
        
        conn.commit()
        print(f"{len(results)} done")
    
    ss = state_stats[st]
    if ss["moved"] or ss["retyped"]:
        print(f"  -> {ss['moved']} moved, {ss['retyped']} retyped")

print(f"\n\n=== FINAL ===")
print(f"States processed: {len(state_stats)}")
print(f"Entries moved out of Judaism: {total_fixed_faith}")
print(f"Facility types corrected: {total_fixed_type}")
conn.close()
