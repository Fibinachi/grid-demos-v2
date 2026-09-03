"""DeepSeek scan of non-US North America Judaism entries.

Targets: CA, MX, GT, BZ, SV, HN, NI, CR, PA, CU, JM, DO, BS, BB, LC,
         PR, VI, KY, BM, AW, CW, MQ, GP

Issues to fix:
1. 78 NULL landmark_type entries in Canada -> classify via DeepSeek
2. Check for misclassified entries across all NA
3. Normalize Canada state names (ON=Ontario, QC=Quebec, etc.)

Logs provenance to provenance_log and enrichment_change_log.
"""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SCRIPT_NAME = "scan_na_jewish_deepseek"
STARTED_AT = datetime.now(timezone.utc).isoformat()

na_countries = [
    'CA', 'Canada', 'MX', 'Mexico', 'GT', 'Guatemala', 'BZ', 'Belize',
    'SV', 'El Salvador', 'HN', 'Honduras', 'NI', 'Nicaragua',
    'CR', 'Costa Rica', 'PA', 'Panama',
    'CU', 'Cuba', 'JM', 'Jamaica', 'HT', 'Haiti', 'DO', 'Dominican Republic',
    'BS', 'Bahamas', 'BB', 'Barbados', 'TT', 'Trinidad and Tobago',
    'GD', 'Grenada', 'LC', 'Saint Lucia', 'VC', 'Saint Vincent',
    'DM', 'Dominica', 'AG', 'Antigua', 'KN', 'Saint Kitts',
    'PR', 'Puerto Rico', 'VI', 'Virgin Islands', 'KY', 'Cayman Islands',
    'BM', 'Bermuda', 'AW', 'Aruba', 'CW', 'Curacao',
    'GL', 'Greenland', 'MQ', 'Martinique', 'GP', 'Guadeloupe'
]

placeholders = ','.join('?' for _ in na_countries)

# Canada province normalization map (code -> full name only)
CA_PROV_MAP = {
    'AB': 'Alberta', 'BC': 'British Columbia', 'MB': 'Manitoba',
    'NB': 'New Brunswick', 'NL': 'Newfoundland and Labrador',
    'NS': 'Nova Scotia', 'NT': 'Northwest Territories', 'NU': 'Nunavut',
    'ON': 'Ontario', 'PE': 'Prince Edward Island', 'QC': 'Quebec',
    'SK': 'Saskatchewan', 'YT': 'Yukon',
    '02': 'Newfoundland and Labrador', '03': 'Prince Edward Island',
    '04': 'Nova Scotia', '05': 'New Brunswick',
    '06': 'Quebec', '07': 'Ontario', '08': 'Manitoba',
    '09': 'Saskatchewan', '10': 'Alberta', '11': 'British Columbia',
    '12': 'Northwest Territories', '13': 'Nunavut', '14': 'Yukon',
}

# ── Provenance helpers ──

def log_enrichment(church_id, field, old_val, new_val, source):
    c.execute(
        "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, ?, ?, ?, ?)",
        (church_id, field, str(old_val) if old_val is not None else None,
         str(new_val) if new_val is not None else None, source)
    )

def update_with_provenance(church_id, field, old_val, new_val, source):
    """Update a field and log the change. Fetches old_val from DB if not provided."""
    if old_val is None:
        c.execute("SELECT {} FROM churches WHERE id=?".format(field), (church_id,))
        row = c.fetchone()
        old_val = row[0] if row else None
    if str(old_val) != str(new_val):
        c.execute("UPDATE churches SET {}=? WHERE id=?".format(field), (new_val, church_id))
        log_enrichment(church_id, field, old_val, new_val, source)

# ── Step 1: Canada province normalization ──

print("=== Step 1: Canada province normalization ===")

prov_fixes = 0
for old_code, new_name in CA_PROV_MAP.items():
    c.execute("SELECT id, state FROM churches WHERE faith='Judaism' AND country IN ('CA','Canada') AND state=?", (old_code,))
    rows = c.fetchall()
    for row in rows:
        update_with_provenance(row[0], 'state', row[1], new_name, 'deepseek_na_scan')
    if rows:
        print(f"  {old_code} -> {new_name}: {len(rows)}")
        prov_fixes += len(rows)

conn.commit()
print(f"  Total province fixes: {prov_fixes}")

# Normalize country 'CA' -> 'Canada'
c.execute("SELECT id, country FROM churches WHERE faith='Judaism' AND country='CA'")
rows = c.fetchall()
for row in rows:
    update_with_provenance(row[0], 'country', 'CA', 'Canada', 'deepseek_na_scan')
if rows:
    print(f"  Country 'CA' -> 'Canada': {len(rows)}")
    conn.commit()

# ── Step 2: Get entries needing DeepSeek scan ──

print(f"\n=== Step 2: DeepSeek scan ===")

# Get entries with problematic landmark types or NULL
c.execute(f"""
    SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches WHERE faith='Judaism' AND country IN ({placeholders})
    AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))
    ORDER BY country, state, name
""", na_countries)
problematic = c.fetchall()
print(f"Problematic entries needing scan: {len(problematic)}")

# Get ALL remaining entries for full scan
c.execute(f"""
    SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches WHERE faith='Judaism' AND country IN ({placeholders})
    ORDER BY country, state, name
""", na_countries)
all_remaining = c.fetchall()
print(f"Total NA entries for full scan: {len(all_remaining)}")

CHUNK_SIZE = 20
total_moved = 0
total_retyped = 0
all_changed_ids = set()
source_name = 'deepseek_na_scan'


def process_deepseek_results(results):
    """Process DeepSeek JSON results and update DB + provenance."""
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
            elif faith == "HINDU":
                new_faith, new_trad, new_type = 'Hindu', trad or 'Other', 'temple'
            elif faith == "BUDDHIST":
                new_faith, new_trad, new_type = 'Buddhist', trad or 'Mahayana', 'temple'
            elif faith == "ISLAM":
                new_faith, new_trad, new_type = 'Islam', trad or 'Sunni', 'mosque'
            else:
                new_faith, new_trad, new_type = 'Other', 'New Age', 'organization'

            update_with_provenance(id_, 'faith', None, new_faith, source_name)
            update_with_provenance(id_, 'tradition', None, new_trad, source_name)
            update_with_provenance(id_, 'landmark_type', None, new_type, source_name)
            total_moved += 1
            moved += 1
        else:
            # Still Jewish - update tradition/type
            mapped = ftype.lower().replace('_', ' ') if ftype else None
            if mapped == 'temple':
                mapped = 'synagogue'
            if trad and trad not in ('Rabbinic', ''):
                c.execute("SELECT tradition FROM churches WHERE id=?", (id_,))
                old_trad = c.fetchone()
                if old_trad and old_trad[0] != trad:
                    update_with_provenance(id_, 'tradition', old_trad[0], trad, source_name)
            if mapped and mapped not in ('synagogue', None):
                c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,))
                old_type = c.fetchone()
                if old_type and old_type[0] != mapped:
                    update_with_provenance(id_, 'landmark_type', old_type[0], mapped, source_name)
                    total_retyped += 1
        all_changed_ids.add(id_)
    return moved


def call_deepseek(items, prompt_template, max_tokens=2500):
    """Call DeepSeek API and return parsed results."""
    prompt = prompt_template.format(items=json.dumps(items, indent=2))
    resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.05,
        "max_tokens": max_tokens
    }, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }, timeout=90)

    if resp.status_code == 200:
        content = resp.json()["choices"][0]["message"]["content"]
        jm = re.search(r'\[.*?\]', content, re.DOTALL)
        if jm:
            return json.loads(jm.group())
        print(f"  NO JSON in response")
        return None
    print(f"  HTTP {resp.status_code}")
    return None


PHASE_A_PROMPT = """Classify each non-US religious site entry carefully.

Key rules:
- Christian names (church, chapel, cathedral, abbey, shrine, jesus, christ, gospel, saint, trinity, holy, grace, faith, cross, our lady, notre dame, st., san, santa, iglesia, mission): CHRISTIAN
- Jewish names (synagogue, temple, beth, bet, chabad, rabbi, torah, yeshiva, kollel, hillel, mikvah, israel, judaism, jewish, hebrew, shalom, tiferet, chesed, meir, levi, cohen): JEWISH
- Non-religious (foundation, society, museum, library, institute, university, college, school, community, center, association): OTHER
- Hindu, Buddhist, Islamic names: use those faith labels

For CHRISTIAN, specify tradition (Catholic, Baptist, Anglican, Orthodox, Pentecostal, etc.) and type (CHURCH, CATHEDRAL, CHAPEL, ABBEY, MISSION, SHRINE)
For JEWISH, specify type: SYNAGOGUE, CHABAD, YESHIVA, KOLLEL, SCHOOL, COMMUNITY_CENTER, MIKVEH, HILLEL, CEMETERY, MUSEUM, ORGANIZATION

Return ONLY valid JSON array:
[{{"id": N, "faith": "CHRISTIAN|JEWISH|HINDU|BUDDHIST|ISLAM|OTHER", "tradition": "...", "type": "SYNAGOGUE|CHURCH|...|null"}}]

{items}"""

PHASE_B_PROMPT = """For each religious site, determine if it is actually Jewish.

Quick classification guide:
- Christian indicators: church, chapel, cathedral, abbey, shrine, jesus, christ, gospel, saint, st., trinity, holy, grace, our lady, notre dame, san, santa, iglesia, mission, pastor, bishop, parish
- Jewish indicators: synagogue, temple (Jewish context), beth/bet, chabad, rabbi, torah, yeshiva, kollel, hillel, mikvah, israel (Jewish org), jewish, hebrew, shalom, congregation (Jewish)
- If name is neutral and location/context is ambiguous, default to JEWISH for entries already marked Jewish

If CHRISTIAN, specify tradition (Catholic, Anglican, Baptist, etc.) and type (CHURCH, CATHEDRAL, CHAPEL, etc.)
If JEWISH, specify tradition (Orthodox, Conservative, Reform, Rabbinic, etc.) and type (SYNAGOGUE, CHABAD, etc.)

Return ONLY JSON:
[{{"id": N, "faith": "JEWISH|CHRISTIAN|OTHER", "tradition": "...", "type": "SYNAGOGUE|CHURCH|..."}}]

{items}"""

# Phase A: scan problematic entries
if problematic:
    print(f"\n--- Phase A: Problematic entries ({len(problematic)}) ---")
    for cs in range(0, len(problematic), CHUNK_SIZE):
        chunk = problematic[cs:cs+CHUNK_SIZE]
        items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
                  "state": str(e[3] or ''), "country": str(e[4] or '')} for e in chunk]
        batch_num = cs // CHUNK_SIZE + 1
        total_batches = (len(problematic) - 1) // CHUNK_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches}...", end=" ")
        sys.stdout.flush()
        results = call_deepseek(items, PHASE_A_PROMPT)
        if results:
            moved = process_deepseek_results(results)
            conn.commit()
            print(f"OK - {moved} moved, {len(results)-moved} retyped")
        else:
            print(f"FAIL")

# Phase B: full scan of all remaining
if all_remaining:
    print(f"\n--- Phase B: Full scan of all ({len(all_remaining)}) ---")
    for cs in range(0, len(all_remaining), CHUNK_SIZE):
        chunk = all_remaining[cs:cs+CHUNK_SIZE]
        items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
                  "state": str(e[3] or ''), "country": str(e[4] or '')} for e in chunk]
        batch_num = cs // CHUNK_SIZE + 1
        total_batches = (len(all_remaining) - 1) // CHUNK_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches}...", end=" ")
        sys.stdout.flush()
        results = call_deepseek(items, PHASE_B_PROMPT, max_tokens=3000)
        if results:
            moved = process_deepseek_results(results)
            conn.commit()
            print(f"OK - {moved} moved out")
        else:
            print(f"FAIL")

print(f"\n=== DeepSeek scan complete ===")
print(f"  Moved out of Judaism: {total_moved}")
print(f"  Retyped (still Jewish): {total_retyped}")
print(f"  Unique churches changed: {len(all_changed_ids)}")

# Log to provenance_log
COMPLETED_AT = datetime.now(timezone.utc).isoformat()
notes = f"DeepSeek NA Judaism scan: {total_moved} moved out, {total_retyped} retyped, {prov_fixes} province fixes."
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)
""", ('deepseek', SCRIPT_NAME, STARTED_AT, COMPLETED_AT,
      len(all_changed_ids), 'faith,tradition,landmark_type,state,country', notes))
conn.commit()
print(f"  Provenance logged.")

# ── Step 3: Final verification ──

print(f"\n=== Step 3: Final verification ===")

c.execute(f"""
    SELECT country, COUNT(*) FROM churches
    WHERE faith='Judaism' AND country IN ({placeholders})
    GROUP BY country ORDER BY COUNT(*) DESC
""", na_countries)
total = 0
for row in c.fetchall():
    print(f"  {row[0]:20s} {row[1]:>5,}")
    total += row[1]
print(f"  {'TOTAL':20s} {total:>5,}")

# Check for any remaining problematic entries
c.execute(f"""
    SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders})
    AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))
""", na_countries)
bad = c.fetchone()[0]
print(f"\nStill problematic: {bad}")
if bad > 0:
    c.execute(f"""
        SELECT id, name, city, country, landmark_type FROM churches
        WHERE faith='Judaism' AND country IN ({placeholders})
        AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))
        ORDER BY country
    """, na_countries)
    for r in c.fetchall():
        print(f"  #{r[0]:>8} {str(r[1] or ''):45s} {str(r[2] or ''):20s} {str(r[3] or ''):10s} type={r[4]}")

# Check province normalization in Canada
c.execute("SELECT state, COUNT(*) FROM churches WHERE faith='Judaism' AND country='Canada' GROUP BY state ORDER BY COUNT(*) DESC")
print(f"\nCanada province distribution:")
for r in c.fetchall():
    print(f"  {r[0]:30s} {r[1]:>5,}")

# Verify provenance was logged
c.execute("SELECT id, churches_updated, notes FROM provenance_log WHERE script_name=? ORDER BY id DESC LIMIT 1", (SCRIPT_NAME,))
row = c.fetchone()
if row:
    print(f"\nProvenance entry #{row[0]}: {row[1]} churches updated. Notes: {row[2]}")

conn.close()
print(f"\nDone!")
