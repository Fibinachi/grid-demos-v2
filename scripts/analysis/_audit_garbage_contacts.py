"""Audit: what data do garbage page-name records carry?"""
from gw_db import connect

db = connect()
c = db.cursor()

garbage_patterns = [
    "name LIKE '%MAINTENANCE%'",
    "name LIKE '%LITURGY AND MUSIC%'",
    "name LIKE '%LIMITED PART TIME%' OR name LIKE '%LAY ECCLESIAL%'",
    "name LIKE '% DIRECTOR %' OR name LIKE '% TECHNICIAN%' OR name LIKE '% ASSISTANT'",
    "name LIKE '%.html' OR name LIKE '%.HTM'",
    "name LIKE '%PUBLIC PAGE%' OR name LIKE '%GROUP PAGE%' OR name LIKE '%MEMORIAL PAGE%'",
    "name LIKE 'http%' OR name LIKE 'www.%' OR name LIKE 'Https:%' OR name LIKE '%goo.gl/maps%'",
    "name LIKE 'IMG%' OR name LIKE 'JPII GROUP%' OR name LIKE '%UNSPLASH%' OR name LIKE 'JEN COUSER%'",
    "name LIKE 'MEDIA ADVISORY%' OR name LIKE 'MEDIA ALERT%'",
    "name LIKE '%JACKPOT BINGO%' OR name LIKE '%ICE CREAM SOCIAL%' OR name LIKE 'MASS TIMES%' OR name LIKE 'LOCATOR%' OR name LIKE 'INSTITUTIONAL RECORDS%' OR name LIKE '%MARRIAGE PREPARATION%' OR name LIKE 'IDEAS GUIDELINES%'",
    "name LIKE 'POPE %' OR name LIKE 'CATHOLIC CHURCH %' OR name LIKE 'VATICAN %' OR name LIKE 'BISHOP %'",
    "name LIKE 'MAN CHARGED%' OR name LIKE 'MASSIVE TURNING%' OR name LIKE 'LEAKED EMAILS%'",
    "name LIKE 'IS THE CATHOLIC CHURCH%' OR name LIKE 'IS THIS%'",
    "name LIKE 'KENYAN%' OR name LIKE 'MADAGASCAR%' OR name LIKE 'KYIVS%'",
    "name LIKE 'IN METOO%' OR name LIKE 'IN THIS TIKTOK%' OR name LIKE 'JOINING CATHOLIC%'",
    "name LIKE 'IGNORING%' OR name LIKE 'IF YOURE%'",
    "name LIKE 'FEAST HIGHLIGHTS%' OR name LIKE 'ICYMI%' OR name LIKE 'ICONOSTASIS%'",
    "name LIKE 'PUERTO RICO%' OR name LIKE 'ONE YEAR OF%' OR name LIKE 'MUSLIM FATHER%'",
    "name LIKE 'NEW GLOBAL INITIATIVE%' OR name LIKE 'AFTER CANADA%'",
    "name LIKE 'INTERRELIGIOUS DIALOGUE%' OR name LIKE 'INSTALLATION OF FR%'",
    "name LIKE 'INDIANA INMATES%' OR name LIKE 'INDIAS SYRO%' OR name LIKE 'JEFF CAVINS%'",
    "name LIKE 'MARRYING IN%' OR name LIKE 'MARSHFIELD PARK RIDE%'",
    "name LIKE 'MEMPHIS CATHOLIC SCHOOLS%' OR name LIKE 'MEMPHIS JOY PROM%'",
    "name LIKE 'LENTEN PENANCE%' OR name LIKE 'LENTEN MISSION%' OR name LIKE 'LENTEN DISPLAY%'",
    "name LIKE 'KJZT%' OR name LIKE 'LETTER FROM%' OR name LIKE 'INDICATIONS OF%'",
    "name LIKE 'JUBILEE YEAR%' OR name LIKE 'IN CENTRAL AFRICA%'",
]

where_clause = " OR ".join(garbage_patterns)
c.execute(f"SELECT id, name, source FROM churches WHERE source = 'catholic_diocese_scrape' AND ({where_clause})")
garbage = c.fetchall()
print(f"Total garbage records: {len(garbage)}")

c.execute("CREATE TEMP TABLE IF NOT EXISTS _garbage_ids (id INTEGER PRIMARY KEY)")
c.execute("DELETE FROM _garbage_ids")
c.executemany("INSERT OR IGNORE INTO _garbage_ids (id) VALUES (?)", [(g[0],) for g in garbage])
db.commit()

# church_contacts
print()
print("=== church_contacts on garbage records ===")
c.execute("""
    SELECT cc.church_id, cc.email, cc.phone, cc.website
    FROM church_contacts cc
    JOIN _garbage_ids g ON cc.church_id = g.id
""")
contacts = c.fetchall()
print(f"Total contacts rows: {len(contacts)}")
useful = 0
for r in contacts:
    vals = []
    if r[1]: vals.append(f"email={r[1][:50]}")
    if r[2]: vals.append(f"phone={r[2]}")
    if r[3]: vals.append(f"website={r[3][:50]}")
    if vals:
        useful += 1
        print(f"  ch={r[0]}: {', '.join(vals)}")
print(f"  With useful contact data: {useful}/{len(contacts)}")

# Enrichment
c.execute("SELECT COUNT(*) FROM church_enrichment ce JOIN _garbage_ids g ON ce.church_id = g.id")
print(f"Enrichment rows: {c.fetchone()[0]}")

# Coordinates
c.execute("SELECT COUNT(*) FROM churches c JOIN _garbage_ids g ON c.id = g.id WHERE c.lat IS NOT NULL AND c.lon IS NOT NULL")
print(f"With lat/lon: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM churches c JOIN _garbage_ids g ON c.id = g.id WHERE c.city IS NOT NULL OR c.state IS NOT NULL")
print(f"With city/state: {c.fetchone()[0]}")

# Duplicate .html check
print()
print("=== Duplicate .html names ===")
c.execute("""
    SELECT c.name, c.id FROM churches c JOIN _garbage_ids g ON c.id = g.id
    WHERE (c.name LIKE '%.html' OR c.name LIKE '%.HTM')
""")
html_records = [(r[0], r[1]) for r in c.fetchall()]
for name, cid in html_records:
    clean = name.rsplit('.', 1)[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE name = ? AND source = 'catholic_diocese_scrape' AND id != ?", (clean, cid))
    cnt = c.fetchone()[0]
    if cnt > 0:
        print(f"  [{cid}] {name} -> duplicate of [{clean}]")

db.close()
print()
print("Done.")
