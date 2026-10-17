"""A2b: break dedup 2-cycles. For each mutual pair (A->B, B->A), the row
with more non-null columns (tie: lower id) becomes the canonical:
status -> NULL, dedup_canonical_id -> NULL. The loser keeps pointing at
the winner."""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
ptr = dict(db.execute(
    "SELECT id, dedup_canonical_id FROM churches "
    "WHERE status='merged' AND dedup_canonical_id IS NOT NULL").fetchall())
merged_ids = set(ptr)
pairs = set()
for rid, tgt in ptr.items():
    if tgt in merged_ids and ptr.get(tgt) == rid and rid < tgt:
        pairs.add((rid, tgt))
print("2-cycle pairs:", len(pairs))

stray = db.execute(
    "SELECT COUNT(*) FROM churches WHERE (status IS NULL OR status!='merged') "
    "AND dedup_canonical_id IS NOT NULL").fetchone()[0]
print("non-merged rows with pointers:", stray)

def nonnull(rid):
    row = db.execute("SELECT * FROM churches WHERE id=?", (rid,)).fetchone()
    return sum(1 for v in row if v is not None)

fixed = []
db.execute("BEGIN")
for a, b in sorted(pairs):
    na, nb = nonnull(a), nonnull(b)
    winner, loser = (b, a) if nb > na else (a, b)
    cur = db.execute(
        "SELECT dedup_canonical_id FROM churches WHERE id=?", (winner,)).fetchone()[0]
    assert cur == loser, (winner, loser, cur)
    db.execute("UPDATE churches SET status=NULL, dedup_canonical_id=NULL WHERE id=?",
               (winner,))
    fixed.append((winner, loser, na if winner == a else nb))

# verify no cycles remain
ptr2 = dict(db.execute(
    "SELECT id, dedup_canonical_id FROM churches "
    "WHERE status='merged' AND dedup_canonical_id IS NOT NULL").fetchall())
m2 = set(ptr2)
cycles = 0
for rid in ptr2:
    seen = set(); cur = rid
    while cur in m2:
        if cur in seen:
            cycles += 1
            break
        seen.add(cur)
        cur = ptr2[cur]
print("winners:", [(w, l) for w, l, _ in fixed])
print("remaining cyclic rows:", cycles)
if cycles == 0:
    db.execute("COMMIT")
    print("COMMITTED")
else:
    db.execute("ROLLBACK")
    print("ROLLED BACK")
print("ROLLBACKS:")
for w, l, _ in fixed:
    print("UPDATE churches SET status='merged', dedup_canonical_id=%d WHERE id=%d;" % (l, w))
db.close()
