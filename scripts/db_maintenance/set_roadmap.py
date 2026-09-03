"""Set up version roadmap."""
import sqlite3, json
from datetime import datetime

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Drop and recreate with nullable version_date
c.execute("DROP TABLE IF EXISTS db_version")
c.execute("""
    CREATE TABLE db_version (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT NOT NULL,
        version_date TEXT,
        status TEXT NOT NULL DEFAULT 'planned',
        description TEXT,
        total_records INTEGER,
        jewish_records INTEGER,
        faith_breakdown TEXT,
        changes_summary TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")

now = datetime.now().isoformat()
roadmap = [
    ('1.0-rc', now, 'release-candidate', 'US + global Jewish cleanup (~24K sites). DeepSeek-assisted classification, name transliteration, facility type taxonomy. Includes Jain (~150) and Confucian (~110) cleanup.'),
    ('1.0', None, 'release', 'US state-by-state sweep complete. Jewish classification finalized. Jain + Confucian included.'),
    ('1.1', None, 'planned', 'European Judaism update — review and reclassify European Jewish entries.'),
    ('1.2', None, 'planned', 'Sikh faith cleanup — review and reclassify ~6K Sikh entries.'),
    ('1.3', None, 'planned', 'Taoist faith cleanup — review and reclassify ~12K Taoist entries.'),
    ('1.4', None, 'planned', 'Shinto faith cleanup — review and reclassify ~65K Shinto entries.'),
    ('1.5', None, 'planned', 'Other faiths cleanup — umbrella (~110K entries).'),
    ('1.5.1', None, 'planned', 'Other — Pagan / Neo-Pagan (Wicca, Druid, Heathen, etc.).'),
    ('1.5.2', None, 'planned', 'Other — Bahai faith entries.'),
    ('1.5.3', None, 'planned', 'Other — African Traditional / Diasporic (Candomble, Santeria, Vodou).'),
    ('1.5.4', None, 'planned', 'Other — Zoroastrian / Parsi entries.'),
    ('1.5.5', None, 'planned', 'Other — Unitarian / Universalist / Ethical Culture.'),
    ('1.5.6', None, 'planned', 'Other — Remaining misc (Animist, Syncretic, New Religious Movements).'),
    ('1.6', None, 'planned', 'Buddhist faith cleanup — ~203K entries, done by region.'),
    ('1.7', None, 'planned', 'Hindu faith cleanup — ~188K entries, complex versioning.'),
    ('1.8', None, 'planned', 'Islam faith cleanup — ~357K entries, done by region.'),
    ('1.8.1', None, 'planned', 'Islam — Middle East / North Africa region.'),
    ('1.8.2', None, 'planned', 'Islam — Sub-Saharan Africa region.'),
    ('1.8.3', None, 'planned', 'Islam — South / Southeast Asia region.'),
    ('1.8.4', None, 'planned', 'Islam — Central Asia / Caucasus region.'),
    ('1.10', None, 'planned', 'Christianity cleanup — ~2.4M entries, largest faith, done by tradition.'),
    ('1.10.1', None, 'planned', 'Christianity — Catholic world (dioceses, parishes, shrines).'),
    ('1.10.2', None, 'planned', 'Christianity — Orthodox world (Patriarchates, metropolitans).'),
    ('1.10.3', None, 'planned', 'Christianity — Protestant world (mainline denominations).'),
    ('1.10.4', None, 'planned', 'Christianity — Non-denominational / Evangelical movements.'),
    ('1.10.5', None, 'planned', 'Christianity — Latter-day Saint / Restorationist movements.'),
    ('1.10.6', None, 'planned', 'Christianity — Minor traditions (Coptic, Armenian, Assyrian, etc.).'),
    ('2.0', None, 'planned', 'Cumulative update across all faiths + global census data integration.'),
]

for ver, date, status, desc in roadmap:
    c.execute("INSERT INTO db_version (version, version_date, status, description) VALUES (?, ?, ?, ?)",
              (ver, date, status, desc))

conn.commit()

print("=== GRID Version Roadmap ===\n")
c.execute("SELECT version, status, description FROM db_version ORDER BY id")
for r in c.fetchall():
    icons = {'release': '✅', 'release-candidate': '🔶', 'planned': '⬜'}
    print(f"  {icons.get(r[1], ' ')} {r[0]:8s} [{r[1]:16s}] {r[2]}")

conn.close()
