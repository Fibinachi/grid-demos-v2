#!/usr/bin/env python3
import re
from pathlib import Path

WPA_DIR = Path('E:/grid/data/wpa')
for f in sorted(WPA_DIR.glob('inventoryofchurc*.txt'))[:10]:
    text = f.read_text(encoding='utf-8', errors='replace')
    # Find title - look for actual text between title tags
    m = re.search(r'<title>Full text of (.*?)</title>', text, re.DOTALL)
    if m:
        title = m.group(1)
        print(f'{f.name}: {title[:80]}')