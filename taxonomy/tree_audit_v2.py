"""Tree audit v2: full_path staleness, root/family/tradition id consistency,
plus full tree render with unicode-safe output."""
import sqlite3, io, sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

db = sqlite3.connect("file:E:/grid/churches.db?mode=ro", uri=True)
rows = db.execute("SELECT id, parent_id, name, full_path, depth, root_id, tradition_id, family_id FROM taxonomy").fetchall()
nodes = {r[0]: dict(zip(
    ["id","parent_id","name","full_path","depth","root_id","tradition_id","family_id"], r)) for r in rows}

def ancestors(nid):
    out, cur, seen = [], nid, set()
    while cur in nodes and cur not in seen:
        seen.add(cur)
        p = nodes[cur]["parent_id"]
        if p is None or p not in nodes:
            break
        out.append(p); cur = p
    return out

def root_of(nid):
    a = ancestors(nid)
    return a[-1] if a else nid

# full_path check
bad_path = []
for nid, n in nodes.items():
    a = ancestors(nid)
    names = [nodes[nid]["name"]] + [nodes[x]["name"] for x in reversed(a)]
    expect = " > ".join(names)
    if (n["full_path"] or "") != expect:
        bad_path.append((nid, n["name"], n["full_path"], expect))
print("FULL_PATH MISMATCHES:", len(bad_path))
for nid, nm, got, exp in bad_path[:25]:
    print("  id=%d %r\n    stored: %r\n    actual: %r" % (nid, nm, got, exp))

# root_id check
bad_root = [(nid, n["root_id"], root_of(nid)) for nid, n in nodes.items()
            if n["root_id"] != root_of(nid)]
print("ROOT_ID MISMATCHES:", len(bad_root))
for nid, got, exp in bad_root[:20]:
    print("  id=%d name=%r stored_root=%s actual_root=%s (%r)" % (
        nid, nodes[nid]["name"], got, exp,
        nodes[exp]["name"] if exp in nodes else "?"))

# family_id: should equal the depth-1 ancestor? check distribution
fam_vals = defaultdict(int)
for nid, n in nodes.items():
    fam_vals[(n["family_id"], nodes[n["family_id"]]["name"] if n["family_id"] in nodes else "?")] += 1
print("FAMILY_ID VALUES:")
for k, v in sorted(fam_vals.items(), key=lambda x: -x[1])[:15]:
    print("  %s: %d" % (k, v))

trad_vals = defaultdict(int)
for nid, n in nodes.items():
    trad_vals[(n["tradition_id"], nodes[n["tradition_id"]]["name"] if n["tradition_id"] in nodes else "?")] += 1
print("TRADITION_ID DISTINCT:", len(trad_vals))

# orphan subtrees: print the 17 orphans with their descendants
kids = defaultdict(list)
for nid, n in nodes.items():
    if n["parent_id"] in nodes:
        kids[n["parent_id"]].append(nid)
orphans = [nid for nid, n in nodes.items() if n["parent_id"] is not None and n["parent_id"] not in nodes]
def walk(nid, ind=0):
    print("  "*ind + "- %s [id=%d]" % (nodes[nid]["name"], nid))
    for c in sorted(kids[nid], key=lambda x: str(nodes[x]["name"]).lower()):
        walk(c, ind+1)
print("ORPHAN SUBTREES:")
for o in sorted(orphans, key=lambda x: str(nodes[x]["name"]).lower()):
    walk(o)

# full tree
roots = [nid for nid, n in nodes.items() if n["parent_id"] is None]
print("FULL TREE (%d roots):" % len(roots))
for r in sorted(roots, key=lambda x: str(nodes[x]["name"]).lower()):
    walk(r)
db.close()
