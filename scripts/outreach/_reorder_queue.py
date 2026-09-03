"""Reorder unified queue by deal size priority."""
import json
from pathlib import Path
from collections import Counter

QF = Path("outputs/outreach/unified_queue.jsonl")
entries = [json.loads(l) for l in QF.read_text(encoding="utf-8").strip().split("\n") if l.strip()]
print(f"Total entries: {len(entries)}")

BIG_NAMES = {
    "experian", "equifax", "transunion", "acxiom", "epsilon", "aristotle",
    "i360", "i-360", "targetsmart", "l2 political", "l2 ", "catalist",
    "liveramp", "safegraph", "foursquare", "neustar", "merkle", "lexisnexis",
    "deloitte", "moody", "blackbaud", "hubspot", "snowflake", "databricks",
}

MED_NAMES = {
    "civis", "deep root", "dspolitical", "tunnl", "resonate", "helix",
    "semcasting", "eyeota", "magnite", "openx", "criteo", "taboola",
    "teads", "index exchange", "sharethrough", "sovrn", "liveintent",
    "mediawallah", "demandbase", "bombora", "6sense", "leadiq",
    "rocketreach", "pitchbook", "preqin", "altrata", "relpro",
}

def priority(e):
    org = (e.get("org", "") + " " + e.get("to", "")).lower()
    src = e.get("source", "")
    cat = e.get("category", "")

    # Tier 1: whales, political, manual additions
    if src in ("whales", "political_data", "cppa_safegraph", "i360_support", "manual"):
        return 1
    if any(n in org for n in BIG_NAMES):
        return 1

    # Tier 2: financial, identity, enterprise
    if cat in ("financial_credit", "identity_fraud"):
        return 2
    if any(n in org for n in MED_NAMES):
        return 2
    if src == "enterprise_csv":
        return 2

    # Tier 3: adtech, healthcare, political
    if cat in ("adtech", "healthcare", "political"):
        return 3

    # Tier 4: list brokers, people search, real estate, B2B, automotive
    if cat in ("list_broker", "people_search", "real_estate", "b2b_sales", "automotive"):
        return 4

    # Tier 5: church teasers, faith media, hunger, muslim orgs, embassies
    if src in ("church_teaser", "faith_media", "faith_hunger", "muslim_org", "mena_embassy"):
        return 5

    # Tier 6: general CPPA mass (long tail)
    return 6

# Sort by priority, preserving original order within same tier
indexed = [(priority(e), i, e) for i, e in enumerate(entries)]
indexed.sort(key=lambda x: (x[0], x[1]))
sorted_entries = [e for _, _, e in indexed]

# Count
tiers = Counter()
for e in sorted_entries:
    tiers[priority(e)] += 1

tier_labels = {1: "Whales & Political", 2: "Financial & Identity", 3: "AdTech & Healthcare",
               4: "List, Search, Real Estate", 5: "Churches & Faith Media", 6: "General (long tail)"}

print("\nNew order:")
for t in sorted(set(priority(e) for e in entries)):
    print(f"  Tier {t} - {tier_labels[t]:30s}: {tiers[t]:>4} entries")

with open(QF, "w", encoding="utf-8") as f:
    for item in sorted_entries:
        f.write(json.dumps(item) + "\n")

print(f"\n--- First 12 (highest priority) ---")
for e in sorted_entries[:12]:
    print(f"  T{priority(e)} | {e.get('org','?')[:48]:48s} -> {e['to']}")

print(f"\n--- Last 5 (lowest priority) ---")
for e in sorted_entries[-5:]:
    print(f"  T{priority(e)} | {e.get('org','?')[:48]:48s} -> {e['to']}")

print(f"\nQueue reordered. {len(sorted_entries)} entries, ~{len(sorted_entries)*3/3600:.1f} days to send.")
