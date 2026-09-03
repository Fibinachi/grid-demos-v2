#!/usr/bin/env python3
"""
Chunked manual OCR correction for WPA files.
Process entries in small batches for manual review/correction.
"""
import json, sqlite3
from pathlib import Path

WPA_DIR = Path("E:/grid/data/wpa")
DB_PATH = Path("E:/grid/wpa.db")

# Load current entries
entries = json.loads((WPA_DIR / "wpa_cleaned_final.json").read_text())

# Chunk into groups of 50 for manual correction
def chunk_entries(entries, size=50):
    for i in range(0, len(entries), size):
        yield entries[i:i+size]

# Show first chunk for manual review
print("=== CHUNK 1 (AR entries) ===")
ar_entries = [e for e in entries if e['state'] == 'AR']
for i, group in enumerate(chunk_entries(ar_entries, 20)):
    print(f"\n--- Batch {i+1} ---")
    for j, e in enumerate(group[:10]):
        print(f"{j+1}. {e['church_name']}")
    if i >= 2:  # Just show first 3 batches
        break