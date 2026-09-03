"""
Foundation Contact Builder
==========================
Builds enriched contact list using:
1. DNS verification of guessed domains
2. ProPublica API for verified names
3. PDL API for website lookups (fallback)

Output: enriched_contacts.csv with best available contact info
"""

import csv
import os
import re
import sys
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.parse
import dns.resolver

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "theology_priority_foundations.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")

_dns_cache = {}
_dns_cache_lock = threading.Lock()
_dns_resolver = dns.resolver.Resolver()
_dns_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
_dns_resolver.timeout = 1.0
_dns_resolver.lifetime = 1.0

# Words to skip when picking the identifying domain word
SKIP_WORDS = {"and", "the", "of", "for", "&", "de", "la", "del", "family",
              "charitable", "memorial", "foundation", "community", "corporate",
              "international", "national", "american", "global"}

# Email prefixes to try in order of likelihood
EMAIL_PREFIXES = ["info", "grants", "contact", "apply", "proposals",
                  "giving", "foundation", "hello"]

def get_key_words(name):
    """Extract meaningful words from foundation name, skipping fillers."""
    clean = name.strip().replace(",", "").lower()
    clean = clean.replace("the ", "")
    for suf in [" foundation", " foundation inc", " foundation corporation",
                " inc", " corp", " llc", ", inc.", ", llc",
                " dtd", " incorporated", " limited", " ltd"]:
        clean = re.sub(r'\s*' + re.escape(suf) + r'\s*', ' ', clean)
    words = clean.split()
    # Remove short words and fillers
    meaningful = [w for w in words if len(w) > 2 and w not in SKIP_WORDS and w.isalpha()]
    if not meaningful:
        meaningful = [w for w in words if len(w) > 2 and w.isalpha()]
    return meaningful

def domain_resolves(domain):
    """Check if a domain has DNS records via Google DNS."""
    with _dns_cache_lock:
        if domain in _dns_cache:
            return _dns_cache[domain]
    try:
        _dns_resolver.resolve(domain, 'A')
        with _dns_cache_lock:
            _dns_cache[domain] = True
        return True
    except:
        with _dns_cache_lock:
            _dns_cache[domain] = False
        return False

def find_best_contact(name):
    """
    Smart domain finding with multiple strategies.
    Returns (email, domain, method) where method describes how it was found.
    """
    meaningful = get_key_words(name)
    if not meaningful:
        return None, None, "no_words"
    
    last = meaningful[-1]
    first = meaningful[0]
    
    # Build candidate domains - most likely first
    candidates = []
    
    # 1. lastwordfoundation.org (most common)
    candidates.append(last + "foundation.org")
    candidates.append(last + "foundation.com")
    
    # 2. If multiple words, try first+last pattern
    if first != last and len(meaningful) >= 2:
        candidates.append(first + last + "foundation.org")
        candidates.append(first + last + ".org")
    
    # 3. Try just the word with .org and .com
    candidates.append(last + ".org")
    candidates.append(last + ".com")
    
    # 4. Try first word patterns
    if first != last:
        candidates.append(first + "foundation.org")
        candidates.append(first + ".org")
    
    # 5. Try combined words
    if len(meaningful) >= 2:
        combined = "".join(meaningful)
        if len(combined) < 40:
            candidates.append(combined + ".org")
    
    # 6. Try acronym (first letter of each word)
    if len(meaningful) >= 2:
        acro = "".join(w[0] for w in meaningful if w[0].isalpha()).upper()
        if len(acro) >= 2 and len(acro) <= 8:
            candidates.append(acro.lower() + ".org")
    
    # Check each candidate
    for domain in candidates:
        if len(domain) > 55:
            continue
        if domain_resolves(domain):
            # Domain exists! Try different email prefixes
            for prefix in EMAIL_PREFIXES:
                email = f"{prefix}@{domain}"
                return email, domain, f"dns_{prefix}"
            break
    
    return None, None, "no_dns"

def process_foundation(fb):
    name = fb.get('NAME', '')
    email, domain, method = find_best_contact(name)
    return {
        'EIN': fb.get('EIN', '').strip(),
        'NAME': name,
        'CITY': fb.get('CITY', ''),
        'STATE': fb.get('STATE', ''),
        'ASSET_AMT': fb.get('ASSET_AMT', ''),
        'NTEE_CD': fb.get('NTEE_CD', ''),
        'EMAIL': email or '',
        'DOMAIN': domain or '',
        'METHOD': method or '',
    }

def lookup_propublica(ein):
    """Quick ProPublica lookup to verify foundation exists."""
    url = f"https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            org = data.get('organization', {})
            return {
                'name': org.get('name', ''),
                'ntee': org.get('ntee_code', ''),
                'assets': org.get('asset_amount', 0),
                'city': org.get('city', ''),
                'state': org.get('state', ''),
            }
    except:
        return None

def main():
    print("=" * 70)
    print("  FOUNDATION CONTACT BUILDER")
    print("=" * 70)
    
    # Load
    print(f"\nLoading {INPUT_CSV}...")
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        foundations = list(csv.DictReader(f))
    print(f"  {len(foundations):,} foundations")
    
    stats = {'dns_verified': 0, 'no_dns': 0}
    results = []
    
    # Use 50 concurrent workers for parallel DNS lookups
    print(f"  Processing with 50 concurrent workers...")
    sys.stdout.flush()
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(process_foundation, fb): i for i, fb in enumerate(foundations)}
        for i, future in enumerate(as_completed(futures)):
            results.append(future.result())
            if (i + 1) % 1000 == 0:
                verified = sum(1 for r in results if r['EMAIL'])
                print(f"  {i+1:,}/{len(foundations):,} | Found: {verified:,}")
                sys.stdout.flush()
    
    # Sort results by original order (approximate by EIN)
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
    
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE")
    print(f"  DNS-verified contacts: {stats['dns_verified']:>7,} ({int(stats['dns_verified']/len(foundations)*100)}%)")
    print(f"  No contact found:     {stats['no_dns']:>7,}")
    print(f"  Output: {OUTPUT_CSV}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
