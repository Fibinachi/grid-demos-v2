"""DeepSeek scan of Judaism entries in South America, Africa, Australia/Oceania.

All three regions have 0 problematic landmark_types (no NULL/church/etc),
so this is a full scan to catch misclassified entries (Christian names etc.).

Logs provenance to enrichment_change_log and provenance_log.
"""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SCRIPT_NAME = "scan_global_jewish_deepseek"
STARTED_AT = datetime.now(timezone.utc).isoformat()
source_name = 'deepseek_global_scan'

# South America
sa_countries = [
    'AR','Argentina','BO','Bolivia','BR','Brazil','CL','Chile','CO','Colombia',
    'EC','Ecuador','GY','Guyana','PY','Paraguay','PE','Peru','SR','Suriname',
    'UY','Uruguay','VE','Venezuela','GF','French Guiana','FK','Falkland Islands'
]

# Africa
af_countries = [
    'ZA','South Africa','NG','Nigeria','KE','Kenya','EG','Egypt','MA','Morocco',
    'DZ','Algeria','TN','Tunisia','LY','Libya','SD','Sudan','SS','South Sudan',
    'ET','Ethiopia','ER','Eritrea','GH','Ghana','CI',"Cote d'Ivoire",'SN','Senegal',
    'UG','Uganda','TZ','Tanzania','ZM','Zambia','ZW','Zimbabwe','MW','Malawi',
    'MZ','Mozambique','AO','Angola','NA','Namibia','BW','Botswana','RW','Rwanda',
    'BI','Burundi','CD','DRC','CG','Congo','GA','Gabon','CM','Cameroon',
    'CF','CAR','TD','Chad','NE','Niger','ML','Mali','BF','Burkina Faso',
    'BJ','Benin','TG','Togo','SL','Sierra Leone','LR','Liberia','GN','Guinea',
    'GM','Gambia','MR','Mauritania','CV','Cape Verde','ST','Sao Tome',
    'GQ','Equatorial Guinea','GW','Guinea-Bissau','KM','Comoros','MG','Madagascar',
    'SC','Seychelles','MU','Mauritius','SZ','Eswatini','LS','Lesotho','DJ','Djibouti',
    'SO','Somalia','SH','St Helena','RE','Reunion','YT','Mayotte'
]

# Australia/Oceania
oc_countries = [
    'AU','Australia','NZ','New Zealand','PG','Papua New Guinea','FJ','Fiji',
    'SB','Solomon Islands','VU','Vanuatu','WS','Samoa','TO','Tonga',
    'FM','Micronesia','MH','Marshall Islands','PW','Palau','KI','Kiribati',
    'TV','Tuvalu','NR','Nauru','NC','New Caledonia','PF','French Polynesia',
    'CK','Cook Islands','WF','Wallis and Futuna','AS','American Samoa',
    'GU','Guam','MP','Northern Mariana Islands','TL','Timor-Leste'
]

regions = [
    ("South America", sa_countries),
    ("Africa", af_countries),
    ("Australia/Oceania", oc_countries),
]

all_countries = []
for name, countries in regions:
    all_countries.extend(countries)

placeholders = ','.join('?' for _ in all_countries)

# ── Provenance helpers ──

def log_enrichment(church_id, field, old_val, new_val):
    c.execute(
        "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, ?, ?, ?, ?)",
        (church_id, field, str(old_val) if old_val is not None else None,
         str(new_val) if new_val is not None else None, source_name)
    )

def update_with_provenance(church_id, field, old_val, new_val):
    if old_val is None:
        c.execute("SELECT {} FROM churches WHERE id=?".format(field), (church_id,))
        row = c.fetchone()
        old_val = row[0] if row else None
    if str(old_val) != str(new_val):
        c.execute("UPDATE churches SET {}=? WHERE id=?".format(field), (new_val, church_id))
        log_enrichment(church_id, field, old_val, new_val)

# ── Scan each region ──

CHUNK_SIZE = 20
total_moved = 0
total_retyped = 0
all_changed_ids = set()

PROMPT = """For each religious site, determine if it is actually Jewish.

Quick classification guide:
- Christian indicators: church, chapel, cathedral, abbey, shrine, jesus, christ, gospel, saint, st., trinity, holy, grace, our lady, notre dame, san, santa, iglesia, mission, pastor, bishop, parish, evangelica, evangelico, evangelique
- Jewish indicators: synagogue, temple (Jewish context), beth/bet, chabad, rabbi, torah, yeshiva, kollel, hillel, mikvah, israel (Jewish org), jewish, hebrew, shalom, congregation (Jewish context), comunidad judia, communaute juive, sepharade
- If name is neutral and location/context is ambiguous, default to JEWISH for entries already marked Jewish

If CHRISTIAN, specify tradition (Catholic, Anglican, Baptist, etc.) and type (CHURCH, CATHEDRAL, CHAPEL, etc.)
If JEWISH, specify tradition (Orthodox, Conservative, Reform, Sephardic, Rabbinic, etc.) and type (SYNAGOGUE, CHABAD, YESHIVA, KOLLEL, SCHOOL, COMMUNITY_CENTER, MIKVEH, HILLEL, CEMETERY, MUSEUM, ORGANIZATION)

Return ONLY JSON:
[{{"id": N, "faith": "JEWISH|CHRISTIAN|OTHER", "tradition": "...", "type": "SYNAGOGUE|CHURCH|..."}}]

{items}"""


def call_deepseek(items, max_tokens=2500):
    prompt = PROMPT.format(items=json.dumps(items, indent=2))
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
        print(f"  NO JSON")
        return None
    print(f"  HTTP {resp.status_code}")
    return None


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
            elif faith == "HINDU":
                new_faith, new_trad, new_type = 'Hindu', trad or 'Other', 'temple'
            elif faith == "BUDDHIST":
                new_faith, new_trad, new_type = 'Buddhist', trad or 'Mahayana', 'temple'
            elif faith == "ISLAM":
                new_faith, new_trad, new_type = 'Islam', trad or 'Sunni', 'mosque'
            else:
                new_faith, new_trad, new_type = 'Other', 'New Age', 'organization'
            update_with_provenance(id_, 'faith', None, new_faith)
            update_with_provenance(id_, 'tradition', None, new_trad)
            update_with_provenance(id_, 'landmark_type', None, new_type)
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
                    update_with_provenance(id_, 'tradition', old_trad[0], trad)
            if mapped and mapped not in ('synagogue', None):
                c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,))
                old_type = c.fetchone()
                if old_type and old_type[0] != mapped:
                    update_with_provenance(id_, 'landmark_type', old_type[0], mapped)
                    total_retyped += 1
        all_changed_ids.add(id_)
    return moved


for region_name, countries in regions:
    r_ph = ','.join('?' for _ in countries)
    c.execute(f"SELECT id, name, city, state, country, landmark_type, tradition FROM churches WHERE faith='Judaism' AND country IN ({r_ph}) ORDER BY country, name", countries)
    entries = c.fetchall()
    if not entries:
        print(f"\n{region_name}: 0 entries, skipping")
        continue

    print(f"\n{'='*60}")
    print(f"=== {region_name}: {len(entries)} entries ===")
    print(f"{'='*60}")

    for cs in range(0, len(entries), CHUNK_SIZE):
        chunk = entries[cs:cs+CHUNK_SIZE]
        items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
                  "state": str(e[3] or ''), "country": str(e[4] or '')} for e in chunk]
        batch_num = cs // CHUNK_SIZE + 1
        total_batches = (len(entries) - 1) // CHUNK_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches}...", end=" ")
        sys.stdout.flush()
        results = call_deepseek(items, max_tokens=3000)
        if results:
            moved = process_results(results)
            conn.commit()
            print(f"OK - {moved} moved out")
        else:
            print(f"FAIL")

print(f"\n{'='*60}")
print(f"=== Scan complete ===")
print(f"{'='*60}")
print(f"  Moved out of Judaism: {total_moved}")
print(f"  Retyped (still Jewish): {total_retyped}")
print(f"  Unique churches changed: {len(all_changed_ids)}")

# ── Log to provenance_log ──
COMPLETED_AT = datetime.now(timezone.utc).isoformat()
notes = f"DeepSeek global Judaism scan (SA/Africa/AU): {total_moved} moved out, {total_retyped} retyped."
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)
""", ('deepseek', SCRIPT_NAME, STARTED_AT, COMPLETED_AT,
      len(all_changed_ids), 'faith,tradition,landmark_type', notes))
conn.commit()
print(f"  Provenance logged.")

# ── Final verification ──
print(f"\n=== Final verification ===")

for region_name, countries in regions:
    r_ph = ','.join('?' for _ in countries)
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({r_ph})", countries)
    total = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({r_ph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", countries)
    prob = c.fetchone()[0]
    c.execute(f"SELECT country, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({r_ph}) GROUP BY country ORDER BY COUNT(*) DESC", countries)
    print(f"\n{region_name} ({total} entries, {prob} problematic):")
    for r in c.fetchall():
        print(f"  {r[0]:25s} {r[1]:>5,}")

# Check provenance was logged
c.execute("SELECT id, churches_updated, notes FROM provenance_log WHERE script_name=? ORDER BY id DESC LIMIT 1", (SCRIPT_NAME,))
row = c.fetchone()
if row:
    print(f"\nProvenance entry #{row[0]}: {row[1]} churches updated. Notes: {row[2]}")

# Check enrichment log count
c.execute("SELECT COUNT(*) FROM enrichment_change_log WHERE change_source=?", (source_name,))
print(f"Enrichment change log entries: {c.fetchone()[0]:,}")

conn.close()
print(f"\nDone!")
