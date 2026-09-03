"""Deep audit of the 76K unclassified Muslim gap."""
import sqlite3
conn = sqlite3.connect("churches.db")
c = conn.cursor()

# Gap: no tradition, no muslim_affiliation
print("=== Gap by country (all) ===")
c.execute("""
    SELECT COALESCE(country, 'NULL') as c, COUNT(*) as cnt 
    FROM churches WHERE faith='Islam' 
      AND (tradition IS NULL OR tradition='')
      AND (muslim_affiliation IS NULL OR muslim_affiliation='')
    GROUP BY c ORDER BY cnt DESC
""")
rows = c.fetchall()
for r in rows:
    print(f"  {r[0]:20s}: {r[1]:>7,}")

# What kinds of names are in the gap?
print("\n=== Gap name patterns (samples) ===")
c.execute("""
    SELECT id, name, city, state, country FROM churches 
    WHERE faith='Islam' 
      AND (tradition IS NULL OR tradition='')
      AND (muslim_affiliation IS NULL OR muslim_affiliation='')
    ORDER BY id
""")
all_rows = c.fetchall()
print(f"Total unclassified: {len(all_rows):,}")

# Check common name patterns in the gap
import re
patterns = {
    "masjid/mosque": 0, "islamic/muslim/quran": 0, 
    "sufi/tariqa": 0, "shia/imam/hussein": 0,
    "salafi/ahl_hadith": 0, "deobandi/darul": 0,
    "ahmadi/baitul": 0, "jafari": 0, "hanafi/maliki/shafii/hanbali": 0,
    "no_keyword": 0
}
for r in all_rows:
    n = (r[1] or "").lower()
    city = (r[2] or "").lower()
    if re.search(r'\b(masjid|mosque)\b', n): patterns["masjid/mosque"] += 1
    elif re.search(r'\b(islam|muslim|quran|allah)\b', n): patterns["islamic/muslim/quran"] += 1
    elif re.search(r'\b(sufi|tariqa|naqsh|qadiri|chishti|barelvi|mawlid|zawiya)\b', n): patterns["sufi/tariqa"] += 1
    elif re.search(r'\b(imam|hussein|mahdi|jafari|ahlul.?bayt|majlis|ashura)\b', n): patterns["shia/imam/hussein"] += 1
    elif re.search(r'\b(salafi|ahl.?hadith|tawheed|furqan|dar.?hadith)\b', n): patterns["salafi/ahl_hadith"] += 1
    elif re.search(r'\b(deobandi|darul.?uloom|tablighi)\b', n): patterns["deobandi/darul"] += 1
    elif re.search(r'\b(ahmadi|baitul|masroor|mirza)\b', n): patterns["ahmadi/baitul"] += 1
    elif re.search(r'\b(jafari|ja.?afari)\b', n): patterns["jafari"] += 1
    elif re.search(r'\b(hanafi|maliki|shafi[ei]|hanbali)\b', n): patterns["hanafi/maliki/shafii/hanbali"] += 1
    else: patterns["no_keyword"] += 1

for k, v in patterns.items():
    print(f"  {k:30s}: {v:>7,} ({v/len(all_rows)*100:.1f}%)")

# Check the "no keyword" ones - what are they?
print("\n=== Sample 'no keyword' entries ===")
count = 0
for r in all_rows:
    n = (r[1] or "").lower()
    if not re.search(r'\b(masjid|mosque|islam|muslim|quran|allah|sufi|tariqa|imam|hussein|salafi|deobandi|ahmadi|hanafi|maliki|shafi|hanbali)\b', n):
        if count < 15:
            print(f"  ID={r[0]:>8d} | {str(r[1] or '')[:55]:55s} | {str(r[2] or ''):20s} {r[3] or ''} | {r[4] or ''}")
        count += 1

print(f"\nTotal 'no keyword': {count:,}")

# Also check misclassifications: non-Islamic traditions under Islam
print("\n=== Misclassifications (non-Islamic traditions under Islam) ===")
c.execute("""
    SELECT tradition, COUNT(*) FROM churches 
    WHERE faith='Islam' AND tradition IS NOT NULL AND tradition != ''
      AND tradition NOT IN ('Sunni','Salafi','Hanafi','Twelver','Maliki','Shafii',
                           'Sufi','Muslim','Zaydi','Ibadi','Ahmadiyya','Ismaili',
                           'Bohra','Nation of Islam','Deobandi','Quranist','Hanbali',
                           'Shia','Sunni (Generic)')
      AND muslim_affiliation IS NULL
    GROUP BY tradition ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  {r[0]:25s}: {r[1]:>7,}")

conn.close()
