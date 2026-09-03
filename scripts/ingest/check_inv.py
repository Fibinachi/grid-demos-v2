#!/usr/bin/env python3
import re
from pathlib import Path

WPA_DIR = Path('E:/grid/data/wpa')
for f in sorted(WPA_DIR.glob('inventoryofchurc*.txt')):
    text = f.read_text(encoding='utf-8', errors='replace')
    # Find title in HTML head
    m = re.search(r'Full text of[^<]*"([^"]*)"', text)
    if m:
        title = m.group(1).replace('&quot;', '"')
        print(f'{f.name}: {title[:80]}')