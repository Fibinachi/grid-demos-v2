#!/usr/bin/env python3
import re
from pathlib import Path

WPA_DIR = Path('E:/grid/data/wpa')
print("=== INVENTORY FILES ===")
for f in sorted(WPA_DIR.glob('inventoryofchurc*.txt')):
    text = f.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'<title>Full text of (.*?)</title>', text, re.DOTALL)
    if m:
        title = m.group(1).replace('&quot;', '').strip()
        print(f'{f.name}: {title}')

print("\\n=== DIRECTORY FILES ===")
for f in sorted(WPA_DIR.glob('directoryofchurc*.txt')):
    text = f.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'<title>Full text of (.*?)</title>', text, re.DOTALL)
    if m:
        title = m.group(1).replace('&quot;', '').strip()
        print(f'{f.name}: {title}')