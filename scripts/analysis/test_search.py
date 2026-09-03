"""Quick test of web search email finding approach."""
import csv
import re
import json
import time
import random
import urllib.request
import urllib.parse
import ssl

EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.\w{2,4}', re.IGNORECASE)
SKIP_DOMAINS = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
                'icloud.com', 'protonmail.com', 'mail.com', 'msn.com', 'live.com',
                'ymail.com', 'zoho.com', 'yandex.com', 'gmx.com', 'fastmail.com'}

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]

def bing_search(query):
    url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}&count=30"
    req = urllib.request.Request(url, headers={
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml',
    })
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        return resp.read().decode('utf-8', errors='replace')

# Test foundations that do theology funding
tests = [
    ("MUSTARD SEED FOUNDATION", "mustardseedfoundation.org"),
    ("SORENSON LEGACY FOUNDATION", "sdihq.com"),
    ("FAITHFUL SERVANTS FOUNDATION", "faithfulservantsfoundation.org"),
    ("MCCUNE FOUNDATION", "mccune.org"),
]

print(f"{'='*70}")
print(f"{'TEST FOUNDATION':40s} {'BING RESULTS'}")
print(f"{'='*70}")

for name, domain in tests:
    time.sleep(2.0)
    
    try:
        # Search 1: @domain
        html = bing_search(f"@{domain} foundation")
        emails = set()
        for m in EMAIL_RE.finditer(html):
            e = m.group(0).lower().strip('.,;:()[]{}<>"\'')
            ed = e.split('@')[1] if '@' in e else ''
            if ed in SKIP_DOMAINS: continue
            if len(e) > 5 and '@' in e:
                emails.add(e)
        
        # Filter to relevant
        domain_emails = [e for e in emails if domain in e or domain.replace('www.','') in e]
        
        print(f"{name[:38]:40s} {domain_emails[:3] or 'NONE FOUND'}")
        
        # Search 2: foundation name + email
        time.sleep(1.5)
        html2 = bing_search(f'"{name[:25]}" foundation "email"')
        emails2 = set()
        for m in EMAIL_RE.finditer(html2):
            e = m.group(0).lower().strip('.,;:()[]{}<>"\'')
            ed = e.split('@')[1] if '@' in e else ''
            if ed in SKIP_DOMAINS: continue
            if len(e) > 5 and '@' in e:
                emails2.add(e)
        
        # Show non-generic looking ones
        interesting = [e for e in emails2 if any(x in e for x in [domain, name.lower()[:10]])]
        print(f"{'':40s} Name-search: {interesting[:3] or 'none'}")
        
    except Exception as ex:
        print(f"{name[:38]:40s} ERROR: {ex}")
    
    print()
