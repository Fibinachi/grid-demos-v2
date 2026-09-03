"""DeepSeek scan of Judaism entries in Asia (excluding Israel)."""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SCRIPT_NAME = "scan_asia_jewish_deepseek"
STARTED_AT = datetime.now(timezone.utc).isoformat()
source_name = 'deepseek_asia_scan'

asia = [
    'AF','Afghanistan','AM','Armenia','AZ','Azerbaijan','BH','Bahrain',
    'BD','Bangladesh','BT','Bhutan','BN','Brunei','KH','Cambodia','CN','China',
    'CY','Cyprus','GE','Georgia','IN','India','ID','Indonesia','IR','Iran',
    'IQ','Iraq','JP','Japan','JO','Jordan','KZ','Kazakhstan','KW','Kuwait',
    'KG','Kyrgyzstan','LA','Laos','LB','Lebanon','MY','Malaysia','MV','Maldives',
    'MN','Mongolia','MM','Myanmar','NP','Nepal','KP','North Korea',
    'OM','Oman','PK','Pakistan','PS','Palestine','PH','Philippines','QA','Qatar',
    'RU','Russia','SA','Saudi Arabia','SG','Singapore','KR','South Korea',
    'LK','Sri Lanka','SY','Syria','TW','Taiwan','TJ','Tajikistan',
    'TH','Thailand','TR','Turkey','TM','Turkmenistan','AE','United Arab Emirates',
    'UZ','Uzbekistan','VN','Vietnam','YE','Yemen',
    'HK','Hong Kong','MO','Macau'
]
placeholders = ','.join('?' for _ in asia)

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

# ── Scan ──
c.execute(f"SELECT id, name, city, state, country, landmark_type, tradition FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) ORDER BY country, name", asia)
entries = c.fetchall()
print(f"Asia entries to scan: {len(entries)}")

CHUNK_SIZE = 20
total_moved = 0
total_retyped = 0
all_changed_ids = set()

PROMPT = """For each religious site, determine if it is actually Jewish.

Quick classification guide:
- Christian indicators: church, chapel, cathedral, shrine, jesus, christ, gospel, saint, trinity, holy, grace, cross, notre dame, st., san, santa, iglesia, mission, pastor, bishop, parish
- Jewish indicators: synagogue, temple, beth/bet, chabad, rabbi, torah, yeshiva, kollel, hillel, mikvah, israel (Jewish org), jewish, hebrew, shalom, congregation
- Muslim indicators: mosque, masjid, islam, allah: ISLAM
- If name is neutral and location/context is ambiguous, default to JEWISH for entries already marked Jewish

If CHRISTIAN, specify tradition (Catholic, Orthodox, Anglican, Baptist, etc.) and type (CHURCH, CATHEDRAL, CHAPEL, etc.)
If JEWISH, specify tradition (Orthodox, Conservative, Reform, Sephardic, Rabbinic, Karaite, etc.) and type (SYNAGOGUE, CHABAD, YESHIVA, KOLLEL, SCHOOL, COMMUNITY_CENTER, MIKVEH, HILLEL, CEMETERY, MUSEUM, ORGANIZATION)

Return ONLY JSON:
[{{"id": N, "faith": "JEWISH|CHRISTIAN|HINDU|BUDDHIST|ISLAM|OTHER", "tradition": "...", "type": "SYNAGOGUE|CHURCH|..."}}]

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
        if jm: return json.loads(jm.group())
        print(f"  NO JSON"); return None
    print(f"  HTTP {resp.status_code}"); return None

def process_results(results):
    global total_moved, total_retyped
    moved = 0
    for r in results:
        id_ = r.get("id")
        faith = r.get("faith", "").upper()
        trad = r.get("tradition", "")
        ftype = (r.get("type") or "").upper()
        if faith in ("CHRISTIAN", "HINDU", "BUDDHIST", "ISLAM", "OTHER", "NEWAGE"):
            if faith == "CHRISTIAN":
                mapped = ftype.lower() if ftype.lower() in ('church','cathedral','chapel','abbey','mission','shrine','cemetery') else 'church'
                new_faith, new_trad, new_type = 'Christian', trad or 'Other Christian', mapped
            elif faith == "HINDU":   new_faith, new_trad, new_type = 'Hindu', trad or 'Other', 'temple'
            elif faith == "BUDDHIST": new_faith, new_trad, new_type = 'Buddhist', trad or 'Mahayana', 'temple'
            elif faith == "ISLAM":   new_faith, new_trad, new_type = 'Islam', trad or 'Sunni', 'mosque'
            else:                    new_faith, new_trad, new_type = 'Other', 'New Age', 'organization'
            update_with_provenance(id_, 'faith', None, new_faith)
            update_with_provenance(id_, 'tradition', None, new_trad)
            update_with_provenance(id_, 'landmark_type', None, new_type)
            total_moved += 1; moved += 1
        else:
            mapped = ftype.lower().replace('_', ' ') if ftype else None
            if mapped == 'temple': mapped = 'synagogue'
            if trad and trad not in ('Rabbinic', ''):
                c.execute("SELECT tradition FROM churches WHERE id=?", (id_,))
                old_trad = c.fetchone()
                if old_trad and old_trad[0] != trad:
                    update_with_provenance(id_, 'tradition', old_trad[0], trad)
            if mapped and mapped not in ('synagogue', None):
                c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,))
                old_type = c.fetchone()
                if old_type and old_type[0] != mapped:
                    update_with_provenance(id_, 'landmark_type', old_type[0], mapped)
                    total_retyped += 1
        all_changed_ids.add(id_)
    return moved

for cs in range(0, len(entries), CHUNK_SIZE):
    chunk = entries[cs:cs+CHUNK_SIZE]
    items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
              "state": str(e[3] or ''), "country": str(e[4] or '')} for e in chunk]
    bn = cs//CHUNK_SIZE+1; tb = (len(entries)-1)//CHUNK_SIZE+1
    print(f"  Batch {bn}/{tb}...", end=" "); sys.stdout.flush()
    results = call_deepseek(items)
    if results:
        m = process_results(results); conn.commit()
        print(f"OK - {m} moved")
    else:
        print(f"FAIL")

print(f"\n=== Scan complete ===")
print(f"  Moved out: {total_moved}, Retyped: {total_retyped}, Changed: {len(all_changed_ids)}")

# Log provenance
COMPLETED_AT = datetime.now(timezone.utc).isoformat()
notes = f"DeepSeek Asia Judaism scan: {total_moved} moved out, {total_retyped} retyped."
c.execute("INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)",
          ('deepseek', SCRIPT_NAME, STARTED_AT, COMPLETED_AT, len(all_changed_ids), 'faith,tradition,landmark_type', notes))
conn.commit()

# Fix chabad regression
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type='chabad'", asia)
n = c.fetchone()[0]
if n:
    c.execute(f"UPDATE churches SET landmark_type='chabad_house' WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type='chabad'", asia)
    print(f"  Fixed chabad->chabad_house: {c.rowcount}")
    conn.commit()

# Fix community center normalization
for old, new in [('community center', 'community_center'), ('mikvah', 'mikveh')]:
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type=?", asia + [old])
    n = c.fetchone()[0]
    if n:
        c.execute(f"UPDATE churches SET landmark_type=? WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type=?", [new] + asia + [old])
        print(f"  Fixed '{old}'->'{new}': {c.rowcount}")
        conn.commit()

# Final verification
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders})", asia)
print(f"\nTotal Judaism in Asia: {c.fetchone()[0]:,}")

c.execute(f"SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", asia)
print(f"\nBy landmark_type:")
for r in c.fetchall():
    print(f"  {r[0]:25s} {r[1]:>5,}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", asia)
print(f"Problematic: {c.fetchone()[0]}")

c.execute(f"SELECT tradition, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY tradition ORDER BY COUNT(*) DESC", asia)
print(f"\nBy tradition:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':30s} {r[1]:>5,}")

c.execute("SELECT COUNT(*) FROM enrichment_change_log WHERE change_source=?", (source_name,))
print(f"\nEnrichment log entries: {c.fetchone()[0]:,}")
conn.close()
print("Done!")
