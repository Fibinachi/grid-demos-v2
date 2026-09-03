#!/usr/bin/env python3
"""Build the final clean send list excluding bounced and declined."""
import csv, os

base = os.path.dirname(os.path.abspath(__file__))

# Load bounced emails
bounced = set()
for path in ['bounced_emails.txt']:
    p = os.path.join(base, path)
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                addr = line.strip().lower()
                if addr and '@' in addr:
                    bounced.add(addr)

# Load declined EINs
declined_eins = set()
declined_path = os.path.join(base, 'declined_foundations.txt')
if os.path.exists(declined_path):
    with open(declined_path) as f:
        for line in f:
            parts = line.strip().split('|')
            if parts and parts[0].strip():
                declined_eins.add(parts[0].strip())

# Load staff real contacts (from website scraping)
staff_emails = {}  # ein -> email
staff_path = os.path.join(base, 'staff_real_contacts.csv')
if os.path.exists(staff_path):
    with open(staff_path) as f:
        for r in csv.DictReader(f):
            emails = r.get('STAFF_EMAILS', '').strip()
            if emails and '@' in emails:
                # Take first real-looking email (skip image files, js versions)
                for e in emails.split(';'):
                    e = e.strip().lower()
                    if '@' in e and not any(x in e for x in ['.png', '.jpg', '.svg', '.css', '.js', 'react@', 'default-', 'user@']):
                        staff_emails[r['EIN']] = e
                        break

# Load the original Gmail send list
send_path = os.path.join(base, 'theology_gmail_send.csv')
with open(send_path) as f:
    rows = list(csv.DictReader(f))

print(f"Original send list: {len(rows)}")
print(f"Bounced addresses: {len(bounced)}")
print(f"Declined EINs: {len(declined_eins)}")
print(f"Staff emails found: {len(staff_emails)}")

# Build clean list
clean = []
skipped_bounced = 0
skipped_declined = 0
kept_staff = 0

for r in rows:
    ein = r['EIN'].strip()
    email = r['EMAIL'].strip().lower() if r['EMAIL'] else ''
    
    # Skip declined
    if ein in declined_eins:
        skipped_declined += 1
        continue
    
    # Check if we have a staff email to use instead (BEFORE bounce check!)
    if ein in staff_emails:
        email = staff_emails[ein]
        kept_staff += 1
    
    # Skip bounced (use possibly-upgraded email)
    if email in bounced:
        skipped_bounced += 1
        continue
    
    if email and '@' in email:
        # Skip clear false positives
        if any(x in email for x in ['.png', '.jpg', '.svg', '.css', '.js', 'react@', 'default-', 'user@', 'rspack@', 'sentry.', '79baaa', 'example@']):
            continue
        
        # Only keep if it's not a generic info@/contact@ address
        # OR if it's a staff email we verified via scraping
        is_staff = ein in staff_emails
        is_generic = any(email.startswith(p) for p in ['info@', 'contact@', 'hello@', 'admin@', 'mail@', 'office@', 'webmaster@', 'support@'])
        
        if is_staff or not is_generic:
            clean.append({
                'EIN': ein,
                'NAME': r['NAME'],
                'CITY': r.get('CITY', ''),
                'STATE': r.get('STATE', ''),
                'NTEE_CD': r.get('NTEE_CD', ''),
                'ASSET_AMT': r.get('ASSET_AMT', '0'),
                'EMAIL': email,
                'SOURCE': 'staff_scrape' if is_staff else 'enriched',
            })

print(f"\nSkipped bounced: {skipped_bounced}")
print(f"Skipped declined: {skipped_declined}")
print(f"Using staff emails: {kept_staff}")
print(f"Clean send list: {len(clean)}")

# Write clean list
clean_path = os.path.join(base, 'theology_clean_send.csv')
with open(clean_path, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['EIN','NAME','CITY','STATE','NTEE_CD','ASSET_AMT','EMAIL','SOURCE']
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(clean)
print(f"Saved: {clean_path}")

# Print summary
print(f"\n{'='*60}")
print(f"CLEAN SEND LIST")
print(f"{'='*60}")
for r in clean[:20]:
    print(f"  {r['EMAIL']:45s} {r['NAME'][:40]}")
