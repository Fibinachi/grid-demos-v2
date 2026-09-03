#!/usr/bin/env python3
"""Examine RI Baptist format in detail."""
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

text = load_clean_text(WPA_DIR / "inventoryofchurc00unse_0.txt")

# Find where actual entries start
idx = text.find("73 First Baptist Church, 1805")
print(f"Found entry at {idx}")
if idx < 0:
    # Try the other pattern
    idx = text.find("Page Baptist Churches")
    print(f"Found section at {idx}")

content = text[idx:idx+20000] if idx > 0 else text[60000:26000]
print(f"\nContent from {idx}:")
print(content[:3000])