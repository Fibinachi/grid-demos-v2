"""
Build Religious/Education Contacts
==================================
Applies DNS-based email discovery to the 15,501 X (Religion)
and B (Education) organizations from IRS data.

Uses the same approach as build_contacts.py:
1. Extract keywords from org name
2. Try domain (keyword.org, keyword.com, keywordfoundation.org)
3. DNS verify MX records
4. Guess common email prefixes

Output: religious_enriched.csv
"""

import csv
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "religious_education_orgs.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "religious_enriched.csv")

_dns_cache = {}
_dns_cache_lock = threading.Lock()
_dns_resolver = dns.resolver.Resolver()
_dns_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
_dns_resolver.timeout = 1.0
_dns_resolver.lifetime = 1.0

SKIP_WORDS = {"and", "the", "of", "for", "&", "de", "la", "del", "family",
              "charitable", "memorial", "foundation", "community", "corporate",
              "international", "national", "american", "global", "society",
              "association", "fund", "trust", "institute", "school", "college",
              "university", "seminary", "ministry", "church", "fellowship"}

EMAIL_PREFIXES = ["info", "contact", "giving", "donate", "support",
                  "hello", "office", "admin", "pastor", "director"]

def get_key_words(name):
    """Extract meaningful words from organization name."""
    clean = name.strip().replace(",", "").lower()
    clean = clean.replace("the ", "")
    for suf in [" foundation", " foundation inc", " inc", " corp", " llc",
                " incorporated", " limited", " ltd", " seminary",
                " university", " college", " institute", " school",
                " ministry", " church", " fellowship", " association",
                " society", " fund", " trust"]:
        clean = re.sub(r'\s*' + re.escape(suf) + r'\s*', ' ', clean)
    words = [w.strip() for w in re.split(r'[\s,./\-&]+', clean) if w.strip()]
    words = [w for w in words if w not in SKIP_WORDS and len(w) > 2]
    return words

def guess_domains(name_words):
    """Generate candidate domains from organization name words."""
    domains = set()
    if not name_words:
        return domains

    primary = name_words[0]
    secondary = name_words[1] if len(name_words) > 1 else None

    tlds = [".org", ".com", ".net"]
    for tld in tlds:
        domains.add(primary + tld)
    if secondary and secondary != primary:
        for tld in tlds:
            domains.add(primary + secondary + tld)
            domains.add(secondary + primary + tld)
    return domains

def check_mx(domain):
    """Check if domain has MX records (DNS cache-friendly)."""
    with _dns_cache_lock:
        if domain in _dns_cache:
            return _dns_cache[domain]
    try:
        _dns_resolver.resolve(domain, 'MX')
        with _dns_cache_lock:
            _dns_cache[domain] = True
        return True
    except:
        with _dns_cache_lock:
            _dns_cache[domain] = False
        return False

def check_a_record(domain):
    """Check if domain has any A/AAAA record."""
    try:
        _dns_resolver.resolve(domain, 'A')
        return True
    except:
        try:
            _dns_resolver.resolve(domain, 'AAAA')
            return True
        except:
            return False

def guess_email(name, domain):
    """Generate likely email address from org name and verified domain."""
    clean = name.strip().lower()
    clean = re.sub(r'[^a-z0-9\s]', '', clean)
    words = [w for w in clean.split() if w not in SKIP_WORDS and len(w) > 2]

    email_guesses = []
    for prefix in EMAIL_PREFIXES:
        email_guesses.append("%s@%s" % (prefix, domain))
    if words:
        first = words[0]
        email_guesses.append("%s@%s" % (first, domain))
        if len(words) > 1:
            combined = "".join(words)
            email_guesses.append("%s@%s" % (combined, domain))
            email_guesses.append("%s%s@%s" % (words[0], words[-1], domain))
    return email_guesses[0] if email_guesses else None

def process_org(org):
    """Process a single organization to find its email."""
    ein = org.get('EIN', '').strip()
    name = org.get('NAME', '').strip()
    city = org.get('CITY', '').strip()
    state = org.get('STATE', '').strip()
    ntee = org.get('NTEE_CD', '').strip()
    assets = org.get('ASSET_AMT', '').strip()

    words = get_key_words(name)
    domains = guess_domains(words)

    result = {
        'EIN': ein, 'NAME': name, 'CITY': city, 'STATE': state,
        'NTEE_CD': ntee, 'ASSET_AMT': assets,
        'EMAIL': '', 'DOMAIN': '', 'METHOD': ''
    }

    if not domains:
        return result

    # Check each domain for MX or A records
    for domain in domains:
        if check_mx(domain):
            result['DOMAIN'] = domain
            email = guess_email(name, domain)
            if email:
                result['EMAIL'] = email
                result['METHOD'] = 'dns_mx'
            return result

    # Fallback: check A record only
    for domain in domains:
        if check_a_record(domain):
            result['DOMAIN'] = domain
            email = guess_email(name, domain)
            if email:
                result['EMAIL'] = email
                result['METHOD'] = 'dns_a'
            return result

    return result

def main():
    print("=" * 70)
    print("  RELIGIOUS/EDUCATION CONTACT BUILDER")
    print("  Processing X (Religion) + B (Education) codes")
    print("=" * 70)

    # Load
    print("\n  Loading %s..." % INPUT_CSV)
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        orgs = list(csv.DictReader(f))
    print("  %d organizations" % len(orgs))

    # Count by type
    x_count = sum(1 for r in orgs if r.get('NTEE_CD','').strip().startswith('X'))
    b_count = sum(1 for r in orgs if r.get('NTEE_CD','').strip().startswith('B'))
    print("  X (Religion): %d  B (Education): %d" % (x_count, b_count))

    stats = {'dns_verified': 0, 'no_dns': 0}
    results = []

    # Process with 50 concurrent DNS workers
    print("\n  Processing with 50 concurrent workers...")
    sys.stdout.flush()

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(process_org, org): i for i, org in enumerate(orgs)}
        for i, future in enumerate(as_completed(futures)):
            results.append(future.result())
            if (i + 1) % 1000 == 0:
                verified = sum(1 for r in results if r['EMAIL'])
                print("  %d/%d | Found: %d" % (i+1, len(orgs), verified))
                sys.stdout.flush()

    # Write output
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        fields = ['EIN', 'NAME', 'CITY', 'STATE', 'ASSET_AMT', 'NTEE_CD',
                  'EMAIL', 'DOMAIN', 'METHOD']
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in results:
            w.writerow(row)
            if row['EMAIL']:
                stats['dns_verified'] += 1
            else:
                stats['no_dns'] += 1

    print("\n" + "=" * 60)
    print("  COMPLETE")
    print("  DNS-verified contacts: %d (%d%%)" % (
        stats['dns_verified'], int(stats['dns_verified']/len(orgs)*100) if orgs else 0))
    print("  No contact found:     %d" % stats['no_dns'])
    print("  Output: %s" % OUTPUT_CSV)
    print("=" * 60)

if __name__ == '__main__':
    main()
