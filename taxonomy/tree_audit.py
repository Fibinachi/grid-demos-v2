"""Read-only audit of the taxonomy tree in E:/grid/churches.db.
Prints the full tree plus structural anomaly checks.
Output is human-readable; pipe to a file for review.
"""
import sqlite3
from collections import defaultdict

db = sqlite3.connect("file:E:/grid/churches.db?mode=ro", uri=True)

cols = [d[1] for d in db.execute("PRAGMA table_info(taxonomy)")]
print("COLUMNS:", cols)

idc = "id"
namec = "name"
parc = "parent_id" if "parent_id" in cols else None
depthc = "depth" if "depth" in cols else None
extra = [c for c in cols if c not in (idc, namec, parc, depthc)]
print("EXTRA COLS:", extra)

sel = [idc, namec]
if parc: sel.append(parc)
if depthc: sel.append(depthc)
sel += extra
rows = db.execute(f"SELECT {', '.join(sel)} FROM taxonomy").fetchall()

nodes = {}
for r in rows:
    d = dict(zip(sel, r))
    nodes[d[idc]] = d

print(f"NODES: {len(nodes)}")

# ---- structural checks ----
kids = defaultdict(list)
for nid, n in nodes.items():
    p = n.get(parc)
    if p is not None:
        kids[p].append(nid)

orphans = [(nid, n.get(parc)) for nid, n in nodes.items()
           if n.get(parc) is not None and n.get(parc) not in nodes]
print(f"\nORPHANS (parent missing): {len(orphans)}")
for nid, p in orphans[:20]:
    print(f"  id={nid} name={nodes[nid][namec]!r} parent_id={p}")

selfpar = [nid for nid, n in nodes.items() if n.get(parc) == nid]
print(f"\nSELF-PARENTS: {len(selfpar)} {selfpar[:20]}")

# cycle detection
def has_cycle():
    seen_all = set()
    bad = []
    for start in nodes:
        path = set()
        cur = start
        while cur is not None and cur in nodes:
            if cur in path:
                bad.append(start); break
            if cur in seen_all:
                break
            path.add(cur)
            cur = nodes[cur].get(parc)
        seen_all |= path
    return bad
cyc = has_cycle()
print(f"\nCYCLES (nodes in a cycle): {len(cyc)} {cyc[:20]}")

# duplicate names under same parent
bypar = defaultdict(list)
for nid, n in nodes.items():
    bypar[(n.get(parc), (n[namec] or "").strip().lower())].append(nid)
dupes_same = {k: v for k, v in bypar.items() if len(v) > 1}
print(f"\nDUPLICATE NAMES UNDER SAME PARENT: {len(dupes_same)}")
for (p, nm), ids in list(dupes_same.items())[:20]:
    print(f"  {nm!r} under parent_id={p}: ids={ids}")

# same name at different parents (conceptual duplicates)
byname = defaultdict(list)
for nid, n in nodes.items():
    byname[(n[namec] or "").strip().lower()].append(nid)
dupes_diff = {k: v for k, v in byname.items() if len(v) > 1}
print(f"\nSAME NAME AT DIFFERENT PARENTS: {len(dupes_diff)}")
for nm, ids in list(dupes_diff.items())[:40]:
    pars = [(i, nodes[i].get(parc),
             nodes[nodes[i].get(parc)][namec] if nodes[i].get(parc) in nodes else None)
            for i in ids]
    print(f"  {nm!r}: {pars}")

# depth consistency (path length vs stored depth)
def path_depth(nid):
    d, cur = 0, nid
    while nodes[cur].get(parc) is not None and nodes[cur].get(parc) in nodes:
        cur = nodes[cur][parc]; d += 1
    return d
if depthc:
    mism = [(nid, nodes[nid][depthc], path_depth(nid)) for nid in nodes
            if nodes[nid][depthc] != path_depth(nid)]
    print(f"\nDEPTH MISMATCHES (stored vs path): {len(mism)}")
    for nid, s, pth in mism[:20]:
        print(f"  id={nid} name={nodes[nid][namec]!r} stored={s} path={pth}")

# suspicious names
import re
sus = []
for nid, n in nodes.items():
    nm = (n[namec] or "")
    if re.search(r"\?|unknown|n/a|tbd|xxx|test|temp|delete|misc$|^node |^\d+$", nm, re.I):
        sus.append((nid, nm))
print(f"\nSUSPICIOUS NAMES: {len(sus)}")
for nid, nm in sus[:30]:
    print(f"  id={nid} {nm!r}")

# name == parent name (redundant level)
red = []
for nid, n in nodes.items():
    p = n.get(parc)
    if p in nodes and (nodes[p][namec] or "").strip().lower() == (n[namec] or "").strip().lower():
        red.append((nid, n[namec], p))
print(f"\nNAME == PARENT NAME: {len(red)}")
for nid, nm, p in red[:30]:
    print(f"  id={nid} {nm!r} under parent id={p}")

# ---- church counts per taxonomy node ----
try:
    counts = dict(db.execute(
        "SELECT taxonomy_id, COUNT(*) FROM churches WHERE taxonomy_id IS NOT NULL "
        "GROUP BY taxonomy_id"))
    print(f"\nCHURCHES WITH TAXONOMY: {sum(counts.values()):,}")
    top = sorted(counts.items(), key=lambda x: -x[1])[:30]
    print("TOP 30 NODES BY CHURCH COUNT:")
    for tid, c in top:
        n = nodes.get(tid, {})
        print(f"  {c:>9,}  id={tid} name={n.get(namec)!r}")
    zero = [nid for nid in nodes if nid not in counts]
    print(f"NODES WITH ZERO CHURCHES: {len(zero)}")
except Exception as e:
    print("count query failed:", e)

# ---- full tree ----
roots = [nid for nid, n in nodes.items() if n.get(parc) is None]
print(f"\nROOTS: {len(roots)}")
for r in roots:
    print(f"  id={r} {nodes[r][namec]!r}")

def walk(nid, indent=0):
    n = nodes[nid]
    line = "  " * indent + f"- {n[namec]} [id={nid}]"
    if depthc:
        line += f" (depth={n[depthc]})"
    print(line)
    for c in sorted(kids[nid], key=lambda x: (nodes[x][namec] or "").lower()):
        walk(c, indent + 1)

print("\n================ FULL TREE ================")
for r in sorted(roots, key=lambda x: (nodes[x][namec] or "").lower()):
    walk(r)
db.close()
