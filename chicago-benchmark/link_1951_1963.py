"""Cook County cross-era entity resolution per schema-spec v0.1 match tiers."""
import sqlite3, json, math, sys
from collections import defaultdict
sys.path.insert(0, ".")
from linklib import (normalize_name, parse_address, address_key, address_match,
                     name_block_key, street_block_key, jaro_winkler)

DB = "cook_phonebooks.db"

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

c = sqlite3.connect(DB)
rows = c.execute("SELECT id, year, name, address, phone, denomination, confidence, city FROM listings").fetchall()
geo = {}
for ak, lat, lon, mt in c.execute("SELECT addr_key, lat, lon, match_type FROM geocode"):
    geo[ak.lower()] = (lat, lon, mt)
c.close()

recs = []
for r in rows:
    rid, year, name, addr, phone, denom, conf, city = r
    recs.append({
        "id": rid, "year": year, "name": name or "", "addr": addr or "",
        "phone": phone or "", "denom": denom or "", "conf": conf, "city": city,
        "nname": normalize_name(name), "akey": address_key(addr),
        "nblock": name_block_key(name), "sblock": street_block_key(addr),
        "geo": geo.get((addr or "").lower()),
    })

by_year = defaultdict(list)
for r in recs:
    by_year[r["year"]].append(r)
print({y: len(v) for y, v in by_year.items()}, flush=True)

def denom_ok(a, b):
    da, db = (a["denom"] or "").upper().strip(), (b["denom"] or "").upper().strip()
    if not da or not db:
        return True  # can't disprove
    return da == db

links = []  # (id_a, id_b, tier, score, note)
review = []  # flagged for human review

def try_tier(a, b):
    """a, b from different eras. Returns (tier, score, note) or None."""
    an, bn = a["nname"], b["nname"]
    jw = jaro_winkler(an, bn)
    addr_same = address_match(a["addr"], b["addr"]) if a["addr"] and b["addr"] else False
    # Tier 1: same address + fuzzy name >= 0.90
    if addr_same and jw >= 0.90:
        return (1, round(jw, 3), "same address + name JW>=0.90")
    # Tier 2: same address, different name -> succession/rename, medium, review
    if addr_same:
        if not denom_ok(a, b):
            return None
        return (2, round(jw, 3), "same address, name differs -> review")
    # Tier 3: same name, different address within 2km (or same street stem)
    if jw >= 0.95:
        ga, gb = a["geo"], b["geo"]
        within = False
        if ga and gb and ga[0] and gb[0]:
            within = haversine_km(ga[0], ga[1], gb[0], gb[1]) <= 2.0
        else:
            sa = parse_address(a["addr"])[2]
            sb = parse_address(b["addr"])[2]
            within = bool(sa and sa == sb)
        if within:
            if not denom_ok(a, b):
                return None
            return (3, round(jw, 3), "same name, nearby/diff address -> review")
    return None

# Blocking: candidates share name-block OR street-block
def blocked_pairs(eras):
    seen = set()
    buckets = defaultdict(list)
    for r in recs:
        if r["year"] not in eras:
            continue
        buckets[("n", r["nblock"])].append(r)
        buckets[("s", r["sblock"])].append(r)
    for members in buckets.values():
        for i in range(len(members)):
            for j in range(i+1, len(members)):
                a, b = members[i], members[j]
                if a["year"] == b["year"]:
                    continue
                key = tuple(sorted((a["id"], b["id"])))
                if key in seen:
                    continue
                seen.add(key)
                yield a, b

npairs = 0
for a, b in blocked_pairs({1951, 1963}):
    npairs += 1
    t = try_tier(a, b)
    if t:
        tier, score, note = t
        links.append((a["id"], b["id"], tier, score, note))
        if tier in (2, 3):
            review.append((a["id"], b["id"], tier, note))
print(f"candidate pairs: {npairs}, links: {len(links)}, review-flagged: {len(review)}", flush=True)

# Union-find with ambiguity detection
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

for r in recs:
    parent[r["id"]] = r["id"]

# ambiguity: one record linked to >1 record in the same other era
by_src = defaultdict(list)
for a, b, tier, score, note in links:
    by_src[a].append((b, tier))
    by_src[b].append((a, tier))

ambiguous_ids = set()
rec_by_id = {r["id"]: r for r in recs}
for src, dsts in by_src.items():
    years = defaultdict(list)
    for d, tier in dsts:
        years[rec_by_id[d]["year"]].append((d, tier))
    for y, dl in years.items():
        if len(dl) > 1:
            # keep only tier-1 auto; rest go to review
            dl_sorted = sorted(dl, key=lambda x: x[1])
            if dl_sorted[0][1] == 1 and all(x[1] > 1 for x in dl_sorted[1:]):
                for d, tier in dl_sorted[1:]:
                    ambiguous_ids.add((min(src, d), max(src, d)))
            else:
                for d, tier in dl:
                    ambiguous_ids.add((min(src, d), max(src, d)))

auto_links = [(a, b, t, s, n) for a, b, t, s, n in links
              if (min(a,b), max(a,b)) not in ambiguous_ids]
print(f"auto links: {len(auto_links)}, ambiguous held: {len(ambiguous_ids)}", flush=True)

for a, b, t, s, n in auto_links:
    union(a, b)

clusters = defaultdict(list)
for r in recs:
    clusters[find(r["id"])].append(r["id"])

# also record tier-1-only stats
t1 = sum(1 for x in auto_links if x[2] == 1)
print(f"tier1: {t1}, clusters: {len(clusters)}", flush=True)
cross = sum(1 for members in clusters.values()
            if len({rec_by_id[i]['year'] for i in members}) > 1)
print(f"clusters spanning eras: {cross}", flush=True)

json.dump({
    "links": [{"a": a, "b": b, "tier": t, "score": s, "note": n} for a, b, t, s, n in auto_links],
    "review": [{"a": a, "b": b, "tier": t, "note": n} for a, b, t, n in review],
    "ambiguous": [{"a": a, "b": b} for a, b in sorted(ambiguous_ids)],
    "clusters": {str(k): v for k, v in clusters.items()},
}, open("linkage_1951_1963.json", "w"), indent=1)
print("wrote linkage_1951_1963.json", flush=True)
