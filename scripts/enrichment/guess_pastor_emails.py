"""Guess pastor emails from known names + websites."""
import sqlite3, csv, re, os, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

d = r'E:\grid'
conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()

# Get all churches with pastor name AND website
cur.execute('''
    SELECT ein, pastor_name, website, name, state
    FROM churches 
    WHERE pastor_name != '' AND website != ''
''')
rows = cur.fetchall()
conn.close()

print(f'Churches with pastor name + website: {len(rows)}')

# Extract first name from pastor ICO field
def extract_first_name(pastor_ico):
    ico = pastor_ico.upper().strip()
    # Remove common titles
    for title in ['REV','REVEREND','PASTOR','BISHOP','FATHER','MINISTER','DR','DOCTOR','MOTHER','SISTER','BROTHER','MRS','MS','MR','HONORABLE','SR','JR','II','III','IV']:
        ico = ico.replace(title, '')
    ico = ico.strip().lstrip('.,- ').strip()
    # Get first word
    first = ico.split()[0] if ico.split() else ''
    return first.strip().lower() if first else ''

def extract_last_name(pastor_ico):
    ico = pastor_ico.upper().strip()
    for title in ['REV','REVEREND','PASTOR','BISHOP','FATHER','MINISTER','DR','DOCTOR','MOTHER','SISTER','BROTHER','MRS','MS','MR','HONORABLE']:
        ico = ico.replace(title, '')
    ico = ico.strip().lstrip('.,- ').strip()
    parts = ico.split()
    # Last name is usually the longest remaining word (not a suffix)
    name = None
    for p in parts:
        p = p.strip('.,- ')
        if p and p not in ('JR','SR','II','III','IV','DE','LA','VAN','VON'):
            name = p
    return name.lower().strip() if name else ''

def clean_domain(website):
    from gw_filters.clean import clean_domain as _clean
    return _clean(website)

# Generate guesses
guesses = []
for ein, pastor_ico, website, church_name, state in rows:
    domain = clean_domain(website)
    if not domain:
        continue
    first = extract_first_name(pastor_ico)
    last = extract_last_name(pastor_ico)
    
    patterns = []
    if first and last:
        patterns.append(f'{first}.{last}@{domain}')
        patterns.append(f'{first}{last}@{domain}')
        patterns.append(f'{first[0]}{last}@{domain}')
        patterns.append(f'{last}.{first}@{domain}')
    patterns.append(f'pastor@{domain}')
    
    # Extract first name from church for firstname@domain
    church_first = ''
    for w in re.findall(r"[A-Z][a-z]+", church_name):
        if w.lower() not in ('the','of','a','an','and','in','at','for','to','by','with','on','church','ministry','chapel','community','fellowship','center','baptist','methodist','lutheran','presbyterian','pentecostal','episcopal','catholic','christian','assembly','gospel','holiness','temple','cathedral','mission','outreach','garden','park','valley','hill','lake','springs','ridge','heights','first','second','third','new','old','mount','mount','st','saint','san','santa','la','las','los','el','de','del','of','the'):
            church_first = w.lower()
            break
    
    if church_first:
        patterns.append(f'{church_first}@{domain}')
    
    guesses.append({
        'ein': ein,
        'church_name': church_name[:60],
        'website': website,
        'domain': domain,
        'pastor_ico': pastor_ico[:50],
        'first_name': first,
        'last_name': last,
        'guesses': list(set(patterns)),
        'state': state,
    })

print(f'Churches with guessable emails: {len(guesses)}')
print(f'Total patterns to check: {sum(len(g["guesses"]) for g in guesses)}')

# Test guesses via DNS/HTTP (fast check)
import urllib.request, socket

def check_email(email):
    """Quick check if email domain resolves."""
    if not email or '@' not in email:
        return False
    domain = email.split('@')[1]
    try:
        socket.getaddrinfo(domain, 80, socket.AF_INET, socket.SOCK_STREAM, 0, socket.AI_CANONNAME)
        return True
    except:
        return False

results = []
checked = 0

for g in guesses:
    best = ''
    for email in g['guesses']:
        if check_email(email):
            best = email
            break
    
    results.append({
        'church_name': g['church_name'],
        'website': g['website'],
        'domain': g['domain'],
        'pastor_name': g['pastor_ico'],
        'first_name': g['first_name'],
        'last_name': g['last_name'],
        'email': best,
        'email_source': 'guess',
        'state': g['state'],
        'ein': g['ein'],
    })
    checked += 1
    
    if checked % 500 == 0:
        found = sum(1 for r in results if r['email'])
        print(f'  {checked}/{len(guesses)} | Found: {found}')

# Save
out = d + '/pastor_email_guesses.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['church_name','website','domain','pastor_name','first_name','last_name','email','email_source','state','ein'])
    w.writeheader()
    w.writerows(results)
print(f'\nSaved: {out}')

found = sum(1 for r in results if r['email'])
print(f'Emails guessed: {found}/{len(results)} ({found/len(results)*100:.1f}%)')

# Update SQLite with guessed emails
conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()
updated = 0
for r in results:
    if r['email']:
        cur.execute('''
            UPDATE churches SET email = ?, email_validated = 0, source = CASE WHEN source NOT LIKE "%guess%" THEN source || ",guess" ELSE source END
            WHERE ein = ? AND (email = '' OR email IS NULL)
        ''', (r['email'], r['ein']))
        if cur.rowcount:
            updated += 1
conn.commit()
print(f'Updated SQLite: {updated} guessed emails added')
conn.close()
