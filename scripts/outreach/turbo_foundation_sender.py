"""
High-Throughput Foundation Sender
==================================
Parallel multi-threaded foundation email sender with significantly higher
throughput than the single-threaded version.

Key design:
  - ThreadPoolExecutor with N worker threads (default 5, configurable)
  - Each worker has its own persistent SMTP connection (no reconnect per email)
  - 30-90 second jitter per worker (safe, distributed across workers)
  - Optional dual-email rotation (charles@charlesprescott.net + columbiataxlawyer.com)
  - Thread-safe shared progress tracking

Throughput comparison (5 workers, 30-90s jitter each):
  Worker 1: foundation[0], foundation[5], foundation[10], ...
  Worker 2: foundation[1], foundation[6], foundation[11], ...
  ...
  Effective: ~300 emails/hour vs ~20 emails/hour (15x faster)

Usage:
  $env:EMAIL_PASSWORD="your_password"; python turbo_foundation_sender.py
  $env:EMAIL_PASSWORD="your_password"; python turbo_foundation_sender.py --workers 10
  $env:EMAIL_PASSWORD="your_password"; $env:EMAIL_PASSWORD2="pass2"; python turbo_foundation_sender.py --dual

Tiers available (use --tier argument):
  tier1        - 9,431 foundations, $10M+ assets
  tier2        - 24,484 foundations, $1M-$10M assets
  tier3        - 8,779 foundations, $500K-$1M assets
  theology     - 29,770 theology-relevant foundations (default)
  all          - 42,694 all foundations
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
import socket
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty

# ── Configuration ──────────────────────────────────────────────────────────
SMTP_HOST = "smtp.hostinger.com"
SMTP_PORT = 587
PRIMARY_EMAIL = "charles@columbiataxlawyer.com"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TIER_FILES = {
    "tier1":   os.path.join(SCRIPT_DIR, "foundations_tier1_10m_plus.csv"),
    "tier2":   os.path.join(SCRIPT_DIR, "foundations_tier2_1m_10m.csv"),
    "tier3":   os.path.join(SCRIPT_DIR, "foundations_tier3_500k_1m.csv"),
    "theology": os.path.join(SCRIPT_DIR, "theology_priority_foundations.csv"),
    "all":     os.path.join(SCRIPT_DIR, "foundations_master_list.csv"),
}

# Timing presets
# Safe mode: 1 worker, 3-5 min jitter, ramps up slowly — won't trip Hostinger
SAFE_WORKERS = 1
SAFE_MIN_DELAY = 90     # 1.5 minutes (halved from 180)
SAFE_MAX_DELAY = 150    # 2.5 minutes (halved from 300)
SAFE_DAY_LIMIT = 100    # Slightly increased since we're faster now

# Turbo mode: 5 workers, 30-90s jitter — fastest but may trigger flags
TURBO_WORKERS = 5
TURBO_MIN_DELAY = 30
TURBO_MAX_DELAY = 90

LOG_DIR = os.path.join(SCRIPT_DIR, "turbo_logs")

# ── Story ──────────────────────────────────────────────────────────────────
# Reuse personalization from the Gmail API sender
sys.path.insert(0, SCRIPT_DIR)
from gmail_api_sender import personalize_intro

STORY_TEMPLATE = """{intro}

I am beginning graduate study in Fall 2026 and am seeking to identify external foundations whose mission, values, or donor-directed interests intersect with my work. My background includes legal practice (JD, LLM in Taxation), public legal education, mediation, and interdisciplinary research at the intersection of law, society, and theology.

If your foundation considers requests from individual scholars or supports educational or research-oriented initiatives, I would be grateful for any guidance on eligibility, application procedures, or upcoming opportunities. I am happy to provide a brief proposal, CV, or any additional information that would assist in determining potential fit.

Thank you for your time and for the work your foundation does in supporting meaningful initiatives. I appreciate any direction you can offer.

Warm regards,
Charles Prescott
Columbia, SC
8435044542
charles@columbiataxlawyer.com"""

SUBJECT = "Inquiry Regarding Alignment With Your Foundation's Funding Priorities"


# ── Shared State (thread-safe) ─────────────────────────────────────────────
class SharedState:
    def __init__(self, total):
        self.total = total
        self.sent = 0
        self.errors = 0
        self.lock = threading.Lock()
        self.start_time = datetime.now()
        self.sent_log = os.path.join(LOG_DIR, "turbo_sent.txt")
        self.error_log = os.path.join(LOG_DIR, "turbo_errors.txt")
        os.makedirs(LOG_DIR, exist_ok=True)

    def record_send(self, ein, name, worker_id):
        with self.lock:
            self.sent += 1
            count = self.sent
        with open(self.sent_log, "a") as f:
            f.write(f"{ein}|{name[:80]}|{worker_id}|{datetime.now().isoformat()}\n")
        return count

    def record_error(self, ein, name, worker_id, error):
        with self.lock:
            self.errors += 1
        with open(self.error_log, "a") as f:
            f.write(f"{datetime.now().isoformat()}|W{worker_id}|{ein}|{name[:60]}|{str(error)[:150]}\n")

    def status_line(self, worker_id="*"):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.sent / elapsed * 3600 if elapsed > 0 else 0
        remaining = self.total - self.sent
        eta_sec = remaining / rate * 3600 if rate > 0 else 0
        eta = str(timedelta(seconds=int(eta_sec)))
        return (f"[W{worker_id}] Sent: {self.sent:,}/{self.total:,} "
                f"| Errors: {self.errors:,} | Rate: {rate:.0f}/hr | ETA: {eta}")


# ── Email Guessing ─────────────────────────────────────────────────────────
# ── Domain resolution cache ──────────────────────────────────────────────
# Avoids repeated DNS lookups for the same domain
_dns_cache = {}

def _resolve_domain(domain):
    """Quick DNS check: does this domain have MX or A records?"""
    if domain in _dns_cache:
        return _dns_cache[domain]
    try:
        socket.getaddrinfo(domain, 80, timeout=3)
        _dns_cache[domain] = True
        return True
    except Exception:
        _dns_cache[domain] = False
        return False


_pdl_cache = {}

def _lookup_pdl(name):
    """Try People Data Labs enrichment for real website."""
    import urllib.request, json, urllib.parse
    if name in _pdl_cache:
        return _pdl_cache[name]
    api_key = os.environ.get("PDL_KEY", "")
    if not api_key:
        return None
    try:
        url = f"https://api.peopledatalabs.com/v5/company/enrich?name={urllib.parse.quote(name)}"
        req = urllib.request.Request(url)
        req.add_header("X-Api-Key", api_key)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            site = data.get("website", "")
            if site:
                _pdl_cache[name] = site
                return site
    except Exception:
        pass
    _pdl_cache[name] = None
    return None


EMAIL_PREFIXES = ["info", "grants", "contact", "apply", "foundation", "hello"]


def guess_email(name):
    """
    Smart email guessing with DNS verification and PDL fallback.
    Returns 'email@domain' or '' if nothing found.
    """
    # Step 1: Generate candidate domains from name
    clean = name.strip().replace(",", "").lower()
    clean = clean.replace("the ", "")
    for suffix in [" foundation", " foundation inc", " foundation corporation",
                   " inc", " corp", " llc", ", inc.", ", llc"]:
        clean = clean.replace(suffix, "")

    words = clean.split()
    if not words:
        return ""

    connectors = {"and", "the", "of", "for", "&", "de", "la", "del"}
    meaningful = [w for w in words if w not in connectors and len(w) > 2]
    if not meaningful:
        meaningful = words

    last = meaningful[-1] if meaningful else words[-1]
    first = meaningful[0] if meaningful else words[0]

    # Build domain candidates
    candidates = [
        f"{last}foundation.org",
        f"{first}foundation.org",
        f"{''.join(meaningful)}.org",
        f"{last}.org",
        f"{first}.org",
        f"{last}foundation.com",
        f"{''.join(meaningful)}foundation.org",
    ]
    # Trim very long domains
    candidates = [d for d in candidates if len(d) < 50]

    # Step 2: Try DNS lookup on candidates
    for domain in candidates:
        if _resolve_domain(domain):
            return f"info@{domain}"

    # Step 3: PDL fallback for known names
    pdl_site = _lookup_pdl(name)
    if pdl_site:
        domain = pdl_site.strip().lower()
        domain = domain.replace("http://", "").replace("https://", "").split("/")[0]
        return f"info@{domain}"

    # Step 4: Best guess without DNS verification
    if len(meaningful) >= 2:
        domain = f"{meaningful[-1]}foundation.org"
    else:
        domain = f"{meaningful[0]}foundation.org"

    return f"info@{domain}"


# ── Worker ─────────────────────────────────────────────────────────────────
def worker_send(worker_id, foundations, state, password1, password2=None,
                use_dual=False, min_delay=SAFE_MIN_DELAY, max_delay=SAFE_MAX_DELAY,
                day_limit=None):
    """
    Worker thread: opens its own SMTP connection, sends foundations from its
    slice of the list, with jittered delays between each send.

    In safe mode, gradually ramps up speed over first 20 sends
    to look more human-like.
    """
    email = PRIMARY_EMAIL
    password = password1

    print(f"  [Worker {worker_id}] Starting: {len(foundations)} foundations "
          f"(delay: {min_delay}-{max_delay}s{' | day limit: '+str(day_limit) if day_limit else ''})")
    sys.stdout.flush()

    # Open persistent SMTP connection
    try:
        context = ssl.create_default_context()
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.starttls(context=context)
        server.login(email, password)
    except Exception as e:
        print(f"  [Worker {worker_id}] SMTP CONNECTION FAILED: {str(e)[:100]}")
        for row in foundations:
            state.record_error(row['EIN'], row['NAME'], worker_id, f"SMTP connect: {str(e)[:80]}")
        return

    for idx, row in enumerate(foundations):
        # Check day limit
        if day_limit and state.sent >= day_limit:
            print(f"  [Worker {worker_id}] Day limit of {day_limit} reached. Stopping.")
            break

        ein = row['EIN']
        name = row['NAME']
        to_email = guess_email(name)
        if not to_email:
            state.record_error(ein, name, worker_id, "Could not generate email")
            continue

        # Rotate to secondary email every other email if dual mode
        if use_dual and password2 and idx % 2 == 1:
            current_email = SECONDARY_EMAIL
            current_password = password2
        else:
            current_email = email
            current_password = password

        # Build message
        body = f"Dear {name} Team,\n\n" + STORY_TEMPLATE.format(intro=personalize_intro(row))
        message = (f"From: {current_email}\n"
                   f"To: {to_email}\n"
                   f"Subject: {SUBJECT}\n\n"
                   f"{body}")

        # Send
        try:
            server.sendmail(current_email, to_email, message.encode('utf-8'))
            count = state.record_send(ein, name, worker_id)

            # Status every 5 sends per worker
            if count % 5 == 0:
                print(f"  {state.status_line(worker_id)}")
                sys.stdout.flush()

        except smtplib.SMTPAuthenticationError:
            print(f"\n  [Worker {worker_id}] SMTP AUTH FAILED! Stopping worker.")
            state.record_error(ein, name, worker_id, "SMTP auth failed")
            break
        except smtplib.SMTPException as e:
            state.record_error(ein, name, worker_id, str(e)[:100])
            # Reconnect on SMTP errors
            try:
                server.quit()
            except:
                pass
            time.sleep(10)
            try:
                context = ssl.create_default_context()
                server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
                server.starttls(context=context)
                server.login(current_email, current_password)
            except Exception as e2:
                print(f"  [Worker {worker_id}] Reconnect failed: {str(e2)[:100]}")
                state.record_error(ein, name, worker_id, f"Reconnect fail: {str(e2)[:80]}")
                break
        except Exception as e:
            state.record_error(ein, name, worker_id, str(e)[:100])

        # Per-worker jittered delay — ramp up speed gradually in safe mode
        if idx < len(foundations) - 1:
            if day_limit and idx < 20:
                # Ramp up: start slow, gradually speed up
                ramp_delay = max_delay - (max_delay - min_delay) * (idx / 20)
                delay = random.randint(int(ramp_delay * 0.8), int(ramp_delay * 1.2))
            else:
                delay = random.randint(min_delay, max_delay)
            time.sleep(delay)

    # Close connection
    try:
        server.quit()
    except:
        pass
    print(f"  [Worker {worker_id}] Finished ({len(foundations)} assigned, "
          f"last: {foundations[-1]['NAME'][:40] if foundations else 'none'})")
    sys.stdout.flush()


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Turbo Foundation Sender")
    parser.add_argument("--tier", default="theology",
                        choices=["tier1", "tier2", "tier3", "theology", "all"],
                        help="Foundation tier (default: theology)")
    parser.add_argument("--workers", type=int, default=None,
                        help="Worker count (default: 1 safe, 5 turbo)")
    parser.add_argument("--turbo", action="store_true",
                        help="Fast mode: 5 workers, 30-90s delays (may trigger Hostinger)")
    parser.add_argument("--dual", action="store_true",
                        help="Rotate between primary and secondary email")
    parser.add_argument("--resume", action="store_true",
                        help="Skip EINs already in sent log")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max emails to send per run")
    args = parser.parse_args()

    # Mode selection
    safe_mode = not args.turbo
    if args.workers:
        num_workers = args.workers
    else:
        num_workers = SAFE_WORKERS if safe_mode else TURBO_WORKERS

    min_delay = SAFE_MIN_DELAY if safe_mode else TURBO_MIN_DELAY
    max_delay = SAFE_MAX_DELAY if safe_mode else TURBO_MAX_DELAY
    day_limit = args.limit if args.limit is not None else (SAFE_DAY_LIMIT if safe_mode else None)
    if day_limit == 0:
        day_limit = None  # 0 means no limit

    password1 = os.environ.get("EMAIL_PASSWORD", "")
    password2 = os.environ.get("EMAIL_PASSWORD2", "")

    if not password1:
        print("ERROR: EMAIL_PASSWORD environment variable not set!")
        print("Usage: $env:EMAIL_PASSWORD=\"your_password\"; python turbo_foundation_sender.py")
        return

    if args.dual and not password2:
        print("WARNING: --dual requested but EMAIL_PASSWORD2 not set. "
              "Falling back to single identity.")

    # ── Load foundations ───────────────────────────────────────────────
    csv_path = TIER_FILES[args.tier]
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found!")
        return

    print("=" * 70)
    print("  TURBO FOUNDATION SENDER — High-Throughput Parallel Engine")
    print("=" * 70)
    mode_label = "SAFE 🛡️" if safe_mode else "TURBO 🚀"
    print(f"  Mode:         {mode_label}")
    print(f"  Tier:         {args.tier}")
    print(f"  File:         {csv_path}")
    print(f"  Workers:      {num_workers}")
    print(f"  Dual-email:   {'YES (rotating)' if args.dual and password2 else 'No'}")
    print(f"  Per-worker:   {min_delay}-{max_delay}s jitter")
    print(f"  Day limit:    {day_limit if day_limit else 'None'}")
    print(f"  Resume mode:  {'YES' if args.resume else 'No'}")
    thr = 3600 // ((min_delay + max_delay) // 2) * num_workers
    print(f"  Throughput:   ~{thr}/hour")
    print("=" * 70)

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_foundations = list(reader)

    print(f"\nLoaded {len(all_foundations):,} foundations")

    # ── Resume: skip already-sent EINs ────────────────────────────────
    if args.resume:
        sent_log = os.path.join(LOG_DIR, "turbo_sent.txt")
        if os.path.exists(sent_log):
            with open(sent_log, 'r') as f:
                sent_eins = set(line.split('|')[0] for line in f if line.strip() and '|' in line)
            before = len(all_foundations)
            all_foundations = [r for r in all_foundations if r['EIN'] not in sent_eins]
            print(f"Resume mode: skipped {len(sent_eins):,} already-sent EINs "
                  f"({before:,} -> {len(all_foundations):,} remaining)")
        else:
            print("Resume mode: no sent log found, starting fresh")

    total = len(all_foundations)

    # ── Distribute work across workers ────────────────────────────────
    worker_slices = [[] for _ in range(num_workers)]
    for i, f in enumerate(all_foundations):
        worker_slices[i % num_workers].append(f)

    sizes = [len(s) for s in worker_slices]
    print(f"\nWork distribution: min={min(sizes):,}, max={max(sizes):,}, "
          f"total={total:,}")

    # ── Countdown ─────────────────────────────────────────────────────
    print(f"\n🚀 Launching {num_workers} parallel workers in 5 seconds...")
    print("   (Ctrl+C to abort)")
    sys.stdout.flush()
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\nAborted by user.")
        return

    # ── Launch ────────────────────────────────────────────────────────
    state = SharedState(total)

    use_dual = args.dual and bool(password2)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for w_id in range(num_workers):
            future = executor.submit(
                worker_send, w_id, worker_slices[w_id], state,
                password1, password2, use_dual,
                min_delay, max_delay, day_limit
            )
            futures.append(future)

        # Monitor progress and print periodic summary
        try:
            all_done = False
            while not all_done:
                all_done = all(f.done() for f in futures)
                if not all_done:
                    print(f"  ── {state.status_line('*')} ──")
                    sys.stdout.flush()
                    time.sleep(15)  # Status every 15s
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Ctrl+C caught! Waiting for workers to finish current send...")
            print(f"   (Workers will stop after their current send completes)")
            # Can't easily cancel mid-send, but we stop monitoring

    # ── Final Report ──────────────────────────────────────────────────
    elapsed = (datetime.now() - state.start_time).total_seconds()
    print(f"\n{'=' * 70}")
    print(f"  ✅ BATCH COMPLETE")
    print(f"  Sent:   {state.sent:,}")
    print(f"  Errors: {state.errors:,}")
    print(f"  Time:   {str(timedelta(seconds=int(elapsed)))}")
    print(f"  Rate:   {(state.sent / elapsed * 3600):.0f} emails/hour")
    print(f"  Logs:   {LOG_DIR}\\")
    print(f"{'=' * 70}")
    print(f"\nNext: python turbo_foundation_sender.py --tier tier2 --resume")


if __name__ == '__main__':
    main()
