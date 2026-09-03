"""
SES Foundation Sender
=====================
Amazon SES high-volume sender for personalized foundation emails.
Uses enriched_contacts.csv for verified emails and gmail_api_sender's
personalization engine for deep NTEE-based tailoring.

50,000+ emails/day through SES. Jittered 15-45s per send.

Usage:
  python ses_foundation_sender.py --tier theology --workers 5
  python ses_foundation_sender.py --tier tier1 --workers 10 --turbo
"""

import csv
import smtplib
import ssl
import time
import random
import os
import sys
import json
import argparse
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# SES Config
SMTP_HOST = "email-smtp.us-east-1.amazonaws.com"
SMTP_PORT = 587
SMTP_USER = "AKIASKQS5JXODSJERNES"
SMTP_PASSWORD = "BCRaP22/Crmx5/SBb63vMJL3O2Tvm1oxwh+hgPPhW3xv"
SENDER_NAME = "Charles Prescott"
SENDER_EMAIL = "charles@columbiataxlawyer.com"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENRICHED_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
CLEAN_CSV = os.path.join(SCRIPT_DIR, "send_list_clean.csv")
LOG_DIR = os.path.join(SCRIPT_DIR, "ses_logs")

# Declined foundation tracker
sys.path.insert(0, SCRIPT_DIR)
from declined_foundations import load_declined_eins

# Personalization engine
sys.path.insert(0, SCRIPT_DIR)
from gmail_api_sender import personalize_intro

SUBJECT = "Inquiry Regarding Alignment With Your Foundation's Funding Priorities"

BODY_MIDDLE = """I am beginning graduate study in Fall 2026 and am seeking to identify external foundations whose mission, values, or donor-directed interests intersect with my work. My background includes legal practice (JD, LLM in Taxation), public legal education, mediation, and interdisciplinary research at the intersection of law, society, and theology.

If your foundation considers requests from individual scholars or supports educational or research-oriented initiatives, I would be grateful for any guidance on eligibility, application procedures, or upcoming opportunities. I am happy to provide a brief proposal, CV, or any additional information that would assist in determining potential fit.

Thank you for your time and for the work your foundation does in supporting meaningful initiatives. I appreciate any direction you can offer."""

SIGNATURE = """Warm regards,
Charles Prescott
Columbia, SC
8435044542
charles@columbiataxlawyer.com"""


class SharedState:
    def __init__(self, total):
        self.total = total
        self.sent = 0
        self.errors = 0
        self.lock = threading.Lock()
        self.start_time = datetime.now()
        os.makedirs(LOG_DIR, exist_ok=True)
        self.sent_log = os.path.join(LOG_DIR, "ses_sent.txt")
        self.error_log = os.path.join(LOG_DIR, "ses_errors.txt")

    def record_send(self, ein, name):
        with self.lock:
            self.sent += 1
            count = self.sent
        with open(self.sent_log, "a") as f:
            f.write(f"{ein}|{name[:80]}|{datetime.now().isoformat()}\n")
        return count

    def record_error(self, ein, name, error):
        with self.lock:
            self.errors += 1
        with open(self.error_log, "a") as f:
            f.write(f"{datetime.now().isoformat()}|{ein}|{name[:60]}|{str(error)[:150]}\n")

    def status(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.sent / elapsed * 3600 if elapsed > 0 else 0
        remaining = self.total - self.sent
        eta_sec = remaining / rate * 3600 if rate > 0 else 0
        return (f"Sent: {self.sent:,}/{self.total:,} | "
                f"Errors: {self.errors:,} | Rate: {rate:.0f}/hr | "
                f"ETA: {str(timedelta(seconds=int(eta_sec)))}")


def send_email(server, to_email, foundation_name, row):
    """Send one personalized email via SES."""
    intro = personalize_intro(row)
    body = f"Dear {foundation_name} Team,\n\n{intro}\n\n{BODY_MIDDLE}\n\n{SIGNATURE}"
    
    message = f"From: {SENDER_NAME} <{SENDER_EMAIL}>\n" \
              f"To: {to_email}\n" \
              f"Subject: {SUBJECT}\n\n" \
              f"{body}"
    
    server.sendmail(SENDER_EMAIL, to_email, message.encode('utf-8'))


def worker_send(worker_id, foundations, state, delay_min, delay_max):
    """Worker thread with persistent SES connection."""
    context = ssl.create_default_context()
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
    server.starttls(context=context)
    server.login(SMTP_USER, SMTP_PASSWORD)
    
    print(f"  [Worker {worker_id}] Starting: {len(foundations)} emails")
    sys.stdout.flush()
    
    for idx, row in enumerate(foundations):
        if idx > 0:
            time.sleep(random.randint(delay_min, delay_max))
        
        ein = row['EIN']
        name = row['NAME']
        to_email = row.get('EMAIL', '') or row.get('SCRAPED_EMAIL', '')
        
        if not to_email:
            state.record_error(ein, name, "No email address")
            continue
        
        try:
            send_email(server, to_email, name, row)
            count = state.record_send(ein, name)
            
            if count % 25 == 0:
                print(f"  [Worker {worker_id}] {state.status()}")
                sys.stdout.flush()
                
        except smtplib.SMTPAuthenticationError:
            print(f"\n  [Worker {worker_id}] SES AUTH FAILED!")
            break
        except smtplib.SMTPException as e:
            state.record_error(ein, name, str(e)[:100])
            # Reconnect
            try:
                server.quit()
            except:
                pass
            time.sleep(5)
            try:
                server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
                server.starttls(context=context)
                server.login(SMTP_USER, SMTP_PASSWORD)
            except:
                break
        except Exception as e:
            state.record_error(ein, name, str(e)[:100])
    
    server.quit()
    print(f"  [Worker {worker_id}] Finished")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="SES Foundation Sender")
    parser.add_argument("--tier", default="theology",
                        choices=["theology", "tier1", "tier2", "tier3"],
                        help="Foundation tier")
    parser.add_argument("--workers", type=int, default=5,
                        help="Parallel workers (default: 5)")
    parser.add_argument("--turbo", action="store_true",
                        help="Fast mode: 5-15s jitter")
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-sent EINs")
    parser.add_argument("--dns-verify", action="store_true",
                        help="Verify domains have MX records before sending")
    parser.add_argument("--skip-declined", action="store_true",
                        help="Skip foundations that have politely declined")
    parser.add_argument("--clean-list", action="store_true",
                        help="Use pre-filtered send_list_clean.csv instead of enriched_contacts.csv")
    args = parser.parse_args()
    
    delay_min, delay_max = (5, 15) if args.turbo else (15, 45)
    
    # Determine source CSV
    source_csv = CLEAN_CSV if args.clean_list else ENRICHED_CSV
    source_label = "send_list_clean.csv (pre-filtered)" if args.clean_list else "enriched_contacts.csv (full)"
    
    print("=" * 70)
    print("  SES FOUNDATION SENDER — Amazon Production")
    print("=" * 70)
    print(f"  Workers:      {args.workers}")
    print(f"  Mode:         {'TURBO' if args.turbo else 'STANDARD'}")
    print(f"  Source:       {source_label}")
    print(f"  Jitter:       {delay_min}-{delay_max}s")
    thr = 3600 // ((delay_min + delay_max) // 2) * args.workers
    print(f"  Throughput:   ~{thr:,}/hour (~{thr*24:,}/day)")
    print(f"  Resume:       {'YES' if args.resume else 'No'}")
    print(f"  Skip declined:{'YES' if args.skip_declined else 'No'}")
    print("=" * 70)
    
    # Load contacts
    if not os.path.exists(source_csv):
        print(f"ERROR: {source_csv} not found!")
        if args.clean_list:
            print("  Run `python build_send_list.py` first to create the clean list")
        return
    
    with open(source_csv, 'r', encoding='utf-8') as f:
        all_rows = list(csv.DictReader(f))
    
    # Filter for email only
    with_email = [r for r in all_rows if r.get('EMAIL', '')]
    print(f"\nLoaded {len(all_rows):,} foundations from {source_label}")
    print(f"With emails: {len(with_email):,}")
    
    # Resume
    if args.resume:
        sent_log = os.path.join(LOG_DIR, "ses_sent.txt")
        if os.path.exists(sent_log):
            with open(sent_log, 'r') as f:
                sent_eins = set(line.split('|')[0] for line in f if line.strip() and '|' in line)
            before = len(with_email)
            with_email = [r for r in with_email if r['EIN'] not in sent_eins]
            print(f"Resume: skipped {len(sent_eins):,} already sent "
                  f"({before:,} -> {len(with_email):,})")
    
    # Skip declined foundations
    if args.skip_declined:
        declined = load_declined_eins()
        if declined:
            before = len(with_email)
            with_email = [r for r in with_email if r['EIN'] not in declined]
            print(f"Skip declined: skipped {len(declined):,} declined "
                  f"({before:,} -> {len(with_email):,})")
    
    if not with_email:
        print("Nothing to send!")
        return

    # DNS MX verify (catch bad domains before sending)
    if args.dns_verify:
        print("\n  Running DNS MX verification...")
        sys.stdout.flush()
        import dns.resolver
        _resolver = dns.resolver.Resolver()
        _resolver.nameservers = ['8.8.8.8', '8.8.4.4']
        _resolver.timeout = 2
        _resolver.lifetime = 2

        # Collect unique domains
        domains = set()
        for r in with_email:
            email = r.get('EMAIL', '').strip()
            if '@' in email:
                domains.add(email.split('@')[1].lower())

        # Check all domains with 200 concurrent workers
        good_domains = set()
        dns_cache = {}
        def check(d):
            if d in dns_cache:
                return d, dns_cache[d]
            try:
                _resolver.resolve(d, 'MX')
                dns_cache[d] = True
                return d, True
            except:
                dns_cache[d] = False
                return d, False

        print(f"    Verifying {len(domains):,} unique domains (200 workers)...")
        sys.stdout.flush()
        with ThreadPoolExecutor(max_workers=200) as ex:
            futures = {ex.submit(check, d): d for d in domains}
            for i, f in enumerate(as_completed(futures)):
                d, ok = f.result()
                if ok:
                    good_domains.add(d)
                if (i + 1) % 500 == 0:
                    print(f"      {i+1}/{len(domains)}...", end='\r')
                    sys.stdout.flush()

        before = len(with_email)
        bad_domains = domains - good_domains
        with_email = [r for r in with_email if r.get('EMAIL','').split('@')[-1].lower() in good_domains]
        print(f"\n    DNS verify: {len(good_domains):,} good domains, "
              f"{len(bad_domains):,} bad ({before:,} -> {len(with_email):,} contacts)")

    # Distribute
    slices = [[] for _ in range(args.workers)]
    for i, r in enumerate(with_email):
        slices[i % args.workers].append(r)
    
    print(f"\n{'=' * 70}")
    print(f"  LAUNCHING {args.workers} workers in 3s...")
    sys.stdout.flush()
    time.sleep(3)
    
    state = SharedState(len(with_email))
    
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = []
        for w_id in range(args.workers):
            futures.append(ex.submit(worker_send, w_id, slices[w_id], state, delay_min, delay_max))
        
        try:
            while not all(f.done() for f in futures):
                print(f"  ── {state.status()} ──")
                sys.stdout.flush()
                time.sleep(30)
        except KeyboardInterrupt:
            print("\nStopping... workers finish current send")
    
    elapsed = (datetime.now() - state.start_time).total_seconds()
    print(f"\n{'=' * 70}")
    print(f"  BATCH COMPLETE")
    print(f"  Sent:   {state.sent:,}")
    print(f"  Errors: {state.errors:,}")
    print(f"  Time:   {str(timedelta(seconds=int(elapsed)))}")
    print(f"  Rate:   {(state.sent / elapsed * 3600):.0f}/hr")
    print(f"  Logs:   {LOG_DIR}\\")
    print(f"{'=' * 70}")
    print(f"\nNext: python ses_foundation_sender.py --resume --skip-declined")


if __name__ == '__main__':
    main()
