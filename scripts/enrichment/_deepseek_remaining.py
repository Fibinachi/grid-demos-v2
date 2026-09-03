"""Quick cleanup of remaining 646 entries across 35 states."""
import sqlite3, os, json, requests, sys, re
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

c.execute("""
    SELECT id, name, tradition, city, state, country, landmark_type FROM churches
    WHERE faith='Judaism' AND country='US'
    AND (landmark_type IS NULL OR landmark_type = '' 
         OR landmark_type IN ('church','chapel','cathedral','mosque','abbey','shrine'))
    ORDER BY state
""")
entries = c.fetchall()
print(f"Remaining: {len(entries)} entries")

CHUNK_SIZE = 20

for cs in range(0, len(entries), CHUNK_SIZE):
    chunk = entries[cs:cs+CHUNK_SIZE]
    items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[3] or ''), "state": str(e[4] or '')} for e in chunk]
    
    prompt = f"""Classify each US religious site. Rules:
- Christian names (church, chapel, cathedral, jesus, gospel, mission, saint, etc): CHRISTIAN
- Jewish names (synagogue, temple, beth, chabad, rabbi, torah, etc): JEWISH  
- Other faiths: HINDU, BUDDHIST, ISLAM, as appropriate
- Non-religious (foundation, society, museum, library, etc): OTHER

If CHRISTIAN, specify tradition: Catholic, Baptist, Methodist, Lutheran, Presbyterian, Pentecostal, Episcopal, Non-denominational, etc.
If JEWISH, specify type: SYNAGOGUE, CHABAD, YESHIVA, KOLLEL, SCHOOL, COMMUNITY_CENTER, MIKVEH, HILLEL, CEMETERY, MUSEUM, ORGANIZATION

Return ONLY JSON: [{{"id": N, "faith": "JEWISH|CHRISTIAN|OTHER", "tradition": "...", "type": "SYNAGOGUE|CHURCH|..."}}]

{json.dumps(items, indent=2)}"""
    
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
            "model": "deepseek-chat", "messages": [{"role":"user","content":prompt}],
            "temperature": 0.1, "max_tokens": 2000
        }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=60)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            jm = re.search(r'\[.*?\]', content, re.DOTALL)
            if jm:
                for r in json.loads(jm.group()):
                    id_ = r.get("id")
                    faith = r.get("faith","").upper()
                    trad = r.get("tradition","")
                    ftype = (r.get("type") or "").upper()
                    
                    if faith == "CHRISTIAN":
                        mapped = ftype.lower() if ftype in ('CHURCH','CATHEDRAL','CHAPEL','ABBEY','MISSION','CEMETERY') else 'church'
                        c.execute("UPDATE churches SET faith='Christian', tradition=?, landmark_type=? WHERE id=?", (trad or 'Protestant', mapped, id_))
                    elif faith == "HINDU":
                        c.execute("UPDATE churches SET faith='Hindu', tradition='Other', landmark_type='temple' WHERE id=?", (id_,))
                    elif faith == "BUDDHIST":
                        c.execute("UPDATE churches SET faith='Buddhist', tradition='Mahayana', landmark_type='temple' WHERE id=?", (id_,))
                    elif faith == "ISLAM":
                        c.execute("UPDATE churches SET faith='Islam', tradition='Sunni', landmark_type='mosque' WHERE id=?", (id_,))
                    elif faith in ("OTHER","NEWAGE"):
                        c.execute("UPDATE churches SET faith='Other', tradition='New Age', landmark_type='organization' WHERE id=?", (id_,))
                    elif ftype:
                        mapped = ftype.lower().replace('_',' ')
                        c.execute("UPDATE churches SET landmark_type=?, tradition=COALESCE(NULLIF(tradition,''),?) WHERE id=?", (mapped, trad or 'Rabbinic', id_))
                conn.commit()
        else:
            print(f" API{resp.status_code}", end="")
    except Exception as e:
        print(f" ERR", end="")
    
    print(f" {cs//CHUNK_SIZE+1}/{(len(entries)-1)//CHUNK_SIZE+1}", end=" ")

print(f"\n\nDone!")
conn.close()
