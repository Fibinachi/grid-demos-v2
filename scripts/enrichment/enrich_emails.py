#!/usr/bin/env python3
"""
Email Enrichment Pipeline
=========================
For each foundation domain, tries these methods in order until an email is found:
  1. WHOIS lookup  — domain registration admin/tech emails
  2. Web search    — DuckDuckGo search for published emails
  3. Name patterns — common email prefixes ($name@domain.com)

Once a method finds a valid email (verified via SMTP), moves to next domain.

Usage:
  python enrich_emails.py                  # Full pipeline
  python enrich_emails.py --quick 50       # Test first 50
  python enrich_emails.py --method whois   # Whois only
  python enrich_emails.py --status         # Show current results
"""

import csv
import os
import sys
import re
import time
import json
import random
import socket
import smtplib
import ssl
import threading
import queue
import secrets
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parseaddr

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
LOG_DIR = os.path.join(SCRIPT_DIR, "ses_logs")
STATE_FILE = os.path.join(SCRIPT_DIR, "enrich_state.json")

# ── DNS/SMTP helpers ─────────────────────────────────────────────

_dns_cache = {}
_dns_lock = threading.Lock()

try:
    import dns.resolver
    _resolver = dns.resolver.Resolver()
    _resolver.nameservers = ['8.8.8.8', '8.8.4.4']
    _resolver.timeout = 2.0
    _resolver.lifetime = 2.0
    HAVE_DNS = True
except ImportError:
    HAVE_DNS = False

def get_mx(domain):
    cache_key = f"mx:{domain}"
    with _dns_lock:
        if cache_key in _dns_cache:
            return _dns_cache[cache_key]
    if not HAVE_DNS:
        with _dns_lock:
            _dns_cache[cache_key] = []
        return []
    try:
        answers = _resolver.resolve(domain, 'MX')
        mx_records = [(r.preference, str(r.exchange).rstrip('.')) for r in answers]
        mx_records.sort(key=lambda x: x[0])
        hosts = [h for _, h in mx_records]
        with _dns_lock:
            _dns_cache[cache_key] = hosts
        return hosts
    except:
        try:
            _resolver.resolve(domain, 'A')
            with _dns_lock:
                _dns_cache[cache_key] = [domain]
            return [domain]
        except:
            with _dns_lock:
                _dns_cache[cache_key] = []
            return []

VERIFY_FROM = "verify@check.columbiataxlawyer.com"

def verify_email(email, timeout=8):
    """SMTP RCPT TO check. Returns 'valid', 'invalid', 'unknown', or 'error'."""
    if not email or '@' not in email:
        return 'error'
    domain = email.split('@')[1].lower()
    mx_hosts = get_mx(domain)
    if not mx_hosts:
        return 'error'
    for mx in mx_hosts[:2]:
        try:
            sock = socket.create_connection((mx, 25), timeout=timeout)
            smtp = smtplib.SMTP()
            smtp.sock = sock
            smtp.timeout = timeout
            try:
                code, _ = smtp.ehlo("verify.columbiataxlawyer.com")
                if code < 200 or code >= 300:
                    smtp.quit()
                    continue
                if smtp.has_extn('STARTTLS'):
                    try:
                        smtp.starttls(ssl.create_default_context())
                        smtp.ehlo("verify.columbiataxlawyer.com")
                    except:
                        pass
                code, _ = smtp.mail(VERIFY_FROM)
                if code < 200 or code >= 300:
                    smtp.quit()
                    continue
                code, _ = smtp.rcpt(email)
                smtp.quit()
                return 'valid' if code == 250 else 'invalid'
            except:
                pass
            finally:
                try:
                    smtp.close()
                except:
                    pass
        except:
            pass
    return 'unknown'

# ── METHOD 1: WHOIS ─────────────────────────────────────────────

def try_whois(domain):
    """Look up domain registration for admin/tech emails."""
    try:
        import whois
        w = whois.whois(domain)
        emails = w.emails if w.emails else []
        if not isinstance(emails, list):
            emails = [emails]
        # Filter out privacy/abuse contacts
        skip_patterns = ['whois', 'abuse', 'privacy', 'proxy', 'domains', 
                         'hostmaster', 'dns-admin', 'noc@', 'host@']
        real = []
        for e in emails:
            if not e:
                continue
            e_lower = str(e).lower().strip()
            if any(p in e_lower for p in skip_patterns):
                continue
            if '@' in e_lower and '.' in e_lower.split('@')[1]:
                real.append(e_lower)
        return list(set(real))
    except Exception:
        return []

# ── METHOD 2: WEB SEARCH (DuckDuckGo) ──────────────────────────

def try_web_search(name, domain):
    """Search DuckDuckGo for emails published on the domain."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []
    
    found = set()
    queries = [
        f'site:{domain} email',
        f'site:{domain} contact',
        f'site:{domain} @{domain}',
        f'"{name}" email @{domain}',
    ]
    
    for query in queries:
        try:
            with DDGS() as ddgs:
                for i, result in enumerate(ddgs.text(query, max_results=5)):
                    if i > 3:
                        break
                    snippet = result.get('body', '') + ' ' + result.get('title', '')
                    # Extract emails from snippet
                    for m in re.finditer(r'[\w.+-]+@' + re.escape(domain), snippet, re.IGNORECASE):
                        found.add(m.group(0).lower())
                    # Also try @domain.com variations
                    base = domain.replace('www.', '')
                    for m in re.finditer(r'[\w.+-]+@[\w.-]*' + re.escape(base), snippet, re.IGNORECASE):
                        found.add(m.group(0).lower())
        except Exception:
            pass
        time.sleep(0.5)  # Polite delay
    
    return list(found)

# ── METHOD 3: CATCH-ALL DETECTION ─────────────────────────────

def check_catch_all(domain):
    """
    Test if a domain is catch-all by SMTP-checking a random string.
    If the server accepts mail to a random nonexistent address,
    the domain accepts ALL email — meaning info@ is definitely valid.
    Returns: 'catchall', 'strict', or 'unknown'
    """
    random_local = secrets.token_hex(8)  # e.g. "a3f8c9d2e1b4a5f6"
    test_email = f"{random_local}@{domain}"
    
    mx_hosts = get_mx(domain)
    if not mx_hosts:
        return 'unknown'
    
    for mx in mx_hosts[:2]:
        try:
            sock = socket.create_connection((mx, 25), timeout=8)
            smtp = smtplib.SMTP()
            smtp.sock = sock
            smtp.timeout = 8
            try:
                code, _ = smtp.ehlo("verify.columbiataxlawyer.com")
                if code < 200 or code >= 300:
                    smtp.quit()
                    continue
                if smtp.has_extn('STARTTLS'):
                    try:
                        smtp.starttls(ssl.create_default_context())
                        smtp.ehlo("verify.columbiataxlawyer.com")
                    except:
                        pass
                code, _ = smtp.mail("catchall@test.local")
                if code < 200 or code >= 300:
                    smtp.quit()
                    continue
                code, _ = smtp.rcpt(test_email)
                smtp.quit()
                if code == 250:
                    return 'catchall'
                elif code in (550, 551, 552, 553, 554):
                    return 'strict'
                else:
                    return 'unknown'
            except:
                pass
            finally:
                try:
                    smtp.close()
                except:
                    pass
        except:
            pass
    return 'unknown'


# ── METHOD 4: WAYBACK MACHINE ─────────────────────────────────

WAYBACK_API = "https://web.archive.org/cdx/search/cdx"

def try_wayback(domain):
    """
    Check the Wayback Machine for archived pages from 2022-2025
    that might contain email addresses (pre-GDPR removal).
    """
    found = set()
    try:
        import urllib.request
        import urllib.parse
        import json
        
        # CDX API: get snapshots from 2022-2025
        params = urllib.parse.urlencode({
            'url': f'*.{domain}/*',
            'output': 'json',
            'fl': 'original,timestamp',
            'from': '20220101',
            'to': '20250607',
            'limit': '50',
            'filter': 'mimetype:text/html',
            'collapse': 'urlkey',
        })
        
        url = f"{WAYBACK_API}?{params}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; grantwizard/1.0)'
        })
        
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        
        if len(data) < 2:
            return []
        
        # Get unique page URLs
        pages = set()
        for row in data[1:]:  # Skip header
            if len(row) >= 2:
                original_url = row[0]
                pages.add(original_url)
        
        # Fetch each unique page and extract emails
        for page_url in list(pages)[:10]:  # Max 10 unique pages
            try:
                # Get the most recent snapshot
                ts = data[1][1] if len(data) > 1 else ''
                archive_url = f"https://web.archive.org/web/{ts}/{page_url}"
                
                page_req = urllib.request.Request(archive_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                with urllib.request.urlopen(page_req, timeout=10) as pr:
                    html = pr.read().decode('utf-8', errors='replace')
                
                # Extract emails
                base_domain = domain.replace('www.', '')
                for m in re.finditer(r'[\w.+-]+@[\w.-]*\.\w{2,4}', html, re.IGNORECASE):
                    email = m.group(0).lower()
                    # Only keep emails matching this domain
                    if base_domain in email:
                        found.add(email)
                
                time.sleep(0.5)  # Polite delay
                
            except Exception:
                continue
    
    except Exception:
        pass
    
    return list(found)


# ── METHOD 5: NAME-BASED PATTERNS ──────────────────────────────

NAME_PREFIXES = [
    "info", "grants", "contact", "apply", "proposals",
    "giving", "foundation", "program", "director",
    "admin", "office", "hello", "support", "president",
    "executive", "secretary", "staff", "trustee",
    "scholarships", "community", "donations", "fellowships",
]

def try_name_patterns(domain):
    """Try common email prefixes at the domain."""
    emails = []
    for prefix in NAME_PREFIXES:
        emails.append(f"{prefix}@{domain}")
    return emails

# ── METHOD 4: SMTP MULTI-PREFIX PROBE ─────────────────────────

SMTP_PREFIXES = [
    "grants", "apply", "contact", "proposals", "program",
    "giving", "foundation", "info", "director", "admin",
    "office", "hello", "support", "president",
    "executive", "secretary", "staff", "trustee",
    "scholarships", "community", "donations", "fellowships",
]

def try_smtp_probe(domain, dashboard=None):
    """
    Try ALL common email prefixes at the domain and SMTP-verify each.
    Returns list of (email, status) for prefixes that pass.
    Stops early if it finds a high-priority prefix (grants, apply, proposals).
    """
    verified = []
    high_priority = {'grants', 'apply', 'proposals', 'contact', 'program'}
    
    # Check if domain has MX first
    mx_hosts = get_mx(domain)
    if not mx_hosts:
        return []
    
    # Score prefixes by likelihood
    scored = [(p, _prefix_score(p)) for p in SMTP_PREFIXES]
    scored.sort(key=lambda x: -x[1])
    
    for prefix, _ in scored:
        email = f"{prefix}@{domain}"
        if dashboard:
            dashboard.update(current_email=email)
            dashboard.render()
        
        status = verify_email(email)
        if status == 'valid':
            verified.append((email, prefix))
            if prefix in high_priority:
                break  # Found a great one, stop
    
    return verified

def _prefix_score(prefix):
    """Score how likely a prefix is to reach decision-makers."""
    scores = {
        'grants': 100, 'apply': 95, 'proposals': 90,
        'contact': 60, 'program': 55, 'giving': 50,
        'director': 45, 'foundation': 40, 'info': 30,
        'admin': 25, 'office': 20, 'hello': 15,
        'support': 10, 'president': 5, 'executive': 5,
        'secretary': 5, 'staff': 5, 'trustee': 5,
        'scholarships': 5, 'community': 5, 'donations': 5,
        'fellowships': 5,
    }
    return scores.get(prefix, 1)

# ── PIPELINE ────────────────────────────────────────────────────

ENRICH_ORDER = ['smtp', 'catchall', 'whois', 'websearch', 'wayback', 'name_patterns']

METHOD_LABELS = {
    'smtp': 'SMTP PROBE',
    'catchall': 'CATCH-ALL',
    'whois': 'WHOIS',
    'websearch': 'WEB SEARCH',
    'wayback': 'WAYBACK MACHINE',
    'name_patterns': 'NAME PATTERNS',
}

METHOD_ICONS = {
    'smtp': '🎯',
    'catchall': '🪤',
    'whois': '📋',
    'websearch': '🔍',
    'wayback': '🕰️',
    'name_patterns': '👤',
}

class LiveDashboard:
    """Live-updating progress dashboard."""
    def __init__(self, total):
        self.total = total
        self.processed = 0
        self.found = {'smtp': 0, 'catchall': 0, 'whois': 0, 'websearch': 0, 'wayback': 0, 'name_patterns': 0}
        self.not_found = 0
        self.skipped = 0
        self.errors = 0
        self.lock = threading.Lock()
        self.start_time = datetime.now()
        self.current_domain = ""
        self.current_method = ""
        self.current_name = ""
        self.current_email = ""
        self.recent_finds = []  # [(name, email, method), ...]
        self.last_update = 0
    
    def update(self, **kwargs):
        with self.lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)
    
    def found_email(self, name, email, method):
        with self.lock:
            self.recent_finds.insert(0, (name, email, method))
            if len(self.recent_finds) > 8:
                self.recent_finds.pop()
    
    def inc(self, key):
        with self.lock:
            if key == 'found':
                # 'found' is a dict, not a simple counter
                pass
            elif hasattr(self, key):
                setattr(self, key, getattr(self, key) + 1)
    
    def render(self):
        with self.lock:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            rate = self.processed / elapsed * 3600 if elapsed > 0 else 0
            remaining = self.total - self.processed
            eta_sec = remaining / rate * 3600 if rate > 0 else 0
            pct = min(self.processed / self.total * 100, 100) if self.total > 0 else 0
            
            # Progress bar
            bar_w = 30
            filled = int(bar_w * pct / 100)
            bar = '█' * filled + '░' * (bar_w - filled)
            found_total = sum(self.found.values())
            
            lines = []
            lines.append(f"\033[2J\033[H")  # Clear screen
            lines.append(f"  ╔{'═'*56}╗")
            lines.append(f"  ║        📧  EMAIL ENRICHMENT PIPELINE          ║")
            lines.append(f"  ╚{'═'*56}╝")
            lines.append(f"")
            lines.append(f"  ╔{'═'*56}╗")
            lines.append(f"  ║  {bar}  {pct:5.1f}%{' '*(29-int(pct/3.3))}║")
            lines.append(f"  ║{' ' * 58}║")
            lines.append(f"  ║  📨 Processed: {self.processed:>6,} / {self.total:,}    ⚡ {rate:>5.0f}/hr    ⏱️ {str(timedelta(seconds=int(elapsed))):>8s}  ║")
            lines.append(f"  ║  ✅ Found:     {found_total:>6,}    ❌ Not found: {self.not_found:>5,}    ⏳ ETA: {str(timedelta(seconds=int(eta_sec))):>8s}  ║")
            lines.append(f"  ║{' ' * 58}║")
            lines.append(f"  ║   🎯 SMTP Probe:   {self.found['smtp']:>5,}    🪤 Catch-all:   {self.found['catchall']:>5,}    ║")
            lines.append(f"  ║   📋 WHOIS:        {self.found['whois']:>5,}    🔍 Web Search:  {self.found['websearch']:>5,}    ║")
            lines.append(f"  ║   🕰️ Wayback:      {self.found['wayback']:>5,}    👤 Name Patterns:{self.found['name_patterns']:>5,}    ║")
            lines.append(f"  ║{' ' * 58}║")
            lines.append(f"  ║  ⏭️  Skipped: {self.skipped:>5,}  ⚠️  Errors: {self.errors:>5,}                        ║")
            lines.append(f"  ╚{'═'*56}╝")
            lines.append(f"")
            lines.append(f"  Now:  {self.current_name[:50]:50s}")
            lines.append(f"  📍   {self.current_domain:35s}  [{METHOD_ICONS.get(self.current_method, '❓')} {METHOD_LABELS.get(self.current_method, '?'):15s}]")
            if self.current_email:
                lines.append(f"  📧   {self.current_email:55s}")
            lines.append(f"")
            
            # Recent finds (show every 5th-ish email found)
            if self.recent_finds:
                lines.append(f"  ── Recent finds ──")
                for i, (n, e, m) in enumerate(self.recent_finds):
                    if i >= 5:
                        break
                    icon = METHOD_ICONS.get(m, '📧')
                    lines.append(f"  {icon} {e:40s}  ({n[:35]})")
                lines.append(f"")
            
            sys.stdout.write('\n'.join(lines))
            sys.stdout.flush()

def process_domain(name, domain, dashboard, quick_mode=False):
    """Process one domain through the enrichment pipeline."""
    dashboard.update(current_domain=domain, current_name=name, current_email="")
    
    verified_email = None
    found_by = None
    
    for method in ENRICH_ORDER:
        if verified_email:
            break
        
        dashboard.update(current_method=method)
        dashboard.render()
        
        if method == 'smtp':
            candidates = [email for email, _ in try_smtp_probe(domain, dashboard)]
            # Already verified — treat as valid without re-verifying
            for email in candidates:
                if verified_email:
                    break
                if not email or '@' not in email:
                    continue
                verified_email = email
                found_by = method
                dashboard.update(current_email=email)
                dashboard.render()
        elif method == 'whois':
            candidates = try_whois(domain)
        elif method == 'websearch':
            candidates = try_web_search(name, domain)
        elif method == 'wayback':
            candidates = try_wayback(domain)
        elif method == 'catchall':
            # Catch-all: mark domain info@ as valid if catch-all detected
            result = check_catch_all(domain)
            if result == 'catchall':
                verified_email = f"info@{domain}"
                found_by = 'catchall'
                dashboard.update(current_email=f"info@{domain} (catch-all ✓)")
                dashboard.render()
            candidates = []
        elif method == 'name_patterns':
            candidates = try_name_patterns(domain)
        else:
            candidates = []
        
        for email in candidates:
            if verified_email:
                break
            if not email or '@' not in email:
                continue
            local, dom = email.split('@', 1)
            if len(local) < 1 or '.' not in dom:
                continue
            
            # Only SMTP-verify if not already verified by smtp probe
            if method != 'smtp':
                dashboard.update(current_email=email)
                dashboard.render()
                
                if quick_mode:
                    verified_email = email
                    found_by = method
                else:
                    status = verify_email(email)
                    if status == 'valid':
                        verified_email = email
                        found_by = method
    
    if verified_email:
        dashboard.found[found_by] += 1
        dashboard.update(current_email=verified_email)
        dashboard.found_email(name, verified_email, found_by)
        dashboard.render()
        return verified_email, found_by
    else:
        dashboard.not_found += 1
        return None, None


def main():
    import argparse
    global ENRICH_ORDER
    parser = argparse.ArgumentParser(description="Email enrichment pipeline")
    parser.add_argument("--quick", type=int, default=0, nargs='?', const=50,
                        help="Process only N domains (quick test mode)")
    parser.add_argument("--method", type=str, default=None,
                        choices=ENRICH_ORDER + ['all'],
                        help="Only run specific method")
    parser.add_argument("--status", action="store_true",
                        help="Show current enrichment status")
    parser.add_argument("--workers", type=int, default=15,
                        help="Concurrent workers")
    args = parser.parse_args()
    
    if args.status:
        show_status()
        return
    
    if args.method and args.method != 'all':
        ENRICH_ORDER = [args.method]
    
    # Load CSV
    if not os.path.exists(CSV_PATH):
        print(f"  ERROR: {CSV_PATH} not found!")
        return
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    # Group by domain, pick the best foundation name per domain
    domain_map = {}
    for r in rows:
        email = (r.get('EMAIL', '') or '').strip()
        if '@' not in email:
            continue
        domain = email.split('@')[1].lower()
        name = r.get('NAME', '').strip()
        # Keep the shortest/simplest name for the domain
        if domain not in domain_map or len(name) < len(domain_map[domain][0]):
            domain_map[domain] = (name, r['EIN'])
    
    domains = list(domain_map.items())
    total = len(domains)
    
    if args.quick and args.quick < len(domains):
        domains = domains[:args.quick]
        total = len(domains)
    
    print(f"\n  Loaded {total:,} unique domains from {len(rows):,} addresses\n")
    time.sleep(2)
    
    dashboard = LiveDashboard(total)
    
    # Track new emails found
    new_emails = {}  # domain -> (email, method)
    skipped = 0
    
    try:
        for idx, (domain, (name, ein)) in enumerate(domains):
            dashboard.update(processed=idx, current_domain=domain, current_name=name)
            dashboard.render()
            
            # Check if already have a good email (not from generic domain)
            current_email = None
            for r in rows:
                if r['EIN'] == ein and '@' in (r.get('EMAIL', '') or ''):
                    current_email = r['EMAIL'].strip()
                    break
            
            # Skip generic/squatter domains entirely
            generic_domains = {'fam.com', 'familyfoundation.com', 'familyfoundation.org',
                               'privatefoundation.org', 'educationalfoundation.org',
                               'educationfoundation.com', 'scholarshipfoundation.org',
                               'charitablefoundation.org', 'foundation.org',
                               'philanthropicfoundation.org', 'religiousfoundation.org',
                               'communityfoundation.org'}
            
            if domain in generic_domains:
                dashboard.inc('skipped')
                continue
            
            result_email, found_by = process_domain(name, domain, dashboard, quick_mode=(args.quick > 0))
            
            if result_email:
                new_emails[domain] = (result_email, found_by)
            
            # Small delay between domains
            if idx < total - 1:
                time.sleep(0.3)
    
    except KeyboardInterrupt:
        print("\n\n  ⚠️  Interrupted! Saving partial results...")
    
    # ── Final Summary ──
    elapsed = (datetime.now() - dashboard.start_time).total_seconds()
    
    print(f"\033[2J\033[H")
    print(f"  {'='*58}")
    print(f"  📧  ENRICHMENT COMPLETE")
    print(f"  {'='*58}")
    print(f"  Domains processed: {dashboard.processed:,} in {elapsed:.0f}s ({dashboard.processed/elapsed*60:.0f}/min)")
    print(f"  ✅  Found via WHOIS:        {dashboard.found['whois']:>5,}")
    print(f"  ✅  Found via Web Search:   {dashboard.found['websearch']:>5,}")
    print(f"  ✅  Found via Name Patterns:{dashboard.found['name_patterns']:>5,}")
    print(f"  ❌  Not found:              {dashboard.not_found:>5,}")
    print(f"  ⏭️  Skipped (generic):      {dashboard.skipped:>5,}")
    print(f"  ⚠️  Errors:                 {dashboard.errors:>5,}")
    print(f"  {'='*58}")
    
    # Update CSV with new emails
    if new_emails:
        updated = 0
        fieldnames = list(rows[0].keys())
        enrich_col = 'ENRICHED_EMAIL'
        method_col = 'ENRICH_METHOD'
        if enrich_col not in fieldnames:
            fieldnames.append(enrich_col)
        if method_col not in fieldnames:
            fieldnames.append(method_col)
        
        for r in rows:
            email = (r.get('EMAIL', '') or '').strip()
            if '@' in email:
                domain = email.split('@')[1].lower()
                if domain in new_emails:
                    new_email, method = new_emails[domain]
                    if new_email != email:
                        r[enrich_col] = new_email
                        r[method_col] = method
                        updated += 1
        
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        
        print(f"  ✅ Updated {updated:,} rows in enriched_contacts.csv")
        print(f"  {'='*58}")
    
    print()

def show_status():
    """Show current enrichment progress from CSV."""
    if not os.path.exists(CSV_PATH):
        print(f"  No {CSV_PATH} found.")
        return
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    total = len(rows)
    with_email = sum(1 for r in rows if r.get('EMAIL', ''))
    enriched = sum(1 for r in rows if r.get('ENRICHED_EMAIL', ''))
    
    print()
    print(f"  📊  ENRICHMENT STATUS")
    print(f"  {'─'*50}")
    print(f"  Total rows:        {total:>7,}")
    print(f"  With email:        {with_email:>7,}")
    print(f"  Enriched (new):    {enriched:>7,}")
    
    if enriched > 0:
        methods = {}
        for r in rows:
            m = r.get('ENRICH_METHOD', '')
            if m:
                methods[m] = methods.get(m, 0) + 1
        print()
        for m, c in sorted(methods.items(), key=lambda x: -x[1]):
            print(f"    {METHOD_ICONS.get(m, '❓')} {METHOD_LABELS.get(m, m):15s} {c:>5,}")
    print()


if __name__ == '__main__':
    main()
