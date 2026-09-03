#!/usr/bin/env python3
import re
from pathlib import Path

WPA_DIR = Path('E:/grid/data/wpa')

for fname in ['directoryofchurc0000cali.txt', 'inventoryofchurc0006flor.txt', 'inventoryofchurc0000verm.txt']:
    text = (WPA_DIR / fname).read_text(encoding='utf-8', errors='replace')
    m = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL | re.IGNORECASE)
    if m:
        print(f'{fname}: pre block found, {len(m.group(1))} chars')
    else:
        # Check for plain text content
        text_only = re.sub(r'<[^>]+>', ' ', text)
        text_only = re.sub(r'\s{2,}', ' ', text_only).strip()
        print(f'{fname}: NO pre block, text content: {len(text_only)} chars')