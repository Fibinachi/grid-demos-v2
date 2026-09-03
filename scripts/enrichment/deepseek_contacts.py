#!/usr/bin/env python3
"""
Deep-dive contact finder for top theology funders and Canadian funders.
Visits actual website contact pages to find real email addresses.
"""
import urllib.request
import urllib.error
import csv
import os
import re
import time
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))

# Top theology seminaries/foundations that need real emails
# (From theology_need_scrape.csv - highest scoring ones)
TARGETS = [
    # (name, website, contact_page_pattern)
    ("Reformed Theological Seminary", "rts.edu", "/about/contact"),
    ("Covenant Theological Seminary", "covenantseminary.edu", "/contact"),
    ("Calvin Theological Seminary", "calvinseminary.edu", "/contact"),
    ("Asbury Theological Seminary", "asburyseminary.edu", "/contact"),
    ("Fuller Theological Seminary", "fuller.edu", "/contact"),
    ("Dallas Theological Seminary", "dts.edu", "/contact"),
    ("Union Theological Seminary", "utsnyc.edu", "/contact"),
    ("Westminster Theological Seminary", "wts.edu", "/contact"),
    ("Trinity Evangelical Divinity School", "tiu.edu", "/divinity/contact"),
    ("Auburn Theological Seminary", "auburnseminary.org", "/contact"),
    
    # Canadian funders
    ("Anglican Foundation of Canada", "anglicanfoundation.org", "/contact"),
    ("J.W. McConnell Family Foundation", "mcconnellfoundation.ca", "/contact"),
    ("Catherine Donnelly Foundation", "catherinedonnellyfoundation.org", "/contact"),
    ("Toronto School of Theology", "tst.edu", "/contact"),
    ("The Calgary Foundation", "calgaryfoundation.org", "/contact"),
    ("The Max Bell Foundation", "maxbell.org", "/contact"),
    ("The Presbyterian Church in Canada Foundation", "presbyterianfoundation.ca", "/contact"),
    ("The Vancouver Foundation", "vancouverfoundation.ca", "/contact"),
]

def find_email_on_page(url, name_hint=''):
    """Fetch a URL and find email addresses on it."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        resp = urllib.request.urlopen(req, timeout=20)
        html = resp.read().decode('utf-8', errors='replace')
        
        # Find email addresses
        emails = re.findall(r'[\w.+-]+@[\w-]+\.(?:ca|org|com|edu|net|us)', html)
        
        # Filter out garbage
        real_emails = []
        for e in emails:
            e = e.lower().strip()
            # Skip obvious junk
            if any(x in e for x in ['example.com', 'domain.com', 'yourname', '.png', '.jpg', '.css', '.js', 'slick-', 'isotope', 'b.and@', 'splide@']):
                continue
            # Skip single-character local parts
            if len(e.split('@')[0]) < 2:
                continue
            if e not in real_emails:
                real_emails.append(e)
        
        return real_emails
    except Exception as e:
        return [f"ERROR: {str(e)[:60]}"]

results = []

for name, domain, contact_path in TARGETS:
    print(f"\n{name} ({domain})...", end=" ", flush=True)
    
    found_emails = []
    
    # Try multiple pages
    for path in ['/', contact_path, '/about', '/contact-us']:
        if not path:
            continue
        url = f"https://www.{domain}{path}"
        emails = find_email_on_page(url, name)
        if emails and not any(e.startswith('ERROR') for e in emails):
            found_emails.extend(emails)
    
    if not found_emails:
        # Try without www
        for path in ['/', contact_path]:
            url = f"https://{domain}{path}"
            emails = find_email_on_page(url, name)
            if emails and not any(e.startswith('ERROR') for e in emails):
                found_emails.extend(emails)
    
    # Deduplicate
    unique = list(set(found_emails))
    
    if unique:
        print(f"✅ {', '.join(unique[:3])}")
    else:
        print(f"❌ Not found")
    
    results.append({
        'name': name,
        'domain': domain,
        'emails': '; '.join(unique[:5]) if unique else '',
    })
    
    time.sleep(1.5)  # Be polite

# Write results
csv_path = os.path.join(base_dir, 'deepseek_contacts.csv')
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['name', 'domain', 'emails'])
    w.writeheader()
    w.writerows(results)

print(f"\n\nSaved: {csv_path}")
print("\n=== FOUND EMAILS ===")
for r in results:
    if r['emails']:
        print(f"  {r['name']}: {r['emails']}")
