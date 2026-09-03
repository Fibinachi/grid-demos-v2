"""Check Ireland classification progress."""
import json
path = r'E:\grid\data\ireland_religious_classified.json'
data = json.load(open(path))
print(f"Entries classified: {len(data)}")
faiths = {}
for r in data:
    f = r.get('faith', '?')
    faiths[f] = faiths.get(f, 0) + 1
for k, v in sorted(faiths.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
