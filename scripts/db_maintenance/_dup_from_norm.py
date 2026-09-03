"""How many duplicates did name normalization reveal?"""
import sqlite3
conn = sqlite3.connect('churches.db')

total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]

# Find (name, state) pairs that appear more than once
print('=== POST-NORMALIZATION DUPLICATES ===')
print('(churches with identical UPPER name + state)\n')

dup_pairs = conn.execute("""
    SELECT name, state, COUNT(*) as cnt, GROUP_CONCAT(source, ', ') as sources
    FROM churches
    WHERE name != '' AND state != ''
    GROUP BY name, state
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
""").fetchall()

print(f'Total duplicate (name, state) pairs: {len(dup_pairs):,}')
dup_churches = sum(r[2] for r in dup_pairs)
unique_names = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT name, state FROM churches WHERE name != '' AND state != ''
        GROUP BY 1,2
    )
""").fetchone()[0]
print(f'Churches in duplicate groups: {dup_churches:,}')
print(f'Unique (name, state) pairs: {unique_names:,}')
print(f'Total churches: {total:,}')
print()

# Top duplicate groups
print('=== TOP 20 DUPLICATE GROUPS ===')
for r in dup_pairs[:20]:
    print(f'  {r[2]}x  "{r[0][:50]:50s}"  {r[1]}  sources: {r[3][:80]}')

# Sources within duplicates
print('\n=== DUPLICATE SOURCE PAIRS ===')
source_pairs = conn.execute("""
    SELECT c1.source, c2.source, COUNT(*) as n
    FROM churches c1
    JOIN churches c2 ON UPPER(c1.name) = UPPER(c2.name) 
                     AND UPPER(c1.state) = UPPER(c2.state)
                     AND c1.id < c2.id
    WHERE c1.name != '' AND c1.state != ''
    GROUP BY 1, 2
    ORDER BY 3 DESC
    LIMIT 15
""").fetchall()
for r in source_pairs:
    print(f'  {r[0]:25s} + {r[1]:25s} = {r[2]:>6,} overlaps')

# Estimate: how many are TRUE duplicates (same church) vs coincidental same-name?
# True duplicates: likely from overture_full + irs, overture_full + churchunion_scraper
# Coincidental: "FIRST BAPTIST CHURCH" in Texas (many different cities)
print('\n=== ESTIMATE: TRUE vs COINCIDENTAL ===')
# If a name appears 5+ times in same state, it's likely a generic name, not a true duplicate
generic = sum(1 for r in dup_pairs if r[2] >= 5)
generic_churches = sum(r[2] for r in dup_pairs if r[2] >= 5)
true_dup_pairs = len(dup_pairs) - generic
true_dup_churches = dup_churches - generic_churches
print(f'  High-frequency (5+ per state, likely generic names): {generic:,} groups ({generic_churches:,} churches)')
print(f'  Low-frequency (2-4 per state, likely TRUE duplicates): {true_dup_pairs:,} groups ({true_dup_churches:,} churches)')

# The real question: how many were CAUSED by the normalization?
# We can't know exactly without pre-normalization state, but we can estimate:
# Before: names like "The First Baptist Church" vs "FIRST BAPTIST CHURCH" were different
# After: both are "FIRST BAPTIST CHURCH" — now they match
# 
# The largest new-duplicate source would be overture_full (Title Case with "The") 
# matching against irs (ALL CAPS without "The")

conn.close()
