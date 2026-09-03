#!/usr/bin/env python3
import re
from pathlib import Path

WPA_DIR = Path('E:/grid/data/wpa')

for fname in ['directoryofchurc0000cali.txt', 'inventoryofchurc0006flor.txt', 'inventoryofchurc0000verm.txt']:
    text = (WPA_DIR / fname).read_text(encoding='utf-8', errors='replace')
    m = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL | re.IGNORECASE)
    if m:
        content = m.group(1)
        print(f'{fname}: pre block exists but is {len(content)} chars')
        print(f'  Inside: {repr(content[:200])}')