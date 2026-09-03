#!/usr/bin/env python3
"""Standardize faith_tradition='Judaism' as the generic label."""
import sqlite3
conn = sqlite3.connect(r'E:\grid\churches.db')
cur = conn.cursor()
cur.execute("""
    UPDATE churches SET faith_tradition='Judaism'
    WHERE faith='Jewish' 
    AND (faith_tradition='Jewish' OR faith_tradition IS NULL OR faith_tradition='')
""")
print(f"Fixed: {cur.rowcount} rows")
conn.commit()

# Verify
print("\nDistribution after fix:")
for row in cur.execute("SELECT faith_tradition, COUNT(*) FROM churches WHERE faith='Jewish' GROUP BY faith_tradition ORDER BY COUNT(*) DESC"):
    print(f"  {str(row[0] or 'NULL'):30s} {row[1]:>8}")
conn.close()
