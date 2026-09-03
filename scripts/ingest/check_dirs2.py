#!/usr/bin/env python3
import re
from pathlib import Path

WPA_DIR = Path('E:/grid/data/wpa')
for f in sorted(WPA_DIR.glob('directoryofchurc*.txt')):
    text = f.read_text(encoding='utf-8', errors='replace')
    # Find title in HTML head
    if '<title>' in text.lower():
        start = text.lower().find('<title>')
        end = text.lower().find('</title>', start)
        if start > 0 and end > start:
            title = text[start+7:end]
            print(f'{f.name}: {title[:100]}')