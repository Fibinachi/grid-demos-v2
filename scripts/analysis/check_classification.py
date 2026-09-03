#!/usr/bin/env python3
"""Quick summary of classification results."""
import csv
import os

base = os.path.dirname(os.path.abspath(__file__))

for fname in ['classified_tier1.csv', 'classified_theology.csv', 'theology_high_priority.csv']:
    path = os.path.join(base, fname)
    if not os.path.exists(path):
        print(f"{fname}: NOT FOUND")
        continue
    with open(path) as f:
        rows = list(csv.DictReader(f))
    high = [r for r in rows if r['priority'] == 'HIGH']
    med = [r for r in rows if r['priority'] == 'MEDIUM']
    low = [r for r in rows if r['priority'] == 'LOW']
    print(f"\n{'='*60}")
    print(f"{fname}: {len(rows)} total, {len(high)} HIGH, {len(med)} MEDIUM, {len(low)} LOW")
    print(f"{'='*60}")
    if high:
        for r in high[:15]:
            print(f"  [{r['theology_score']:>3s}] {r['name'][:60]} ({r['city']}, {r['state']}) [{r['ntee_code']}]")
