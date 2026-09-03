"""Gemini classifier for ALL Other-faith entries (34,601).
Reclassifies every entry with faith='Other' using Gemini Flash (free tier).
Mirrors DeepSeek scan pattern but uses Google Gemini API.
"""
import sqlite3, os, json, sys, re, time
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

API_KEY = os.environ.get("GOOGLE_GEMINI_API_KEY", "")
if not API_KEY:
    print("ERROR: GOOGLE_GEMINI_API_KEY not set!")
    sys.exit(1)

from google import genai

SCRIPT_NAME = "classify_other_gemini"
STARTED_AT = datetime.now(timezone.utc).isoformat()
SOURCE_NAME = "gemini_other_faith_scan"

client = genai.Client(api_key=API_KEY)
GEMINI_MODEL = "models/gemini-2.0-flash"

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
SYSTEM_PROMPT = """You are a religious site classifier. For each entry, analyze the name, location, landmark_type, and existing tradition to determine the CORRECT faith.

Faith options: Christian, Islam, Buddhist, Hindu, Jain, Sikh, Shinto, Taoist, Judaism, Confucian, Bahai, Pagan, Non-Religious, Other

Quick guide:
- CHRISTIAN: church, chapel, cathedral, basilica, monastery, convent, abbey, mission, shrine (Mary/saints), iglesia, ermita, st./saint/san/santa, jesus, christ, gospel, pastor, bishop, protestant, catholic, baptist, methodist, presbyterian, lutheran, orthodox, pentecostal, evangelical, anglican, episcopal, salvation army, adventist, mennonite, quaker
- ISLAM: mosque, masjid, cami, islamic, muslim, madrasa, dargah, minaret, sufi
- BUDDHIST: wat, vihara, buddha, dharma, pagoda, stupa, temple (Thai/Cambodian/Japanese/Chinese/Korean context), theravada, mahayana, zen
- HINDU: mandir, temple (Indian context), shiva, vishnu, krishna, hanuman, devi
- SHINTO: jinja, jingu, shrine (Japan context), kami
- TAOIST: tao, taoist, dao, temple (Chinese folk context)
- JUDAISM: synagogue, jewish, shul, temple (Jewish context), chabad
- BAHAI: bahai, baha'i
- SIKH: gurdwara, sikh
- JAIN: jain, derasar
- NON-RELIGIOUS: secular, atheist, humanist, ethical society, non-religious cemetery
- PAGAN: wicca, druid, pagan, norse, hellenic polytheism

For each entry also provide:
- tradition: specific denomination/tradition (e.g., "Catholic", "Sunni", "Mahayana", "Vaishnavism", "Reform")
- landmark_type: correct facility type (church, mosque, temple, shrine, synagogue, gurdwara, monastery, chapel, cathedral, pagoda, community_center, cemetery, school, organization, museum, other)

Return ONLY valid JSON array: [{"id": N, "faith": "...", "tradition": "...", "landmark_type": "..."}]"""

CHUNK_SIZE = 50
total_classified = 0
total_moved = 0
api_calls = 0
start_time = time.time()

def progress_bar(current, total, **kwargs):
    pct = current / total * 100
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / rate if rate > 0 else 0
    parts = [f"\r  {current:,}/{total:,} ({pct:.0f}%) | {rate:.0f}/s | ETA {eta:.0f}s"]
    for k, v in kwargs.items():
        parts.append(f"{k}={v:,}")
    print(" | ".join(parts), end="", flush=True)


def call_gemini(items):
    global api_calls
    user_text = json.dumps(items, indent=2)
    
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_text,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.05,
                max_output_tokens=4096,
            ),
        )
        api_calls += 1
        text = resp.text.strip()
        # Strip markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
        jm = re.search(r'\[.*\]', text, re.DOTALL)
        if jm:
            try:
                return json.loads(jm.group())
            except json.JSONDecodeError:
                print(f"\n  JSON PARSE ERROR: {text[:200]}")
                return None
        print(f"\n  NO JSON in response: {text[:200]}")
        return None
    except Exception as e:
        print(f"\n  GEMINI ERROR: {e}")
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
    }

    for r in results:
        rid = r.get("id")
        if not rid:
            continue
        
        new_faith = faith_map.get(r.get("faith", "").upper(), "Other")
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

    results = call_gemini(items)
    if results:
        process_results(results)
        conn.commit()
    else:
        time.sleep(2)
        results = call_gemini(items)  # retry once
        if results:
            process_results(results)
            conn.commit()

    # Respect rate limit: 60 RPM = 1/sec
    time.sleep(1.05)
    
    processed = min(cs + CHUNK_SIZE, TOTAL)
    progress_bar(processed, TOTAL, moved=total_moved, classified=total_classified, calls=api_calls)

print()
elapsed = time.time() - start_time
print(f"\n=== Scan complete ({elapsed:.0f}s) ===")
print(f"  Total entries: {TOTAL:,}")
print(f"  API calls:     {api_calls:,}")
print(f"  Classified:    {total_classified:,}")
print(f"  Moved out of Other: {total_moved:,}")

# ── Summary ──
print("\n=== Faith distribution (scanned entries) ===")
c.execute("""SELECT faith, COUNT(*) FROM churches 
    WHERE id IN (SELECT church_id FROM enrichment_change_log WHERE change_source=?) 
    GROUP BY faith ORDER BY COUNT(*) DESC""", (SOURCE_NAME,))
for row in c.fetchall():
    print(f"  {row[0]:25s} {row[1]:>8,}")

still_other = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Other'").fetchone()[0]
print(f"\n  Remaining Other faith: {still_other:,}")

conn.close()
