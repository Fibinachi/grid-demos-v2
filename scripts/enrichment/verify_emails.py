#!/usr/bin/env python3
"""
Email Address Verifier
======================
Does a lightweight SMTP handshake (no email sent) to check if mailboxes
actually exist. Uses each domain's MX server and the RCPT TO command.

Usage:
  python verify_emails.py                  # Verify all, update CSV
  python verify_emails.py --quick          # Verify first 100 as a sample
  python verify_emails.py --stats          # Just show current validation stats
  python verify_emails.py --domain gatesfoundation.org  # Check one domain

How it works:
  1. Looks up the MX record for each domain
  2. Connects to the mail server
  3. Does HELO → MAIL FROM → RCPT TO (never sends actual data)
  4. 250 = mailbox exists, 550+ = doesn't exist
  5. Some servers lie (always accept or always reject) — those are flagged
"""

import csv
import os
import sys
import re
import socket
import smtplib
import ssl
import time
import random
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parseaddr
import dns.resolver

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
LOG_DIR = os.path.join(SCRIPT_DIR, "ses_logs")
VERIFY_LOG = os.path.join(LOG_DIR, "verify_results.csv")

# DNS cache
_dns_cache = {}
_dns_lock = threading.Lock()
_resolver = dns.resolver.Resolver()
_resolver.nameservers = ['8.8.8.8', '8.8.4.4']
_resolver.timeout = 2.0
_resolver.lifetime = 2.0

# Rate-limiting: track last contact time per MX server
_mx_last_hit = {}
_mx_lock = threading.Lock()

VERIFIED_HEADER = "EMAIL_VERIFIED"
METHOD_HEADER = "VERIFY_METHOD"

# ── DNS Helpers ──────────────────────────────────────────────────

def get_mx(domain):
    """Look up MX records for a domain. Returns priority-sorted host list."""
    cache_key = f"mx:{domain}"
    with _dns_lock:
        if cache_key in _dns_cache:
            return _dns_cache[cache_key]
    try:
        answers = _resolver.resolve(domain, 'MX')
        mx_records = [(r.preference, str(r.exchange).rstrip('.')) for r in answers]
        mx_records.sort(key=lambda x: x[0])
        hosts = [h for _, h in mx_records]
        with _dns_lock:
            _dns_cache[cache_key] = hosts
        return hosts
    except dns.resolver.NoAnswer:
        # No MX — try the domain itself as an A record fallback
        try:
            _resolver.resolve(domain, 'A')
            with _dns_lock:
                _dns_cache[cache_key] = [domain]
            return [domain]
        except:
            with _dns_lock:
                _dns_cache[cache_key] = []
            return []
    except Exception:
        with _dns_lock:
            _dns_cache[cache_key] = []
        return []

def extract_domain(email):
    """Extract domain from email address."""
    _, addr = parseaddr(f"<{email}>")
    if not addr:
        return None
    parts = addr.split('@')
    if len(parts) != 2:
        return None
    return parts[1].lower().strip()

# ── SMTP Verification ────────────────────────────────────────────

VERIFY_FROM = "verify@check.columbiataxlawyer.com"

def verify_mailbox(email, timeout=10):
    """
    Verify a single email address via SMTP RCPT TO handshake.
    Returns (email, status, detail):
      status: 'valid', 'invalid', 'unknown', 'error'
    """
    domain = extract_domain(email)
    if not domain:
        return email, 'error', 'invalid_email_format'
    
    mx_hosts = get_mx(domain)
    if not mx_hosts:
        return email, 'error', 'no_mx_or_a_record'
    
    # Try each MX host in priority order
    last_error = None
    for mx in mx_hosts[:3]:  # Only try top 3 MX hosts
        # Rate-limit: at least 0.5s between connections to same MX
        with _mx_lock:
            last_hit = _mx_last_hit.get(mx, 0)
            now = time.time()
            wait = max(0, 0.5 - (now - last_hit))
            if wait > 0:
                time.sleep(wait)
            _mx_last_hit[mx] = time.time()
        
        try:
            sock = socket.create_connection((mx, 25), timeout=timeout)
            smtp = smtplib.SMTP()
            smtp.sock = sock
            smtp.set_debuglevel(0)
            smtp.timeout = timeout
            
            try:
                code, _ = smtp.ehlo("verify.columbiataxlawyer.com")
                if code < 200 or code >= 300:
                    smtp.quit()
                    continue
                
                # Try STARTTLS if available
                if smtp.has_extn('STARTTLS'):
                    try:
                        smtp.starttls(ssl.create_default_context())
                        smtp.ehlo("verify.columbiataxlawyer.com")
                    except:
                        pass  # Non-fatal, continue without TLS
                
                code, _ = smtp.mail(VERIFY_FROM)
                if code < 200 or code >= 300:
                    smtp.quit()
                    continue
                
                code, msg = smtp.rcpt(email)
                smtp.quit()
                
                if code == 250:
                    return email, 'valid', f'accepted_by_{mx}'
                elif code in (550, 551, 552, 553, 554):
                    reason = str(msg).strip().lower()
                    if 'spam' in reason or 'denied' in reason or 'rejected' in reason:
                        return email, 'unknown', f'rejected_{mx}'
                    return email, 'invalid', f'rejected_{code}_by_{mx}'
                else:
                    # Non-standard response — could be greylisting or policy
                    return email, 'unknown', f'code_{code}_from_{mx}'
                    
            except smtplib.SMTPHeloError:
                # Try HELO as fallback
                try:
                    smtp.helo("verify.columbiataxlawyer.com")
                    code, _ = smtp.mail(VERIFY_FROM)
                    if code >= 200 and code < 300:
                        code, msg = smtp.rcpt(email)
                        smtp.quit()
                        if code == 250:
                            return email, 'valid', f'accepted_via_helo_{mx}'
                        else:
                            return email, 'unknown', f'helo_code_{code}'
                except:
                    pass
                last_error = 'helo_error'
            except smtplib.SMTPServerDisconnected:
                last_error = 'disconnected'
            except smtplib.SMTPConnectError:
                last_error = 'connect_refused'
            except socket.timeout:
                last_error = 'timeout'
            except Exception as e:
                last_error = str(e)[:80]
            finally:
                try:
                    smtp.close()
                except:
                    pass
                    
        except socket.timeout:
            last_error = f'timeout_connecting_{mx}'
        except ConnectionRefusedError:
            last_error = f'connection_refused_{mx}'
        except Exception as e:
            last_error = f'{type(e).__name__}:{str(e)[:60]}'
    
    return email, 'error', last_error or 'all_mx_failed'


# ── Batch Processing ─────────────────────────────────────────────

def process_row(row, timeout=10):
    """Process a single CSV row and return updated row."""
    email = (row.get('EMAIL', '') or row.get('SCRAPED_EMAIL', '') or '').strip()
    if not email:
        row[VERIFIED_HEADER] = 'skipped'
        row[METHOD_HEADER] = 'no_email'
        return row
    
    email, status, detail = verify_mailbox(email, timeout=timeout)
    row[VERIFIED_HEADER] = status
    row[METHOD_HEADER] = detail
    return row


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verify email addresses via SMTP handshake")
    parser.add_argument("--quick", type=int, nargs='?', const=100, default=0,
                        help="Only verify first N addresses (default: 100)")
    parser.add_argument("--stats", action="store_true",
                        help="Show current verification stats only")
    parser.add_argument("--domain", type=str, default=None,
                        help="Verify all emails for a specific domain")
    parser.add_argument("--workers", type=int, default=20,
                        help="Concurrent verifiers (default: 20)")
    parser.add_argument("--timeout", type=int, default=10,
                        help="SMTP timeout per connection (default: 10s)")
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
        return
    
    if args.domain:
        verify_domain(args.domain, args.workers, args.timeout)
        return
    
    verify_all(args.quick, args.workers, args.timeout)


def show_stats():
    """Show current verification stats from CSV."""
    if not os.path.exists(CSV_PATH):
        print(f"No {CSV_PATH} found.")
        return
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    total = len(rows)
    with_email = sum(1 for r in rows if r.get('EMAIL', ''))
    
    # Check if already verified
    if VERIFIED_HEADER in rows[0] if rows else False:
        valid = sum(1 for r in rows if r.get(VERIFIED_HEADER) == 'valid')
        invalid = sum(1 for r in rows if r.get(VERIFIED_HEADER) == 'invalid')
        unknown = sum(1 for r in rows if r.get(VERIFIED_HEADER) == 'unknown')
        error = sum(1 for r in rows if r.get(VERIFIED_HEADER) == 'error')
        skipped = sum(1 for r in rows if r.get(VERIFIED_HEADER) == 'skipped')
        unverified = sum(1 for r in rows if not r.get(VERIFIED_HEADER))
        
        print()
        print("  📊  EMAIL VERIFICATION STATS")
        print(f"  {'─'*50}")
        print(f"  Total rows:       {total:>7,}")
        print(f"  With emails:      {with_email:>7,}")
        print(f"  ✅ Valid:          {valid:>7,}")
        print(f"  ❌ Invalid:        {invalid:>7,}")
        print(f"  ❓ Unknown:        {unknown:>7,}")
        print(f"  ⚠️  Error:          {error:>7,}")
        print(f"  ⏭️  Skipped (no email): {skipped:>7,}")
        print(f"  🔄 Unverified:     {unverified:>7,}")
        print(f"  {'─'*50}")
        if valid + invalid + unknown > 0:
            valid_pct = valid / (valid + invalid + unknown) * 100
            print(f"  ✅ Hit rate: {valid_pct:.0f}% of checked addresses look valid")
        print()
    else:
        print(f"\n  📊  CONTACTS OVERVIEW (unverified)")
        print(f"  {'─'*50}")
        print(f"  Total rows:       {total:>7,}")
        print(f"  With emails:      {with_email:>7,}")
        print(f"  Without emails:   {total - with_email:>7,}")
        print(f"\n  Run without --stats to verify them.")
        print()


def verify_domain(domain, workers, timeout):
    """Verify all addresses for a specific domain."""
    print(f"\n  🔍 Checking all addresses @{domain}...\n")
    
    if not os.path.exists(CSV_PATH):
        print(f"  {CSV_PATH} not found!")
        return
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    # Find matching rows
    matching = []
    for i, row in enumerate(rows):
        email = (row.get('EMAIL', '') or '').strip().lower()
        if extract_domain(email) == domain.lower():
            matching.append((i, row))
    
    if not matching:
        print(f"  No addresses found for domain '{domain}'")
        return
    
    print(f"  Found {len(matching)} addresses for {domain}")
    print()
    
    for idx, (i, row) in enumerate(matching):
        email = (row.get('EMAIL', '') or '').strip()
        print(f"  [{idx+1}/{len(matching)}] {row['NAME'][:45]:45s} {email}")
        email_addr, status, detail = verify_mailbox(email, timeout=timeout)
        if status == 'valid':
            print(f"        ✅ VALID — {detail}")
        elif status == 'invalid':
            print(f"        ❌ INVALID — {detail}")
        elif status == 'unknown':
            print(f"        ❓ UNKNOWN — {detail}")
        else:
            print(f"        ⚠️  ERROR — {detail}")
        print()
        
        if idx < len(matching) - 1:
            time.sleep(random.uniform(0.3, 1.0))


def verify_all(quick_count, workers, timeout):
    """Verify all email addresses in the CSV."""
    if not os.path.exists(CSV_PATH):
        print(f"  ERROR: {CSV_PATH} not found!")
        return
    
    print("=" * 70)
    print("  EMAIL ADDRESS VERIFIER — SMTP Handshake")
    print("=" * 70)
    print("  This checks if mailboxes exist by doing a lightweight")
    print("  SMTP handshake (NO email is sent). Uses MX records")
    print("  and RCPT TO command.")
    print()
    print("  ⚠️  Some mail servers lie (always accept or always reject).")
    print("  ⚠️  Results marked 'unknown' need manual review.")
    print("=" * 70)
    
    # Load CSV
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    
    print(f"\n  Loaded {len(rows):,} rows")
    
    # Add headers if missing
    if VERIFIED_HEADER not in fieldnames:
        fieldnames.append(VERIFIED_HEADER)
    if METHOD_HEADER not in fieldnames:
        fieldnames.append(METHOD_HEADER)
    
    # Find unverified rows
    to_check = []
    for i, row in enumerate(rows):
        email = (row.get('EMAIL', '') or row.get('SCRAPED_EMAIL', '') or '').strip()
        if not email:
            row[VERIFIED_HEADER] = 'skipped'
            row[METHOD_HEADER] = 'no_email'
        elif not row.get(VERIFIED_HEADER):
            to_check.append((i, row))
    
    if quick_count > 0:
        to_check = to_check[:quick_count]
    
    verified_before = sum(1 for r in rows if r.get(VERIFIED_HEADER) not in (None, '', 'skipped'))
    
    if not to_check:
        print("  ✅ All addresses already verified!")
        show_stats()
        return
    
    print(f"  To verify: {len(to_check):,} addresses")
    print(f"  Already verified: {verified_before:,}")
    print(f"  Workers: {workers} | Timeout: {timeout}s")
    print()
    
    # Group by domain to avoid hammering one server
    domain_groups = {}
    for i, row in to_check:
        email = (row.get('EMAIL', '') or '').strip()
        domain = extract_domain(email) or 'unknown'
        if domain not in domain_groups:
            domain_groups[domain] = []
        domain_groups[domain].append((i, row))
    
    print(f"  Unique domains: {len(domain_groups):,}")
    print()
    
    # Process with interleaved domains for politeness
    results = {'valid': 0, 'invalid': 0, 'unknown': 0, 'error': 0, 'skipped': 0}
    total = len(to_check)
    start = datetime.now()
    
    # Flatten but interleave by domain
    queue = []
    domain_items = list(domain_groups.items())
    while any(items for _, items in domain_items):
        for d, items in domain_items:
            if items:
                queue.append(items.pop(0))
    
    done = 0
    try:
        with ThreadPoolExecutor(max_workers=min(workers, 50)) as ex:
            futures = {}
            for idx, (i, row) in enumerate(queue):
                fut = ex.submit(process_row, row, timeout)
                futures[fut] = (i, row)
                
                # Pace submission: submit in batches
                if (idx + 1) % (workers * 2) == 0:
                    time.sleep(0.5)
            
            for fut in as_completed(futures):
                row = fut.result()
                i, _ = futures[fut]
                rows[i] = row
                
                status = row.get(VERIFIED_HEADER, 'error')
                results[status] = results.get(status, 0) + 1
                done += 1
                
                if done % 100 == 0:
                    elapsed = (datetime.now() - start).total_seconds()
                    rate = done / elapsed if elapsed > 0 else 0
                    print(f"  [{done:,}/{total:,}] "
                          f"✅{results.get('valid',0)} "
                          f"❌{results.get('invalid',0)} "
                          f"❓{results.get('unknown',0)} "
                          f"⚠️{results.get('error',0)} "
                          f"| {rate:.0f}/min", end='\r')
                    sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n\n  ⚠️  Interrupted! Saving partial results...")
    
    # Save
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n  {'='*50}")
    print(f"  ✅ VERIFICATION COMPLETE")
    print(f"  {'='*50}")
    print(f"  Checked: {done:,} in {elapsed:.0f}s ({done/elapsed*60:.0f}/min)")
    print(f"  ✅ Valid:   {results.get('valid', 0):>6,}")
    print(f"  ❌ Invalid: {results.get('invalid', 0):>6,}")
    print(f"  ❓ Unknown: {results.get('unknown', 0):>6,}")
    print(f"  ⚠️  Error:   {results.get('error', 0):>6,}")
    print(f"  ⏭️  Skipped: {results.get('skipped', 0):>6,}")
    print(f"  {'='*50}")
    print(f"  Updated: {CSV_PATH}")
    print()


if __name__ == '__main__':
    main()
