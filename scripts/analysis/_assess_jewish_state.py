"""Assess current state of US Judaism entries for deepseek scan."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Count all Judaism entries in US
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US'")
total = c.fetchone()[0]
print(f"Total Judaism in US: {total:,}")

# By landmark_type
c.execute("SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' GROUP BY landmark_type ORDER BY COUNT(*) DESC")
print("\nBy landmark_type:")
for row in c.fetchall():
    print(f"  {row[0]:20s} {row[1]:>7,}")

# By tradition
c.execute("SELECT COALESCE(tradition,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' GROUP BY tradition ORDER BY COUNT(*) DESC")
print("\nBy tradition:")
for row in c.fetchall():
    print(f"  {row[0]:20s} {row[1]:>7,}")

# By state (all)
c.execute("SELECT state, COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' GROUP BY state ORDER BY COUNT(*) DESC")
print("\nBy state:")
for row in c.fetchall():
    print(f"  {row[0] or 'NULL':20s} {row[1]:>7,}")

# Entries with problematic types
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='US' AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))")
bad = c.fetchone()[0]
print(f"\nProblematic (NULL/church/chapel/etc): {bad:,}")

# Also check if there's a deepseek log or result tracking table
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%deepseek%'").fetchall()
print(f"\nDeepseek tables: {[t[0] for t in tables]}")

conn.close()
