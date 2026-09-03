"""DeepSeek scan of all Bahrain mosque entries.
Verifies faith=Islam classification and refines tradition + muslim_affiliation.

Bahrain is ~60% Shia, so we need to check which mosques are Sunni vs Shia
based on naming patterns (e.g., names referencing Imams → Shia).
"""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SCRIPT_NAME = "scan_bahrain_deepseek"
STARTED_AT = datetime.now(timezone.utc).isoformat()
source_name = 'deepseek_bahrain_scan'

# ── Query all Bahrain API-imported entries ──
c.execute("""
    SELECT id, name, name_transliterated, tradition, faith, landmark_type
    FROM churches 
    WHERE country='BH' AND source_primary='bahrain_gov_api'
    ORDER BY id
""")
entries = c.fetchall()
print(f"Bahrain entries to scan: {len(entries):,}")

CHUNK_SIZE = 30
total_moved = 0       # moved out of Islam
total_trad_fixes = 0  # tradition refined (Sunni→Shia etc.)
total_affiliation = 0 # muslim_affiliation updated
all_changed_ids = set()

PROMPT = """For each Islamic religious site, determine if it is correctly classified as Islam and refine the tradition.

Bahrain has both Sunni and Shia mosques. Classify based on the name, Arabic name, and context.

Classification rules:
- ISLAM indicators: mosque/masjid in English or Arabic (مسجد, جامع), Islamic names
- SUNNI indicators: generic mosque names, family names (Al Haj, Bin...), Salafi/Reform names (Al Eslah), standard Arabic religious names
- SHIA indicators: references to Ahl al-Bayt (Imam Ali, Imam Jaffar al-Sadiq, Imam Moosa, Imam Hussein, Imam Hasan), 
  Fatimah/Zahra names, Al Rasool, Al Emam, references to the Prophet's family
- NON-ISLAM: church, cross, monastery, or clearly non-Islamic names → mark as OTHER

For ISLAM entries:
- tradition: "Sunni" (generic), "Shia" (if clearly Shia named)
- affiliation: the specific madhab/fiqh tradition:
  - "Maliki" (predominant in Bahrain for Sunnis)
  - "Shafii" 
  - "Hanafi"
  - "Hanbali"
  - "Salafi" (for reform-oriented mosques like Al Eslah)
  - "Sufi"
  - "Twelver" (for Shia mosques)
  - null if uncertain
- landmark_type: keep as "mosque" unless clearly something else

For NON-ISLAM entries:
- faith: OTHER, CHRISTIAN, etc.
- tradition: specify
- type: appropriate facility type

IMPORTANT: Most Bahrain mosques are Sunni/Maliki. Look for Shia indicators carefully:
- مسجد الإمام (Imam mosque) → likely Shia
- Names with Ali, Fatima, Hasan, Hussein, Jaffar, Moosa al-Kadhim → likely Shia
- جامع (Jamea/Jamia) typically means a Friday mosque, could be either

Return ONLY JSON:
[{{"id": N, "faith": "ISLAM|OTHER|CHRISTIAN", "tradition": "Sunni|Shia|null", "affiliation": "Maliki|Shafii|Hanafi|Hanbali|Salafi|Sufi|Twelver|null", "type": "mosque|..."}}]

{items}"""

def call_deepseek(items, max_tokens=4000):
    prompt = PROMPT.format(items=json.dumps(items, indent=2))
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
        print(f"  NO JSON found in response")
        return None
    print(f"  HTTP {resp.status_code}")
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
        return True
    return False


def process_results(results):
    global total_moved, total_trad_fixes, total_affiliation
    for r in results:
        id_ = r.get("id")
        faith = r.get("faith", "").upper()
        trad = r.get("tradition")
        affil = r.get("affiliation")
        ftype = (r.get("type") or "").lower().replace(' ', '_')

        if not id_:
            continue

        all_changed_ids.add(id_)

        if faith != "ISLAM":
            # Moved out of Islam
            if faith == "CHRISTIAN":
                new_faith, new_trad, new_type = 'Christian', trad or 'Other Christian', ftype or 'church'
            else:
                new_faith, new_trad, new_type = 'Other', trad or 'Other', ftype or 'organization'

            moved = update_with_provenance(id_, 'faith', None, new_faith)
            update_with_provenance(id_, 'tradition', None, new_trad)
            update_with_provenance(id_, 'landmark_type', None, new_type)
            if moved:
                total_moved += 1
            continue

        # Confirmed Islam - refine tradition
        if trad and trad.lower() != 'null':
            c.execute("SELECT tradition FROM churches WHERE id=?", (id_,))
            old_trad = c.fetchone()
            if old_trad:
                old_t = (old_trad[0] or '').lower()
                new_t = trad.lower()
                if old_t != new_t and new_t in ('shia', 'sunni'):
                    if update_with_provenance(id_, 'tradition', old_trad[0], trad):
                        total_trad_fixes += 1

        # Update muslim_affiliation
        if affil and affil.lower() != 'null':
            c.execute("SELECT muslim_affiliation FROM churches WHERE id=?", (id_,))
            old_aff = c.fetchone()
            if old_aff:
                old_a = (old_aff[0] or '').lower()
                new_a = affil.lower()
                if old_a != new_a:
                    if update_with_provenance(id_, 'muslim_affiliation', old_aff[0], affil):
                        total_affiliation += 1

        # Update landmark_type if provided
        if ftype and ftype != 'mosque':
            c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,))
            old_lt = c.fetchone()
            if old_lt:
                if (old_lt[0] or '').lower() != ftype:
                    update_with_provenance(id_, 'landmark_type', old_lt[0], ftype)


# ── Scan in batches ──
from tqdm import tqdm

for cs in range(0, len(entries), CHUNK_SIZE):
    chunk = entries[cs:cs+CHUNK_SIZE]
    items = [{"id": e[0], "name": str(e[1] or ''),
              "arabic_name": str(e[2] or ''),
              "tradition": str(e[3] or ''),
              "faith": str(e[4] or ''),
              "type": str(e[5] or '')} for e in chunk]
    bn = cs//CHUNK_SIZE + 1
    tb = (len(entries)-1)//CHUNK_SIZE + 1
    
    # Simple progress print
    print(f"  Batch {bn}/{tb} ({len(items)} items)...", end=" ")
    sys.stdout.flush()

    results = call_deepseek(items)
    if results:
        process_results(results)
        conn.commit()
        print(f"OK - faith_moves={total_moved} trad_fixes={total_trad_fixes} affil={total_affiliation}")
    else:
        print(f"FAIL - retrying once...")
        results = call_deepseek(items)
        if results:
            process_results(results)
            conn.commit()
            print(f"  OK on retry - faith_moves={total_moved} trad_fixes={total_trad_fixes} affil={total_affiliation}")
        else:
            print(f"  FAILED after retry, skipping batch {bn}")

# ── Set confidence for all scanned entries ──
print("\n=== Updating confidence columns ===")
update_count = 0
for id_ in all_changed_ids:
    c.execute("UPDATE churches SET muslim_confidence=?, muslim_classification_source=?, muslim_updated=? WHERE id=?",
              (0.95, source_name, datetime.now(timezone.utc).isoformat(), id_))
    update_count += 1
conn.commit()

# Also set confidence for remaining entries that weren't changed
c.execute("""
    UPDATE churches SET muslim_confidence=?, muslim_classification_source=?, muslim_updated=?
    WHERE country='BH' AND source_primary='bahrain_gov_api'
      AND (muslim_classification_source IS NULL OR muslim_classification_source != ?)
""", (0.95, source_name, datetime.now(timezone.utc).isoformat(), source_name))
remaining = c.rowcount
conn.commit()

print(f"\n=== Scan complete ===")
print(f"  Total entries in scan: {len(entries):,}")
print(f"  Moved out of Islam: {total_moved}")
print(f"  Tradition fixes (Sunni↔Shia): {total_trad_fixes}")
print(f"  Muslim affiliation set: {total_affiliation}")
print(f"  Unique IDs with changes: {len(all_changed_ids)}")
print(f"  Confidence updated (remaining): {remaining}")

# ── Log provenance ──
COMPLETED_AT = datetime.now(timezone.utc).isoformat()
notes = f"DeepSeek Bahrain scan: {total_moved} moved out, {total_trad_fixes} tradition fixes, {total_affiliation} affiliation updates."
c.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes) 
    VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)""",
    ('deepseek', SCRIPT_NAME, STARTED_AT, COMPLETED_AT, len(all_changed_ids),
     'faith,tradition,muslim_affiliation,muslim_confidence,muslim_classification_source', notes))
conn.commit()

# ── Summary ──
c.execute("SELECT tradition, COUNT(*) FROM churches WHERE country='BH' AND source_primary='bahrain_gov_api' GROUP BY tradition ORDER BY COUNT(*) DESC")
print("\nFinal tradition distribution:")
for r in c.fetchall():
    print(f"  {r[0]!r}: {r[1]}")

c.execute("SELECT muslim_affiliation, COUNT(*) FROM churches WHERE country='BH' AND source_primary='bahrain_gov_api' AND muslim_affiliation IS NOT NULL GROUP BY muslim_affiliation ORDER BY COUNT(*) DESC")
print("\nMuslim affiliation distribution:")
for r in c.fetchall():
    print(f"  {r[0]!r}: {r[1]}")

c.execute("SELECT muslim_classification_source, COUNT(*) FROM churches WHERE country='BH' AND source_primary='bahrain_gov_api' GROUP BY muslim_classification_source")
print("\nClassification source:")
for r in c.fetchall():
    print(f"  {r[0]!r}: {r[1]}")

conn.close()
print("\n✅ Done!")
