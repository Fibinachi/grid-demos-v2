#!/usr/bin/env python3
"""Extract numbered Baptist church entries - the actual archival inventory format."""

import re
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")

def load_clean_text(filepath):
    text = filepath.read_text(encoding='utf-8', errors='replace')
    clean = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL|re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

fp = WPA_DIR / "inventoryofchurc00unse_0.txt"
text = load_clean_text(fp)

# The format is: number Churc,h name, dates, location, page refs
# Look for patterns like: "43 FIRST BAPTIST..." or "1 FIRST SIX PRINCIPLE..."

# Find the actual numbered inventory section
# Skip the introduction (first ~60K chars) and TOC
inventory_start = text.find("43 FIRST BAPTIST")
if inventory_start < 0:
    # Fallback - look for "Page Baptist Churches -" which starts the actual entry list
    for pattern in ["Page Baptist Churches", "Page", "1 FIRST", "2 SECOND"]:
        idx = text.find(pattern)
        if idx > 0:
            print(f"Found '{pattern}' at {idx}")
            inventory_start = idx
            break

print(f"Inventory starts at: {inventory_start}")
content = text[inventory_start:]

# Split by numbered entries
# Pattern: number followed by church/congregation name
entries = []
for m in re.finditer(r'(\d{1,3})\s+([A-Z][A-Z\s]{10,150}?)(?:,\s*([\d\-–\?]{1,30}))', content):
    num = m.group(1)
    name = m.group(2).strip()
    dates = m.group(3).strip() if m.group(3) else ""
    
    # Get the rest of the line (location, page refs)
    rest_start = m.end()
    rest_end = content.find("\n", rest_start) if "\n" in content else rest_start + 300
    rest = content[rest_start:rest_start+300]
    
    entries.append({'num': int(num), 'name': name, 'dates': dates, 'rest': rest})

print(f"Found {len(entries)} entries")
print("\n=== First 20 entries ===")
for e in sorted(entries, key=lambda x: x['num'])[:20]:
    print(f"{e['num']}. {e['name'][:60]} ({e['dates']})")
    print(f"   {e['rest'][:120]}...")
    print()