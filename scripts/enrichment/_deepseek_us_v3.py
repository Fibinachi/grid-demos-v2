"""DeepSeek US state-by-state v3 - classify Christian tradition too."""
import sqlite3, os, json, requests, sys
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

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
    
    prompt = f"""For each US religious site, classify it and specify its tradition.

If CHRISTIAN, specify tradition as one of: Catholic, Baptist, Methodist, Lutheran, Presbyterian, Pentecostal, Episcopal, Anglican, Mormon/LDS, Jehovah's Witnesses, Seventh-day Adventist, Orthodox, Congregational, Church of Christ, Non-denominational, Evangelical, Messianic, Salvation Army, Quaker, United Church of Christ, Christian Science, or Other Christian.

If JEWISH, specify tradition as: Orthodox, Conservative, Reform, Reconstructionist, Chabad, Sephardic, Humanistic, Karaite, or Rabbinic (default).

Facility types for JEWISH: SYNAGOGUE, CHABAD, YESHIVA, KOLLEL, SCHOOL, COMMUNITY_CENTER, MIKVEH, HILLEL, CEMETERY, MUSEUM, ORGANIZATION, FOOD, RETAIL, SENIOR_HOME
Facility types for CHRISTIAN: CHURCH, CATHEDRAL, CHAPEL, ABBEY, MISSION, CEMETERY, SCHOOL
Facility types for others: MOSQUE, TEMPLE, ORGANIZATION

Return ONLY JSON array:
[{{"id": N, "faith": "JEWISH|CHRISTIAN|HINDU|BUDDHIST|ISLAM|OTHER", "tradition": "Catholic|Baptist|...", "type": "SYNAGOGUE|CHURCH|...|null"}}]

{json.dumps(items, indent=2)}"""
    
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
            "model": "deepseek-chat", "messages": [{"role":"user","content":prompt}],
            "temperature": 0.1, "max_tokens": 2500
        }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=60)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            import re; jm = re.search(r'\[.*?\]', content, re.DOTALL)
            if jm: return json.loads(jm.group())
        else:
            print(f" API{resp.status_code}", end="")
    except Exception as e: print(f" Err:{e}", end="")
    return []

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
    
    print(f"\n=== {st} ({len(entries):,}) ===")
    
    for cs in range(0, len(entries), CHUNK_SIZE):
        chunk = entries[cs:cs+CHUNK_SIZE]
        print(f"  {cs//CHUNK_SIZE+1}/{(len(entries)-1)//CHUNK_SIZE+1}...", end="")
        sys.stdout.flush()
        
        results = classify_chunk(chunk)
        if not results: print("FAIL"); continue
        
        for r in results:
            id_ = r.get("id")
            faith = r.get("faith","").upper()
            trad = r.get("tradition","")
            ftype = (r.get("type") or "").upper()
            
            moved = False
            if faith == "CHRISTIAN":
                mapped_type = ftype.lower() if ftype in ('CHURCH','CATHEDRAL','CHAPEL','ABBEY','MISSION','CEMETERY','SCHOOL') else 'church'
                c.execute("UPDATE churches SET faith='Christian', tradition=?, landmark_type=? WHERE id=?", (trad or 'Protestant', mapped_type, id_))
                moved = True
            elif faith == "HINDU":
                c.execute("UPDATE churches SET faith='Hindu', tradition=?, landmark_type=? WHERE id=?", (trad or 'Other', 'temple', id_))
                moved = True
            elif faith == "BUDDHIST":
                c.execute("UPDATE churches SET faith='Buddhist', tradition=?, landmark_type=? WHERE id=?", (trad or 'Mahayana', ftype.lower() if ftype else 'temple', id_))
                moved = True
            elif faith == "ISLAM":
                c.execute("UPDATE churches SET faith='Islam', tradition=?, landmark_type=? WHERE id=?", (trad or 'Sunni', ftype.lower() if ftype else 'mosque', id_))
                moved = True
            elif faith in ("OTHER", "NEWAGE"):
                c.execute("UPDATE churches SET faith='Other', tradition='New Age', landmark_type=? WHERE id=?", (ftype.lower() if ftype else 'organization', id_))
                moved = True
            
            if moved:
                total_moved += 1
            elif ftype and ftype not in ('SYNAGOGUE', 'TEMPLE', ''):
                mapped_type = ftype.lower().replace('_', ' ')
                if mapped_type != 'synagogue':
                    c.execute("UPDATE churches SET landmark_type=? WHERE id=? AND (landmark_type IS NULL OR landmark_type='synagogue')", (mapped_type, id_))
                    total_retyped += 1
                # Also set tradition if provided
                if trad and trad not in ('Rabbinic', ''):
                    c.execute("UPDATE churches SET tradition=? WHERE id=? AND (tradition IS NULL OR tradition='')", (trad, id_))
        
        conn.commit()
        print(f"OK", end=" ")
    
    print(f" | M:{total_moved} R:{total_retyped}")

print(f"\n\nFINAL: {total_moved} moved out, {total_retyped} retyped")
conn.close()
