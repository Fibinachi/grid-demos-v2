"""Finish the last ~60 entries of Europe scan + fix regressions + Israel + BQ.

Covers: last 3 batches of Europe, normalization cleanup, then Israel scan.
"""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY: print("ERROR: DEEPSEEK_API_KEY not set!"); sys.exit(1)

source_name = 'deepseek_europe_scan2'

europe = [
    'AL','Albania','AD','Andorra','AT','Austria','BY','Belarus','BE','Belgium',
    'BA','Bosnia','BG','Bulgaria','HR','Croatia','CZ','Czech Republic',
    'DK','Denmark','EE','Estonia','FI','Finland','FR','France','DE','Germany',
    'GR','Greece','HU','Hungary','IS','Iceland','IE','Ireland','IT','Italy',
    'XK','Kosovo','LV','Latvia','LI','Liechtenstein','LT','Lithuania',
    'LU','Luxembourg','MT','Malta','MD','Moldova','MC','Monaco','ME','Montenegro',
    'NL','Netherlands','MK','North Macedonia','NO','Norway','PL','Poland',
    'PT','Portugal','RO','Romania','SM','San Marino','RS','Serbia',
    'SK','Slovakia','SI','Slovenia','ES','Spain','SE','Sweden','CH','Switzerland',
    'UA','Ukraine','GB','United Kingdom','VA','Vatican City',
    'GG','Guernsey','JE','Jersey','IM','Isle of Man','GI','Gibraltar',
    'England','Scotland','Wales','Northern Ireland'
]
ph = ','.join('?' for _ in europe)

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

PROMPT = """For each religious site, determine if it is actually Jewish.
Quick classification guide:
- Christian: church, chapel, cathedral, shrine, jesus, christ, gospel, saint, trinity, holy, grace, cross, notre dame, st., san, santa, iglesia, mission, pastor, bishop, parish, evangel, kirche, eglise, igreja, chiesa
- Jewish: synagogue, temple, beth/bet, chabad, rabbi, torah, yeshiva, kollel, hillel, mikvah, israel, jewish, hebrew, shalom, congregation, sepharade, judische
- Muslim: mosque, masjid, islam, allah: ISLAM
- Default to JEWISH if neutral
If CHRISTIAN: tradition + type (CHURCH/CATHEDRAL/CHAPEL)
If JEWISH: tradition + type (SYNAGOGUE/CHABAD/YESHIVA/KOLLEL/SCHOOL/COMMUNITY_CENTER/MIKVEH/HILLEL/CEMETERY/MUSEUM/ORGANIZATION)
Return ONLY JSON array:
[{{"id": N, "faith": "JEWISH|CHRISTIAN|HINDU|BUDDHIST|ISLAM|OTHER", "tradition": "...", "type": "SYNAGOGUE|CHURCH|..."}}]
{items}"""

def call_deepseek(items):
    prompt = PROMPT.format(items=json.dumps(items, indent=2))
    for attempt in range(3):
        try:
            resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
                "model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.05, "max_tokens": 3000
            }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=120)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                jm = re.search(r'\[.*?\]', content, re.DOTALL)
                if jm: return json.loads(jm.group())
                print(f" NOJSON", end="")
            else:
                print(f" HTTP{resp.status_code}", end="")
        except Exception as e:
            print(f" ERR", end="")
    return None

# ── Step 1: Get last unscanned entries ──
total_total = 0
print("=== Step 1: Check already scanned vs remaining ===")
c.execute("SELECT COUNT(DISTINCT church_id) FROM enrichment_change_log WHERE change_source IN ('deepseek_europe_scan','deepseek_europe_scan2')")
already = c.fetchone()[0]
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph})", europe)
remaining_all = c.fetchone()[0]
print(f"Already scanned: {already} churches, Remaining: {remaining_all} entries")

# ── Step 2: Scan last remaining ──
print(f"\n=== Step 2: Scan remaining ===")
c.execute(f"SELECT id, name, city, state, country, landmark_type, tradition FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND id NOT IN (SELECT DISTINCT church_id FROM enrichment_change_log WHERE change_source IN ('deepseek_europe_scan','deepseek_europe_scan2')) ORDER BY country, name", europe)
entries = c.fetchall()
print(f"Unscanned entries: {len(entries)}")

CHUNK_SIZE = 20
total_moved = 0
total_retyped = 0
all_changed_ids = set()

def process_results(results):
    global total_moved, total_retyped
    moved = 0
    for r in results:
        id_ = r.get("id"); faith = r.get("faith","").upper()
        trad = r.get("tradition",""); ftype = (r.get("type") or "").upper()
        if faith in ("CHRISTIAN","HINDU","BUDDHIST","ISLAM","OTHER","NEWAGE"):
            if faith == "CHRISTIAN":
                mapped = ftype.lower() if ftype.lower() in ('church','cathedral','chapel','abbey','mission','shrine','cemetery') else 'church'
                nf, nt, nl = 'Christian', trad or 'Other Christian', mapped
            elif faith == "HINDU":   nf, nt, nl = 'Hindu', trad or 'Other', 'temple'
            elif faith == "BUDDHIST": nf, nt, nl = 'Buddhist', trad or 'Mahayana', 'temple'
            elif faith == "ISLAM":   nf, nt, nl = 'Islam', trad or 'Sunni', 'mosque'
            else:                    nf, nt, nl = 'Other', 'New Age', 'organization'
            update_with_provenance(id_, 'faith', None, nf)
            update_with_provenance(id_, 'tradition', None, nt)
            update_with_provenance(id_, 'landmark_type', None, nl)
            total_moved += 1; moved += 1
        else:
            mapped = ftype.lower().replace('_',' ') if ftype else None
            if mapped == 'temple': mapped = 'synagogue'
            if trad and trad not in ('Rabbinic',''):
                c.execute("SELECT tradition FROM churches WHERE id=?", (id_,))
                ot = c.fetchone()
                if ot and ot[0] != trad: update_with_provenance(id_, 'tradition', ot[0], trad)
            if mapped and mapped not in ('synagogue',None):
                c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,))
                ot = c.fetchone()
                if ot and ot[0] != mapped:
                    update_with_provenance(id_, 'landmark_type', ot[0], mapped)
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
        print(f"FAIL - skipping {len(items)} entries")

# ── Step 3: Fix regressions ──
print(f"\n=== Step 3: Fix regressions ===")
for old, new in [('chabad','chabad_house'),('community center','community_center'),('mikvah','mikveh')]:
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type=?", europe + [old])
    n = c.fetchone()[0]
    if n:
        c.execute(f"UPDATE churches SET landmark_type=? WHERE faith='Judaism' AND country IN ({ph}) AND landmark_type=?", [new] + europe + [old])
        print(f"  {old}->{new}: {c.rowcount}")
        conn.commit()

# Fix any remaining problematic
c.execute(f"SELECT id, name, country, landmark_type FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", europe)
for r in c.fetchall():
    print(f"  Fixing #{r[0]}: {r[1]} type={r[3]} -> synagogue")
    c.execute("UPDATE churches SET landmark_type='synagogue' WHERE id=?", (r[0],))
    conn.commit()

# ── Step 4: Summary ──
print(f"\n=== Step 4: Summary ===")
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph})", europe)
print(f"Europe Judaism entries: {c.fetchone()[0]:,}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", europe)
print(f"Problematic: {c.fetchone()[0]}")

c.execute(f"SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", europe)
for r in c.fetchall():
    print(f"  {r[0]:25s} {r[1]:>5,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel')")
il = c.fetchone()[0]
print(f"\nWorldwide: {total:,} (Israel: {il:,}, ex-Israel: {total-il:,})")

conn.close()
print("\nEurope done!")
