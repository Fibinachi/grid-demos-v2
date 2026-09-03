import json
from pathlib import Path

entries = json.loads(Path('E:/grid/data/wpa/clean_wpa_entries.json').read_text())

print('=== Sample clean entries ===')
for e in entries[:20]:
    print(f"  {e['state']}: {e['church_name'][:80]}")