"""Deep analysis of NULL-denom Christian records by source."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')

print("=== NULL DENOM CHRISTIAN BY SOURCE WITH SAMPLE NAMES ===")
sources = db.execute("""
    SELECT source, COUNT(*) as cnt 
    FROM churches 
    WHERE faith = 'Christian' AND (denomination IS NULL OR denomination = '')
    GROUP BY source ORDER BY cnt DESC
""").fetchall()

for src, cnt in sources:
    samples = db.execute("""
        SELECT name, landmark_type, country, faith_tradition 
        FROM churches 
        WHERE faith = 'Christian' AND (denomination IS NULL OR denomination = '')
        AND source = ? AND name IS NOT NULL AND name != ''
        LIMIT 5
    """, (src,)).fetchall()
    print(f"\n--- {src} ({cnt:,}) ---")
    for s in samples:
        print(f"  {str(s[0] or '')[:60]:60s} | {str(s[1] or ''):20s} | {s[2] or ''} | {s[3] or ''}")

print("\n\n=== EXISTING DENOMINATIONS THAT NEED CLEANUP ===")
# Check for inconsistent naming
pairs = [
    ("Roman Catholic", "Catholic"),
    ("Non-Denominational", "Non-Denominational / Independent"),
    ("Episcopal", "Episcopal Church"),
    ("Mormon/LDS", "LDS / Mormon"),
    ("Church of the Nazarene", "Nazarene"),
    ("Seventh-day Adventist Church", "Adventist"),
    ("United Methodist Church", "Methodist"),
    ("Southern Baptist Convention", "Baptist"),
    ("Assemblies of God", "Pentecostal"),
    ("Presbyterian Church (U.S.A.)", "Presbyterian"),
    ("Lutheran Church - Missouri Synod", "Lutheran"),
    ("Evangelical Lutheran Church in America", "Lutheran"),
    ("African Methodist Episcopal Church", "AME"),
    ("Wesleyan Church", "Wesleyan"),
    ("Anglican Church in North America", "Anglican"),
    ("Church of the Nazarene", "Nazarene"),
]
for a, b in pairs:
    ca = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND denomination=?", (a,)).fetchone()[0]
    cb = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND denomination=?", (b,)).fetchone()[0]
    print(f"  {a}: {ca:,}  vs  {b}: {cb:,}")

print("\n\n=== NULL FAITH_TRADITION BUT CHRISTIAN FAITH ===")
c = db.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith = 'Christian' AND (faith_tradition IS NULL OR faith_tradition = '')
""")
print(f"  {c.fetchone()[0]:,}")

print("\n=== NULL FAITH_TRADITION BY SOURCE ===")
c = db.execute("""
    SELECT source, COUNT(*) as cnt 
    FROM churches 
    WHERE faith = 'Christian' AND (faith_tradition IS NULL OR faith_tradition = '')
    GROUP BY source ORDER BY cnt DESC LIMIT 15
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== CHRISTIAN NAME PATTERNS THAT CAN INFER DENOM ===")
# Check common name patterns that indicate specific denominations
patterns = [
    ("%Catholic%", "Catholic"),
    ("%Roman Catholic%", "Catholic"),
    ("%Baptist%", "Baptist"),
    ("%Methodist%", "Methodist"),
    ("%United Methodist%", "Methodist"),
    ("%Lutheran%", "Lutheran"),
    ("%Presbyterian%", "Presbyterian"),
    ("%Anglican%", "Anglican"),
    ("%Episcopal%", "Anglican/Episcopal"),
    ("%Orthodox%", "Orthodox"),
    ("%Pentecostal%", "Pentecostal"),
    ("%Assemblies of God%", "Pentecostal"),
    ("%Evangelical%", "Evangelical"),
    ("%Non-Denominational%", "Non-Denominational"),
    ("%Salvation Army%", "Salvation Army"),
    ("%Seventh.day%", "Adventist"),
    ("%Nazarene%", "Nazarene"),
    ("%Wesleyan%", "Wesleyan"),
    ("%Mennonite%", "Anabaptist"),
    ("%Brethren%", "Anabaptist"),
    ("%Church of Christ%", "Churches of Christ"),
    ("%Church of God%", "Church of God"),
    ("%Jehovah%", "Jehovah's Witnesses"),
    ("%Mormon%", "LDS"),
    ("%LDS%", "LDS"),
    ("%Quaker%", "Quaker"),
    ("%Congregational%", "Congregational"),
    ("%United Church of Christ%", "Congregational"),
    ("%Christian Church%", "Christian Church"),
    ("%Disciples of Christ%", "Disciples of Christ"),
    ("%Holiness%", "Holiness"),
    ("%AME %", "AME"),
    ("%AME.%", "AME"),
    ("%African Methodist%", "AME"),
    ("%CME %", "CME"),
    ("%Christian Methodist%", "CME"),
    ("%COGIC%", "COGIC"),
    ("%Foursquare%", "Foursquare"),
    ("%Calvary Chapel%", "Calvary Chapel"),
    ("%Vineyard%", "Vineyard"),
    ("%Mennonite%", "Anabaptist"),
]
for pat, label in patterns:
    cnt = db.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE faith = 'Christian' AND (denomination IS NULL OR denomination = '')
        AND UPPER(name) LIKE ?
    """, (pat.upper(),)).fetchone()[0]
    if cnt > 0:
        print(f"  {label:25s}: {cnt:>8,}  (pattern: {pat})")

db.close()
