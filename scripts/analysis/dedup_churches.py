#!/usr/bin/env python3
"""
Build a deduplicated master church email list.
Merges Anglican + Main scraper outputs, removes placeholders like user@domain.com,
deduplicates by email and by church name, keeping the best email per church.
"""
import csv, os
from collections import defaultdict

SCRIPT = '/home/ubuntu/grantwizard'
OUTPUT = os.path.join(SCRIPT, 'church_master_emails.csv')

def load(fname):
    path = os.path.join(SCRIPT, fname)
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 3:
                rows.append({
                    'name': row[0].strip(),
                    'website': row[1].strip(),
                    'email': row[2].strip().lower(),
                    'source': row[3].strip() if len(row) > 3 else '',
                })
    return rows

ang = load('church_anglican_episcopal_emails.csv')
main = load('church_contacts_emails.csv')
print(f"Loaded: Anglican={len(ang)}, Main={len(main)}")

BAD = {'user@domain.com', 'user@domain.org', 'admin@domain.com',
       'info@domain.com', 'contact@domain.com', 'webmaster@domain.com',
       'test@test.com', 'example@example.com', ''}
def good(e):
    return e not in BAD and '@' in e and not e.startswith('user@')

ang_g = [r for r in ang if good(r['email'])]
main_g = [r for r in main if good(r['email'])]
print(f"After filtering: Anglican={len(ang_g)} (removed {len(ang)-len(ang_g)}), "
      f"Main={len(main_g)} (removed {len(main)-len(main_g)})")

# By-email index (main priority)
by_email = {}
for r in main_g:
    by_email[r['email']] = r
added = 0
for r in ang_g:
    if r['email'] not in by_email:
        by_email[r['email']] = r
        added += 1
print(f"Anglican-only added: {added}")

# Group by church name, pick best email
def priority(email):
    local = email.split('@')[0].lower()
    if any(x in local for x in ['pastor','rector','vicar','minister']):
        return 10
    if any(x in local for x in ['office','admin','administrator']):
        return 9
    if any(x in local for x in ['secretary','treasurer']):
        return 7
    if any(x in local for x in ['info','contact','hello']):
        return 5
    if '(guess)' in email:
        return 3
    return 4

by_name = defaultdict(list)
for email, r in by_email.items():
    by_name[r['name']].append(r)

final = []
dupes = 0
for name, entries in by_name.items():
    if len(entries) > 1:
        dupes += 1
        entries.sort(key=lambda x: (-priority(x['email']), x['email']))
    final.append(entries[0])

with open(OUTPUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['church_name', 'website', 'email', 'source_url'])
    for r in sorted(final, key=lambda x: x['email']):
        w.writerow([r['name'], r['website'], r['email'], r['source']])

print(f"\n=== MASTER LIST ===")
print(f"Unique churches with emails: {len(final)}")
print(f"Name duplicates resolved: {dupes}")
print(f"Output: church_master_emails.csv")

# Stats
domains = defaultdict(int)
for r in final:
    domains[r['email'].split('@')[1]] += 1
print("\nTop email domains:")
for dom, cnt in sorted(domains.items(), key=lambda x: -x[1])[:10]:
    print(f"  {dom}: {cnt}")
