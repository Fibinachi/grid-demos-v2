#!/usr/bin/env python3
"""Analyze what additional filters would cut the list."""
import csv, os

base = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(base, 'theology_foundations_only.csv')) as f:
    rows = list(csv.DictReader(f))

total = len(rows)
high = [r for r in rows if r['PRIORITY'] == 'HIGH']
med = [r for r in rows if r['PRIORITY'] == 'MEDIUM']

print(f"Current: {total} total ({len(high)} HIGH, {len(med)} MEDIUM)")
print()

# Filter 1: Asset threshold
tiers = {
    '>= $10M': ('10M+', lambda a: a >= 10000000),
    '>= $5M': ('5M+', lambda a: a >= 5000000),
    '>= $1M': ('1M+', lambda a: a >= 1000000),
    '>= $500K': ('500K+', lambda a: a >= 500000),
}

print(f"{'Filter':<25} {'Remaining':>8} {'HIGH':>6} {'MEDIUM':>6} {'Removed':>8}")
print("-" * 55)

# Asset filter combos with NTEE and score filters
for label, (short, fn) in tiers.items():
    kept = [r for r in rows if not r['ASSET_AMT'] or r['ASSET_AMT'] == '0' or fn(float(r['ASSET_AMT']))]
    print(f"Asset {label:<17} {len(kept):>8} {len([r for r in kept if r['PRIORITY']=='HIGH']):>6} {len([r for r in kept if r['PRIORITY']=='MEDIUM']):>6} {total - len(kept):>8}")

print()

# Filter 2: NTEE restriction (keep only T and X codes)
ntee_only = [r for r in rows if r.get('NTEE','').startswith(('T', 'X'))]
print(f"NTEE T+X only:        {len(ntee_only):>6} ({len([r for r in ntee_only if r['PRIORITY']=='HIGH']):>4}H, {len([r for r in ntee_only if r['PRIORITY']=='MEDIUM']):>5}M) - removed {total-len(ntee_only)}")

# Filter 3: Score threshold for MEDIUM
for threshold in [25, 30, 35]:
    kept = [r for r in rows if r['PRIORITY'] == 'HIGH' or int(r['THEOLOGY_SCORE']) >= threshold]
    print(f"Score >= {threshold:<20} {len(kept):>6} ({len([r for r in kept if r['PRIORITY']=='HIGH']):>4}H, {len([r for r in kept if r['PRIORITY']=='MEDIUM']):>5}M) - removed {total-len(kept)}")

print()

# COMBINED FILTERS (best combinations)
print("=== COMBINED FILTERS ===")
combos = [
    ("$1M+ assets", lambda r: not r['ASSET_AMT'] or r['ASSET_AMT'] == '0' or float(r['ASSET_AMT']) >= 1000000),
    ("NTEE T/X only", lambda r: r.get('NTEE','').startswith(('T', 'X'))),
    ("Score >= 25 (MEDIUM floor)", lambda r: r['PRIORITY'] == 'HIGH' or int(r['THEOLOGY_SCORE']) >= 25),
    ("Score >= 30 (MEDIUM floor)", lambda r: r['PRIORITY'] == 'HIGH' or int(r['THEOLOGY_SCORE']) >= 30),
    ("$500K + NTEE T/X", lambda r: (not r['ASSET_AMT'] or r['ASSET_AMT'] == '0' or float(r['ASSET_AMT']) >= 500000) and r.get('NTEE','').startswith(('T', 'X'))),
    ("$1M + NTEE T/X", lambda r: (not r['ASSET_AMT'] or r['ASSET_AMT'] == '0' or float(r['ASSET_AMT']) >= 1000000) and r.get('NTEE','').startswith(('T', 'X'))),
]

# Build combined filter sets
filter_sets = [
    ("$1M + T/X only", 
     lambda r: (not r['ASSET_AMT'] or r['ASSET_AMT'] == '0' or float(r['ASSET_AMT']) >= 1000000) 
               and r.get('NTEE','').startswith(('T', 'X'))),
    
    ("$1M + T/X + Score>=25", 
     lambda r: (not r['ASSET_AMT'] or r['ASSET_AMT'] == '0' or float(r['ASSET_AMT']) >= 1000000) 
               and r.get('NTEE','').startswith(('T', 'X'))
               and (r['PRIORITY'] == 'HIGH' or int(r['THEOLOGY_SCORE']) >= 25)),
    
    ("$500K + T/X + Score>=30", 
     lambda r: (not r['ASSET_AMT'] or r['ASSET_AMT'] == '0' or float(r['ASSET_AMT']) >= 500000) 
               and r.get('NTEE','').startswith(('T', 'X'))
               and (r['PRIORITY'] == 'HIGH' or int(r['THEOLOGY_SCORE']) >= 30)),
    
    ("$1M + T/X + Score>=30", 
     lambda r: (not r['ASSET_AMT'] or r['ASSET_AMT'] == '0' or float(r['ASSET_AMT']) >= 1000000) 
               and r.get('NTEE','').startswith(('T', 'X'))
               and (r['PRIORITY'] == 'HIGH' or int(r['THEOLOGY_SCORE']) >= 30)),
    
    ("Score>=35 (no asset filter)", 
     lambda r: r['PRIORITY'] == 'HIGH' or int(r['THEOLOGY_SCORE']) >= 35),
]

for label, fn in filter_sets:
    kept = [r for r in rows if fn(r)]
    removed = total - len(kept)
    h = len([r for r in kept if r['PRIORITY'] == 'HIGH'])
    m = len([r for r in kept if r['PRIORITY'] == 'MEDIUM'])
    rdy = len([r for r in kept if r['HAS_EMAIL'] == 'YES'])
    print(f"\n{label}:")
    print(f"  Remaining: {len(kept):,} ({h}H, {m}M) — removed {removed:,}")
    print(f"  Ready to send: {rdy}")
    if kept:
        print(f"  Top 5: {' | '.join(r['NAME'][:40] for r in kept[:5])}")
