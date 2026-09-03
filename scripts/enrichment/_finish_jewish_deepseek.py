"""Finish the DeepSeek scan of American Judaism.

Issues to fix:
1. 83 entries with landmark_type='church' but faith still='Judaism' → re-scan via DeepSeek
2. 3 entries with NULL landmark_type → classify via DeepSeek
3. Normalization: 'chabad'→'chabad_house', 'community center'→'community_center', 
   'temple'→'synagogue', 'senior home'→'senior_home'
4. 2 entries with tradition='Jewish' → 'Rabbinic'
"""
import sqlite3, os, json, requests, sys, re
from datetime import datetime

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

# ── Step 1: Fix normalization issues (no API needed) ──

print("=== Step 1: Normalization fixes ===")

fixes = {
    "landmark_type = 'community_center'": "landmark_type = 'community center'",
    "landmark_type = 'chabad_house'": "landmark_type = 'chabad'",
    "landmark_type = 'synagogue'": "landmark_type = 'temple'",
    "landmark_type = 'senior_home'": "landmark_type = 'senior home'",
}

normalized = 0
for new_val, old_val in fixes.items():
    c.execute(f"UPDATE churches SET {new_val} WHERE faith='Judaism' AND country='US' AND {old_val}")
    n = c.rowcount
    if n:
        old_type = old_val.split("=")[1].strip().strip("'")
        new_type = new_val.split("=")[1].strip().strip("'")
        print(f"  Fixed {n} entries: {old_type} -> {new_type}")
        normalized += n

# Fix tradition='Jewish' → 'Rabbinic'
c.execute("UPDATE churches SET tradition='Rabbinic' WHERE faith='Judaism' AND country='US' AND tradition='Jewish'")
n = c.rowcount
if n:
    print(f"  Fixed {n} entries: tradition='Jewish' → 'Rabbinic'")
    normalized += n

conn.commit()
print(f"  Normalized {normalized} total")

# ── Step 2: Get entries needing DeepSeek re-scan ──

print("\n=== Step 2: DeepSeek re-scan ===")

c.execute("""
    SELECT id, name, city, state, landmark_type, tradition
    FROM churches WHERE faith='Judaism' AND country='US'
    AND (landmark_type IS NULL OR landmark_type IN ('church','chapel','cathedral','mosque','abbey','shrine'))
    ORDER BY state, name
""")
entries = c.fetchall()
print(f"Entries needing DeepSeek scan: {len(entries)}")

if not entries:
    print("Nothing to scan. Done!")
else:
    CHUNK_SIZE = 20
    total_moved = 0
    total_retyped = 0
    
    for cs in range(0, len(entries), CHUNK_SIZE):
        chunk = entries[cs:cs+CHUNK_SIZE]
        items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''), "state": str(e[3] or '')} for e in chunk]
        
        batch_num = cs // CHUNK_SIZE + 1
        total_batches = (len(entries) - 1) // CHUNK_SIZE + 1
        
        prompt = f"""Classify each US religious site entry carefully.

Key rules:
- Names with: church, chapel, cathedral, abbey, shrine, jesus, christ, gospel, mission (religious), saint, pastor, bishop, trinity, holy, grace, faith, cross, potter's house, victory outreach, good shepherd, family altar, freedom life, cornerstone, potters house, holy cross → CHRISTIAN
- Names with: synagogue, temple (Jewish context), beth, chabad, rabbi, torah, yeshiva, kollel, hillel, mikvah, israel (Jewish org), judaism, jewish, zion (Jewish), hebrew → JEWISH
- Non-religious: foundation, society, museum, library, institute, university, college, school (non-yeshiva), community (non-church), center (non-church), fund, theatre, broadcasting, communications, association → OTHER
- Hindu, Buddhist, Islamic names → use those faith labels

For CHRISTIAN entries, specify the Christian tradition (Catholic, Baptist, Methodist, Lutheran, Presbyterian, Pentecostal, Episcopal, Non-denominational, etc.)
For JEWISH entries, specify type: SYNAGOGUE, CHABAD, YESHIVA, KOLLEL, SCHOOL, COMMUNITY_CENTER, MIKVEH, HILLEL, CEMETERY, MUSEUM, ORGANIZATION
For CHRISTIAN entries, facility type: CHURCH, CATHEDRAL, CHAPEL, ABBEY, MISSION

Return ONLY valid JSON array (no markdown, no commentary):
[{{"id": N, "faith": "CHRISTIAN|JEWISH|HINDU|BUDDHIST|ISLAM|OTHER", "tradition": "...", "type": "SYNAGOGUE|CHURCH|...|null"}}]

{json.dumps(items, indent=2)}"""
        
        print(f"  Batch {batch_num}/{total_batches} ({len(items)} entries)...", end=" ")
        sys.stdout.flush()
        
        try:
            resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.05,
                "max_tokens": 2500
            }, headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }, timeout=90)
            
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                jm = re.search(r'\[.*?\]', content, re.DOTALL)
                if jm:
                    results = json.loads(jm.group())
                    moved_batch = 0
                    for r in results:
                        id_ = r.get("id")
                        faith = r.get("faith", "").upper()
                        trad = r.get("tradition", "")
                        ftype = (r.get("type") or "").upper()
                        
                        if faith == "CHRISTIAN":
                            mapped = ftype.lower() if ftype in ('CHURCH','CATHEDRAL','CHAPEL','ABBEY','MISSION','CEMETERY') else 'church'
                            c.execute("UPDATE churches SET faith='Christian', tradition=?, landmark_type=? WHERE id=?", 
                                      (trad or 'Protestant', mapped, id_))
                            total_moved += 1
                            moved_batch += 1
                        elif faith == "HINDU":
                            c.execute("UPDATE churches SET faith='Hindu', tradition=?, landmark_type='temple' WHERE id=?", (trad or 'Other', id_))
                            total_moved += 1
                            moved_batch += 1
                        elif faith == "BUDDHIST":
                            c.execute("UPDATE churches SET faith='Buddhist', tradition=?, landmark_type='temple' WHERE id=?", (trad or 'Mahayana', id_))
                            total_moved += 1
                            moved_batch += 1
                        elif faith == "ISLAM":
                            c.execute("UPDATE churches SET faith='Islam', tradition=?, landmark_type='mosque' WHERE id=?", (trad or 'Sunni', id_))
                            total_moved += 1
                            moved_batch += 1
                        elif faith in ("OTHER", "NEWAGE", "NON-RELIGIOUS"):
                            c.execute("UPDATE churches SET faith='Other', tradition='New Age', landmark_type='organization' WHERE id=?", (id_,))
                            total_moved += 1
                            moved_batch += 1
                        else:
                            # Still Jewish - just set landmark_type
                            mapped = ftype.lower().replace('_', ' ') if ftype else 'synagogue'
                            if mapped == 'temple':
                                mapped = 'synagogue'
                            c.execute("UPDATE churches SET landmark_type=?, tradition=COALESCE(NULLIF(tradition,''),?) WHERE id=?", 
                                      (mapped, trad or 'Rabbinic', id_))
                            total_retyped += 1
                    
                    conn.commit()
                    print(f"OK — {moved_batch} moved, {len(results)-moved_batch} retyped")
                else:
                    print(f"NO JSON in response")
                    print(f"  Response: {content[:200]}")
            else:
                print(f"HTTP {resp.status_code}")
        except Exception as e:
            print(f"ERROR: {e}")
    
    print(f"\n=== DeepSeek scan complete ===")
    print(f"  Moved out of Judaism: {total_moved}")
    print(f"  Retyped (still Jewish): {total_retyped}")

# ── Step 3: Final verification ──

print("\n=== Step 3: Final verification ===")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US'")
remaining = c.fetchone()[0]
print(f"Total Judaism in US: {remaining:,}")

c.execute("SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' GROUP BY landmark_type ORDER BY COUNT(*) DESC")
print("\nRemaining by landmark_type:")
for row in c.fetchall():
    print(f"  {row[0]:20s} {row[1]:>7,}")

# Check for any remaining problematic types
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))")
bad = c.fetchone()[0]
print(f"\nStill problematic: {bad}")
if bad > 0:
    print("\nRemaining problematic entries:")
    c.execute("""
        SELECT id, name, city, state, landmark_type FROM churches 
        WHERE faith='Judaism' AND country='US' 
        AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))
        ORDER BY state
    """)
    for r in c.fetchall():
        print(f"  #{r[0]:>8} {str(r[1] or ''):45s} {str(r[2] or ''):20s} {str(r[3] or ''):10s} type={r[4]}")

# Check normalization
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='chabad'")
n = c.fetchone()[0]
print(f"\nStill 'chabad' (should be 'chabad_house'): {n}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='community center'")
n = c.fetchone()[0]
print(f"Still 'community center' (should be 'community_center'): {n}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='temple'")
n = c.fetchone()[0]
print(f"Still 'temple' (should be 'synagogue'): {n}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND landmark_type='senior home'")
n = c.fetchone()[0]
print(f"Still 'senior home' (should be 'senior_home'): {n}")

conn.close()
print("\nDone!")
