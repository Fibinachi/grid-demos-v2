"""Import all missing datasets into SQLite."""
import csv, sqlite3, re, os

d = r'E:\grid'
conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()

def normalize(name):
    n = re.sub(r'[^A-Z0-9 ]', ' ', (name or '').upper()).strip()
    return re.sub(r'\s+', ' ', n)

def import_master_emails():
    """900 hand-collected church emails."""
    path = d + '/church_master_emails.csv'
    if not os.path.exists(path):
        return 0
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    
    imported = 0
    for r in rows:
        church = normalize(r.get('church_name',''))
        email = (r.get('email','') or '').strip().lower()
        website = (r.get('website','') or '').strip()
        if not church or not email:
            continue
        
        # Try to match by domain
        domain = ''
        if '@' in email:
            domain = email.split('@')[1]
        
        matched = cur.execute("SELECT id, email FROM churches WHERE name = ? AND email = '' LIMIT 1", (church,)).fetchone()
        if not matched and domain:
            matched = cur.execute("SELECT id, email FROM churches WHERE website LIKE ? AND email = '' LIMIT 1", (f'%{domain}%',)).fetchone()
        
        if matched:
            cur.execute("UPDATE churches SET email = ?, has_website = 1, email_validated = 1, last_updated = datetime('now') WHERE id = ?", (email, matched[0]))
        else:
            cur.execute("INSERT INTO churches (name, website, email, source, has_website, email_validated) VALUES (?, ?, ?, 'master', 1, 1)", (church, website, email))
        imported += 1
    
    conn.commit()
    return imported

def import_phase1b():
    """Phase 1b results - 383 emails from 2,767 missing website churches."""
    path = d + '/found_chunk_1b_results.csv'
    if not os.path.exists(path):
        return 0, 0
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    
    imported = 0
    with_email = 0
    for r in rows:
        church = normalize(r.get('church_name',''))
        website = (r.get('website','') or '').strip()
        email = (r.get('email','') or '').strip().lower()
        phone = (r.get('phone','') or '').strip()
        state = (r.get('state','') or '').strip().upper()[:2]
        city = (r.get('city','') or '').strip()
        
        if not church:
            continue
        if email:
            with_email += 1
        
        matched = cur.execute("SELECT id, email FROM churches WHERE name = ? AND state = ? LIMIT 1", (church, state)).fetchone()
        if not matched and state:
            matched = cur.execute("SELECT id, email FROM churches WHERE name = ? AND email = '' LIMIT 1", (church,)).fetchone()
        
        if matched:
            if email and (not matched[1] or matched[1] == ''):
                cur.execute("UPDATE churches SET email = ?, phone = CASE WHEN ? != '' THEN ? ELSE phone END, has_website = 1, email_validated = 1, last_updated = datetime('now') WHERE id = ?", (email, phone, phone, matched[0]))
        else:
            cur.execute("INSERT INTO churches (name, website, email, phone, state, city, source, has_website, email_validated) VALUES (?, ?, ?, ?, ?, ?, 'finder', 1, 1)", (church, website, email, phone, state, city))
        imported += 1
    
    conn.commit()
    return imported, with_email

def import_final_send_list():
    """8,769 foundation emails from old send list."""
    path = d + '/final_send_list_10k.csv'
    if not os.path.exists(path):
        return 0
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    
    imported = 0
    for r in rows:
        email = (r.get('email','') or '').strip().lower()
        name = (r.get('name','') or '').strip()
        source = (r.get('source','') or '').strip()
        
        if not email or '@' not in email:
            continue
        
        # Check if email already exists
        exists = cur.execute("SELECT id FROM churches WHERE email = ? LIMIT 1", (email,)).fetchone()
        if not exists:
            cur.execute("INSERT INTO churches (name, email, source, email_validated) VALUES (?, ?, 'foundation', 1)", (name, email))
            imported += 1
    
    conn.commit()
    return imported

print('Importing master emails...')
m = import_master_emails()
print(f'  {m} master emails imported')

print('Importing Phase 1b results...')
p, e = import_phase1b()
print(f'  {p} Phase 1b rows processed ({e} with email)')

print('Importing final send list...')
f = import_final_send_list()
print(f'  {f} foundation emails imported')

# Final count
cur.execute("SELECT COUNT(*) FROM churches WHERE email != ''")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches")
all_churches = cur.fetchone()[0]
conn.close()

print(f'\n=== Final DB Status ===')
print(f'Total churches: {all_churches:,}')
print(f'With email: {total:,}')
