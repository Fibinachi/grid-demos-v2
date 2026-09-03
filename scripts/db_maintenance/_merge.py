import sqlite3

stag = sqlite3.connect("E:/grid/jp_shrines.db")
rows = stag.execute("SELECT name, lat, lon, qid FROM shrines").fetchall()
stag.close()

main = sqlite3.connect("E:/grid/churches.db")
main.execute("PRAGMA journal_mode=WAL")
grid = set(main.execute(
    "SELECT ROUND(lat,2), ROUND(lon,2) FROM holy_sites WHERE lat IS NOT NULL"
).fetchall())

new = []
for n, la, lo, q in rows:
    g = (round(la, 2), round(lo, 2))
    if g not in grid:
        new.append((n, "Shinto", None, "JP", la, lo,
                    "wikidata", None, 1, "shrine", q, None, 0.5, None))
        grid.add(g)

print("Staged: {:,}  New: {:,}".format(len(rows), len(new)))

main.execute("BEGIN IMMEDIATE")
main.executemany(
    "INSERT OR IGNORE INTO holy_sites "
    "(name,faith,tradition,country,lat,lon,"
    "source_primary,source_secondary,is_landmark,landmark_type,"
    "wikidata_qid,osm_id,confidence_score,website) "
    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", new)
main.commit()

total = main.execute("SELECT COUNT(*) FROM holy_sites").fetchone()[0]
shinto = main.execute("SELECT COUNT(*) FROM holy_sites WHERE faith='Shinto'").fetchone()[0]
jp_s = main.execute("SELECT COUNT(*) FROM holy_sites WHERE faith='Shinto' AND country='JP'").fetchone()[0]
main.close()

print("holy_sites: {:,}  Shinto: {:,}  Japan Shinto: {:,}".format(total, shinto, jp_s))
