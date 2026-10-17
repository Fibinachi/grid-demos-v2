"""B5: mechanical taxonomy node merges.
(loser -> survivor): (230->487), (224->490), (395->396),
(169->166), (171->166), (172->166).
For each: repoint churches, reparent loser children (prefix-swap paths),
delete loser, log provenance. Prints rollback SQL."""
import sqlite3
from datetime import datetime

MERGES = [(230, 487), (224, 490), (395, 396), (169, 166), (171, 166), (172, 166)]
TAXCOLS = ["id", "parent_id", "name", "full_path", "depth",
           "root_id", "tradition_id", "family_id"]

def esc(s):
    return "NULL" if s is None else "'%s'" % s.replace("'", "''")

def q(v):
    return "NULL" if v is None else str(v)

db = sqlite3.connect(r"E:\grid\churches.db")
kids = {}
for nid, pid in db.execute("SELECT id, parent_id FROM taxonomy"):
    kids.setdefault(pid, []).append(nid)

def subtree_ids(nid):
    out = []; stack = [nid]
    while stack:
        n = stack.pop(); out.append(n)
        stack.extend(kids.get(n, []))
    return out

rollbacks = []
db.execute("BEGIN")
for loser, surv in MERGES:
    lrow = db.execute("SELECT * FROM taxonomy WHERE id=?", (loser,)).fetchone()
    srow = db.execute("SELECT id, name, parent_id FROM taxonomy WHERE id=?", (surv,)).fetchone()
    assert lrow is not None, "loser missing: %d" % loser
    assert srow is not None, "survivor missing: %d" % surv
    ld = dict(zip(TAXCOLS, lrow))
    spath = db.execute("SELECT full_path FROM taxonomy WHERE id=?", (surv,)).fetchone()[0]
    # churches
    ch = [r[0] for r in db.execute(
        "SELECT id FROM churches WHERE taxonomy_id=?", (loser,))]
    db.execute("UPDATE churches SET taxonomy_id=? WHERE taxonomy_id=?", (surv, loser))
    # children reparent + repath
    moved = []
    for c in kids.get(loser, []):
        oldp = db.execute("SELECT full_path FROM taxonomy WHERE id=?", (c,)).fetchone()[0]
        newp = spath + oldp[len(ld["full_path"]):]
        db.execute("UPDATE taxonomy SET parent_id=?, full_path=? WHERE id=?",
                   (surv, newp, c))
        moved.append((c, oldp))
    db.execute("DELETE FROM taxonomy WHERE id=?", (loser,))
    print("merge %d '%s' -> %d '%s': churches repointed=%d, children moved=%d" % (
        loser, ld["name"], surv, srow[1], len(ch), len(moved)))
    # rollback (reverse order not needed; independent)
    rb = ["-- rollback merge %d -> %d" % (loser, surv),
          "INSERT INTO taxonomy (%s) VALUES (%s);" % (
              ",".join(TAXCOLS),
              ",".join(q(ld[c]) if c != "name" and c != "full_path"
                        else esc(ld[c]) for c in TAXCOLS))]
    if ch:
        rb.append("UPDATE churches SET taxonomy_id=%d WHERE id IN (%s);" % (
            loser, ",".join(map(str, ch))))
    for c, oldp in moved:
        rb.append("UPDATE taxonomy SET parent_id=%d, full_path='%s' WHERE id=%d;" % (
            loser, oldp.replace("'", "''"), c))
    rollbacks.extend(rb)

# provenance log row
db.execute(
    "INSERT INTO provenance_log (source, script_name, started_at, completed_at, "
    "churches_updated, status, notes) VALUES (?,?,?,?,?,?,?)",
    ("taxonomy", "dedup_b5_taxonomy_merges", datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
     datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 4, "completed",
     "Mechanical dedup merges 2026-10-07: Zaydi 230->487; Ibadhi 224->Ibadi 490; "
     "Church of God (Cleveland) 395->396; LDS aliases 169,171,172->166. "
     "Rollback SQL: ~/workspace/grid/dedup/dedup-rollback-2026-10-07.sql"))

# verify
ok = True
for loser, surv in MERGES:
    gone = db.execute("SELECT COUNT(*) FROM taxonomy WHERE id=?", (loser,)).fetchone()[0]
    left = db.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=?", (loser,)).fetchone()[0]
    orph = db.execute("SELECT COUNT(*) FROM taxonomy t LEFT JOIN taxonomy p ON p.id=t.parent_id "
                      "WHERE t.parent_id IS NOT NULL AND p.id IS NULL").fetchone()[0]
    print("verify loser %d: node gone=%s, churches left=%d, total orphans=%d" % (
        loser, gone == 0, left, orph))
    ok = ok and gone == 0 and left == 0
if ok:
    db.execute("COMMIT")
    print("COMMITTED")
else:
    db.execute("ROLLBACK")
    print("ROLLED BACK")
print("ROLLBACKS-BEGIN")
for rb in rollbacks:
    print(rb)
print("ROLLBACKS-END")
db.close()
