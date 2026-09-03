"""DeepSeek scan of all Sikh entries worldwide.
Checks for misclassifications and refines tradition + landmark_type."""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SCRIPT_NAME = "scan_sikh_deepseek"
STARTED_AT = datetime.now(timezone.utc).isoformat()
source_name = 'deepseek_sikh_scan'

# ── Ensure columns exist ──
existing = {r[1] for r in c.execute('PRAGMA table_info(churches)').fetchall()}
for col, dtype in [
    ('sikh_affiliation', 'TEXT'),
    ('sikh_confidence', 'REAL'),
    ('sikh_classification_source', 'TEXT'),
    ('sikh_updated', 'TEXT'),
]:
    if col not in existing:
        c.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')
        print(f'  Added column: {col}')
conn.commit()

# ── Provenance helpers ──
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

# ── Query all Sikh entries ──
c.execute("""
    SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches WHERE faith = 'Sikh'
    ORDER BY country, name
""")
entries = c.fetchall()
print(f"Sikh entries to scan: {len(entries):,}")

CHUNK_SIZE = 20
total_moved = 0      # moved out of Sikh faith
total_retyped = 0    # landmark_type changed
total_tradition = 0  # tradition refined
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
- tradition: specify the tradition (e.g. Sunni, Catholic, Vaishnavism, Theravada, etc.)
- type: the most appropriate facility type (temple, mosque, church, mandir, ashram, etc.)

IMPORTANT NOTES:
- "Gurdwara" / "Gurudwara" in the name is a STRONG indicator the site is Sikh
- "Temple" alone (without sikh/guru/khalsa) in non-Indian context is often Hindu
- "Shrine" for Sikh entries should ONLY be used for actual memorial shrines, NOT gurdwaras
- Most Sikh places of worship should be landmark_type='gurdwara'
- Only use landmark_type='temple' for major historical gurdwaras (like Harmandir Sahib, etc.)
- Use landmark_type='shrine' only for actual memorials/samadhs, not regular gurdwaras

Return ONLY JSON:
[{{"id": N, "faith": "SIKH|HINDU|BUDDHIST|CHRISTIAN|ISLAM|JAIN|OTHER", "tradition": "...", "type": "gurdwara|temple|shrine|school|community_center|mosque|church|mandir|..."}}]

{items}"""

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
            try:
                return json.loads(jm.group())
            except json.JSONDecodeError:
                print(f"  JSON PARSE ERROR")
                return None
        print(f"  NO JSON found in response")
        return None
    print(f"  HTTP {resp.status_code}")
    return None

def process_results(results):
    global total_moved, total_retyped, total_tradition
    for r in results:
        id_ = r.get("id")
        faith = r.get("faith", "").upper()
        trad = r.get("tradition", "")
        ftype = (r.get("type") or "").lower().replace(' ', '_')

        if not id_:
            continue

        if faith != "SIKH":
            # Moved out of Sikh faith
            if faith == "HINDU":
                new_faith, new_trad, new_type = 'Hindu', trad or 'Other', ftype or 'temple'
            elif faith == "BUDDHIST":
                new_faith, new_trad, new_type = 'Buddhist', trad or 'Other', ftype or 'temple'
            elif faith == "CHRISTIAN":
                new_faith, new_trad, new_type = 'Christian', trad or 'Other Christian', ftype or 'church'
            elif faith == "ISLAM":
                new_faith, new_trad, new_type = 'Islam', trad or 'Sunni', ftype or 'mosque'
            elif faith == "JAIN":
                new_faith, new_trad, new_type = 'Jain', trad or 'Other', ftype or 'temple'
            else:
                new_faith, new_trad, new_type = 'Other', trad or 'New Age', ftype or 'organization'

            update_with_provenance(id_, 'faith', None, new_faith)
            update_with_provenance(id_, 'tradition', None, new_trad)
            update_with_provenance(id_, 'landmark_type', None, new_type)
            total_moved += 1
        else:
            # Confirmed Sikh - check tradition and landmark_type
            # Update tradition if provided and different
            if trad and trad.lower() not in ('sikh', ''):
                c.execute("SELECT tradition FROM churches WHERE id=?", (id_,))
                old_trad = c.fetchone()
                if old_trad:
                    old_t = (old_trad[0] or '').lower()
                    new_t = trad.lower()
                    if old_t != new_t:
                        update_with_provenance(id_, 'tradition', old_trad[0], trad)
                        total_tradition += 1

            # Update landmark_type if provided and different
            if ftype:
                c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,))
                old_lt = c.fetchone()
                if old_lt:
                    old_t = (old_lt[0] or '').lower()
                    if old_t != ftype and old_t not in ('gurdwara',) and ftype != '':
                        # Don't downgrade gurdwara to temple/shrine if already correctly set
                        update_with_provenance(id_, 'landmark_type', old_lt[0], ftype)
                        total_retyped += 1

        all_changed_ids.add(id_)

# ── Scan in batches ──
for cs in range(0, len(entries), CHUNK_SIZE):
    chunk = entries[cs:cs+CHUNK_SIZE]
    items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
              "state": str(e[3] or ''), "country": str(e[4] or ''),
              "type": str(e[5] or ''), "tradition": str(e[6] or '')} for e in chunk]
    bn = cs//CHUNK_SIZE + 1
    tb = (len(entries)-1)//CHUNK_SIZE + 1
    print(f"  Batch {bn}/{tb} ({len(items)} items)...", end=" ")
    sys.stdout.flush()

    results = call_deepseek(items)
    if results:
        process_results(results)
        conn.commit()
        print(f"OK - {total_moved} moved, {total_retyped} retyped, {total_tradition} tradition updates")
    else:
        print(f"FAIL - retrying once...")
        results = call_deepseek(items)
        if results:
            process_results(results)
            conn.commit()
            print(f"  OK on retry - {total_moved} moved, {total_retyped} retyped, {total_tradition} tradition updates")
        else:
            print(f"  FAILED after retry, skipping batch")

print(f"\n=== Scan complete ===")
print(f"  Total entries: {len(entries):,}")
print(f"  Moved out of Sikh: {total_moved}")
print(f"  Landmark type changes: {total_retyped}")
print(f"  Tradition updates: {total_tradition}")
print(f"  Unique IDs changed: {len(all_changed_ids)}")

# ── Log provenance ──
COMPLETED_AT = datetime.now(timezone.utc).isoformat()
notes = f"DeepSeek Sikh scan: {total_moved} moved out, {total_retyped} retyped, {total_tradition} tradition updates."
c.execute("INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)",
          ('deepseek', SCRIPT_NAME, STARTED_AT, COMPLETED_AT, len(all_changed_ids),
           'faith,tradition,landmark_type,sikh_affiliation,sikh_confidence,sikh_classification_source', notes))

# ── Update sikh_affiliation/confidence for remaining entries ──
print()
print("=== Updating sikh_affiliation/confidence for all Sikh entries ===")
c.execute("""
    SELECT id, tradition, landmark_type FROM churches
    WHERE faith = 'Sikh'
      AND (sikh_affiliation IS NULL OR sikh_affiliation = '')
""")
to_update = c.fetchall()
print(f"  Records to update sikh_affiliation: {len(to_update):,}")

for row in to_update:
    id_, trad, lt = row
    aff = 'Gurdwara'  # default
    if lt == 'school':
        aff = 'Khalsa School'
    elif lt == 'community_center':
        aff = 'Sikh Center'
    elif lt == 'museum':
        aff = 'Sikh Museum'
    elif lt == 'library':
        aff = 'Sikh Library'
    elif lt == 'shrine':
        aff = 'Sikh Shrine'

    # Override based on tradition
    if trad == 'Singh Sabha':
        aff = 'Gurdwara (Singh Sabha)'
    elif trad == 'Nanaksar':
        aff = 'Gurdwara (Nanaksar)'
    elif trad == 'Ravidassia':
        aff = 'Gurdwara (Ravidassia)'
    elif trad == 'Ramgarhia':
        aff = 'Gurdwara (Ramgarhia)'
    elif trad == 'Nirmala':
        aff = 'Gurdwara (Nirmala)'

    conf = 0.85  # DeepSeek-verified confidence
    src = 'deepseek_sikh_scan'

    c.execute("""
        UPDATE churches SET
            sikh_affiliation = ?,
            sikh_confidence = ?,
            sikh_classification_source = ?,
            sikh_updated = datetime('now'),
            last_updated = datetime('now')
        WHERE id = ?
    """, (aff, conf, src, id_))

conn.commit()

# ── Final report ──
print()
print("=== FINAL SIKH BREAKDOWN ===")
c.execute("""
    SELECT sikh_affiliation, COUNT(*) as cnt,
           ROUND(AVG(sikh_confidence), 3) as avg_conf
    FROM churches WHERE faith = 'Sikh' AND sikh_affiliation != '' AND sikh_affiliation IS NOT NULL
    GROUP BY sikh_affiliation ORDER BY cnt DESC
""")
for r in c.fetchall():
    print(f"  {str(r[0]):35s} {r[1]:>7,}  (avg conf: {r[2]:.3f})")

print()
c.execute("""
    SELECT COUNT(*) FROM churches WHERE faith = 'Sikh'
    AND (sikh_affiliation IS NULL OR sikh_affiliation = '')
""")
unclassified = c.fetchone()[0]
print(f"Unclassified: {unclassified}")

print()
print("=== TRADITIONS (post-scan) ===")
c.execute("""
    SELECT tradition, COUNT(*) FROM churches WHERE faith = 'Sikh'
    GROUP BY tradition ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  {str(r[0]):30s} {r[1]:>7,}")

print()
print("=== LANDMARK TYPES (post-scan) ===")
c.execute("""
    SELECT landmark_type, COUNT(*) FROM churches WHERE faith = 'Sikh'
    GROUP BY landmark_type ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  {str(r[0]):30s} {r[1]:>7,}")

conn.commit()
conn.close()
print(f"\nDone! Provenance logged as '{SCRIPT_NAME}'")
