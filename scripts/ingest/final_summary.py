#!/usr/bin/env python3
"""
Summary of WPA extraction results.
"""
import sqlite3

conn = sqlite3.connect('E:/grid/wpa.db')

print("=== WPA Database Summary ===")
print(f"Total churches extracted: {conn.execute('SELECT COUNT(*) FROM wpa_churches').fetchone()[0]}")

print("\nBy state:")
for state, count in conn.execute("SELECT state, COUNT(*) FROM wpa_churches GROUP BY state ORDER BY COUNT(*) DESC").fetchall():
    print(f"  {state}: {count}")

print("\n=== Sample clean entries (AR) ===")
clean_ar = [r[0] for r in conn.execute("SELECT church_name FROM wpa_churches WHERE state='AR' AND LENGTH(church_name) < 40 LIMIT 15").fetchall()]
for e in clean_ar:
    print(f"  {e}")

conn.close()

print("\nFiles created:")
print("  - E:/grid/data/wpa/wpa_all_final.json (all extracted entries)")
print("  - E:/grid/wpa.db (sqlite database)")
print("  - E:/grid/scripts/ingest/wpa_all_complete.py (extraction script)")