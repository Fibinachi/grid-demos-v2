"""Resume DeepSeek Sikh scan for entries missed due to API quota exhaustion.
Skips entries already reviewed in the first run (tracked via enrichment_change_log)."""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SCRIPT_NAME = "scan_sikh_deepseek_resume"
STARTED_AT = datetime.now(timezone.utc).isoformat()
source_name = 'deepseek_sikh_scan'

# ── Find already-reviewed IDs ──
c.execute("""
    SELECT DISTINCT church_id FROM enrichment_change_log
    WHERE change_source = 'deepseek_sikh_scan'
""")
reviewed = {r[0] for r in c.fetchall()}
print(f"Already reviewed by DeepSeek: {len(reviewed):,} entries")

# ── Query ONLY unreviewed Sikh entries ──
placeholders = ','.join('?' * len(reviewed)) if reviewed else 'NULL'
c.execute(f"""
    SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches WHERE faith = 'Sikh'
    AND id NOT IN ({placeholders})
    ORDER BY country, name
""", tuple(reviewed) if reviewed else ())
entries = c.fetchall()
print(f"Remaining to scan: {len(entries):,}")

if not entries:
    print("Nothing to do!")
    conn.close()
    sys.exit(0)

CHUNK_SIZE = 20
total_moved = 0
total_retyped = 0
total_tradition = 0
all_changed_ids = set()

PROMPT = """For each religious site, determine if it is actually SIKH.

Quick classification guide:
- SIKH indicators: gurdwara/gurudwara, khalsa, sikh, singh sabha, guru (nanak, gobind, granth, etc.), sri guru, harmandir, darbar sahib, punjab religious, sikh centre/society/temple
- HINDU indicators: mandir, temple (without sikh/guru/khalsa context), shiva, vishnu, krishna, hanuman, durga, devi, ram, laxmi, temple trust, dharmashala, ashram (without sikh context)
- MUSLIM/ISLAM indicators: mosque, masjid, islam, allah
- CHRISTIAN indicators: church, chapel, cathedral, shrine (UNLESS clearly Sikh), jesus, christ, gospel, saint, st., pastor, bishop
- BUDDHIST indicators: wat, vihara, buddha, dharma, meditation centre, stupa, pagoda

For SIKH entries:
- tradition: Khalsa, Singh Sabha, Nanaksar, Ravidassia, Ramgarhia, Ram Rai, Nirmala, or just Sikh (generic)
- landmark_type: gurdwara, temple (only for major historical ones like Harmandir Sahib), shrine (only for memorials), school, museum, community_center, library

For NON-SIKH entries:
- faith: HINDU, BUDDHIST, CHRISTIAN, ISLAM, JAIN, OTHER
- tradition: specify the tradition
- type: the most appropriate facility type

IMPORTANT NOTES:
- "Gurdwara" / "Gurudwara" in the name is a STRONG indicator the site is Sikh
- "Temple" alone (without sikh/guru/khalsa) in non-Indian context is often Hindu
- Most Sikh places of worship should be landmark_type='gurdwara'
- Use landmark_type='shrine' only for actual memorials/samadhs

Return ONLY JSON:
[{{"id": N, "faith": "SIKH|HINDU|BUDDHIST|CHRISTIAN|ISLAM|JAIN|OTHER", "tradition": "...", "type": "gurdwara|temple|shrine|school|community_center|mosque|church|mandir|..."}}]

{items}"""

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

def call_deepseek(items, max_tokens=3000):
    prompt = PROMPT.format(items=json.dumps(items, indent=2))
    resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.05, "max_tokens": max_tokens
    }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=90)
    if resp.status_code == 200:
        content = resp.json()["choices"][0]["message"]["content"]
        jm = re.search(r'\[.*?\]', content, re.DOTALL)
        if jm:
            try: return json.loads(jm.group())
            except json.JSONDecodeError: print(f"  JSON PARSE ERROR"); return None
        print(f"  NO JSON"); return None
    print(f"  HTTP {resp.status_code}")
    return None

def process_results(results):
    global total_moved, total_retyped, total_tradition
    for r in results:
        id_ = r.get("id"); faith = r.get("faith", "").upper()
        trad = r.get("tradition", ""); ftype = (r.get("type") or "").lower().replace(' ', '_')
        if not id_: continue

        if faith != "SIKH":
            faith_map = {'HINDU': ('Hindu', 'Other', ftype or 'temple'),
                         'BUDDHIST': ('Buddhist', 'Other', ftype or 'temple'),
                         'CHRISTIAN': ('Christian', trad or 'Other Christian', ftype or 'church'),
                         'ISLAM': ('Islam', 'Sunni', ftype or 'mosque'),
                         'JAIN': ('Jain', 'Other', ftype or 'temple')}
            nf, nt, ntype = faith_map.get(faith, ('Other', 'New Age', ftype or 'organization'))
            update_with_provenance(id_, 'faith', None, nf)
            update_with_provenance(id_, 'tradition', None, nt)
            update_with_provenance(id_, 'landmark_type', None, ntype)
            total_moved += 1
        else:
            if trad and trad.lower() not in ('sikh', ''):
                c.execute("SELECT tradition FROM churches WHERE id=?", (id_,))
                old_trad = c.fetchone()
                if old_trad and (old_trad[0] or '').lower() != trad.lower():
                    update_with_provenance(id_, 'tradition', old_trad[0], trad)
                    total_tradition += 1
            if ftype:
                c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,))
                old_lt = c.fetchone()
                if old_lt and (old_lt[0] or '').lower() != ftype:
                    update_with_provenance(id_, 'landmark_type', old_lt[0], ftype)
                    total_retyped += 1
        all_changed_ids.add(id_)

# ── Scan ──
for cs in range(0, len(entries), CHUNK_SIZE):
    chunk = entries[cs:cs+CHUNK_SIZE]
    items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
              "state": str(e[3] or ''), "country": str(e[4] or ''),
              "type": str(e[5] or ''), "tradition": str(e[6] or '')} for e in chunk]
    bn = cs//CHUNK_SIZE + 1; tb = (len(entries)-1)//CHUNK_SIZE + 1
    print(f"  Batch {bn}/{tb} ({len(items)} items)...", end=" "); sys.stdout.flush()

    results = call_deepseek(items)
    if results:
        process_results(results); conn.commit()
        print(f"OK - cumulative: {total_moved} moved, {total_retyped} retyped, {total_tradition} tradition")
    else:
        print(f"FAIL - retrying...")
        results = call_deepseek(items)
        if results:
            process_results(results); conn.commit()
            print(f"  OK on retry")
        else:
            print(f"  FAILED, skipping batch")

print(f"\n=== Resume scan complete ===")
print(f"  Remaining entries: {len(entries):,}")
print(f"  Moved out of Sikh: {total_moved}")
print(f"  Landmark type changes: {total_retyped}")
print(f"  Tradition updates: {total_tradition}")
print(f"  Unique IDs changed: {len(all_changed_ids)}")

COMPLETED_AT = datetime.now(timezone.utc).isoformat()
notes = f"DeepSeek Sikh resume scan: {total_moved} moved out, {total_retyped} retyped, {total_tradition} tradition updates."
c.execute("INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)",
          ('deepseek', SCRIPT_NAME, STARTED_AT, COMPLETED_AT, len(all_changed_ids),
           'faith,tradition,landmark_type', notes))
conn.commit()
conn.close()
print(f"Done! Provenance logged as '{SCRIPT_NAME}'")
