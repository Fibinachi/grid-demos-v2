"""DeepSeek classifier for ALL Other-faith entries (34,601).
Reclassifies every entry with faith='Other' — user doesn't trust prior classification.
"""
import sqlite3, os, json, sys, re, requests, time
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SCRIPT_NAME = "classify_other_deepseek"
STARTED_AT = datetime.now(timezone.utc).isoformat()
SOURCE_NAME = "deepseek_other_faith_full_scan"

# ── Query ALL Other-faith entries ──
c.execute("""
    SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches
    WHERE faith = 'Other'
    ORDER BY country, name
""")
entries = c.fetchall()
TOTAL = len(entries)
print(f"Other-faith entries to classify: {TOTAL:,}")

# ── Prompt ──
SYSTEM_PROMPT = """Classify each religious site by determining its CORRECT faith group.

For each entry, analyze the name, location, landmark_type, and any existing tradition to determine:
1. faith: Christian | Islam | Buddhist | Hindu | Jain | Sikh | Shinto | Taoist | Judaism | Confucian | Bahai | Pagan | Non-Religious | Other
2. tradition: Be specific (e.g., Catholic, Sunni, Mahayana, Vaishnavism, Reform, etc.)
3. landmark_type: The correct facility type

Quick classification guide:
- Christian: church, chapel, cathedral, basilica, monastery, convent, abbey, mission, shrine (esp. Virgin Mary/saints), iglesia, ermita, st./saint/san/santa, jesus, christ, gospel, pastor, bishop, protestant, catholic, baptist, methodist, presbyterian, lutheran, orthodox, pentecostal, evangelical, anglican, episcopal, adventist, mennonite, quaker, salvation army, evangelical, born again, christadelphian
- Islam: mosque, masjid, cami, islamic, muslim, madrasa, dargah, minaret, sufi
- Buddhist: wat, vihara, buddha, dharma, pagoda, stupa, temple (Thai/Cambodian/Japanese context), theravada, mahayana, zen
- Hindu: mandir, temple (Indian context), shiva, vishnu, krishna, hanuman, devi, ganesha
- Shinto: jinja, jingu, shrine (Japan context), kami
- Taoist: tao, taoist, dao, temple (Chinese folk context)
- Judaism: synagogue, jewish, shul, temple (Jewish context), chabad
- Bahai: bahai, baha'i
- Sikh: gurdwara, sikh
- Jain: jain, derasar
- Non-Religious: secular, atheist, humanist, ethical society, non-religious cemetery, non denominational (if clearly secular)
- Pagan: wicca, druid, pagan, norse, hellenic, kemetic

Return ONLY valid JSON:
[{"id": N, "faith": "...", "tradition": "...", "landmark_type": "..."}]"""

CHUNK_SIZE = 30
total_classified = 0
total_moved = 0
api_calls = 0
start_time = time.time()
chunks_done = 0


def progress_bar(current, total, **kwargs):
    pct = current / total * 100
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / rate if rate > 0 else 0
    parts = [f"\r  {current:,}/{total:,} ({pct:.0f}%) | {rate:.0f}/s | ETA {eta:.0f}s"]
    for k, v in kwargs.items():
        parts.append(f"{k}={v:,}")
    print(" | ".join(parts), end="", flush=True)


def call_deepseek(items):
    global api_calls
    user_text = json.dumps(items, indent=2)
    prompt = f"{SYSTEM_PROMPT}\n\n{user_text}"

    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.05, "max_tokens": 4096
        }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=180)
        api_calls += 1

        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            jm = re.search(r'\[.*\]', content, re.DOTALL)
            if jm:
                try:
                    return json.loads(jm.group())
                except json.JSONDecodeError:
                    print(f"\n  JSON PARSE ERROR: {content[:200]}")
                    return None
            print(f"\n  NO JSON in response: {content[:200]}")
            return None
        print(f"\n  HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return None


def log_enrichment(church_id, field, old_val, new_val):
    c.execute("""INSERT INTO enrichment_change_log 
        (church_id, field_name, old_value, new_value, change_source) 
        VALUES (?, ?, ?, ?, ?)""",
        (church_id, field, str(old_val) if old_val is not None else None,
         str(new_val) if new_val is not None else None, SOURCE_NAME))


def update_field(church_id, field, new_val):
    c.execute(f"SELECT {field} FROM churches WHERE id=?", (church_id,))
    row = c.fetchone()
    old_val = row[0] if row else None
    if str(old_val) != str(new_val):
        c.execute(f"UPDATE churches SET {field}=? WHERE id=?", (new_val, church_id))
        log_enrichment(church_id, field, old_val, new_val)
        return True
    return False


def process_results(results):
    global total_classified, total_moved
    if not results:
        return

    faith_map = {
        'CHRISTIAN': 'Christian', 'ISLAM': 'Islam', 'BUDDHIST': 'Buddhist',
        'HINDU': 'Hindu', 'JAIN': 'Jain', 'SIKH': 'Sikh',
        'SHINTO': 'Shinto', 'TAOIST': 'Taoist', 'JUDAISM': 'Judaism',
        'CONFUCIAN': 'Confucian', 'BAHAI': 'Bahai', 'PAGAN': 'Pagan',
        'NON-RELIGIOUS': 'Non-Religious', 'OTHER': 'Other',
        'OTHER ABRAHAMIC': 'Other Abrahamic',
        'NON_RELIGIOUS': 'Non-Religious',
    }

    for r in results:
        rid = r.get("id")
        if not rid:
            continue

        new_faith = faith_map.get(r.get("faith", "").upper().replace(" ", "_"), "Other")
        new_trad = r.get("tradition", "")
        new_type = (r.get("landmark_type") or "").lower().replace(" ", "_")

        if update_field(rid, "faith", new_faith):
            total_moved += 1
        if new_trad:
            update_field(rid, "tradition", new_trad)
        if new_type:
            update_field(rid, "landmark_type", new_type)
        total_classified += 1


# ── Main scan loop ──
print("\nScanning...")
for cs in range(0, TOTAL, CHUNK_SIZE):
    chunk = entries[cs:cs + CHUNK_SIZE]
    items = [{"id": e[0], "name": str(e[1] or ""), "city": str(e[2] or ""),
              "state": str(e[3] or ""), "country": str(e[4] or ""),
              "type": str(e[5] or ""), "tradition": str(e[6] or "")} for e in chunk]

    chunks_done += 1
    if chunks_done == 1:
        print(f"Chunk 1: {len(items)} entries, prompt ~{len(json.dumps(items)):,} chars...", flush=True)
    
    results = call_deepseek(items)
    if results:
        if chunks_done == 1:
            print(f"OK ({len(results)} results)", flush=True)
        process_results(results)
        conn.commit()
    else:
        if chunks_done == 1:
            print(f"FAILED, retrying...", flush=True)
        time.sleep(3)
        results = call_deepseek(items)  # retry once
        if results:
            if chunks_done == 1:
                print(f"OK on retry", flush=True)
            process_results(results)
            conn.commit()
        elif chunks_done == 1:
            print(f"FAILED on retry too", flush=True)

    time.sleep(0.3)  # gentle rate limit

    processed = min(cs + CHUNK_SIZE, TOTAL)
    progress_bar(processed, TOTAL, moved=total_moved, classified=total_classified, calls=api_calls)

print()
elapsed = time.time() - start_time
print(f"\n=== Scan complete ({elapsed:.0f}s) ===")
print(f"  Total entries:  {TOTAL:,}")
print(f"  API calls:      {api_calls:,}")
print(f"  Classified:     {total_classified:,}")
print(f"  Moved out:      {total_moved:,}")

# ── Summary ──
print("\n=== New faith distribution (scanned entries) ===")
c.execute("""SELECT faith, COUNT(*) FROM churches 
    WHERE id IN (SELECT DISTINCT church_id FROM enrichment_change_log WHERE change_source=?) 
    GROUP BY faith ORDER BY COUNT(*) DESC""", (SOURCE_NAME,))
for row in c.fetchall():
    print(f"  {row[0]:25s} {row[1]:>8,}")

still_other = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Other'").fetchone()[0]
print(f"\n  Remaining Other faith: {still_other:,}")

conn.close()
