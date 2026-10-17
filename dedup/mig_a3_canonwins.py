"""A3: canonical-wins reconciliation. For status='merged' rows, copy the six
classification columns from the terminal canonical. Only rows where at
least one column disagrees are touched. Old values are printed for
rollback capture."""
import sqlite3

COLS = ["taxonomy_id", "movement_id", "tradition_id",
        "legacy_id", "faith_id", "culture_id"]

db = sqlite3.connect(r"E:\grid\churches.db")

print("pre-change disagreements vs canonical:")
total = 0
for c in COLS:
    n = db.execute(
        "SELECT COUNT(*) FROM churches m JOIN churches t ON t.id=m.dedup_canonical_id "
        "WHERE m.status='merged' AND m.%s IS NOT t.%s" % (c, c)).fetchone()[0]
    print("  %s: %s" % (c, "{:,}".format(n)))

# rows needing change + their old values
sel = ("SELECT m.id," + ",".join("m.%s" % c for c in COLS) +
       " FROM churches m JOIN churches t ON t.id=m.dedup_canonical_id "
       "WHERE m.status='merged' AND (" +
       " OR ".join("m.%s IS NOT t.%s" % (c, c) for c in COLS) + ")")
rows = db.execute(sel).fetchall()
print("rows to update:", "{:,}".format(len(rows)))
print("OLDVALS-BEGIN")
for r in rows:
    print("%d|%s" % (r[0], "|".join("" if v is None else str(v) for v in r[1:])))
print("OLDVALS-END")

db.execute("BEGIN")
cur = db.execute(
    "UPDATE churches AS m SET "
    "taxonomy_id=t.taxonomy_id, movement_id=t.movement_id, tradition_id=t.tradition_id, "
    "legacy_id=t.legacy_id, faith_id=t.faith_id, culture_id=t.culture_id "
    "FROM churches AS t WHERE m.status='merged' AND t.id=m.dedup_canonical_id AND ("
    + " OR ".join("m.%s IS NOT t.%s" % (c, c) for c in COLS) + ")")
print("updated:", "{:,}".format(cur.rowcount))

left = 0
for c in COLS:
    left += db.execute(
        "SELECT COUNT(*) FROM churches m JOIN churches t ON t.id=m.dedup_canonical_id "
        "WHERE m.status='merged' AND m.%s IS NOT t.%s" % (c, c)).fetchone()[0]
print("post disagreements:", left)
if left == 0 and cur.rowcount == len(rows):
    db.execute("COMMIT")
    print("COMMITTED")
else:
    db.execute("ROLLBACK")
    print("ROLLED BACK")
db.close()
