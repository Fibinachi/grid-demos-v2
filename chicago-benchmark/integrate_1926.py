"""Integrate 1926 schedules: merge worker outputs, audit, link to later eras, rebuild v1.0."""
import json, csv, sys, glob
from collections import Counter, defaultdict
sys.path.insert(0, ".")
from linklib import normalize_name, jaro_winkler

STAGING = "/home/hatch/workspace/grid/chicago-benchmark/staging/"
WORK = "/home/hatch/workspace/zenodo-deposits/chicago-benchmark-v1.0/work/"

def load_all():
    recs, seen = [], set()
    for pat in ["1926_cook_raw.jsonl", "1926_w0.jsonl", "1926_w1.jsonl", "1926_w2.jsonl"]:
        for fn in glob.glob(STAGING + pat):
            with open(fn) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    rid = str(r.get("record_id"))
                    if rid in seen:
                        continue
                    seen.add(rid)
                    recs.append(r)
    return recs

def main():
    recs = load_all()
    print(f"1926 unique records: {len(recs)}", flush=True)
    # audit
    print("missing name:", sum(1 for r in recs if not r.get("church_name")), flush=True)
    print("places:", Counter(r.get("place") or "?" for r in recs).most_common(6), flush=True)
    # write schedules CSV
    fields = ["record_id", "schedule_id", "church_name", "denomination_family",
              "census_code", "place", "male_members", "female_members",
              "members_13plus", "ss_officers", "ss_scholars", "edifices",
              "edifice_value", "pastors_residence", "residence_value",
              "expenses", "benevolences", "total_expenditures",
              "clergy", "schedule_image", "url"]
    with open(WORK + "schedules_1926.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in recs:
            row = {k: r.get(k, "") or "" for k in fields}
            cl = r.get("clergy") or []
            row["clergy"] = json.dumps([c.get("name", "") for c in cl])
            w.writerow(row)
    print("wrote schedules_1926.csv", flush=True)

    # ---- 1926 linkage: NOT POSSIBLE from transcriptions ----
    # The 1926 "church_name" field contains denomination labels (only 106 unique
    # values across 1,805 records, e.g. "Roman Catholic Church" x333), not
    # individual church names. Actual names are in the schedule scan images.
    # All 1926 records become singleton entities. The 1926 layer is a
    # standalone cross-section (membership/finances/clergy by denomination).
    links_1926 = []
    singletons = len(recs)
    print(f"1926 linked: 0 (names are denomination-level; all singletons)", flush=True)
    json.dump([], open(WORK + "links_1926.json", "w"))

    # ---- rebuild observations + entities with 1926 ----
    obs = list(csv.DictReader(open(WORK + "observations_v1.csv", encoding="utf-8")))
    # assign new 1926 observations to entities (linked -> existing ccid; else new ccid)
    obs1926 = []
    ent_of_1926 = {}
    for i, r in enumerate(recs):
        o = {
            "observation_id": f"1926_{i:06d}", "canonical_id": "",
            "church_name_raw": r.get("church_name") or "",
            "church_name_normalized": normalize_name(r.get("church_name") or ""),
            "address_raw": "", "address_normalized": "",
            "denomination_raw": r.get("denomination_family") or "",
            "taxonomy_id": "", "latitude": "", "longitude": "",
            "coord_confidence": "none", "era": 1926, "source": "census_1926",
            "source_ref": r.get("url") or "", "status": "active",
        }
        obs1926.append(o)
    linkmap = {l["rec"]: l for l in
               json.load(open(WORK + "links_1926.json"))}
    for i, o in enumerate(obs1926):
        if i in linkmap:
            o["canonical_id"] = linkmap[i]["entity"]
            ent_of_1926[i] = linkmap[i]["entity"]

    # new entities for unlinked 1926
    import csv as csvm
    ents = list(csvm.DictReader(open(WORK + "entities_v1.csv", encoding="utf-8")))
    maxcc = max(int(e["canonical_id"].split("_")[1]) for e in ents)
    new_ents = []
    for i, o in enumerate(obs1926):
        if not o["canonical_id"]:
            maxcc += 1
            ccid = f"cc_{maxcc:05d}"
            o["canonical_id"] = ccid
            new_ents.append({
                "canonical_id": ccid, "best_name": o["church_name_raw"],
                "first_seen_era": 1926, "last_seen_era": 1926,
                "n_observations": 1, "survivorship": "unknown",
                "closure_era_estimate": "", "linkage_confidence": "high",
                "eras": "1926"})
    # update n_observations and eras for entities that gained 1926
    gained = defaultdict(int)
    for i, e in ent_of_1926.items():
        gained[e] += 1
    for e in ents:
        if e["canonical_id"] in gained:
            e["n_observations"] = str(int(e["n_observations"]) + gained[e["canonical_id"]])
            e["first_seen_era"] = "1926"
            eras = sorted(set(e["eras"].split(";")) | {"1926"}, key=int)
            e["eras"] = ";".join(eras)
    ents.extend(new_ents)
    all_obs = obs + obs1926

    with open(WORK + "observations_v2.csv", "w", newline="", encoding="utf-8") as f:
        w = csvm.DictWriter(f, fieldnames=list(all_obs[0].keys()))
        w.writeheader(); w.writerows(all_obs)
    with open(WORK + "entities_v2.csv", "w", newline="", encoding="utf-8") as f:
        w = csvm.DictWriter(f, fieldnames=list(ents[0].keys()))
        w.writeheader(); w.writerows(ents)

    # survivorship recompute
    from collections import Counter as C
    print("ENTITIES:", len(ents), flush=True)
    print("SURVIVORSHIP:", dict(C(e["survivorship"] for e in ents)), flush=True)
    pre = [e for e in ents if int(e["first_seen_era"]) < 2026]
    s = sum(1 for e in pre if e["survivorship"] == "survived_to_2026")
    print(f"pre-2026 entities: {len(pre)}, survived: {s} ({100*s/max(1,len(pre)):.1f}%)", flush=True)
    # 1926-specific
    e26 = [e for e in ents if e["first_seen_era"] == "1926" or "1926" in e["eras"].split(";")]
    print(f"entities with 1926: {len(e26)}, survived to 2026: "
          f"{sum(1 for e in e26 if e['survivorship']=='survived_to_2026')}", flush=True)
    print("wrote observations_v2.csv, entities_v2.csv", flush=True)

if __name__ == "__main__":
    main()
