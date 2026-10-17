"""A2: flatten dedup chains. Every merged row's dedup_canonical_id is
rewritten to the terminal canonical (first target that is not itself a
merged row with a pointer). Cycles / non-terminating chains are reported
and left untouched."""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
rows = db.execute(
    "SELECT id, dedup_canonical_id FROM churches "
    "WHERE status='merged' AND dedup_canonical_id IS NOT NULL"
).fetchall()
ptr = dict(rows)
print("merged rows with pointer:", len(ptr))
dangling = db.execute(
    "SELECT COUNT(*) FROM churches c LEFT JOIN churches t ON t.id=c.dedup_canonical_id "
    "WHERE c.status='merged' AND c.dedup_canonical_id IS NOT NULL AND t.id IS NULL"
).fetchone()[0]
print("dangling pointers:", dangling)

# target id -> is it a merged row with a pointer?
merged_ids = set(ptr.keys())

def terminal(start):
    seen = set()
    cur = start
    while True:
        nxt = ptr.get(cur)
        if nxt is None:
            return ("dangling", cur)  # target row not merged (or missing)
        if nxt in seen or nxt == cur:
            return ("cycle", cur)
        seen.add(cur)
        if nxt not in merged_ids:
            return ("ok", nxt)  # terminal canonical
        cur = nxt

updates = []
old_ptrs = []
cycles = 0
for rid, p in ptr.items():
    kind, term = terminal(rid)
    if kind == "cycle":
        cycles += 1
    elif kind == "ok" and term != p:
        updates.append((term, rid))
        old_ptrs.append("%d:%d" % (rid, p))

print("chains needing flatten:", len(updates), "| cycles:", cycles)
print("OLDPTRS:" + ",".join(old_ptrs))
db.execute("BEGIN")
db.executemany(
    "UPDATE churches SET dedup_canonical_id=? WHERE id=?", updates
)
# verify: no merged row should point at another merged row with a pointer
left = db.execute(
    "SELECT COUNT(*) FROM churches c JOIN churches t ON t.id=c.dedup_canonical_id "
    "WHERE c.status='merged' AND t.status='merged' AND t.dedup_canonical_id IS NOT NULL"
).fetchone()[0]
print("remaining chained pointers:", left)
if left == 0 and cycles == 0 and dangling == 0:
    db.execute("COMMIT")
    print("COMMITTED")
else:
    db.execute("ROLLBACK")
    print("ROLLED BACK - investigate")
db.close()
