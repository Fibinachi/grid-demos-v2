#!/usr/bin/env python3
"""Build a send-ready CSV with real email addresses for the Gmail sender."""
import csv, os

base = os.path.dirname(os.path.abspath(__file__))

# Load final list (has EINs but no actual EMAIL column)
with open(os.path.join(base, 'theology_final_send.csv')) as f:
    final = list(csv.DictReader(f))

# Load enriched contacts (has actual emails keyed by EIN)
email_map = {}
for fname in ['enriched_contacts.csv', 'enriched_contacts_clean.csv', 'enriched_contacts_verified.csv']:
    path = os.path.join(base, fname)
    if os.path.exists(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                ein = r.get('EIN', '').strip()
                email = r.get('EMAIL', '').strip()
                if ein and email and email not in ('', 'dns_info'):
                    email_map[ein] = email

print(f"Loaded {len(email_map)} email addresses from enriched contacts")
print(f"Final list has {len(final)} foundations")

# Build send-ready rows
send_rows = []
missing_email = 0
for r in final:
    ein = r['EIN'].strip()
    email = email_map.get(ein, '')
    
    if not email:
        missing_email += 1
        continue
    
    send_rows.append({
        'EIN': ein,
        'NAME': r['NAME'],
        'CITY': r.get('CITY', ''),
        'STATE': r.get('STATE', ''),
        'NTEE_CD': r.get('NTEE', ''),
        'ASSET_AMT': r.get('ASSET_AMT', '0'),
        'EMAIL': email,
    })

print(f"Rows with emails: {len(send_rows)}")
print(f"Missing emails (skipped): {missing_email}")

# Write send-ready CSV
out_path = os.path.join(base, 'theology_gmail_send.csv')
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['EIN','NAME','CITY','STATE','NTEE_CD','ASSET_AMT','EMAIL'])
    w.writeheader()
    w.writerows(send_rows)

print(f"Saved: {out_path}")
print(f"First 3 rows:")
for r in send_rows[:3]:
    print(f"  {r['EIN']} - {r['NAME'][:50]} <{r['EMAIL']}>")
