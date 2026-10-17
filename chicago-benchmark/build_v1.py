"""Build v1.0 observations + entities + survivorship for the Cook County benchmark."""
import sqlite3, json, csv, math, sys
from collections import defaultdict
sys.path.insert(0, ".")
from linklib import normalize_name, parse_address, jaro_winkler

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# ---- load ----
link = json.load(open("linkage_1951_1963.json"))
c = sqlite3.connect("cook_phonebooks.db")
listings = {}
callno = {}
for r in c.execute("SELECT id, year, name, address, phone, denomination, confidence, city, call_no FROM listings"):
    listings[r[0]] = r
    callno[(r[1], r[8])] = r[0]
geo = {}
for ak, lat, lon in c.execute("SELECT addr_key, lat, lon FROM geocode"):
    geo[ak.lower()] = (lat, lon)
pb_grid = dict(c.execute("SELECT id, grid_church_id FROM entities WHERE grid_church_id IS NOT NULL"))
app = defaultdict(list)
for eid, year, cn in c.execute("SELECT entity_id, year, call_no FROM appearances"):
    app[eid].append((year, cn))
c.close()

rows = list(csv.DictReader(open("cook_remap.csv", encoding="utf-8")))
m = {r["church_id"]: r for r in rows}
def resolve(cid):
    seen = set()
    while True:
        if cid in seen:
            return cid
        seen.add(cid)
        r = m.get(cid)
        if not r or r["status"] != "merged" or not r["dedup_canonical_id"]:
            return cid
        cid = r["dedup_canonical_id"]

canon_info = {}
for r in rows:
    cid = resolve(r["church_id"])
    if cid not in canon_info:
        canon_info[cid] = m.get(cid, r)
print(f"2026 canonicals: {len(canon_info)}", flush=True)

# ---- union-find ----
parent = {}
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[rb] = ra

for lid in listings:
    parent[("pb", lid)] = ("pb", lid)
for cid in canon_info:
    parent[("g26", cid)] = ("g26", cid)

for l in link["links"]:
    union(("pb", l["a"]), ("pb", l["b"]))

# phonebook -> 2026 via remapped grid links (through appearances; call_no is 'listings:<id>')
n1 = 0
for eid, gid in pb_grid.items():
    canon = resolve(str(gid))
    for year, cn in app.get(eid, []):
        try:
            lid = int(str(cn).split(":")[-1])
        except (ValueError, IndexError):
            continue
        if lid in listings:
            union(("pb", lid), ("g26", canon))
            n1 += 1
print(f"pb->2026 via grid links: {n1}", flush=True)

# additional pb->2026: name + proximity for clusters lacking 2026
clusters = defaultdict(list)
for lid in listings:
    clusters[find(("pb", lid))].append(("pb", lid))
for cid in canon_info:
    clusters[find(("g26", cid))].append(("g26", cid))

no26_pb = [x[1] for members in clusters.values() for x in members
           if x[0] == "pb" and not any(y[0] == "g26" for y in members)]
print(f"pb listings in clusters without 2026: {len(no26_pb)}", flush=True)

grid_idx = defaultdict(list)
for cid, info in canon_info.items():
    try:
        lat, lon = float(info["latitude"]), float(info["longitude"])
    except (TypeError, ValueError):
        continue
    grid_idx[(round(lat, 2), round(lon, 2))].append((cid, lat, lon, info))

n2 = 0
for lid in no26_pb:
    r = listings[lid]
    nname = normalize_name(r[2])
    g = geo.get((r[3] or "").lower())
    if not g or not g[0]:
        continue
    lat, lon = g[0], g[1]
    best = None
    for dlat in (-0.01, 0, 0.01):
        for dlon in (-0.01, 0, 0.01):
            for cid, clat, clon, info in grid_idx.get((round(lat + dlat, 2), round(lon + dlon, 2)), []):
                if haversine_km(lat, lon, clat, clon) > 0.5:
                    continue
                jw = jaro_winkler(nname, normalize_name(info["name"] or ""))
                if jw >= 0.90 and (best is None or jw > best[0]):
                    best = (jw, cid)
    if best:
        union(("pb", lid), ("g26", best[1]))
        n2 += 1
print(f"pb->2026 name+proximity: {n2}", flush=True)

# ---- rebuild + emit ----
clusters = defaultdict(list)
for lid in listings:
    clusters[find(("pb", lid))].append(("pb", lid))
for cid in canon_info:
    clusters[find(("g26", cid))].append(("g26", cid))

observations, entities, linkage_log = [], [], []
for l in link["links"]:
    linkage_log.append({"a_obs": f"pb_{l['a']}", "b_obs": f"pb_{l['b']}",
                        "tier": l["tier"], "score": l["score"],
                        "note": l["note"], "auto": True})
for r in link["review"]:
    linkage_log.append({"a_obs": f"pb_{r['a']}", "b_obs": f"pb_{r['b']}",
                        "tier": r["tier"], "score": None,
                        "note": r["note"], "auto": False})
for amb in link["ambiguous"]:
    linkage_log.append({"a_obs": f"pb_{amb['a']}", "b_obs": f"pb_{amb['b']}",
                        "tier": None, "score": None,
                        "note": "ambiguous: held for human review, not merged",
                        "auto": False})

seq = 0
for root, members in sorted(clusters.items(), key=lambda x: str(x[0])):
    seq += 1
    ccid = f"cc_{seq:05d}"
    eras, best_name, best_n = set(), "", 0
    for kind, i in members:
        if kind == "pb":
            r = listings[i]
            year = r[1]
            eras.add(year)
            nm = r[2] or ""
            if len(nm) > best_n:
                best_name, best_n = nm, len(nm)
            g = geo.get((r[3] or "").lower())
            observations.append({
                "observation_id": f"{year}_{i:06d}", "canonical_id": ccid,
                "church_name_raw": nm, "church_name_normalized": normalize_name(nm),
                "address_raw": r[3] or "",
                "address_normalized": "|".join(parse_address(r[3] or "")),
                "denomination_raw": r[5] or "", "taxonomy_id": "",
                "latitude": g[0] if g else "", "longitude": g[1] if g else "",
                "coord_confidence": "low" if g else "none",
                "era": year, "source": f"dir_{year}",
                "source_ref": f"listings.id={i}", "status": "active"})
        else:
            info = canon_info[i]
            eras.add(2026)
            nm = info["name"] or ""
            if len(nm) > best_n:
                best_name, best_n = nm, len(nm)
            observations.append({
                "observation_id": f"2026_{i}", "canonical_id": ccid,
                "church_name_raw": nm, "church_name_normalized": normalize_name(nm),
                "address_raw": "", "address_normalized": "",
                "denomination_raw": info.get("tradition") or "",
                "taxonomy_id": info.get("taxonomy_id") or "",
                "latitude": info.get("latitude") or "",
                "longitude": info.get("longitude") or "",
                "coord_confidence": "high",
                "era": 2026, "source": "grid_2026",
                "source_ref": f"churches.id={i}",
                "status": info.get("status") or "active"})
    members_pb = [i for k, i in members if k == "pb"]
    ct = [l["tier"] for l in link["links"] if l["a"] in members_pb or l["b"] in members_pb]
    lconf = "high" if (not ct or min(ct) == 1) else "medium"
    first_e, last_e = min(eras), max(eras)
    has26 = 2026 in eras
    statuses = [o["status"] for o in observations if o["canonical_id"] == ccid]
    if any(s == "closed" for s in statuses):
        surv, closure = "closed", "2026"
    elif has26:
        surv, closure = "survived_to_2026", ""
    else:
        surv, closure = "unknown", ""
    entities.append({
        "canonical_id": ccid, "best_name": best_name,
        "first_seen_era": first_e, "last_seen_era": last_e,
        "n_observations": len(members), "survivorship": surv,
        "closure_era_estimate": closure, "linkage_confidence": lconf,
        "eras": ";".join(str(e) for e in sorted(eras))})

print(f"observations: {len(observations)}, entities: {len(entities)}", flush=True)
with open("observations_v1.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(observations[0].keys()))
    w.writeheader(); w.writerows(observations)
with open("entities_v1.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(entities[0].keys()))
    w.writeheader(); w.writerows(entities)
json.dump(linkage_log, open("linkage_log_v1.json", "w"), indent=1)

from collections import Counter as C
esurv = C(e["survivorship"] for e in entities)
print("SURVIVORSHIP:", dict(esurv), flush=True)
pre = [e for e in entities if e["first_seen_era"] in (1951, 1963)]
print(f"entities w/ pre-2026 origins: {len(pre)}, "
      f"survived: {sum(1 for e in pre if e['survivorship']=='survived_to_2026')}, "
      f"closed: {sum(1 for e in pre if e['survivorship']=='closed')}, "
      f"unknown: {sum(1 for e in pre if e['survivorship']=='unknown')}", flush=True)
print("wrote observations_v1.csv, entities_v1.csv, linkage_log_v1.json", flush=True)
