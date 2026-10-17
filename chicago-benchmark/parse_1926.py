"""Parse 1926 scrape JSONL into observations and link to later eras (name+denomination only)."""
import json, sys
sys.path.insert(0, ".")
from linklib import normalize_name, jaro_winkler

def load_1926(path):
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except Exception:
                continue
    return recs

def audit(recs):
    from collections import Counter
    print(f"1926 records: {len(recs)}")
    print("missing church_name:", sum(1 for r in recs if not r.get("church_name")))
    print("missing denomination_family:", sum(1 for r in recs if not r.get("denomination_family")))
    print("places:", Counter(r.get("place") or "?" for r in recs).most_common(8))
    print("denom families:", Counter(r.get("denomination_family") or "?" for r in recs).most_common(10))
    # generic-name share
    generic = 0
    for r in recs:
        n = normalize_name(r.get("church_name") or "")
        toks = [t for t in n.split() if t not in ("CHURCH", "SAINT")]
        if len(toks) <= 1:
            generic += 1
    print(f"generic names (<=1 distinctive token): {generic} ({100*generic/max(1,len(recs)):.1f}%)")

def to_observation(r, seq):
    return {
        "observation_id": f"1926_{seq:06d}",
        "canonical_id": "",
        "church_name_raw": r.get("church_name") or "",
        "church_name_normalized": normalize_name(r.get("church_name") or ""),
        "address_raw": "",
        "address_normalized": "",
        "denomination_raw": r.get("denomination_family") or "",
        "taxonomy_id": "",
        "latitude": "", "longitude": "",
        "coord_confidence": "none",
        "era": 1926, "source": "census_1926",
        "source_ref": r.get("url") or "",
        "status": "active",
        "_place": r.get("place") or "",
        "_record": r,
    }

if __name__ == "__main__":
    recs = load_1926("/home/hatch/workspace/grid/chicago-benchmark/staging/1926_cook_raw.jsonl")
    audit(recs)
