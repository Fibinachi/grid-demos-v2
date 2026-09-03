"""DeepSeek classifier for NULL faith entries (1,732).
These are entries with NULL faith that need proper faith classification."""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SCRIPT_NAME = "classify_null_faith_deepseek"
STARTED_AT = datetime.now(timezone.utc).isoformat()
source_name = 'deepseek_null_faith_scan'

# ── Query NULL faith entries ──
c.execute("""
    SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches
    WHERE faith IS NULL OR faith = '' OR LOWER(faith) = 'null'
    ORDER BY country, name
""")
entries = c.fetchall()
print(f"NULL faith entries to classify: {len(entries):,}")

CHUNK_SIZE = 60
total_classified = 0

PROMPT = """Classify each religious site by determining its CORRECT faith group.

For each entry, analyze the name, location, and any existing type/tradition info to determine:
1. faith: CHRISTIAN | ISLAM | BUDDHIST | HINDU | JAIN | SIKH | SHINTO | TAOIST | JUDAISM | CONFUCIAN | OTHER
2. tradition: Be specific (e.g., Catholic, Sunni, Mahayana, Vaishnavism, etc.)
3. type: The most appropriate facility type (church, mosque, temple, shrine, monastery, chapel, synagogue, gurdwara, pagoda, cathedral, etc.)

Quick classification guide:
- CHRISTIAN: church, chapel, cathedral, basilica, monastery, convent, abbey, mission, shrine (esp. Virgin Mary/saints), iglesia, ermita, st./saint/san/santa, jesus, christ, gospel, pastor, bishop
- ISLAM: mosque, masjid, cami, islamic, muslim, madrasa, dargah, minaret
- BUDDHIST: wat, vihara, buddha, dharma, pagoda, stupa, temple (Asian context)
- HINDU: mandir, temple (Indian context), shiva, vishnu, krishna, hanuman, devi
- SHINTO: jinja, jingu, shrine (Japan context), kami
- TAOIST: tao, taoist, dao, temple (Chinese context)

Return ONLY valid JSON:
[{{"id": N, "faith": "CHRISTIAN|ISLAM|BUDDHIST|HINDU|JAIN|SIKH|SHINTO|TAOIST|JUDAISM|CONFUCIAN|OTHER", "tradition": "...", "type": "church|mosque|temple|shrine|..."}}]

{items}"""

def call_deepseek(items, max_tokens=4000):
    prompt = PROMPT.format(items=json.dumps(items, indent=2))
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.05, "max_tokens": max_tokens
        }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=120)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            jm = re.search(r'\[.*?\]', content, re.DOTALL)
            if jm:
                try:
                    return json.loads(jm.group())
                except json.JSONDecodeError:
                    print(f"  JSON PARSE ERROR")
                    return None
            print(f"  NO JSON in response")
            return None
        print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

def log_enrichment(church_id, field, old_val, new_val):
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, ?, ?, ?, ?)",
              (church_id, field, str(old_val) if old_val is not None else None,
               str(new_val) if new_val is not None else None, source_name))

def update_with_provenance(church_id, field, old_val, new_val):
    if old_val is None:
        c.execute(f"SELECT {field} FROM churches WHERE id=?", (church_id,))
        row = c.fetchone()
        old_val = row[0] if row else None
    if str(old_val) != str(new_val):
        c.execute(f"UPDATE churches SET {field}=? WHERE id=?", (new_val, church_id))
        log_enrichment(church_id, field, old_val, new_val)

def process_results(results):
    global total_classified
    for r in results:
        id_ = r.get("id")
        faith = r.get("faith", "").upper()
        trad = r.get("tradition", "")
        ftype = (r.get("type") or "").lower().replace(' ', '_')

        if not id_:
            continue

        # Map faith
        faith_map = {
            'CHRISTIAN': 'Christian', 'ISLAM': 'Islam', 'BUDDHIST': 'Buddhist',
            'HINDU': 'Hindu', 'JAIN': 'Jain', 'SIKH': 'Sikh',
            'SHINTO': 'Shinto', 'TAOIST': 'Taoist', 'JUDAISM': 'Judaism',
            'CONFUCIAN': 'Confucian', 'OTHER': 'Other'
        }
        new_faith = faith_map.get(faith, 'Other')

        # Map landmark_type
        type_map = {
            'church': 'church', 'chapel': 'chapel', 'cathedral': 'cathedral',
            'basilica': 'basilica', 'monastery': 'monastery', 'convent': 'convent',
            'abbey': 'abbey', 'mission': 'mission', 'shrine': 'shrine',
            'mosque': 'mosque', 'temple': 'temple', 'synagogue': 'synagogue',
            'gurdwara': 'gurdwara', 'pagoda': 'pagoda', 'stupa': 'stupa',
            'cemetery': 'cemetery', 'school': 'school', 'community_center': 'community_center',
            'organization': 'organization', 'museum': 'museum', 'library': 'library',
            'wayside_shrine': 'wayside_shrine', 'hermitage': 'hermitage',
            'sanctuary': 'sanctuary', 'oratory': 'oratory', 'retreat_center': 'retreat_center',
        }
        new_type = type_map.get(ftype, ftype if ftype else None)

        update_with_provenance(id_, 'faith', None, new_faith)
        if trad:
            update_with_provenance(id_, 'tradition', None, trad)
        if new_type:
            update_with_provenance(id_, 'landmark_type', None, new_type)
        total_classified += 1

# ── Scan in batches ──
for cs in range(0, len(entries), CHUNK_SIZE):
    chunk = entries[cs:cs+CHUNK_SIZE]
    items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
              "state": str(e[3] or ''), "country": str(e[4] or ''),
              "type": str(e[5] or ''), "tradition": str(e[6] or '')} for e in chunk]

    results = call_deepseek(items)
    if results:
        process_results(results)
        conn.commit()
    else:
        # Retry once
        results = call_deepseek(items)
        if results:
            process_results(results)
            conn.commit()

    # Progress bar
    pct = min(cs + CHUNK_SIZE, len(entries)) / len(entries) * 100
    print(f"\r  Progress: {min(cs + CHUNK_SIZE, len(entries)):,}/{len(entries):,} ({pct:.0f}%) | classified: {total_classified}", end="")
    sys.stdout.flush()

print()
print(f"\n=== Scan complete ===")
print(f"  Total NULL faith entries: {len(entries):,}")
print(f"  Total classified: {total_classified}")

# ── Summary ──
print("\n=== Classification summary ===")
for row in c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith IS NOT NULL AND faith != '' AND LOWER(faith) != 'null' AND id IN (SELECT church_id FROM enrichment_change_log WHERE change_source=?) GROUP BY faith ORDER BY COUNT(*) DESC", (source_name,)):
    print(f"  {row[0]:25s} {row[1]:>8,}")

# Also show any still-null
still_null = c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith = '' OR LOWER(faith) = 'null'").fetchone()[0]
if still_null:
    print(f"\n  ⚠ Still NULL faith: {still_null:,}")
else:
    print(f"\n  ✓ No remaining NULL faith entries!")

conn.close()
