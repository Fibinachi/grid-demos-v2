"""Cross-reference ACT Heritage Register religious sites against churches.db"""
import sqlite3

db = sqlite3.connect('E:/grid/churches.db')

# Get all ACT/Canberra churches (NOT Tasmania Kingstons)
cur = db.execute(
    "SELECT id, name, city, landmark_type, faith "
    "FROM churches WHERE country='AU' AND "
    "(state='ACT' OR city LIKE '%canberra%')"
)
all_rows = {r[0]: r for r in cur.fetchall()}
print(f'Canberra-area churches in DB: {len(all_rows)}')
print()

print('=== All existing Canberra church names ===')
for rid, r in sorted(all_rows.items(), key=lambda x: x[1][1]):
    print(f'  id={rid}  {r[1]}  ({r[2]})  [{r[3]}]')
print()

# Now check the heritage register entries
notable = [
    ('All Saints Church', 'Ainslie'),
    ('Canberra Baptist Church and Manse', 'Kingston'),
    ('Canberra Church of England Girls Grammar School - Boarding House', 'Deakin'),
    ('Canberra National Seventh Day Adventist Church', 'Turner'),
    ('Cuppacumbalong (De Salis) Cemetery', 'Tharwa'),
    ('Free Serbian Orthodox Church And Murals', 'Forrest'),
    ('Greek Orthodox Church', 'Kingston'),
    ('Holy Trinity Lutheran Church', 'Turner'),
    ('Sacred Heart Church', 'Calwell'),
    ("St Andrew's Church Precinct", 'Forrest'),
    ("St Christopher's Cathedral Precinct", 'Forrest'),
    ("St Edmund's Anglican Church", 'Tharwa'),
    ('St John the Baptist Church and Churchyard', 'Reid'),
    ("St Joseph's Catholic Church", "O'Connor"),
    ("St Ninian's Church", 'Lyneham'),
    ("St Paul's Church", 'Griffith'),
    ('Tharwa General Cemetery', 'Tharwa'),
    ('Ukranian Orthodox Church', 'Turner'),
    ('Uniting Church, Reid', 'Reid'),
    ('Weetangera Cemetery', 'Weetangera'),
    ('Woden Cemetery', 'Phillip'),
]

print('=== Heritage Register entries vs DB ===')
for name, suburb in notable:
    nlow = name.lower()
    # Search by individual key terms
    key_terms = [w for w in nlow.split() if w not in ('the','and','of','in','at','a','an','for','to','st','st.','-',
                'church','precinct','churchyard','&','school','boarding','house','girls','grammar') and len(w) > 3]

    matches = []
    for rid, r in all_rows.items():
        dbname = (r[1] or '').lower()
        common = [t for t in key_terms if t in dbname]
        if len(common) >= 2 or (len(common) >= 1 and len(key_terms) <= 2):
            matches.append((len(common), rid, r))

    if matches:
        matches.sort(key=lambda x: -x[0])
        best = matches[0]
        r = best[2]
        print(f'  EXISTS: {name} ({suburb})')
        print(f'           id={best[1]} db="{r[1]}" city={r[2]} type={r[3]}')
    else:
        print(f'  MISSING: {name} ({suburb})')

db.close()
