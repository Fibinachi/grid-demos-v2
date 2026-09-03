"""Analyze umbrella corp / diocese / legal entity patterns in church names."""
import sqlite3
import re

db = sqlite3.connect(r'E:\grid\churches.db')

patterns = [
    # Ukrainian / Eastern Rite corp patterns
    ("UKRAINIAN CATH EPISC CORP", "Ukrainian Catholic Episcopal Corp"),
    ("CATHOLIC EPISCOPAL CORPORATION", "Catholic Episcopal Corp"),
    ("UKRAINIAN CATHOLIC EPISCOPAL CORPORATION", "Ukrainian Catholic Episcopal Corp"),
    ("UKRAINIAN CATH EPISC CORP", "Ukrainian Cath Episc Corp"),
    ("UKR CATH EPISC CORP", "Ukr Cath Episc Corp"),
    ("GREEK CATHOLIC EPISCOPAL CORPORATION", "Greek Catholic Episcopal Corp"),
    
    # "CORPORATION OF" patterns
    ("CORPORATION OF THE", "Corporation of the"),
    ("CORPORATION OF", "Corporation of"),
    ("EPISCOPAL CORPORATION OF", "Episcopal Corporation of"),
    ("EPISCOPAL CORP OF", "Episcopal Corp of"),
    ("EPISC CORP OF", "Episc Corp of"),
    
    # "DIOCESE OF" / "ARCHDIOCESE OF" / "ARCHDIOCESAN"
    ("ARCHDIOCESE OF", "Archdiocese of"),
    ("DIOCESE OF", "Diocese of"),
    ("ARCHDIOCESAN", "Archdiocesan"),
    
    # Trust / foundation / society prefixes
    ("TRUST UNDER", "Trust under"),
    ("TRUSTEES OF", "Trustees of"),
    ("FOUNDATION", "Foundation"),
    
    # French Canadian fabric patterns
    ("FABRIQUE DE LA PAROISSE", "Fabrique de la paroisse"),
    ("LA FABRIQUE DE", "La fabrique de"),
    ("FABRIQUE DE", "Fabrique de"),
    ("FABRIQUE ST", "Fabrique St"),
    ("FABRIQUE SAINT", "Fabrique Saint"),
    
    # League / society / council prefixes (non-church entities)
    ("CATHOLIC WOMEN'S LEAGUE", "Catholic Women's League"),
    ("KNIGHTS OF COLUMBUS", "Knights of Columbus"),
    ("CATHOLIC MEN'S", "Catholic Men's"),
    
    # "OBLATES OF" patterns
    ("OBLATES OF MARY", "Oblates of Mary"),
    ("OBLATES OF", "Oblates of"),
    
    # "CORP" standalone
    ("CORP OF", "Corp of"),
    (" CORP ", " Corp "),
    (" CORPORATION ", " Corporation "),
]

print("=" * 100)
print("  UMBRELLA / LEGAL ENTITY PATTERNS IN CHURCH NAMES")
print("=" * 100)

for pattern, label in patterns:
    cur = db.execute(f"SELECT COUNT(*) FROM churches WHERE name LIKE ?", (f'%{pattern[:50]}%',))
    cnt = cur.fetchone()[0]
    if cnt > 0:
        print(f"  {label:50s} {cnt:>8,} records")

# Also look for "INC" after certain patterns
print()
print("-" * 100)
print("  INC / INC. breakdown (how many have INC vs proper name)")
print("-" * 100)
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '% INC' OR name LIKE '% INC.'")
total_inc = cur.fetchone()[0]
print(f"  Total names ending in INC/INC.: {total_inc:,}")

# Show some truncated names where the name looks like it has corp boilerplate
print()
print("=" * 100)
print("  SAMPLE TRUNCATED/CORP NAMES (len >= 55)")
print("=" * 100)
cur = db.execute("""
    SELECT name, LENGTH(name) FROM churches 
    WHERE LENGTH(name) >= 55 
      AND (name LIKE '%CORP%' OR name LIKE '%CORPORATION%' OR name LIKE '%DIOCESE%')
    LIMIT 30
""")
for r in cur.fetchall():
    print(f"  ({r[1]:2d}) {r[0]}")

print()
print("=" * 100)
print("  SAMPLE NAMES WITH 'CORPORATION OF' OR 'CORP OF'")
print("=" * 100)
cur = db.execute("""
    SELECT name, LENGTH(name) FROM churches 
    WHERE name LIKE '%CORP OF%' OR name LIKE '%CORPORATION OF%'
    LIMIT 30
""")
for r in cur.fetchall():
    print(f"  ({r[1]:2d}) {r[0]}")

db.close()
