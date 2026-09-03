"""Analyze Phase 1b results."""
import csv, re

d = r'E:\grid'
results = list(csv.DictReader(open(d + '/found_chunk_1b_results.csv', encoding='utf-8-sig')))

total = len(results)
with_website = sum(1 for r in results if r.get('website','').strip())
with_email = sum(1 for r in results if r.get('email','').strip())

print('Phase 1b Results (2,767 contacts without websites):')
print('  Total processed:', total)
print('  Websites found:', with_website, f'({with_website/total*100:.1f}%)')
print('  Emails found:', with_email, f'({with_email/total*100:.1f}%)')

# Check quality
real_emails = 0
for r in results:
    e = (r.get('email','') or '').strip()
    w = (r.get('website','') or '').strip()
    if e and '@' in e and not re.search(r'(example|test|placeholder)', e.lower()):
        real_emails += 1

print(f'  Real-looking emails: {real_emails}')

# Show what websites were found
print('\nSample of found websites (first 15):')
for r in results[:15]:
    w = (r.get('website','') or '').strip()[:60]
    n = r['church_name'][:40]
    e = (r.get('email','') or '').strip()
    print(f'  {n}: {w}  email={e[:30] if e else "empty"}')

# Count unique domains
from collections import Counter
domains = Counter()
for r in results:
    w = (r.get('website','') or '').strip()
    if w:
        try:
            domain = re.sub(r'https?://(www\.)?', '', w).split('/')[0].split(':')[0]
            domains[domain] += 1
        except:
            pass

print('\nMost common domains found:')
for d, c in domains.most_common(15):
    print(f'  {d}: {c}')
