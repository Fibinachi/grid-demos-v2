"""Europe normalization cleanup + Israel scan + flag BQ update."""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")

europe = ['AL','Albania','AD','Andorra','AT','Austria','BY','Belarus','BE','Belgium',
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
    'England','Scotland','Wales','Northern Ireland']
eph = ','.join('?' for _ in europe)

print("=== Step 1: Europe normalization ===")
# Fix chabad regression
c.execute(f"UPDATE churches SET landmark_type='chabad_house' WHERE faith='Judaism' AND country IN ({eph}) AND landmark_type='chabad'", europe)
print(f"  chabad->chabad_house: {c.rowcount}")
# Fix community center
c.execute(f"UPDATE churches SET landmark_type='community_center' WHERE faith='Judaism' AND country IN ({eph}) AND landmark_type='community center'", europe)
print(f"  community center->community_center: {c.rowcount}")
# Fix mikvah->mikveh
c.execute(f"UPDATE churches SET landmark_type='mikveh' WHERE faith='Judaism' AND country IN ({eph}) AND landmark_type='mikvah'", europe)
print(f"  mikvah->mikveh: {c.rowcount}")
# Fix remaining problematic
c.execute(f"SELECT id, name, landmark_type FROM churches WHERE faith='Judaism' AND country IN ({eph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", europe)
for r in c.fetchall():
    c.execute("UPDATE churches SET landmark_type='synagogue' WHERE id=?", (r[0],))
    print(f"  Fixed #{r[0]}: {r[1]} type={r[2]} -> synagogue")
conn.commit()

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({eph})", europe)
eu = c.fetchone()[0]
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({eph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", europe)
print(f"\nEurope: {eu:,} entries, {c.fetchone()[0]} problematic")

# ── Step 2: Israel scan ──
print(f"\n=== Step 2: Israel scan ===")
if not API_KEY: print("ERROR: DEEPSEEK_API_KEY not set!"); sys.exit(1)

source_name = 'deepseek_israel_scan'
STARTED_AT = datetime.now(timezone.utc).isoformat()

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

c.execute("SELECT id, name, city, state, country, landmark_type, tradition FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel') ORDER BY name")
entries = c.fetchall()
print(f"Israel entries to scan: {len(entries)}")

CHUNK_SIZE = 20
total_moved = 0
total_retyped = 0
all_changed_ids = set()

PROMPT = """For each religious site in Israel, determine if it is actually Jewish.
- Christian indicators: church, chapel, monastery, convent, shrine, jesus, christ, gospel, saint, trinity, holy, grace, cross, notre dame, st., san, santa, mission, pastor, bishop, parish, baptist, catholic, orthodox (Christian)
- Muslim indicators: mosque, masjid, islam, allah: ISLAM
- Jewish indicators: synagogue, temple, beth/bet, chabad, rabbi, torah, yeshiva, kollel, hillel, mikvah, israel, jewish, hebrew, shalom, congregation, sepharade
- Default to JEWISH for neutral names in Israel
If CHRISTIAN: tradition (Catholic, Orthodox, etc.) + type (CHURCH, CATHEDRAL, CHAPEL, MONASTERY, CONVENT, SHRINE)
If JEWISH: tradition (Orthodox, Conservative, Reform, Sephardic, Rabbinic, etc.) + type (SYNAGOGUE, CHABAD, YESHIVA, KOLLEL, SCHOOL, COMMUNITY_CENTER, MIKVEH, HILLEL, CEMETERY, MUSEUM, ORGANIZATION)
Return ONLY JSON array:
[{{"id": N, "faith": "JEWISH|CHRISTIAN|HINDU|BUDDHIST|ISLAM|OTHER", "tradition": "...", "type": "SYNAGOGUE|CHURCH|..."}}]
{items}"""

for cs in range(0, len(entries), CHUNK_SIZE):
    chunk = entries[cs:cs+CHUNK_SIZE]
    items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
              "state": str(e[3] or ''), "country": str(e[4] or '')} for e in chunk]
    bn = cs//CHUNK_SIZE+1; tb = (len(entries)-1)//CHUNK_SIZE+1
    print(f"  Batch {bn}/{tb}...", end=" "); sys.stdout.flush()

    prompt = PROMPT.format(items=json.dumps(items, indent=2))
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
            "model": "deepseek-chat", "messages": [{"role":"user","content":prompt}],
            "temperature": 0.05, "max_tokens": 3000
        }, headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"}, timeout=120)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            jm = re.search(r'\[.*?\]', content, re.DOTALL)
            if jm:
                results = json.loads(jm.group())
                moved = 0
                for r in results:
                    id_ = r.get("id"); faith = r.get("faith","").upper()
                    trad = r.get("tradition",""); ftype = (r.get("type") or "").upper()
                    if faith in ("CHRISTIAN","HINDU","BUDDHIST","ISLAM","OTHER","NEWAGE"):
                        if faith == "CHRISTIAN":
                            mapped = ftype.lower() if ftype.lower() in ('church','cathedral','chapel','abbey','mission','shrine','monastery','convent','cemetery') else 'church'
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
                conn.commit()
                print(f"OK - {moved} moved")
            else:
                print(f" NOJSON")
                # Still commit partial results
                conn.commit()
        else:
            print(f" HTTP{resp.status_code}")
            conn.commit()
    except Exception as e:
        print(f" ERR {e}")
        conn.commit()

print(f"\nIsrael scan complete: {total_moved} moved out, {total_retyped} retyped")

# Log provenance
COMPLETED_AT = datetime.now(timezone.utc).isoformat()
c.execute("INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)",
          ('deepseek', 'scan_israel_jewish_deepseek', STARTED_AT, COMPLETED_AT,
           len(all_changed_ids), 'faith,tradition,landmark_type',
           f'DeepSeek Israel Judaism scan: {total_moved} moved out, {total_retyped} retyped.'))
conn.commit()
print("  Provenance logged.")

# Fix Israel chabad regression
c.execute("UPDATE churches SET landmark_type='chabad_house' WHERE faith='Judaism' AND country IN ('IL','Israel') AND landmark_type='chabad'")
if c.rowcount: print(f"  chabad->chabad_house: {c.rowcount}")
c.execute("UPDATE churches SET landmark_type='community_center' WHERE faith='Judaism' AND country IN ('IL','Israel') AND landmark_type='community center'")
if c.rowcount: print(f"  community center->community_center: {c.rowcount}")
conn.commit()

# ── Step 3: Final worldwide state ──
print(f"\n=== Step 3: Final worldwide state ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel')")
il = c.fetchone()[0]
print(f"Worldwide Judaism: {total:,} (Israel: {il:,}, ex-Israel: {total-il:,})")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))")
print(f"Problematic entries worldwide: {c.fetchone()[0]}")

c.execute("SELECT country, COUNT(*) FROM churches WHERE faith='Judaism' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 15")
print(f"\nTop 15 countries:")
for r in c.fetchall():
    print(f"  {r[0]:25s} {r[1]:>6,}")

# Show total enrichment log entries from deepseek scans
c.execute("SELECT change_source, COUNT(*) FROM enrichment_change_log WHERE change_source LIKE 'deepseek%' GROUP BY change_source ORDER BY change_source")
print(f"\nDeepSeek provenance summary:")
for r in c.fetchall():
    print(f"  {r[0]:30s} {r[1]:>6,}")

conn.close()
print("\nDone! BQ copy needs to be refreshed with current DB state.")
