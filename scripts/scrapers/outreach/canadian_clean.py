#!/usr/bin/env python3
"""Clean up Canadian funders list and generate final output."""
import csv, os, re

base = os.path.dirname(os.path.abspath(__file__))

# Load raw results
with open(os.path.join(base, 'canadian_funding_sources.csv')) as f:
    rows = list(csv.DictReader(f))

# Email validation - remove false positives from JS libs
def is_valid_email(email):
    """Check if email looks real, not a JS library version string."""
    if not email:
        return False
    bad_patterns = ['@3.', '@4.', '@1.', '@2.', '@0.', 'slick-carousel', 
                    'isotope-layout', 'example@', 'user@', 'test@']
    for p in bad_patterns:
        if p in email.lower():
            return False
    if not re.match(r'^[\w.+-]+@[\w-]+\.[\w.-]+$', email):
        return False
    return True

clean = [r for r in rows if r['source'] == 'curated_list']
for r in clean:
    if not is_valid_email(r.get('email', '')):
        r['email'] = ''
    # Clean phone numbers - remove false positives
    phone = r.get('phone', '')
    if phone and (len(phone) < 10 or not any(c.isdigit() for c in phone)):
        r['phone'] = ''

# Write clean version
out_path = os.path.join(base, 'canadian_funding_sources.csv')
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['name','url','domain','email','phone','notes','source','country'])
    w.writeheader()
    w.writerows(clean)

print(f"Cleaned list: {len(clean)} Canadian funding sources")
print(f"With valid emails: {len([r for r in clean if r['email']])}")
print(f"With websites: {len([r for r in clean if r['url']])}")
print(f"\nSaved: {out_path}")

# Print clean top picks
print(f"\n{'='*70}")
print("TOP CANADIAN FUNDING SOURCES FOR THEOLOGICAL EDUCATION")
print(f"{'='*70}")

priority = [
    ("Anglican Foundation of Canada", "Direct - Anglican Church funds theology"),
    ("United Church of Canada Foundation", "Direct - United Church theology grants"),
    ("J.W. McConnell Family Foundation", "Major Canadian education funder"),
    ("Catherine Donnelly Foundation", "Adult education, theological focus"),
    ("Toronto School of Theology", "Local - Toronto theology consortium"),
    ("Trinity College Alumni Association", "Direct - Trinity College alumni"),
    ("Ontario Student Assistance Program", "Ontario government student aid"),
    ("SSHRC", "Federal humanities/theology research funding"),
    ("Laidlaw Foundation", "Education and youth programs"),
    ("Vancouver Foundation", "Major Canadian community foundation"),
]

for name, why in priority:
    r = next((x for x in clean if x['name'] == name), None)
    if r:
        email = f"  Email: {r['email']}" if r['email'] else "  Email: scrape needed"
        url = f"  URL: {r['url']}" if r['url'] else "  URL: unknown"
        print(f"\n{name}")
        print(f"  Why: {why}")
        print(url)
        print(email)
