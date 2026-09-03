"""Check maintenance job posting records in detail."""
from gw_db import connect

db = connect()
c = db.cursor()

# All job-like names from catholic_diocese_scrape
print("=== ALL job-like names from catholic_diocese_scrape ===")
c.execute("""
    SELECT name, COUNT(*) as cnt 
    FROM churches 
    WHERE source = 'catholic_diocese_scrape'
    AND (name LIKE '% DIRECTOR %' OR name LIKE '% TECHNICIAN%' 
         OR name LIKE '% ASSISTANT' OR name LIKE '% COORDINATOR%'
         OR name LIKE 'MAINTENANCE%' OR name LIKE 'LITURGY AND MUSIC%'
         OR name LIKE 'LIMITED PART TIME%' OR name LIKE 'LAY ECCLESIAL%')
    GROUP BY name 
    ORDER BY cnt DESC
""")
rows = c.fetchall()
for r in rows:
    # Get one record's details
    c.execute("SELECT id, name, lat, lon, country, city, state, denomination, faith FROM churches WHERE name = ? LIMIT 1", (r[0],))
    d = c.fetchone()
    # Get contact data
    c.execute("SELECT COUNT(*) FROM church_contacts WHERE church_id = ?", (d[0],))
    contact_cnt = c.fetchone()[0]
    print(f"  [{r[1]}] contacts={contact_cnt} faith={d[8]!r} denom={d[7]!r}")
    print(f"         {d[1][:100]!r}")
    print(f"         {d[4]!r}/{d[5]!r}/{d[6]!r} ({d[2]}, {d[3]})")
    print()

# Also look at the full set of garbage names: article titles, media advisories, etc.
print()
print("=== CHECKING ARTICLE TITLE RECORDS - do they have contact data? ===")
c.execute("""
    SELECT name, source, COUNT(*) as cnt, MIN(id) as sample_id
    FROM churches 
    WHERE source = 'catholic_diocese_scrape'
    AND (name LIKE 'POPE %' OR name LIKE 'CATHOLIC CHURCH %' 
         OR name LIKE 'VATICAN %' OR name LIKE 'BISHOP %'
         OR name LIKE 'MAN CHARGED%' OR name LIKE 'LEAKED EMAILS%'
         OR name LIKE 'MASSIVE TURNING%' OR name LIKE 'KYIVS%'
         OR name LIKE 'KJZT%' OR name LIKE 'KENYAN%'
         OR name LIKE 'MADAGASCAR%' OR name LIKE 'MUSLIM FATHER%'
         OR name LIKE 'PUERTO RICO%' OR name LIKE 'ONE YEAR OF%'
         OR name LIKE 'NEW GLOBAL INITIATIVE%'
         OR name LIKE 'FEAST HIGHLIGHTS%' OR name LIKE 'AFTER CANADA%'
         OR name LIKE 'IS THIS%' OR name LIKE 'IS THE CATHOLIC CHURCH%'
         OR name LIKE 'IF YOURE%' OR name LIKE 'IGNORING%'
         OR name LIKE 'IN METOO%' OR name LIKE 'IN THIS TIKTOK%'
         OR name LIKE 'INDIANA INMATES%' OR name LIKE 'INDIAS SYRO%'
         OR name LIKE 'MARRYING%' OR name LIKE 'JEFF CAVINS%'
         OR name LIKE 'MEMPHIS CATHOLIC%' OR name LIKE 'MEMPHIS JOY%'
         OR name LIKE 'JOINING CATHOLIC%'
         OR name LIKE 'INTERRELIGIOUS DIALOGUE%'
         OR name LIKE 'ICONOSTASIS%' OR name LIKE 'ICYMI%'
         OR name LIKE 'IDEAS GUIDELINES%' OR name LIKE 'LENTEN%'
         OR name LIKE 'INSTALLATION OF FR%'
         OR name LIKE 'IN CATHOLIC%' OR name LIKE 'IN CENTRAL AFRICA%'
         OR name LIKE 'LOCAL CATHOLIC%' OR name LIKE 'MARSHFIELD%'
         OR name LIKE 'MASS AT%' OR name LIKE 'MASS TO BE%'
         OR name LIKE 'LETTER FROM%' OR name LIKE 'KEANY%')
    GROUP BY name 
    ORDER BY cnt DESC
""")
rows = c.fetchall()
print(f"Found {len(rows)} article-like names")
total = 0
with_contacts = 0
for r in rows:
    total += r[2]
    c.execute("SELECT COUNT(*) FROM church_contacts WHERE church_id = ?", (r[3],))
    cc = c.fetchone()[0]
    if cc > 0:
        with_contacts += 1
        print(f"  HAS CONTACTS [{r[2]}] {r[0][:100]}")
    else:
        pass  # no contacts - pure garbage
print(f"Total: {total} records, {with_contacts} have church_contacts entries")

# Same for .html records
print()
print("=== .html records - contact data? ===")
c.execute("SELECT id, name, source FROM churches WHERE name LIKE '%.html'")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM church_contacts WHERE church_id = ?", (r[0],))
    cc = c.fetchone()[0]
    print(f"  contacts={cc} {r[1][:100]}")

# Same for social pages
print()
print("=== SOCIAL PAGE records - contact data? ===")
c.execute("""
    SELECT c.id, c.name, c.source, COUNT(cc.id) as contact_cnt
    FROM churches c
    LEFT JOIN church_contacts cc ON cc.church_id = c.id
    WHERE c.name LIKE '%PUBLIC PAGE%' OR c.name LIKE '%GROUP PAGE%' OR c.name LIKE '%MEMORIAL PAGE%'
    GROUP BY c.id
    ORDER BY contact_cnt DESC
""")
for r in c.fetchall():
    print(f"  contacts={r[3]} id={r[0]} source={r[2]!r} {r[1][:100]}")

# Same for URLs as names
print()
print("=== URL-as-name records - contact data? ===")
c.execute("""
    SELECT c.id, c.name, c.source, COUNT(cc.id) as contact_cnt
    FROM churches c
    LEFT JOIN church_contacts cc ON cc.church_id = c.id
    WHERE c.name LIKE 'http%' OR c.name LIKE 'www.%' 
       OR c.name LIKE 'Https:%' OR c.name LIKE '%goo.gl/maps%'
    GROUP BY c.id
    ORDER BY contact_cnt DESC
""")
for r in c.fetchall():
    print(f"  contacts={r[3]} id={r[0]} source={r[2]!r} {r[1][:100]}")

print()
print("Done.")
