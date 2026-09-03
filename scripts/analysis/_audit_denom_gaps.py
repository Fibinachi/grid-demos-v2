#!/usr/bin/env python3
"""Audit DB gaps by denomination to prioritize scraping targets."""
import sqlite3, os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db = sqlite3.connect(os.path.join(PROJECT_DIR, "churches.db"))
total = 258006

print("=== Faith Traditions ===")
for r in db.execute("SELECT faith_tradition, COUNT(*) FROM churches GROUP BY faith_tradition ORDER BY COUNT(*) DESC"):
    print(f"  {r[0]:20s} {r[1]:>7,} ({r[1]/total*100:.1f}%)")

print()
print("=== Denomination Name Matches (keyword in name) ===")
checks = [
    ("Catholic (name/denom)", "%catholic%"),
    ("Baptist", "%baptist%"),
    ("Methodist", "%methodist%"),
    ("Lutheran", "%lutheran%"),
    ("Presbyterian", "%presbyterian%"),
    ("Episcopal/Anglican", "%episcopal%"),
    ("Pentecostal", "%pentecostal%"),
    ("Church of God", "%church of god%"),
    ("Assemblies of God", "%assemblies of god%"),
    ("LDS/Mormon", "%latter-day%"),
    ("Seventh-day Adventist", "%seventh-day%"),
    ("Non-denominational", "%non-denominational%"),
    ("Calvary Chapel", "%calvary chapel%"),
    ("Nazarene", "%nazarene%"),
    ("Christian Church (Disciple)", "%christian church%"),
]
for label, pattern in checks:
    cnt = db.execute("SELECT COUNT(*) FROM churches WHERE LOWER(name) LIKE ?", (pattern,)).fetchone()[0]
    has_web = db.execute("SELECT COUNT(*) FROM churches WHERE LOWER(name) LIKE ? AND website IS NOT NULL AND website != ''", (pattern,)).fetchone()[0]
    has_email = db.execute("SELECT COUNT(*) FROM churches WHERE LOWER(name) LIKE ? AND email IS NOT NULL AND email != ''", (pattern,)).fetchone()[0]
    web_pct = has_web/cnt*100 if cnt else 0
    email_pct = has_email/cnt*100 if cnt else 0
    print(f"  {label:30s} {cnt:>6,} ({cnt/total*100:.1f}%)  web={web_pct:.0f}%  email={email_pct:.0f}%")

# US Catholic parishes: ~17,000 actual, we have ~2,000
print()
cath = db.execute("SELECT COUNT(*) FROM churches WHERE LOWER(denomination) LIKE '%catholic%' OR LOWER(name) LIKE '%catholic%'").fetchone()[0]
print(f"Catholic identified: {cath:,} / ~17,000 expected US parishes = {(17000-cath):,} MISSING")

# Episcopal: ~6,500 congregations
epis = db.execute("SELECT COUNT(*) FROM churches WHERE LOWER(denomination) LIKE '%episcopal%' OR LOWER(name) LIKE '%episcopal%'").fetchone()[0]
print(f"Episcopal identified: {epis:,} / ~6,500 expected = {(6500-epis):,} MISSING")

# ELCA: ~8,500
luth = db.execute("SELECT COUNT(*) FROM churches WHERE LOWER(name) LIKE '%lutheran%'").fetchone()[0]
print(f"Lutheran identified: {luth:,} / ~8,500 ELCA + ~5,500 LCMS = ~14,000 expected")

# UMC: ~30,000
umc = db.execute("SELECT COUNT(*) FROM churches WHERE LOWER(name) LIKE '%methodist%'").fetchone()[0]
print(f"Methodist identified: {umc:,} / ~30,000 UMC expected")

# PCUSA: ~8,500
pres = db.execute("SELECT COUNT(*) FROM churches WHERE LOWER(name) LIKE '%presbyterian%'").fetchone()[0]
print(f"Presbyterian identified: {pres:,} / ~8,500 PCUSA expected")

# SBC: ~47,000
bap = db.execute("SELECT COUNT(*) FROM churches WHERE LOWER(name) LIKE '%baptist%'").fetchone()[0]
print(f"Baptist identified: {bap:,} / ~47,000 SBC expected")

db.close()
