import sqlite3
conn = sqlite3.connect('churches.db')

# Find and fix ALL Latter Rain churches
print('=== FIXING LATTER RAIN CLASSIFICATION ===')

# 1. Fix denomination + classification_source for all Latter Rain churches
updated = conn.execute("""
    UPDATE churches 
    SET denomination = 'Latter Rain Pentecostal',
        classification_source = 'name_heuristic_latter_rain_fix'
    WHERE (UPPER(name) LIKE '%LATTER RAIN%')
      AND (denomination IS NULL 
           OR denomination = '' 
           OR denomination = 'Unknown'
           OR denomination NOT LIKE '%Latter Rain%')
""").rowcount
print(f'  Fixed denomination: {updated} churches')

# 2. Count remaining
remaining = conn.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE UPPER(name) LIKE '%LATTER RAIN%'
""").fetchone()[0]
print(f'  Total Latter Rain churches: {remaining}')

# 3. Verify - show all
print('\n=== VERIFICATION ===')
for r in conn.execute("""
    SELECT id, name, city, state, denomination, classification_source
    FROM churches
    WHERE UPPER(name) LIKE '%LATTER RAIN%'
    ORDER BY state, city
""").fetchall():
    print(f'  {r[0]:>7}  {r[1][:45]:45s}  {r[2]:15s} {r[3]:3s}  denom={r[4]:35s}  cls={r[5]}')

# 4. Also fix the single LDS/Mormon one if it exists
lds_misclass = conn.execute("""
    SELECT id, name, denomination FROM churches
    WHERE UPPER(name) LIKE '%LATTER RAIN%' AND denomination = 'LDS / Mormon'
""").fetchone()
if lds_misclass:
    conn.execute("""
        UPDATE churches SET denomination = 'Latter Rain Pentecostal',
        classification_source = 'name_heuristic_latter_rain_fix'
        WHERE id = ?
    """, (lds_misclass[0],))
    print(f'\n  Fixed misclassified: {lds_misclass[1]} (was {lds_misclass[2]})')

conn.commit()

# 5. Now verify LDS churches are clean
print('\n=== LDS CHURCHES (should NOT contain Latter Rain) ===')
lds_count = conn.execute("""
    SELECT COUNT(*) FROM churches
    WHERE denomination LIKE '%Latter-day%' OR denomination LIKE '%LDS%'
""").fetchone()[0]
lds_lr = conn.execute("""
    SELECT COUNT(*) FROM churches
    WHERE (denomination LIKE '%Latter-day%' OR denomination LIKE '%LDS%')
      AND UPPER(name) LIKE '%LATTER RAIN%'
""").fetchone()[0]
print(f'  Total LDS-denominated churches: {lds_count}')
print(f'  Latter Rain in LDS set: {lds_lr} (should be 0)')

conn.close()
print('\nDone.')
