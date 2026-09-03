import sqlite3, os, time

# Wait for DB unlock
for attempt in range(12):
    try:
        conn = sqlite3.connect('churches.db', timeout=5)
        c = conn.cursor()
        c.execute('SELECT 1')
        break
    except:
        if attempt < 11:
            time.sleep(5)
        else:
            print('DB still locked')
            exit(1)

c.execute('PRAGMA integrity_check')
print(f'Integrity: {c.fetchone()[0]}')
print(f'Size: {os.path.getsize("churches.db")/1024/1024:.0f} MB')

c.execute('SELECT COUNT(*) FROM churches')
total = c.fetchone()[0]
print(f'\nChurches: {total:,}')

# Classification
c.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NULL OR denomination=''")
unclass = c.fetchone()[0]
print(f'Unclassified: {unclass:,} ({round(100-unclass*100/total,1)}% classified)')

c.execute("SELECT COUNT(*) FROM churches WHERE denomination='Non-Denominational'")
print(f'Non-Denom: {c.fetchone()[0]:,}')

c.execute("SELECT COUNT(*) FROM churches WHERE classification_source='nondenom_classifier_v3'")
print(f'Non-Denom (v3 classifier): {c.fetchone()[0]:,}')

# Coverage
c.execute("""
SELECT 
    ROUND(100.0*COUNT(CASE WHEN website IS NOT NULL AND website!='' THEN 1 END)/COUNT(*),1),
    ROUND(100.0*COUNT(CASE WHEN email IS NOT NULL AND email!='' THEN 1 END)/COUNT(*),1),
    ROUND(100.0*COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END)/COUNT(*),1),
    ROUND(100.0*COUNT(CASE WHEN tract_fips IS NOT NULL AND tract_fips!='' THEN 1 END)/COUNT(*),1),
    ROUND(100.0*COUNT(CASE WHEN county_fips IS NOT NULL AND county_fips!='' THEN 1 END)/COUNT(*),1),
    ROUND(100.0*COUNT(CASE WHEN county_median_hh_income IS NOT NULL THEN 1 END)/COUNT(*),1),
    ROUND(100.0*COUNT(CASE WHEN city IS NOT NULL AND city!='' THEN 1 END)/COUNT(*),1)
FROM churches WHERE country='US'
""")
r = c.fetchone()
print(f'\nUS Coverage (of {total:,}):')
print(f'  Website:   {r[0]}%')
print(f'  Email:     {r[1]}%')
print(f'  Geo:       {r[2]}%')
print(f'  Tract:     {r[3]}%')
print(f'  County:    {r[4]}%')
print(f'  ACS:       {r[5]}%')
print(f'  City:      {r[6]}%')

# Top denoms
c.execute("""
SELECT denomination, COUNT(*) FROM churches 
WHERE denomination IS NOT NULL AND denomination!=''
GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 12
""")
print(f'\nTop Denoms:')
for r2 in c.fetchall():
    print(f'  {r2[0][:40]:40s} {r2[1]:>8,}')

# Provenance
c.execute('SELECT COUNT(*) FROM provenance_log')
print(f'\nProvenance log: {c.fetchone()[0]} entries')
c.execute('SELECT COUNT(*) FROM broadcast_ministries')
print(f'Broadcast ministries: {c.fetchone()[0]}')

# Total classified
c.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination!=''")
class_total = c.fetchone()[0]
print(f'\nTotal classified: {class_total:,} ({round(class_total*100/total,1)}%)')

conn.close()
