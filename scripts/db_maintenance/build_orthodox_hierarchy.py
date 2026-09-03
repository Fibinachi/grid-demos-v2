"""
Build Orthodox hierarchy table (Eastern + Oriental).
Structure: Patriarchate/Jurisdiction → Diocese → Parish

Christian Orthodox only (excludes Jewish Orthodox taxonomy 542-546).
"""
import sqlite3

db = sqlite3.connect('churches.db')
db.execute("PRAGMA journal_mode=WAL")

# Christian Orthodox taxonomy IDs (NOT Jewish Orthodox 542-546)
ORTHODOX_TAX_IDS = [
    18,     # Orthodox (parent)
    178,    # Eastern Orthodox
    179,    # Antiochian Orthodox
    180,    # Bulgarian Orthodox
    181,    # Georgian Orthodox
    182,    # Greek Orthodox
    184,    # Romanian Orthodox
    185,    # Russian Orthodox
    186,    # Serbian Orthodox
    187,    # Ukrainian Orthodox
    191,    # Oriental Orthodox
    192,    # Armenian Apostolic
    193,    # Coptic Orthodox
    194,    # Eritrean Orthodox
    195,    # Ethiopian Orthodox
    196,    # Malankara Orthodox
    197,    # Syriac Orthodox
]
OX = ORTHODOX_TAX_IDS
ox_ph = ','.join('?' * len(OX))

print("=" * 70)
print("ORTHODOX HIERARCHY (Eastern + Oriental)")
print("=" * 70)

db.execute("DROP TABLE IF EXISTS orthodox_hierarchy")
db.execute("""
    CREATE TABLE orthodox_hierarchy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER,
        church_id INTEGER REFERENCES churches(id),
        name TEXT NOT NULL,
        original_name TEXT,
        orthodox_type TEXT NOT NULL CHECK(orthodox_type IN (
            'patriarchate','jurisdiction','archdiocese','diocese','metropolis','parish','monastery','cathedral','other'
        )),
        orthodox_detail TEXT,
        jurisdiction TEXT,
        diocese_name TEXT,
        rite TEXT,
        country TEXT, city TEXT, state TEXT,
        lat REAL, lon REAL,
        parent_type TEXT,
        relationship TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
db.execute("CREATE INDEX IF NOT EXISTS idx_orth_hier_type ON orthodox_hierarchy(orthodox_type)")
db.execute("CREATE INDEX IF NOT EXISTS idx_orth_hier_parent ON orthodox_hierarchy(parent_id)")
db.execute("CREATE INDEX IF NOT EXISTS idx_orth_hier_church ON orthodox_hierarchy(church_id)")

# Orthodox filter: Christian faith + Orthodox taxonomy + NOT Jewish Orthodox
# Also include tradition-based matches
ORTHODOX_WHERE = f"""
    (taxonomy_id IN ({ox_ph}) OR tradition IN (
        'Orthodox','Eastern Orthodox','Oriental Orthodox','Coptic Orthodox','Armenian Apostolic',
        'Greek Orthodox','Russian Orthodox','Serbian Orthodox','Romanian Orthodox',
        'Bulgarian Orthodox','Georgian Orthodox','Ukrainian Orthodox','Antiochian Orthodox',
        'Syriac Orthodox','Syrian Orthodox','Ethiopian Orthodox','Malankara Orthodox',
        'Eritrean Orthodox','Orthodox Churches','Orthodox (general)'
    ))
    AND faith = 'Christian'
"""

# Count
total_orth = db.execute(f"SELECT COUNT(*) FROM churches WHERE {ORTHODOX_WHERE}", OX).fetchone()[0]
print(f"  Christian Orthodox churches: {total_orth:,}")

# ===== JURISDICTIONS =====
JURISDICTIONS = {
    'UA': [('Ukrainian Orthodox Church', 'UOC', 'Eastern Orthodox', 187)],
    'RU': [('Russian Orthodox Church', 'ROC', 'Eastern Orthodox', 185)],
    'GR': [('Church of Greece', 'CoG', 'Eastern Orthodox', 182)],
    'RO': [('Romanian Orthodox Church', 'RoOC', 'Eastern Orthodox', 184)],
    'RS': [('Serbian Orthodox Church', 'SOC', 'Eastern Orthodox', 186)],
    'BG': [('Bulgarian Orthodox Church', 'BOC', 'Eastern Orthodox', 180)],
    'CY': [('Church of Cyprus', 'CoC', 'Eastern Orthodox', 182)],
    'ET': [('Ethiopian Orthodox Tewahedo Church', 'EOTC', 'Oriental Orthodox', 195)],
    'GE': [('Georgian Orthodox Church', 'GOC', 'Eastern Orthodox', 181)],
    'AM': [('Armenian Apostolic Church', 'AAC', 'Oriental Orthodox', 192)],
    'ER': [('Eritrean Orthodox Tewahedo Church', 'EriOTC', 'Oriental Orthodox', 194)],
    'SY': [('Syriac Orthodox Church', 'SOC', 'Oriental Orthodox', 197)],
    'IN': [('Malankara Orthodox Syrian Church', 'MOSC', 'Oriental Orthodox', 196)],
    # US has multiple overlapping jurisdictions
    'US': [
        ('Greek Orthodox Archdiocese of America', 'GOA', 'Eastern Orthodox', 182),
        ('Orthodox Church in America', 'OCA', 'Eastern Orthodox', 185),
        ('Antiochian Orthodox Christian Archdiocese', 'AOCA', 'Eastern Orthodox', 179),
        ('Serbian Orthodox Church in North America', 'SOC-NA', 'Eastern Orthodox', 186),
        ('Russian Orthodox Church Outside Russia', 'ROCOR', 'Eastern Orthodox', 185),
        ('Ukrainian Orthodox Church of the USA', 'UOC-USA', 'Eastern Orthodox', 187),
        ('Romanian Orthodox Metropolia of the Americas', 'ROMA', 'Eastern Orthodox', 184),
        ('Bulgarian Orthodox Church USA', 'BOC-USA', 'Eastern Orthodox', 180),
        ('Coptic Orthodox Church USA', 'COC-USA', 'Oriental Orthodox', 193),
        ('Armenian Apostolic Church USA', 'AAC-USA', 'Oriental Orthodox', 192),
        ('Ethiopian Orthodox Church USA', 'EOTC-USA', 'Oriental Orthodox', 195),
    ],
}

jurisdiction_ids = {}
for country, juris_list in JURISDICTIONS.items():
    for name, short, rite, tax_id in juris_list:
        cur = db.cursor()
        cur.execute("""INSERT INTO orthodox_hierarchy (name,orthodox_type,jurisdiction,rite,country,notes)
                       VALUES (?, 'jurisdiction', ?, ?, ?, ?)""",
                    (name, short, rite, country, f"tax_id={tax_id}"))
        jurisdiction_ids[(country, short)] = cur.lastrowid

# Remaining countries: one jurisdiction per country
already = list(JURISDICTIONS.keys())
for country, count in db.execute(f"""
    SELECT country, COUNT(*) FROM churches WHERE {ORTHODOX_WHERE}
    AND country NOT IN ({','.join('?'*len(already))})
    GROUP BY country HAVING COUNT(*) >= 10 ORDER BY COUNT(*) DESC
""", OX + already).fetchall():
    short = f"Orthodox-{country}"
    cur = db.cursor()
    cur.execute("""INSERT INTO orthodox_hierarchy (name,orthodox_type,jurisdiction,country,notes)
                   VALUES (?, 'jurisdiction', ?, ?, ?)""",
                (f"Orthodox Church in {country}", short, country, f"{count:,} churches"))
    jurisdiction_ids[(country, short)] = cur.lastrowid

print(f"  Jurisdictions: {len(jurisdiction_ids)}")

# ===== DIOCESES =====
# For top countries, create state-level dioceses
for country, juris_list in JURISDICTIONS.items():
    # Count Orthodox churches in this country
    country_count = db.execute(f"SELECT COUNT(*) FROM churches WHERE {ORTHODOX_WHERE} AND country=?", OX + [country]).fetchone()[0]
    
    if country_count > 50 and country in ('US','UA','RU','GR','RO','RS','BG'):
        # State-level dioceses
        for state, cnt in db.execute(f"""
            SELECT state, COUNT(*) FROM churches WHERE {ORTHODOX_WHERE} AND country=? AND state IS NOT NULL AND state != ''
            GROUP BY state ORDER BY COUNT(*) DESC
        """, OX + [country]).fetchall():
            for name, short, rite, tax_id in juris_list:
                jid = jurisdiction_ids.get((country, short))
                if jid:
                    db.execute("""INSERT INTO orthodox_hierarchy (parent_id,name,orthodox_type,diocese_name,jurisdiction,rite,country,state,relationship,notes)
                                  VALUES (?,?, 'diocese',?,?,?,?,?,'part_of',?)""",
                               (jid, f"Orthodox Diocese of {state}", state, short, rite, country, state, f"{cnt:,} churches"))
    elif country in ('US',):
        pass  # already handled above
    else:
        # Single diocese per country
        for name, short, rite, tax_id in juris_list:
            jid = jurisdiction_ids.get((country, short))
            if jid:
                db.execute("""INSERT INTO orthodox_hierarchy (parent_id,name,orthodox_type,diocese_name,jurisdiction,rite,country,relationship,notes)
                              VALUES (?,?, 'diocese',?,?,?,?,'part_of',?)""",
                           (jid, f"Diocese of {name}", short, short, rite, country, f"{country_count:,} churches"))

# Other countries: one diocese each
for country, count in db.execute(f"""
    SELECT country, COUNT(*) FROM churches WHERE {ORTHODOX_WHERE}
    AND country NOT IN ({','.join('?'*len(already))})
    GROUP BY country HAVING COUNT(*) >= 10 ORDER BY COUNT(*) DESC
""", OX + already).fetchall():
    jid = jurisdiction_ids.get((country, f"Orthodox-{country}"))
    if jid:
        db.execute("""INSERT INTO orthodox_hierarchy (parent_id,name,orthodox_type,diocese_name,jurisdiction,country,relationship,notes)
                      VALUES (?,?, 'diocese',?,?,?,'part_of',?)""",
                   (jid, f"Diocese of {country}", country, f"Orthodox-{country}", country, f"{count:,} churches"))

print("  Dioceses inserted")

# ===== LINK PARISHES =====
print("  Linking parishes...")

# US: Link to GOA as default jurisdiction (largest)
goa = db.execute("SELECT id FROM orthodox_hierarchy WHERE jurisdiction='GOA'").fetchone()
if goa:
    for state, in db.execute(f"SELECT DISTINCT state FROM churches WHERE {ORTHODOX_WHERE} AND country='US' AND state IS NOT NULL", OX).fetchall():
        dio = db.execute("SELECT id FROM orthodox_hierarchy WHERE diocese_name=? AND country='US' AND jurisdiction='GOA'", (state,)).fetchone()
        if not dio:
            dio = db.execute("SELECT id FROM orthodox_hierarchy WHERE diocese_name=? AND country='US' AND jurisdiction='OCA'", (state,)).fetchone()
        if dio:
            db.execute(f"""INSERT INTO orthodox_hierarchy (parent_id,church_id,name,orthodox_type,diocese_name,jurisdiction,country,state,lat,lon,relationship)
                SELECT ?,c.id,c.name,'parish',?,'GOA','US',c.state,c.latitude,c.longitude,'part_of'
                FROM churches c WHERE {ORTHODOX_WHERE} AND c.country='US' AND c.state=?""",
                [dio[0], state] + OX + [state])

# UA, RU, GR, RO, RS, BG, CY, ET — link by state
for country in ['UA','RU','GR','RO','RS','BG','CY','ET']:
    juris = list(JURISDICTIONS.get(country, [(None,None,None,None)]))[0]
    short = juris[1]
    if not short: continue
    for state, in db.execute(f"SELECT DISTINCT state FROM churches WHERE {ORTHODOX_WHERE} AND country=? AND state IS NOT NULL", OX + [country]).fetchall():
        dio = db.execute("SELECT id FROM orthodox_hierarchy WHERE diocese_name=? AND country=? AND jurisdiction=?", (state, country, short)).fetchone()
        if dio:
            db.execute(f"""INSERT INTO orthodox_hierarchy (parent_id,church_id,name,orthodox_type,diocese_name,jurisdiction,country,state,lat,lon,relationship)
                SELECT ?,c.id,c.name,'parish',?,?,c.country,c.state,c.latitude,c.longitude,'part_of'
                FROM churches c WHERE {ORTHODOX_WHERE} AND c.country=? AND c.state=?""",
                [dio[0], state, short] + OX + [country, state])

# Other countries: link all to their jurisdiction's diocese
for (country, short), jid in jurisdiction_ids.items():
    if country in ('US','UA','RU','GR','RO','RS','BG','CY','ET'): continue
    dio = db.execute("SELECT id FROM orthodox_hierarchy WHERE jurisdiction=? AND country=? AND orthodox_type='diocese'", (short, country)).fetchone()
    if dio:
        db.execute(f"""INSERT INTO orthodox_hierarchy (parent_id,church_id,name,orthodox_type,jurisdiction,country,state,lat,lon,relationship)
            SELECT ?,c.id,c.name,'parish',?,c.country,c.state,c.latitude,c.longitude,'part_of'
            FROM churches c WHERE {ORTHODOX_WHERE} AND c.country=?""",
            [dio[0], short] + OX + [country])

db.commit()

# ===== STATS =====
print(f"\n{'='*70}")
print("ORTHODOX HIERARCHY COMPLETE")
print(f"{'='*70}")
total_h = db.execute("SELECT COUNT(*) FROM orthodox_hierarchy").fetchone()[0]
print(f"  Orthodox churches:        {total_orth:>10,}")
print(f"  Hierarchy rows:           {total_h:>10,}")
for typ, count in db.execute("SELECT orthodox_type, COUNT(*) FROM orthodox_hierarchy GROUP BY orthodox_type ORDER BY COUNT(*) DESC").fetchall():
    print(f"    {typ:<15s}: {count:>10,}")

# By rite
print(f"\n  By Rite:")
for rite, count in db.execute("SELECT rite, COUNT(*) FROM orthodox_hierarchy WHERE rite IS NOT NULL GROUP BY rite ORDER BY COUNT(*) DESC").fetchall():
    print(f"    {rite:<25s}: {count:>10,}")

# By country
print(f"\n  Top Countries:")
for country, count in db.execute(f"SELECT country, COUNT(*) FROM churches WHERE {ORTHODOX_WHERE} GROUP BY country ORDER BY COUNT(*) DESC LIMIT 15", OX).fetchall():
    print(f"    {country:<5s}: {count:>8,}")

db.execute("""INSERT INTO provenance_log (source,script_name,started_at,completed_at,status,notes)
              VALUES ('orthodox_hierarchy','build_orthodox_hierarchy.py',datetime('now'),datetime('now'),'completed',?)""",
           (f"Built orthodox_hierarchy: {total_h} rows for {total_orth} Orthodox churches"))
db.commit()
db.close()
print("\nDone.")
