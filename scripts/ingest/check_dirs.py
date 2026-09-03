#!/usr/bin/env python3
import re
from pathlib import Path

WPA_DIR = Path('E:/grid/data/wpa')

# Check all directory files
for f in sorted(WPA_DIR.glob('directoryofchurc*.txt')):
    text = f.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'Full text of[^<]*"([^"]*)"', text)
    title = m.group(1)[-120:] if m else 'UNKNOWN'
    print(f'{f.name}: {title}')