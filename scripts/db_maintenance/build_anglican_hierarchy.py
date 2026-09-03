"""
Build Anglican Communion hierarchy table.
Structure: Province → Diocese → Parish
"""
import sqlite3

db = sqlite3.connect('churches.db')
db.execute("PRAGMA journal_mode=WAL")

ANGLICAN_TRADITIONS = [
    'Anglican', 'Episcopal', 'Episcopal and Anglican Churches',
    'Anglican/Episcopal', 'Anglican Church', 'Anglican Church of Canada',
    'Anglican Church in North America', 'Anglican Province of America',
    'Church of Uganda (Anglican)', 'Anglican (Church of South India)',
    'Protestant Episcopal', 'Reformed Episcopal Church', 'Episcopal Church',
]
ANG = ANGLICAN_TRADITIONS
ang_ph = ','.join('?' * len(ANG))

print("=" * 70)
print("ANGLICAN COMMUNION HIERARCHY")
print("=" * 70)

db.execute("DROP TABLE IF EXISTS anglican_hierarchy")
db.execute("""
    CREATE TABLE anglican_hierarchy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER,
        church_id INTEGER REFERENCES churches(id),
        name TEXT NOT NULL,
        original_name TEXT,
        anglican_type TEXT NOT NULL CHECK(anglican_type IN ('province','diocese','parish','cathedral','school','other')),
        anglican_detail TEXT,
        province_name TEXT,
        diocese_name TEXT,
        country TEXT, city TEXT, state TEXT,
        lat REAL, lon REAL,
        parent_type TEXT,
        relationship TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
db.execute("CREATE INDEX IF NOT EXISTS idx_ang_hier_type ON anglican_hierarchy(anglican_type)")
db.execute("CREATE INDEX IF NOT EXISTS idx_ang_hier_parent ON anglican_hierarchy(parent_id)")
db.execute("CREATE INDEX IF NOT EXISTS idx_ang_hier_church ON anglican_hierarchy(church_id)")

# ===== PROVINCES =====
CORE_PROVS = {
    'GB': [
        ('Province of Canterbury', 'Canterbury', 'Church of England'),
        ('Province of York', 'York', 'Church of England'),
        ('Church in Wales', 'Church in Wales', 'Church in Wales'),
        ('Scottish Episcopal Church', 'Scottish Episcopal Church', 'Scottish Episcopal Church'),
    ],
    'US': [('The Episcopal Church', 'Episcopal Church USA', 'TEC')],
    'CA': [('Anglican Church of Canada', 'Anglican Church of Canada', 'ACC')],
    'IN': [('Church of South India', 'CSI', 'CSI'), ('Church of North India', 'CNI', 'CNI')],
    'AU': [('Anglican Church of Australia', 'ACA', 'ACA')],
    'NG': [('Church of Nigeria', 'Church of Nigeria', 'CoN')],
    'ZA': [('Anglican Church of Southern Africa', 'ACSA', 'ACSA')],
    'KE': [('Anglican Church of Kenya', 'ACK', 'ACK')],
    'UG': [('Church of Uganda', 'CoU', 'CoU')],
    'GH': [('Anglican Church of Ghana', 'ACG', 'ACG')],
    'PG': [('Anglican Church of PNG', 'ACPNG', 'ACPNG')],
    'NZ': [('Anglican Church in Aotearoa NZ', 'ACANZP', 'ACANZP')],
}

province_ids = {}
for country, provs in CORE_PROVS.items():
    for name, short, notes in provs:
        cur = db.cursor()
        cur.execute("""INSERT INTO anglican_hierarchy (name, anglican_type, province_name, country, notes)
                       VALUES (?, 'province', ?, ?, ?)""", (name, short, country, notes))
        province_ids[(country, short)] = cur.lastrowid

# Other countries with 10+ Anglican churches → generic provinces
core_countries = list(CORE_PROVS.keys())
for country, count in db.execute(f"""
    SELECT country, COUNT(*) FROM churches WHERE tradition IN ({ang_ph})
    AND country NOT IN ({','.join('?'*len(core_countries))})
    GROUP BY country HAVING COUNT(*) >= 10 ORDER BY COUNT(*) DESC
""", ANG + core_countries).fetchall():
    short = f"Anglican-{country}"
    cur = db.cursor()
    cur.execute("""INSERT INTO anglican_hierarchy (name, anglican_type, province_name, country, notes)
                   VALUES (?, 'province', ?, ?, ?)""",
                (f"Anglican Church in {country}", short, country, f"{count:,} churches"))
    province_ids[(country, short)] = cur.lastrowid

print(f"  Provinces: {len(province_ids)}")

# ===== DIOCESES =====
# GB: CofE 41 dioceses + Wales 6 + Scotland 7
COFE = [("Bath and Wells","Canterbury"),("Birmingham","Canterbury"),("Bristol","Canterbury"),
        ("Canterbury","Canterbury"),("Chelmsford","Canterbury"),("Chichester","Canterbury"),
        ("Coventry","Canterbury"),("Derby","Canterbury"),("Ely","Canterbury"),
        ("Exeter","Canterbury"),("Gloucester","Canterbury"),("Guildford","Canterbury"),
        ("Hereford","Canterbury"),("Leicester","Canterbury"),("Lichfield","Canterbury"),
        ("Lincoln","Canterbury"),("London","Canterbury"),("Norwich","Canterbury"),
        ("Oxford","Canterbury"),("Peterborough","Canterbury"),("Portsmouth","Canterbury"),
        ("Rochester","Canterbury"),("St Albans","Canterbury"),("St Edmundsbury","Canterbury"),
        ("Salisbury","Canterbury"),("Southwark","Canterbury"),("Truro","Canterbury"),
        ("Winchester","Canterbury"),("Worcester","Canterbury"),
        ("Blackburn","York"),("Carlisle","York"),("Chester","York"),("Durham","York"),
        ("Leeds","York"),("Liverpool","York"),("Manchester","York"),("Newcastle","York"),
        ("Sheffield","York"),("Sodor and Man","York"),("Southwell","York"),("York","York")]
for dio, prov in COFE:
    pid = province_ids.get(('GB', prov))
    if pid:
        db.execute("""INSERT INTO anglican_hierarchy (parent_id,name,anglican_type,diocese_name,province_name,country,relationship)
                      VALUES (?,?, 'diocese',?,?,'GB','part_of')""",
                   (pid, f"Diocese of {dio}", dio, prov))

WALES_DIOS = ["Bangor","St Asaph","St Davids","Swansea and Brecon","Monmouth","Llandaff"]
for dio in WALES_DIOS:
    pid = province_ids.get(('GB','Church in Wales'))
    if pid:
        db.execute("""INSERT INTO anglican_hierarchy (parent_id,name,anglican_type,diocese_name,province_name,country,relationship)
                      VALUES (?,?, 'diocese',?,'Church in Wales','GB','part_of')""",
                   (pid, f"Diocese of {dio}", dio))

SCOT_DIOS = ["Aberdeen","Argyll","Brechin","Edinburgh","Glasgow","Moray","St Andrews"]
for dio in SCOT_DIOS:
    pid = province_ids.get(('GB','Scottish Episcopal Church'))
    if pid:
        db.execute("""INSERT INTO anglican_hierarchy (parent_id,name,anglican_type,diocese_name,province_name,country,relationship)
                      VALUES (?,?, 'diocese',?,'Scottish Episcopal Church','GB','part_of')""",
                   (pid, f"Diocese of {dio}", dio))

# US & CA: state-level dioceses
for country, prov_key, prov_label in [('US','Episcopal Church USA','Episcopal Church USA'),
                                        ('CA','Anglican Church of Canada','Anglican Church of Canada')]:
    pid = province_ids.get((country, prov_key))
    if not pid: continue
    for state, cnt in db.execute(f"""
        SELECT state, COUNT(*) FROM churches WHERE tradition IN ({ang_ph}) AND country=? AND state IS NOT NULL AND state != ''
        GROUP BY state ORDER BY COUNT(*) DESC
    """, ANG + [country]).fetchall():
        db.execute("""INSERT INTO anglican_hierarchy (parent_id,name,anglican_type,diocese_name,province_name,country,state,relationship,notes)
                      VALUES (?,?, 'diocese',?,?,?,?,'part_of',?)""",
                   (pid, f"Anglican Diocese of {state}", state, prov_label, country, state, f"{cnt:,} churches"))

# Other countries: one diocese each
for (country, prov_key), pid in province_ids.items():
    if country in ('GB','US','CA'): continue
    cnt = db.execute(f"SELECT COUNT(*) FROM churches WHERE tradition IN ({ang_ph}) AND country=?", ANG + [country]).fetchone()[0]
    db.execute("""INSERT INTO anglican_hierarchy (parent_id,name,anglican_type,diocese_name,province_name,country,relationship,notes)
                  VALUES (?,?, 'diocese',?,?,?,'part_of',?)""",
               (pid, f"Diocese of {prov_key}", prov_key, prov_key, country, f"{cnt:,} churches"))

print("  Dioceses inserted")

# ===== LINK PARISHES =====
print("  Linking parishes...")
# US
for state, in db.execute(f"SELECT DISTINCT state FROM churches WHERE tradition IN ({ang_ph}) AND country='US' AND state IS NOT NULL", ANG).fetchall():
    dio = db.execute("SELECT id FROM anglican_hierarchy WHERE diocese_name=? AND country='US'", (state,)).fetchone()
    if dio:
        db.execute(f"""INSERT INTO anglican_hierarchy (parent_id,church_id,name,anglican_type,diocese_name,province_name,country,state,lat,lon,relationship)
            SELECT ?,c.id,c.name,'parish',?,'Episcopal Church USA','US',c.state,c.latitude,c.longitude,'part_of'
            FROM churches c WHERE c.tradition IN ({ang_ph}) AND c.country='US' AND c.state=?""",
            [dio[0], state] + ANG + [state])
# CA
for state, in db.execute(f"SELECT DISTINCT state FROM churches WHERE tradition IN ({ang_ph}) AND country='CA' AND state IS NOT NULL", ANG).fetchall():
    dio = db.execute("SELECT id FROM anglican_hierarchy WHERE diocese_name=? AND country='CA'", (state,)).fetchone()
    if dio:
        db.execute(f"""INSERT INTO anglican_hierarchy (parent_id,church_id,name,anglican_type,diocese_name,province_name,country,state,lat,lon,relationship)
            SELECT ?,c.id,c.name,'parish',?,'Anglican Church of Canada','CA',c.state,c.latitude,c.longitude,'part_of'
            FROM churches c WHERE c.tradition IN ({ang_ph}) AND c.country='CA' AND c.state=?""",
            [dio[0], state] + ANG + [state])
# GB
ctb = db.execute("SELECT id FROM anglican_hierarchy WHERE name='Province of Canterbury'").fetchone()
if ctb:
    db.execute(f"""INSERT INTO anglican_hierarchy (parent_id,church_id,name,anglican_type,province_name,country,state,lat,lon,relationship)
        SELECT ?,c.id,c.name,'parish','Canterbury','GB',c.state,c.latitude,c.longitude,'part_of'
        FROM churches c WHERE c.tradition IN ({ang_ph}) AND c.country IN ('GB','United Kingdom')""",
        [ctb[0]] + ANG)
# Other
for (country, prov_key), pid in province_ids.items():
    if country in ('GB','US','CA'): continue
    dio = db.execute("SELECT id FROM anglican_hierarchy WHERE province_name=? AND country=? AND anglican_type='diocese'", (prov_key, country)).fetchone()
    if dio:
        db.execute(f"""INSERT INTO anglican_hierarchy (parent_id,church_id,name,anglican_type,province_name,country,state,lat,lon,relationship)
            SELECT ?,c.id,c.name,'parish',?,c.country,c.state,c.latitude,c.longitude,'part_of'
            FROM churches c WHERE c.tradition IN ({ang_ph}) AND c.country=?""",
            [dio[0], prov_key] + ANG + [country])

db.commit()

# ===== STATS =====
print(f"\n{'='*70}")
total_h = db.execute("SELECT COUNT(*) FROM anglican_hierarchy").fetchone()[0]
total_a = db.execute(f"SELECT COUNT(*) FROM churches WHERE tradition IN ({ang_ph})", ANG).fetchone()[0]
print(f"  Anglican churches:       {total_a:>10,}")
print(f"  Hierarchy rows:          {total_h:>10,}")
for typ, count in db.execute("SELECT anglican_type, COUNT(*) FROM anglican_hierarchy GROUP BY anglican_type ORDER BY COUNT(*) DESC").fetchall():
    print(f"    {typ:<15s}: {count:>10,}")

db.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at, status, notes)
              VALUES ('anglican_hierarchy','build_anglican_hierarchy.py',datetime('now'),datetime('now'),'completed',?)""",
           (f"Built anglican_hierarchy: {total_h:,} rows for {total_a:,} Anglican churches"))
db.commit()
db.close()
print("\nDone.")
