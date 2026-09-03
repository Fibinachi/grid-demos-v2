#!/usr/bin/env python3
"""
Apply geographic, asset, NTEE, and score filters to create the final focused list.
Uses gw_filters.geo for all filter logic — single source of truth.
"""
import csv, os
from gw_filters import geo

base = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(base, 'theology_foundations_only.csv')) as f:
    rows = list(csv.DictReader(f))

total = len(rows)
kept, removed = geo.filter_foundations(rows)

print(f"Current: {total}")
print(f"Removed - geographic: {removed['geo']}")
print(f"Removed - NTEE: {removed['ntee']}")
print(f"Removed - assets: {removed['assets']}")
print(f"Removed - score: {removed['score']}")
print(f"Remaining: {len(kept)}")

# === NOW APPLY ADDITIONAL FILTERS ===
# Asset >= $1M, NTEE T/X, Score >= 30

def passes_filters(r):
    """Combined filter: $1M+ assets, NTEE T/X, Score >= 30"""
    # Score filter
    score = int(r['THEOLOGY_SCORE'])
    if r['PRIORITY'] != 'HIGH' and score < 30:
        return False
    
    # NTEE filter
    ntee = r.get('NTEE', '')
    if ntee and not ntee.startswith(('T', 'X')):
        return False
    
    # Asset filter
    asset_str = r.get('ASSET_AMT', '0').strip()
    if asset_str and asset_str != '0':
        try:
            asset = float(asset_str)
            if asset < 1000000:  # $1M minimum
                return False
        except:
            pass
    
    return True

filtered = [r for r in kept if passes_filters(r)]
high = [r for r in filtered if r['PRIORITY'] == 'HIGH']
med = [r for r in filtered if r['PRIORITY'] == 'MEDIUM']
ready = [r for r in filtered if r['HAS_EMAIL'] == 'YES']

print(f"\nAfter all filters ($1M+ / T+X NTEE / Score>=30):")
print(f"  Total: {len(filtered)}")
print(f"  HIGH: {len(high)}, MEDIUM: {len(med)}")
print(f"  Ready to send: {len(ready)}")

# Save
out_path = os.path.join(base, 'theology_final_list.csv')
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(filtered)
print(f"\nSaved: {out_path}")

# Ready-to-send subset
ready_path = os.path.join(base, 'theology_final_send.csv')
ready_list = [r for r in filtered if r['HAS_EMAIL'] == 'YES']
with open(ready_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(ready_list)
print(f"Ready to send: {len(ready_list)} -> {ready_path}")

# Print top 30
print(f"\n{'='*70}")
print(f"TOP 30 FINAL LIST (for Columbia, SC based applicant)")
print(f"{'='*70}")
for r in filtered[:30]:
    email = '✓' if r['HAS_EMAIL'] == 'YES' else '✗'
    print(f"  [{r['PRIORITY']:6s}] [{r['THEOLOGY_SCORE']:>3s}] {email} {r['NAME'][:55]} ({r['CITY']}, {r['STATE']})")
