"""
GRID taxonomy migration 2026-10-07
Move Methodist (215), Adventist (207), Holiness (213) from Protestant (19)
to Post-Protestant (212).

Approved by Charles 2026-10-07 22:43 EDT.
Scope: 3 roots, 33 nodes total (incl. descendants), ~108,487 churches in subtrees.

Deliberate non-changes (per 2026-10-07 audit, structural columns carry
legacy faith-relative semantics and must not be blindly recalculated):
  - depth: unchanged. Roots stay at depth 2, matching the destination
    siblings Evangelical (333) and Pentecostal (218).
  - root_id: unchanged (2 = Christian for all).
  - family_id: unchanged. Subtrees of 215/207/213 carry family_id=19
    (Protestant family), exactly like the Evangelical and Pentecostal
    subtrees already under Post-Protestant.

Only parent_id and full_path change.

Rollback: restore from the pre-migration backup
  E:\\grid\\backups\\churches_pre_taxonomy_move_<ts>.db
or run ROLLBACK_SQL below.
"""

import sqlite3
import sys

DB = r"E:\grid\churches.db"
MOVED = (215, 207, 213)
OLD_PARENT = 19
NEW_PARENT = 212
OLD_PREFIX = "Abrahamic/Christian/Protestant/"
NEW_PREFIX = "Abrahamic/Christian/Post-Protestant/"

ROLLBACK_SQL = """
-- ROLLBACK for 2026-10-07 move (run inside a transaction)
UPDATE taxonomy SET parent_id = 19 WHERE id IN (215, 207, 213);
UPDATE taxonomy
SET full_path = REPLACE(full_path,
    'Abrahamic/Christian/Post-Protestant/',
    'Abrahamic/Christian/Protestant/')
WHERE full_path LIKE 'Abrahamic/Christian/Post-Protestant/%';
"""


def subtree_ids(db, roots):
    kids = {}
    for nid, pid in db.execute("SELECT id, parent_id FROM taxonomy"):
        kids.setdefault(pid, []).append(nid)
    out = []
    stack = list(roots)
    while stack:
        n = stack.pop()
        out.append(n)
        stack.extend(kids.get(n, []))
    return out


def main():
    db = sqlite3.connect(DB)
    try:
        ids = subtree_ids(db, MOVED)

        # Pre-flight: confirm all three roots are still under Protestant
        cur = db.execute(
            "SELECT id, parent_id FROM taxonomy WHERE id IN (215,207,213)"
        ).fetchall()
        assert all(p == OLD_PARENT for _, p in cur), \
            "precondition failed: a root is no longer under Protestant: %r" % (cur,)

        # Pre-flight: all subtree paths must carry the old prefix
        bad = db.execute(
            "SELECT id, full_path FROM taxonomy WHERE id IN (%s)"
            % ",".join("?" * len(ids)),
            ids,
        ).fetchall()
        bad = [r for r in bad if not (r[1] or "").startswith(OLD_PREFIX)]
        assert not bad, "precondition failed: off-prefix paths: %r" % (bad,)

        db.execute("BEGIN")
        db.execute(
            "UPDATE taxonomy SET parent_id = ? WHERE id IN (?,?,?)",
            (NEW_PARENT, *MOVED),
        )
        cur = db.execute(
            "UPDATE taxonomy SET full_path = REPLACE(full_path, ?, ?) "
            "WHERE full_path LIKE ? || '%%' AND id IN (%s)"
            % ",".join("?" * len(ids)),
            (OLD_PREFIX, NEW_PREFIX, OLD_PREFIX, *ids),
        )
        n_paths = cur.rowcount
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    finally:
        db.close()

    print("moved roots: 3, subtree nodes repathed: %d" % n_paths)
    print("ROLLBACK_SQL:")
    print(ROLLBACK_SQL)


if __name__ == "__main__":
    main()
