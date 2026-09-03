"""Audit schools in churches.db — schema exploration and school counts"""
import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")
cur = db.cursor()

# Tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [t[0] for t in cur.fetchall()]
print("=== TABLES ===")
for t in tables:
    print(t)

print()

# Churches columns
cur.execute("PRAGMA table_info(churches)")
cols = cur.fetchall()
print("=== CHURCHES COLUMNS ===")
for c in cols:
    nullable = "NOT NULL" if c[3] else "NULL"
    default = f" default={c[4]}" if c[4] else ""
    print(f"  {c[1]:30s} {c[2]:20s} {nullable}{default}")

print()

# Look for school-related tables
for t in tables:
    if 'school' in t.lower() or 'education' in t.lower():
        cur.execute(f"PRAGMA table_info({t})")
        cols2 = cur.fetchall()
        print(f"=== {t} COLUMNS ===")
        for c in cols2:
            nullable = "NOT NULL" if c[3] else "NULL"
            print(f"  {c[1]:30s} {c[2]:20s} {nullable}")
        # Count
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  Count: {cur.fetchone()[0]}")
        print()

# Check church_sources
if 'church_sources' in tables:
    cur.execute("PRAGMA table_info(church_sources)")
    cols2 = cur.fetchall()
    print("=== church_sources COLUMNS ===")
    for c in cols2:
        nullable = "NOT NULL" if c[3] else "NULL"
        print(f"  {c[1]:30s} {c[2]:20s} {nullable}")
    cur.execute("SELECT COUNT(*) FROM church_sources")
    print(f"  Count: {cur.fetchone()[0]}")
    print()

# Check church_contacts
if 'church_contacts' in tables:
    cur.execute("PRAGMA table_info(church_contacts)")
    cols2 = cur.fetchall()
    print("=== church_contacts COLUMNS ===")
    for c in cols2:
        nullable = "NOT NULL" if c[3] else "NULL"
        print(f"  {c[1]:30s} {c[2]:20s} {nullable}")
    cur.execute("SELECT COUNT(*) FROM church_contacts")
    print(f"  Count: {cur.fetchone()[0]}")
    print()

# Check enrichment tables
for t in tables:
    if 'enrich' in t.lower():
        cur.execute(f"PRAGMA table_info({t})")
        cols2 = cur.fetchall()
        print(f"=== {t} COLUMNS ===")
        for c in cols2:
            nullable = "NOT NULL" if c[3] else "NULL"
            print(f"  {c[1]:30s} {c[2]:20s} {nullable}")
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  Count: {cur.fetchone()[0]}")
        print()

db.close()
