import json
from pathlib import Path

entries = json.loads(Path('E:/grid/data/wpa/wpa_final_clean.json').read_text())

print("=== Sample valid entries ===")
for e in entries[:30]:
    print(f"  {e['church_name'][:60]}")

print(f"\nTotal: {len(entries)} entries")