"""Check email types and pastor targeting capability."""
import csv, re, sqlite3, os

d = r'E:\grid'

# Get Phase 1 chunk 0 from EC2
scp_path = os.path.join(d, 'scraped_chunk_0.csv')
if not os.path.exists(scp_path):
    os.system(f'scp -i ~/.ssh/grantwizard-key.pem ubuntu@18.118.169.15:~/scraped_chunk_0.csv "{scp_path}"')

r = list(csv.DictReader(open(scp_path, encoding='utf-8')))

total = len(r)
with_email = sum(1 for x in r if x.get('email','').strip())
print(f'Phase 1 chunk 0: {total} total, {with_email} with email')

# Classify email types
generic = 0
pastor_titled = 0
name_likely = 0
for x in r:
    e = (x.get('email','') or '').strip().lower()
    if not e or '@' not in e:
        continue
    local = e.split('@')[0]
    if local in ('info','contact','office','admin','hello','connect','welcome','mail','church','secretary','communications','support','feedback','media','webmaster','service'):
        generic += 1
    elif any(w in local for w in ['pastor','rev','reverend','bishop','minister','clergy','chaplain','priest','vicar','rector','father']):
        pastor_titled += 1
    else:
        name_likely += 1

print(f'  Generic (info@, office@): {generic} ({generic/with_email*100:.0f}%)')
print(f'  Pastor-titled: {pastor_titled} ({pastor_titled/with_email*100:.0f}%)')
print(f'  Named/staff: {name_likely} ({name_likely/with_email*100:.0f}%)')

# Show pastor-titled
print('\nPastor-titled emails:')
for x in r:
    e = (x.get('email','') or '').strip().lower()
    local = e.split('@')[0]
    if any(w in local for w in ['pastor','rev','reverend','bishop','rector']):
        n = x.get('church_name','')[:40]
        print(f'  {e}  |  {n}')

# Cross-reference with DB
conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM churches WHERE pastor_name != "" AND email != ""')
both = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM churches WHERE pastor_name != "" AND email = "" AND website != ""')
name_web_no_email = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM churches WHERE pastor_name != "" AND email = ""')
name_no_email = cur.fetchone()[0]

print(f'\n=== Cross-reference ===')
print(f'Pastor name + email known: {both}')
print(f'Pastor name + website but NO email: {name_web_no_email}')
print(f'Pastor name known, no email at all: {name_no_email}')
print(f'\nCAN target: {both} (direct pastor email)')
print(f'CAN GUESS: {name_web_no_email} (pastor name + website = guessable)')

conn.close()
