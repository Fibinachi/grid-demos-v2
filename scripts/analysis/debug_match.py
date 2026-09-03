"""Debug deep profile matching"""
import csv, sqlite3

conn = sqlite3.connect('/home/ec2-user/grantwizard/churches.db')
cur = conn.cursor()

with open('/home/ec2-user/grantwizard/data/deep_profiles.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f'Total deep profile rows: {len(rows)}')

# Check for website matches
matched = 0
misses = 0
sample_misses = []
sample_matched = []
for row in rows:
    website = (row.get('website') or '').strip().lower()
    if not website:
        misses += 1
        continue
    
    cur.execute("SELECT id, website FROM churches WHERE LOWER(website)=?", (website,))
    result = cur.fetchone()
    if result:
        matched += 1
        if len(sample_matched) < 3:
            sample_matched.append((row.get('church_name'), website))
    else:
        # Try with www prefix variations
        w2 = website.replace('https://', '').replace('http://', '').lstrip('www.').rstrip('/')
        cur.execute("SELECT id, website FROM churches WHERE LOWER(website) LIKE ?", ('%' + w2 + '%',))
        result2 = cur.fetchone()
        if result2:
            matched += 1
            if len(sample_matched) < 5:
                sample_matched.append((row.get('church_name'), website, '-> fuzzy', result2[1]))
        else:
            misses += 1
            if len(sample_misses) < 5:
                sample_misses.append((row.get('church_name'), website))

print(f'Matched: {matched}')
print(f'Missed: {misses}')

print('\nSample matches:')
for s in sample_matched:
    print(f'  {s}')

print('\nSample misses:')
for s in sample_misses:
    print(f'  {s}')

# Check what websites exist in the DB for Phase 1
cur.execute("SELECT COUNT(DISTINCT website) FROM churches WHERE source='phase1' AND website != ''")
p1 = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches WHERE source='phase1' AND website != ''")
p1_total = cur.fetchone()[0]
print(f'\nPhase 1 unique websites in DB: {p1} (out of {p1_total} records)')

conn.close()
