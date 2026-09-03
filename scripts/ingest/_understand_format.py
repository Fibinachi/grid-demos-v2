#!/usr/bin/env python3
"""Understand the RI Baptist inventory format in detail."""

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

# Find the actual numbered inventory section
inventory_start = text.find("Page Baptist Churches - Northern")
if inventory_start < 0:
    inventory_start = text.find("43 FIRST BAPTIST")
print(f"Inventory starts at: {inventory_start}")

content = text[inventory_start:inventory_start+150000]

# Save to file for inspection
with open('C:/Users/charlesp/AppData/Local/Temp/kilo/ri_inventory_section.txt', 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved first 150K chars of inventory section to ri_inventory_section.txt")

# Now let's look at what a typical entry looks like
print("\n=== Looking for numbered patterns ===")
# The format appears to be: "6 First Baptist Church..." followed by content on same line
# Let's look for "6 " followed by typical Baptist church naming
samples = re.findall(r'((\d{1,3})\s+(.*?)(?=\s{2,}\d{1,3}\s|$))', content[:50000])
print(f"Found {len(samples)} potential numbered sections")
for s in samples[:10]:
    print(f"  - {s[1]}. {s[2][:80]}")