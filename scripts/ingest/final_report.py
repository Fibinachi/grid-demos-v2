#!/usr/bin/env python3
"""
Final WPA extraction report.
"""
import sqlite3

conn = sqlite3.connect('E:/grid/wpa.db')

print("=" * 60)
print("WPA CHURCH DIRECTORY EXTRACTION - FINAL REPORT")
print("=" * 60)

total = conn.execute("SELECT COUNT(*) FROM wpa_churches").fetchone()[0]
print(f"\nTotal churches extracted: {total}")

print("\nBreakdown by state:")
for state, count in conn.execute("SELECT state, COUNT(*) FROM wpa_churches GROUP BY state ORDER BY COUNT(*) DESC").fetchall():
    pct = count / total * 100
    print(f"  {state}: {count} ({pct:.1f}%)")

print("\nData quality check:")
long_entries = conn.execute("SELECT COUNT(*) FROM wpa_churches WHERE LENGTH(church_name) > 80").fetchone()[0]
short_entries = conn.execute("SELECT COUNT(*) FROM wpa_churches WHERE LENGTH(church_name) < 10").fetchone()[0]
print(f"  Long (>80 chars): {long_entries}")
print(f"  Short (<10 chars): {short_entries}")

print("\nFiles ready for integration:")
print("  - E:/grid/data/wpa/wpa_cleaned_final.json (cleaned entries)")
print("  - E:/grid/wpa.db (sqlite database)")

conn.close()