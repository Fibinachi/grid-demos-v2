"""Get CSV coordinates for ground truth churches."""
import csv

with open('Churches_4106776180121190077.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# Look for specific churches
targets = {
    "Christ the King Catholic": None,
    "New Day Fellowship": None,
    "Miracle Temple Ministries": None,
    "Shiloh Missionary Baptist": None,
}

for r in rows:
    name = r['LOCATION'].upper()
    for t in targets:
        if t.upper() in name and targets[t] is None:
            targets[t] = {
                'name': r['LOCATION'],
                'x': float(r['x']),
                'y': float(r['y']),
                'addr': r['FULL_ADDR'],
                'community': r['COMMUNITY'],
            }

for t, d in targets.items():
    if d:
        print(f"✓ {t}: x={d['x']:.2f}, y={d['y']:.2f}, addr={d['addr']}, community={d['community']}")
    else:
        print(f"✗ {t}: NOT in CSV")
