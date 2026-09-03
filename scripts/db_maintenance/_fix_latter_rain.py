import sqlite3
conn = sqlite3.connect('churches.db')

print('=== LATTER RAIN CHURCHES ===')
# Find all Latter Rain churches
rows = conn.execute("""
    SELECT id, name, city, state, denomination, classification_source, source
    FROM churches
    WHERE name LIKE '%LATTER RAIN%' OR name LIKE '%LATTER RAIN%'
    ORDER BY state, city
""").fetchall()
print(f'Total "Latter Rain" in name: {len(rows)}')

# Count by current denomination
from collections import Counter
denoms = Counter(r[4] for r in rows)
print('\nCurrent denomination labels:')
for d, n in denoms.most_common():
    print(f'  {d or "(blank)":40s} {n}')

# Count by classification_source
srcs = Counter(r[5] for r in rows)
print('\nClassification sources:')
for s, n in srcs.most_common():
    print(f'  {s or "(blank)":40s} {n}')

# Show a sample
print('\n=== SAMPLE ===')
for r in rows[:20]:
    print(f'  {r[0]:>7}  {r[1][:50]:50s}  {r[2]:15s} {r[3]}  denom={r[4]}  cls={r[5]}')

# ── Also find LDS churches misclassified ──
print('\n=== LDS CHURCHES (actual Latter-day Saints) ===')
lds = conn.execute("""
    SELECT COUNT(*), denomination
    FROM churches
    WHERE (name LIKE '%LATTER-DAY%' OR name LIKE '%LATTER DAY%')
      AND name NOT LIKE '%LATTER RAIN%'
    GROUP BY denomination
    ORDER BY 1 DESC
""").fetchall()
for n, d in lds:
    print(f'  {d or "(blank)":40s} {n}')

# ── Fix plan ──
print('\n=== FIX PLAN ===')
# 1. Reclassify Latter Rain churches as "Latter Rain" denomination
latter_rain_ids = [r[0] for r in rows]
print(f'  1. {len(latter_rain_ids)} churches with "Latter Rain" in name')
print(f'     Set denomination = "Latter Rain Pentecostal"')
print(f'     Set classification_source = "name_heuristic_latter_rain_fix"')

# 2. Check: are any Latter Rain churches currently classified as LDS?
lds_misclass = [r for r in rows if r[4] and 'latter-day' in str(r[4]).lower()]
print(f'  2. Misclassified as LDS: {len(lds_misclass)}')
for r in lds_misclass:
    print(f'     {r[0]} {r[1][:50]} -> {r[4]}')

# 3. General LDS classification check - find ALL churches with denomination = LDS
print('\n=== ALL CHURCHES WITH LDS DENOMINATION ===')
lds_all = conn.execute("""
    SELECT id, name, city, state, classification_source
    FROM churches
    WHERE denomination LIKE '%Latter-day%'
    ORDER BY name
""").fetchall()
print(f'Total with LDS denomination: {len(lds_all)}')
# Check for Latter Rain in this set
lr_in_lds = [r for r in lds_all if 'LATTER RAIN' in str(r[1]).upper()]
print(f'Latter Rain misclassified as LDS: {len(lr_in_lds)}')
for r in lr_in_lds:
    print(f'  {r[0]} {r[1][:50]}')

conn.close()
