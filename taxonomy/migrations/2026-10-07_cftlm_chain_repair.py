"""
GRID CFTLM chain repair migration 2026-10-07.

Enforces Charles's intended invariant: each church carries one value per
rank (culture/faith/legacy/tradition/movement), and each rank is derived
from the next-deeper rank's parent chain. The deepest non-null rank on a
church is authoritative; all shallower ranks are recomputed from it.

Pre-migration violations observed 2026-10-07:
  movement->tradition: 3,660 | tradition->legacy: 475,453
  legacy->faith: 2,084      | faith->culture: 18,629

Rank tables themselves have a few dangling parent refs (5 movements,
15 traditions, 3 legacies); LEFT JOINs keep those churches' ancestors
NULL rather than dropping them. Affected churches are reported.

Rollback: restore the pre-migration backup
  E:\\grid\\backups\\churches_pre_cftlm_repair_<ts>.db
"""

import sqlite3
import sys

DB = r"E:\grid\churches.db"

PASSES = [
    ("movement holders (deepest=movement)", """
        UPDATE churches AS c SET
          tradition_id = m.tradition_id,
          legacy_id    = t.legacy_id,
          faith_id     = l.faith_id,
          culture_id   = f.culture_id
        FROM movement m
        LEFT JOIN tradition t ON t.id = m.tradition_id
        LEFT JOIN legacy    l ON l.id = t.legacy_id
        LEFT JOIN faith     f ON f.id = l.faith_id
        WHERE c.movement_id = m.id
    """),
    ("tradition holders (deepest=tradition)", """
        UPDATE churches AS c SET
          legacy_id    = t.legacy_id,
          faith_id     = l.faith_id,
          culture_id   = f.culture_id
        FROM tradition t
        LEFT JOIN legacy l ON l.id = t.legacy_id
        LEFT JOIN faith  f ON f.id = l.faith_id
        WHERE c.tradition_id = t.id AND c.movement_id IS NULL
    """),
    ("legacy holders (deepest=legacy)", """
        UPDATE churches AS c SET
          faith_id   = l.faith_id,
          culture_id = f.culture_id
        FROM legacy l
        LEFT JOIN faith f ON f.id = l.faith_id
        WHERE c.legacy_id = l.id
          AND c.movement_id IS NULL AND c.tradition_id IS NULL
    """),
    ("faith holders (deepest=faith)", """
        UPDATE churches AS c SET
          culture_id = f.culture_id
        FROM faith f
        WHERE c.faith_id = f.id
          AND c.movement_id IS NULL AND c.tradition_id IS NULL
          AND c.legacy_id IS NULL
    """),
]

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
    db = sqlite3.connect(DB)
    try:
        db.execute("BEGIN")
        for name, sql in PASSES:
            cur = db.execute(sql)
            print("pass [%s]: %s rows processed" % (name, "{:,}".format(cur.rowcount)))
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise

    print("verification (expect all 0):")
    ok = True
    for name, q in VERIFY:
        n = db.execute(q).fetchone()[0]
        print("  %s violations: %s" % (name, "{:,}".format(n)))
        ok = ok and n == 0

    # Churches whose deepest rank dangles (ancestors unresolvable)
    dangle = db.execute(
        "SELECT COUNT(*) FROM churches c JOIN movement m ON m.id=c.movement_id "
        "LEFT JOIN tradition t ON t.id=m.tradition_id WHERE t.id IS NULL"
    ).fetchone()[0]
    print("churches with dangling movement->tradition ref:", "{:,}".format(dangle))
    db.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
