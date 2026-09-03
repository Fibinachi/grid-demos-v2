"""Analyze missing-email foundations to understand the opportunity."""
import csv, os, re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")

with open(CSV_PATH, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

missing = [r for r in rows if not r.get("EMAIL", "").strip()]
total = len(rows)

print(f"Total records:       {total:>6,}")
print(f"With email:          {total - len(missing):>6,}")
print(f"Missing email:       {len(missing):>6,}")
print()

# Show sample
print("=== SAMPLE (first 15) ===")
for r in missing[:15]:
    name = r["NAME"][:55]
    city = r.get("CITY", "")[:18]
    state = r.get("STATE", "")
    assets = r.get("ASSET_AMT", "0")
    ntee = r.get("NTEE_CD", "")
    print(f"  {name:55s} | {city:18s} | {state:2s} | ${assets:>10s} | {ntee}")

print()

# Asset distribution
assets = []
for r in missing:
    try:
        a = float(r.get("ASSET_AMT", 0) or 0)
        assets.append(a)
    except:
        assets.append(0)

print("=== ASSET DISTRIBUTION ===")
buckets = [
    ("$50M+       ", 50_000_000, 999_999_999_999),
    ("$10M-$50M   ", 10_000_000, 50_000_000),
    ("$5M-$10M    ", 5_000_000, 10_000_000),
    ("$1M-$5M     ", 1_000_000, 5_000_000),
    ("$500K-$1M   ", 500_000, 1_000_000),
]
for label, lo, hi in buckets:
    cnt = sum(1 for a in assets if lo <= a < hi)
    print(f"  {label}: {cnt:>5,}")
print(f"  Under $500K: {sum(1 for a in assets if a < 500_000):>5,}")

print()

# Name analysis - can we extract meaningful names for domain guessing?
print("=== NAME PATTERNS (for domain guessing) ===")
STOP_WORDS = {
    "THE", "AND", "&", "FOUNDATION", "INC", "CORP", "CORPORATION",
    "FAMILY", "MEMORIAL", "TRUST", "FUND", "ENDOWMENT",
    "FOR", "OF", "IN", "TO", "A", "AN",
    "PRIVATE", "CHARITABLE", "PHILANTHROPIC",
    "SR", "JR", "III", "II", "IV",
    "COMPANY", "ENTERPRISES", "LLC", "PA",
}

def guess_domain(name):
    """Try to extract a domain from foundation name."""
    if not name:
        return []
    candidates = []
    upper = name.upper()
    
    # Try removing suffix words progressively
    words = upper.split()
    # Remove trailing stop words
    while words and words[-1] in STOP_WORDS:
        words = words[:-1]
    
    if not words:
        return []
    
    # The last meaningful word is likely the key name
    key_word = words[-1].lower().replace("'S", "s")
    
    # Try common TLDs
    for tld in [".org", ".com", ".net", ".foundation", ".us"]:
        candidates.append(f"{key_word}{tld}")
        candidates.append(f"{key_word}foundation{tld}")
    
    # Try the full name as domain
    name_slug = "-".join(w.lower().replace("'S", "s") for w in words if w not in STOP_WORDS and len(w) > 1)
    if name_slug:
        candidates.append(f"{name_slug}.org")
    
    return candidates

# Count how many have extractable names
extractable = 0
for r in missing:
    domains = guess_domain(r["NAME"])
    if domains:
        extractable += 1

print(f"  Foundations with extractable name: {extractable:,} / {len(missing):,}")
print()

# Show some domain guess examples
print("=== DOMAIN GUESS EXAMPLES ===")
for r in missing[:20]:
    domains = guess_domain(r["NAME"])
    print(f"  {r['NAME'][:50]:50s} -> {domains[0]}")
