"""
Delete junk faith row 614 'Scientology' (2026-10-08).

Approved by Charles 2026-10-08: "Yes, repair the 330 and delete the row."

Discrepancy found pre-execution: faith 614 is referenced by 330 churches,
none of them Scientology (fallout from the Pleiades misclassification and
canonical-wins propagation). Deleting the row alone would leave 330 dangling
faith_ids, so the repair recomputes them first:

  - 222 churches, taxonomy_id IS NULL -> faith_id=NULL, culture_id=NULL
    (dataset convention: 1,144,151 NULL-taxonomy/NULL-faith churches all
    have NULL culture)
  - 108 churches with taxonomy set -> faith_id/culture_id derived from the
    taxonomy chain: walk up from taxonomy_id to the first ancestor whose
    name exactly matches a faith row name; take that faith row's id and its
    culture_id. Fails loudly on no-match or ambiguous match.

Then DELETE FROM faith WHERE id=614, and re-run the v2 chain verifications.

ROLLBACK (all 330 pre-change rows had faith_id=614, culture_id=560):
  UPDATE churches SET faith_id=614, culture_id=560
    WHERE faith_id IS NULL AND culture_id IS NULL
       OR (faith_id IN (2,52));  -- narrow by id list in practice
  INSERT INTO faith (id, name, culture_id, description)
    VALUES (614, 'Scientology', 560, NULL);
"""

import io
import sqlite3
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"E:\grid\churches.db"

VERIFY = [
    ("movement->tradition",
     "SELECT COUNT(*) FROM churches c JOIN movement m ON m.id=c.movement_id "
     "WHERE c.tradition_id IS NOT NULL AND m.tradition_id != c.tradition_id"),
    ("tradition->legacy",
     "SELECT COUNT(*) FROM churches c JOIN tradition t ON t.id=c.tradition_id "
     "WHERE c.legacy_id IS NOT NULL AND t.legacy_id != c.legacy_id"),
    ("legacy->faith",
     "SELECT COUNT(*) FROM churches c JOIN legacy l ON l.id=c.legacy_id "
     "WHERE c.faith_id IS NOT NULL AND l.faith_id != c.faith_id"),
    ("faith->culture",
     "SELECT COUNT(*) FROM churches c JOIN faith f ON f.id=c.faith_id "
     "WHERE c.culture_id IS NOT NULL AND f.culture_id != c.culture_id"),
]


def main():
    db = sqlite3.connect(DB, timeout=120)
    faith_by_name = {}
    for fid, name, cult in db.execute("SELECT id, name, culture_id FROM faith"):
        if name == "Scientology":
            continue
        if name in faith_by_name:
            raise RuntimeError("duplicate faith name: %r" % name)
        faith_by_name[name] = (fid, cult)

    rows = db.execute(
        "SELECT id, taxonomy_id FROM churches WHERE faith_id=614").fetchall()
    print("churches with faith_id=614:", len(rows))
    assert len(rows) == 330, "expected 330, found %d" % len(rows)

    targets = {}
    for cid, tid in rows:
        if tid is None:
            targets[cid] = (None, None)
            continue
        cur, seen = tid, set()
        hit = None
        while cur and cur not in seen:
            seen.add(cur)
            r = db.execute(
                "SELECT name, parent_id FROM taxonomy WHERE id=?",
                (cur,)).fetchone()
            if not r:
                break
            if r[0] in faith_by_name:
                hit = faith_by_name[r[0]]
                break
            cur = r[1]
        if hit is None:
            raise RuntimeError(
                "no faith-level ancestor for church %s taxonomy %s"
                % (cid, tid))
        targets[cid] = hit

    dist = Counter(targets.values())
    print("target distribution (faith_id, culture_id):", dict(dist))
    assert set(dist) <= {(None, None), (2, 555), (52, 6)}, \
        "unexpected targets: %s" % set(dist)

    db.execute("BEGIN IMMEDIATE")
    try:
        for cid, (f, c) in targets.items():
            db.execute(
                "UPDATE churches SET faith_id=?, culture_id=? WHERE id=?",
                (f, c, cid))
        n = db.execute("DELETE FROM faith WHERE id=614").rowcount
        print("deleted faith rows:", n)
        assert n == 1
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise

    ok = True
    n = db.execute(
        "SELECT COUNT(*) FROM churches WHERE faith_id=614").fetchone()[0]
    print("churches still referencing faith 614:", n)
    ok = ok and n == 0
    n = db.execute("SELECT COUNT(*) FROM faith WHERE id=614").fetchone()[0]
    print("faith row 614 remaining:", n)
    ok = ok and n == 0
    for name, q in VERIFY:
        n = db.execute(q).fetchone()[0]
        print("  %s violations: %s" % (name, "{:,}".format(n)))
        ok = ok and n == 0
    db.close()
    print("RESULT:", "OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
