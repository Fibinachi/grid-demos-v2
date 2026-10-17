"""
CFTLM chain repair v2, 2026-10-07.

v1 left 780 violations: 1,811 churches carry movement_id values (130, 210)
that don't exist in movement (they're tradition ids leaked into the
column; all 1,811 already have the same value in tradition_id, so nulling
is lossless), and 361 carry tradition_id values from other tables'
id spaces. Dangling FKs blocked v1's passes (inner joins skip them).

v2: (A) null dangling movement_id/tradition_id; (B) re-run v1's four
derivation passes; (C) verify zero violations.

Flagged, not touched: faith row 614 'Scientology' is junk (a faith-table
duplicate of taxonomy 614); needs Charles's call to delete.
"""

import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"E:\grid\churches.db"

PASSES = [
    ("movement", """
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
    ("tradition", """
        UPDATE churches AS c SET
          legacy_id    = t.legacy_id,
          faith_id     = l.faith_id,
          culture_id   = f.culture_id
        FROM tradition t
        LEFT JOIN legacy l ON l.id = t.legacy_id
        LEFT JOIN faith  f ON f.id = l.faith_id
        WHERE c.tradition_id = t.id AND c.movement_id IS NULL
    """),
    ("legacy", """
        UPDATE churches AS c SET
          faith_id   = l.faith_id,
          culture_id = f.culture_id
        FROM legacy l
        LEFT JOIN faith f ON f.id = l.faith_id
        WHERE c.legacy_id = l.id
          AND c.movement_id IS NULL AND c.tradition_id IS NULL
    """),
    ("faith", """
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
    db = sqlite3.connect(DB, timeout=120)
    db.execute("BEGIN IMMEDIATE")
    try:
        n1 = db.execute(
            "UPDATE churches SET movement_id=NULL WHERE movement_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM movement m WHERE m.id=movement_id)"
        ).rowcount
        n2 = db.execute(
            "UPDATE churches SET tradition_id=NULL WHERE tradition_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM tradition t WHERE t.id=tradition_id)"
        ).rowcount
        print("nulled dangling movement_id:", n1, "| tradition_id:", n2)
        for name, sql in PASSES:
            n = db.execute(sql).rowcount
            print("pass [%s]: %s rows" % (name, "{:,}".format(n)))
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    ok = True
    for name, q in VERIFY:
        n = db.execute(q).fetchone()[0]
        print("  %s violations: %s" % (name, "{:,}".format(n)))
        ok = ok and n == 0
    for col, tbl in [("movement_id", "movement"), ("tradition_id", "tradition")]:
        n = db.execute(
            "SELECT COUNT(*) FROM churches WHERE %s IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM %s t WHERE t.id=%s)" % (col, tbl, col)).fetchone()[0]
        print("  dangling %s: %s" % (col, n))
        ok = ok and n == 0
    db.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
