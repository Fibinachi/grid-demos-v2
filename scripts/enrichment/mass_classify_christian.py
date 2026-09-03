"""Mass classification of tax=2 (Christian) bucket by name patterns."""
import sqlite3, time

DB = "E:/grid/churches.db"
db = sqlite3.connect(DB)

# (pattern, target_tax, label)
UPDATES = [
    ("%Baptist%", 281, "Baptist"),
    ("%Methodist%", 380, "Methodist"),
    ("%Presbyterian%", 219, "Presbyterian"),
    ("%Lutheran%", 356, "Lutheran"),
    ("%Anglican%", 13, "Anglican"),
    ("%Orthodox%", 178, "Orthodox"),
    ("%Non-Denominational%", 388, "Non-Denominational"),
    ("%Pentecostal%", 218, "Pentecostal"),
    ("%Adventist%", 256, "Adventist"),
    ("%Apostolic%", 391, "Apostolic"),
    ("%Holiness%", 342, "Holiness"),
    ("%Nazarene%", 343, "Nazarene"),
    ("%Reformed%", 221, "Reformed"),
    ("%Mennonite%", 268, "Mennonite"),
    ("%Church of God%", 137, "Church of God"),
    ("%Church of Christ%", 321, "Church of Christ"),
    ("%Disciples of Christ%", 318, "Disciples of Christ"),
    ("%Assemblies of God%", 392, "Assemblies of God"),
    ("%Full Gospel%", 405, "Full Gospel"),
    ("%Congregational%", 315, "Congregational"),
    ("%Episcopal%", 13, "Episcopal→Anglican"),
    ("%RCCG%", 419, "RCCG"),
    ("%Redeemed Christian%", 419, "Redeemed Christian"),
    ("%Catholic%", 14, "Catholic"),
    ("%Evangelical%", 333, "Evangelical"),
    ("%Jehovah%", 399, "Jehovah"),
    ("%Christian Church%", 317, "Christian Church"),
    ("%United Reformed%", 221, "United Reformed"),
    ("%United Methodist%", 380, "United Methodist"),
    ("%AME%", 296, "AME"),
    ("%COGIC%", 393, "COGIC"),
    ("%Salvation Army%", 152, "Salvation Army"),
    ("%Quaker%", 310, "Quaker"),
    ("%Society of Friends%", 310, "Friends"),
    ("%Moravian%", 308, "Moravian"),
    ("%Wesleyan%", 345, "Wesleyan"),
    ("%Free Methodist%", 340, "Free Methodist"),
    ("%Calvary Chapel%", 332, "Calvary Chapel"),
    ("%Vineyard%", 331, "Vineyard"),
    ("%Foursquare%", 403, "Foursquare"),
    ("%Four Square%", 403, "Foursquare"),
    ("%Church of the Nazarene%", 343, "Nazarene"),
    ("%Brethren%", 320, "Brethren"),
    ("%Mennonite Brethren%", 268, "Mennonite Brethren"),
    ("%Iglesia Ni Cristo%", 423, "Iglesia ni Cristo"),
    ("%Uniting Church%", 317, "Uniting Church"),
    ("%United Church of Christ%", 316, "UCC"),
    ("%Coptic%", 86, "Coptic/Eastern Catholic"),
    ("%Seventh-day%", 256, "SDA"),
    ("%7th Day%", 256, "SDA"),
]

total = 0
for pattern, target_tax, label in UPDATES:
    t0 = time.time()
    before = db.total_changes
    db.execute(f"UPDATE churches SET taxonomy_id=?, last_updated=datetime('now') WHERE taxonomy_id=2 AND name LIKE ?", (target_tax, pattern))
    n = db.total_changes - before
    if n > 100:
        print(f"  {label}: {n:>8,} in {time.time()-t0:.1f}s")
    total += n

db.commit()
print(f"\nTotal reclassified from tax=2: {total:,}")

# Final count
r = db.execute("SELECT COUNT(1) FROM churches WHERE taxonomy_id=2").fetchone()[0]
print(f"tax=2 remaining: {r:,}")

db.close()
