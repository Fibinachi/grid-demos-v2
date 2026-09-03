"""Quick DNS MX check - fast domain validation"""
import csv, os, sys, json, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import dns.resolver

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts_verified.csv")

_resolver = dns.resolver.Resolver()
_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
_resolver.timeout = 1.0
_resolver.lifetime = 1.0

_dns_cache = {}
_cache_lock = threading.Lock()

def check_mx(domain):
    with _cache_lock:
        if domain in _dns_cache:
            return _dns_cache[domain]
    try:
        _resolver.resolve(domain, 'MX')
        with _cache_lock:
            _dns_cache[domain] = True
        return True
    except:
        with _cache_lock:
            _dns_cache[domain] = False
        return False

def main():
    print("=" * 60)
    print("  QUICK DNS MX VERIFICATION")
    print("=" * 60)
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    print("  Contacts: %d" % len(rows))
    
    # Get unique domains
    domains = set()
    for r in rows:
        email = r.get('EMAIL', '').strip()
        if '@' in email:
            domains.add(email.split('@')[1].lower())
    
    print("  Unique domains: %d" % len(domains))
    print("  Checking MX records...")
    sys.stdout.flush()
    
    # Check all domains in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=200) as ex:
        futures = {ex.submit(check_mx, d): d for d in domains}
        for i, f in enumerate(as_completed(futures)):
            d = futures[f]
            results[d] = f.result()
            if (i + 1) % 500 == 0:
                print("    %d/%d domains checked..." % (i+1, len(domains)))
                sys.stdout.flush()
    
    good_domains = {d for d, v in results.items() if v}
    bad_domains = {d for d, v in results.items() if not v}
    
    print()
    print("  Domains with MX:  %d" % len(good_domains))
    print("  Domains no MX:    %d (will be removed)" % len(bad_domains))
    print()
    
    # Filter rows
    clean = []
    removed = 0
    no_mx_emails = set()
    for r in rows:
        email = r.get('EMAIL', '').strip().lower()
        if '@' in email:
            domain = email.split('@')[1]
            if domain not in good_domains:
                removed += 1
                no_mx_emails.add(email)
                continue
        clean.append(r)
    
    print("  Removed (no MX):  %d" % removed)
    print("  Kept:             %d" % len(clean))
    print()
    
    # Save
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(clean)
    
    print("  Saved: %s" % OUTPUT_PATH)
    print()
    print("  Sample removed:")
    for e in sorted(no_mx_emails)[:10]:
        print("    %s" % e)
    print("=" * 60)

if __name__ == '__main__':
    main()
