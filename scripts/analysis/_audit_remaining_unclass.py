"""Audit the 2,009 remaining unclassified Islam records."""
import sqlite3, re
conn = sqlite3.connect("churches.db")
c = conn.cursor()

c.execute("""
    SELECT id, name, city, country FROM churches 
    WHERE faith='Islam' AND (tradition IS NULL OR tradition='')
    ORDER BY id
""")
rows = c.fetchall()
print(f"Remaining unclassified: {len(rows)}")

# Categorize
categories = {
    "christian_name": [],  # Church/Christ/Saint in name
    "islamic_name": [],    # Islamic/masjid/mosque etc.
    "other_name": [],      # Foundation, center, etc.
}

for r in rows:
    n = (r[1] or "").lower()
    if re.search(r'\b(church|christ|catholic|saint|st\.|trinity|bible|gospel|chapel|cathedral|monastery|parish)\b', n):
        categories["christian_name"].append(r)
    elif re.search(r'\b(islam|muslim|masjid|mosque|quran|allah|ummah|halal|iman|al-|darul|salafi|sufi|tariqa|shia|sunni)\b', n):
        categories["islamic_name"].append(r)
    else:
        categories["other_name"].append(r)

for k, v in categories.items():
    print(f"\n{k:20s}: {len(v):>5,}")
    if v:
        for r in v[:10]:
            print(f"  ID={r[0]:>8d} | {str(r[1] or '')[:55]:55s} | {str(r[2] or ''):20s} {r[3] or ''}")

# Fix Christian-named ones
print("\n=== Fixing Christian-named misclassifications ===")
fix_count = 0
for r in categories["christian_name"]:
    ch_id, name, city, country = r
    c.execute("UPDATE churches SET faith='Christian', tradition=NULL, taxonomy_id=NULL WHERE id=?", (ch_id,))
    fix_count += 1
    
print(f"Fixed {fix_count} Christian-named → Christian faith")

# The Islamic-named ones just need a default tradition
print(f"\n=== Setting default tradition for Islamic-named ({len(categories['islamic_name'])} records) ===")
for r in categories["islamic_name"]:
    ch_id = r[0]
    c.execute("UPDATE churches SET tradition='Sunni', muslim_affiliation='Sunni', muslim_confidence=0.25, muslim_classification_source='name_bare_fallback' WHERE id=?", (ch_id,))

print(f"Updated {len(categories['islamic_name'])} records")

conn.commit()

# Final check
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND (tradition IS NULL OR tradition='')")
remaining = c.fetchone()[0]
print(f"\nStill unclassified after fix: {remaining}")
print(f"Other-name remaining: {len(categories['other_name'])} (these need manual review)")

conn.close()
