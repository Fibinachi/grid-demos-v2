"""
Foundation Batch Sender - Tier 1
=================================
Sends personalized grant-seeking emails to private foundations from the
IRS-scraped master list. Uses 2-4 minute random jitter between sends.

Tier 1: $10M+ assets ($10M, $100M+, $1B+ grant-makers)
~9,431 foundations including Gates, Ford, Hewlett, Bloomberg, Mellon, etc.

Usage:
  $env:EMAIL_PASSWORD="your_password"; python foundation_batch_sender.py

To stop: Ctrl+C (will lose progress unless using --resume)
"""

import csv
import smtplib
import ssl
import time
import random
import os
import sys
import json
from datetime import datetime, timedelta

# Configuration
SMTP_HOST = "smtp.hostinger.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "charles@charlesprescott.net"
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")

# File paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TIER1_CSV = os.path.join(SCRIPT_DIR, "foundations_tier1_10m_plus.csv")
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "foundation_batch_progress.json")
SENT_LOG = os.path.join(SCRIPT_DIR, "foundation_batch_sent.txt")
ERROR_LOG = os.path.join(SCRIPT_DIR, "foundation_batch_errors.txt")

# Timing
MIN_DELAY = 120   # 2 minutes minimum between sends
MAX_DELAY = 240   # 4 minutes maximum between sends
STATUS_EVERY = 5   # Print progress every N sends

# The story to tell - theological studies at Trinity College
STORY = """I am writing to seek your support for my theological education at the University of Toronto's Trinity College.

At 44 years old, I am embarking on a Certificate in Theological Studies beginning September 2026, pursuing a long-held calling that I am now in a position to answer. My goal is to serve communities through thoughtful, grounded ministry — work that requires both rigorous academic preparation and genuine spiritual formation.

The program at Trinity College offers exactly this foundation: a globally respected theological institution within one of the world's great universities. The $30,000 CAD tuition represents a significant investment for me as a self-funded student, and I am reaching out to foundations like yours that share a commitment to theological education and community service.

I would be grateful to discuss how my background and calling align with your foundation's mission. I am happy to provide any additional information you may need.

Thank you for your consideration.

With gratitude,
Charles Prescott
charles@charlesprescott.net"""


def load_progress():
    """Load send progress from checkpoint file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {'sent': 0, 'last_index': -1, 'completed': False, 'started_at': None}


def save_progress(progress):
    """Save send progress."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)


def load_sent_eins():
    """Load set of already-sent EINs."""
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def log_sent(ein, name):
    """Log a successful send."""
    with open(SENT_LOG, 'a') as f:
        f.write(f"{ein}\n")


def log_error(ein, name, error_msg):
    """Log a send error."""
    with open(ERROR_LOG, 'a') as f:
        f.write(f"{datetime.now().isoformat()} | {ein} | {name[:60]} | {error_msg}\n")


def send_email(to_addr, foundation_name, sender_email, password):
    """Send a personalized grant request email."""
    # Personalize with foundation name
    body = f"""Dear {foundation_name} Grant Committee,

{STORY}"""

    message = f"""From: {sender_email}
To: {to_addr}
Subject: Request for Support: Theological Studies at Trinity College, University of Toronto

{body}"""

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(sender_email, password)
        server.sendmail(sender_email, to_addr, message.encode('utf-8'))


def guess_email(name):
    """Generate a likely info@ email from foundation name."""
    name_clean = name.strip()
    name_clean = name_clean.replace(',', '')

    # Generate domain from name
    # "The ABC Foundation" -> abc
    # "John D and Catherine T MacArthur Foundation" -> macarthur
    slug = name_clean.lower()
    # Remove common prefixes
    slug = slug.replace('the ', '')
    # Remove legal suffixes
    for suffix in [' foundation', ' foundation inc', ' foundation corporation',
                   ' inc', ' corp', ' llc', ', inc.', ', llc']:
        slug = slug.replace(suffix, '')

    # Try to get the last meaningful word
    words = slug.split()
    if not words:
        return ''

    # For compound names, try the last word that's not a connector
    connectors = {'and', 'the', 'of', 'for', '&', 'de', 'la', 'del'}
    meaningful = [w for w in words if w not in connectors and len(w) > 2]

    if not meaningful:
        meaningful = words

    # Generate multiple possible domains
    # Pattern 1: lastmeaningfulwordfoundation.org
    if len(meaningful) >= 2:
        domain1 = f"{meaningful[-1]}foundation.org"
    else:
        domain1 = f"{meaningful[0]}foundation.org"

    # Pattern 2: fullslug.org
    domain2 = f"{''.join(meaningful)}.org"

    # Pattern 3: mainword.org
    domain3 = f"{meaningful[0]}.org"

    # Return the one that seems most likely
    # For well-known foundations, try the shorter domain
    emails = [
        f"info@{domain1}",
        f"grants@{domain1}",
        f"info@{domain2}",
        f"grants@{domain2}",
    ]

    return emails[0]  # Start with the most likely


def estimate_eta(sent_count, total_count, elapsed_seconds):
    """Estimate remaining time."""
    if sent_count == 0:
        return "N/A"
    avg_per_email = elapsed_seconds / sent_count
    remaining = (total_count - sent_count) * avg_per_email
    return str(timedelta(seconds=int(remaining)))


def main():
    if not EMAIL_PASSWORD:
        print("ERROR: EMAIL_PASSWORD environment variable not set!")
        print("Usage: $env:EMAIL_PASSWORD=\"your_password\"; python foundation_batch_sender.py")
        return

    # Load tier 1 foundations
    print("=" * 60)
    print("FOUNDATION BATCH SENDER - TIER 1 (10M+)")
    print("=" * 60)
    print(f"Reading {TIER1_CSV}...")

    if not os.path.exists(TIER1_CSV):
        print(f"ERROR: {TIER1_CSV} not found!")
        return

    with open(TIER1_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        foundations = list(reader)

    total = len(foundations)
    print(f"Total Tier 1 foundations: {total:,}")

    # Load progress
    progress = load_progress()
    sent_eins = load_sent_eins()

    if progress.get('started_at'):
        started = datetime.fromisoformat(progress['started_at'])
        elapsed = (datetime.now() - started).total_seconds()
        print(f"Previous run: {progress['sent']:,} sent, started {started.isoformat()}")
    else:
        progress['started_at'] = datetime.now().isoformat()
        elapsed = 0

    start_index = progress['last_index'] + 1
    if start_index > 0:
        print(f"Resuming from index {start_index:,}")

    print(f"\nWill send with {MIN_DELAY}-{MAX_DELAY}s random delay between sends")
    print(f"Estimated runtime: ~{total * (MIN_DELAY + MAX_DELAY) // 2 // 3600}h")
    print(f"\nPress Ctrl+C to pause (progress saved)")
    print("=" * 60)

    # Confirm with user
    print(f"\nReady to send to {total:,} foundations. Starting in 5 seconds...")
    print("(Press Ctrl+C within 5 seconds to abort)")
    sys.stdout.flush()
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\nAborted by user.")
        return

    # Connect to SMTP once
    print("Connecting to SMTP server...")
    context = ssl.create_default_context()
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    server.starttls(context=context)
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    print(f"Connected to {SMTP_HOST}:{SMTP_PORT}")
    sys.stdout.flush()

    try:
        for i, foundation in enumerate(foundations):
            if i < start_index:
                continue

            ein = foundation['EIN']
            name = foundation['NAME']
            if ein in sent_eins:
                continue

            # Generate guess email
            to_email = guess_email(name)
            if not to_email:
                print(f"  [{i+1}/{total}] SKIP {name[:50]} - could not generate email")
                log_error(ein, name, "Could not generate email")
                progress['last_index'] = i
                save_progress(progress)
                continue

            # Send
            try:
                send_email(to_email, name, EMAIL_ADDRESS, EMAIL_PASSWORD)
                progress['sent'] += 1
                sent_eins.add(ein)
                log_sent(ein, name)

                # Status update
                if progress['sent'] % STATUS_EVERY == 0:
                    elapsed = (datetime.now() - datetime.fromisoformat(progress['started_at'])).total_seconds()
                    eta = estimate_eta(progress['sent'], total, elapsed)
                    print(f"  [{progress['sent']:,}/{total:,}] Sent: {name[:50]} -> {to_email} | ETA: {eta}")
                    sys.stdout.flush()

            except smtplib.SMTPAuthenticationError:
                print(f"\nERROR: SMTP Authentication failed! Check EMAIL_PASSWORD.")
                print("Hostinger may have disabled SMTP. Check hPanel.")
                break
            except smtplib.SMTPException as e:
                err = str(e)[:150]
                print(f"  [{i+1}/{total}] FAIL {name[:40]} -> {err}")
                log_error(ein, name, err)
            except Exception as e:
                err = str(e)[:150]
                print(f"  [{i+1}/{total}] ERROR {name[:40]} -> {err}")
                log_error(ein, name, err)

            # Save progress after each send
            progress['last_index'] = i
            save_progress(progress)

            # Jittered delay between sends (not after the last one)
            if i < total - 1:
                delay = random.randint(MIN_DELAY, MAX_DELAY)
                time.sleep(delay)

    except KeyboardInterrupt:
        print(f"\n\nPaused by user. Progress saved: {progress['sent']:,} sent")
        save_progress(progress)

    finally:
        server.quit()
        print(f"\nSession ended. Total sent this run: {progress['sent']:,}")

    progress['completed'] = True
    save_progress(progress)
    print(f"\n{'=' * 60}")
    print(f"TIER 1 BATCH COMPLETE!")
    print(f"Total sent: {progress['sent']:,}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
