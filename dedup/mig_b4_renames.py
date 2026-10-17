"""B4: rename X-under-X generic child nodes to 'X (unspecified)'.
Skips 353 (Lutheran) and 412 (Pentecostal): '(unspecified)' nodes already
exist under the same parents (358, 413) -> flagged for Charles.
Processes parents before children; repaths each subtree by prefix swap."""
import sqlite3

RENAME_IDS = [15, 52, 73, 84, 133, 165, 170, 253, 260, 281, 321, 325, 342,
              380, 388, 429, 440, 451, 484]

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

def esc(s):
    return s.replace("'", "''")

# parents before children: sort by current path length
infos = []
for nid in RENAME_IDS:
    name, path = db.execute(
        "SELECT name, full_path FROM taxonomy WHERE id=?", (nid,)).fetchone()
    infos.append((len(path), nid, name, path))
infos.sort()

rollbacks = []
db.execute("BEGIN")
n_repathed = 0
for _, nid, name, path in infos:
    # re-fetch in case an ancestor rename already changed our path
    name, path = db.execute(
        "SELECT name, full_path FROM taxonomy WHERE id=?", (nid,)).fetchone()
    new_name = name + " (unspecified)"
    new_path = path.rsplit("/", 1)[0] + "/" + new_name
    ids = subtree_ids(nid)
    db.execute("UPDATE taxonomy SET name=? WHERE id=?", (new_name, nid))
    cur = db.execute(
        "UPDATE taxonomy SET full_path=? || SUBSTR(full_path, ?) "
        "WHERE id IN (%s)" % ",".join("?" * len(ids)),
        (new_path, len(path) + 1, *ids))
    n_repathed += cur.rowcount
    rollbacks.append(
        "UPDATE taxonomy SET name='%s' WHERE id=%d;\n"
        "UPDATE taxonomy SET full_path='%s' || SUBSTR(full_path, %d) "
        "WHERE full_path LIKE '%s%%';" % (
            esc(name), nid, esc(path), len(new_path) + 1, esc(new_path)))

# verify: renamed nodes all carry the suffix; no sibling name collisions
dups = db.execute(
    """SELECT parent_id, name, COUNT(*) FROM taxonomy
       WHERE id IN (%s) GROUP BY parent_id, name HAVING COUNT(*) > 1"""
    % ",".join("?" * len(RENAME_IDS)), RENAME_IDS).fetchall()
suff = db.execute(
    "SELECT COUNT(*) FROM taxonomy WHERE id IN (%s) AND name NOT LIKE '%% (unspecified)'"
    % ",".join("?" * len(RENAME_IDS)), RENAME_IDS).fetchone()[0]
print("renamed:", len(infos), "| repathed:", n_repathed,
      "| dup names under same parent:", len(dups), "| missing suffix:", suff)
if len(dups) == 0 and suff == 0:
    db.execute("COMMIT")
    print("COMMITTED")
else:
    db.execute("ROLLBACK")
    print("ROLLED BACK")
print("ROLLBACKS-BEGIN")
for rb in reversed(rollbacks):
    print(rb)
print("ROLLBACKS-END")
db.close()
