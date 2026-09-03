#!/usr/bin/env python3
import re
from pathlib import Path

WPA_DIR = Path('E:/grid/data/wpa')
for fname in ['inventoryofchurc00hist.txt', 'inventoryofchurc00hist_0.txt', 'inventoryofchurc00hist_1.txt', 'inventoryofchurc0006flor.txt']:
    text = (WPA_DIR / fname).read_text(encoding='utf-8', errors='replace')
    m = re.search(r'Full text of[^<]*"([^"]*)"', text)
    if m:
        print(f'{fname}: {m.group(1)}')