"""A1: clear dedup self-loops. Rows with status='merged' whose
dedup_canonical_id points to themselves are treated as canonicals:
status -> NULL, dedup_canonical_id -> NULL."""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
pre = db.execute(
    "SELECT COUNT(*) FROM churches WHERE status='merged' AND dedup_canonical_id=id"
).fetchone()[0]
print("pre self-loops:", pre)
db.execute("BEGIN")
cur = db.execute(
    "UPDATE churches SET status=NULL, dedup_canonical_id=NULL "
    "WHERE status='merged' AND dedup_canonical_id=id"
)
print("updated:", cur.rowcount)
post = db.execute(
    "SELECT COUNT(*) FROM churches WHERE status='merged' AND dedup_canonical_id=id"
).fetchone()[0]
null_ptr = db.execute(
    "SELECT COUNT(*) FROM churches WHERE status='merged' AND dedup_canonical_id IS NULL"
).fetchone()[0]
print("post self-loops:", post, "| merged with NULL ptr:", null_ptr)
if post == 0 and null_ptr == 0 and cur.rowcount == pre:
    db.execute("COMMIT")
    print("COMMITTED")
else:
    db.execute("ROLLBACK")
    print("ROLLED BACK")
db.close()
