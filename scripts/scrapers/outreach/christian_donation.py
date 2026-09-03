"""
Christian Business Donation Ask Sender
=======================================
Sends a humble "small dollar ask" to Christian-owned businesses
and religious organizations. The ask is framed as an act of faith -
trusting that God will provide through His people.

Tiers:
  --tier religious      : IRS X (Religion) and B (Education) codes
  --tier directories    : Christian business directory contacts
  --tier all            : Both combined (default)

Usage:
  python christian_donation_sender.py --tier all --workers 5
  python christian_donation_sender.py --tier directories --workers 3
"""

import csv
import os
import sys
import time
import json
import random
import threading
import argparse
import smtplib
import ssl
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# -- CONFIG --
SMTP_HOST = "email-smtp.us-east-1.amazonaws.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER", "AKIASKQS5JXODSJERNES")
SMTP_PASS = os.environ.get("SMTP_PASS", "BCRaP22/Crmx5/SBb63vMJL3O2Tvm1oxwh+hgPPhW3xv")
FROM_EMAIL = "charles@columbiataxlawyer.com"
FROM_NAME = "Charles Prescott"

CHRISTIAN_CSV = os.path.join(SCRIPT_DIR, "christian_contacts.csv")
ENRICHED_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
SENT_LOG = os.path.join(SCRIPT_DIR, "christian_sent_log.csv")
PROGRESS_LOG = os.path.join(SCRIPT_DIR, "christian_donation_progress.json")

# -- EMAIL TEMPLATE --
SUBJECT_TEMPLATES = [
    "A small ask, an act of faith",
    "Stepping out in faith - would you help?",
    "A future minister needs your help",
    "Supporting a call to ministry",
    "An act of faith and a small request",
]

def build_email(first_name=None, business_name=None):
    """Build the donation ask email."""

    greeting = "Dear %s," % (first_name or business_name or "Friend")

    body = """%s

I know this is an unusual email to receive, but I'm writing to you as a fellow believer - stepping out in faith and trusting that God will provide.

My name is Charles Prescott. I'm currently pursuing a Certificate in Theology at Trinity College at the University of Toronto — a feeder program into the PhD track. My goal is to devote my life to theological scholarship and teaching.

But here's the honest truth: advanced theological education is expensive. My tuition costs about $30,000 CAD for the program, and I'm working hard to make it happen. I've sent letters to foundations, applied for scholarships, and taken every step I can think of.

And now - in what feels like a real act of faith - I'm asking you.

I'm not asking for a large gift. Even $10, $25, or $50 would be a tremendous help and a powerful encouragement. If every Christian business that receives this gave just a small amount, it would be more than enough.

Your support would go directly toward my tuition: books, classes, and the training I need to serve God's people as a pastor.

If you feel led to help, you can donate here:
https://buy.stripe.com/eVaeYj3U78jt8Io8ww

Or if you'd like to learn more about my journey, just reply to this email. I'd love to connect.

Thank you for reading this. Thank you for even considering it. Whether you give or not, I'm grateful that you're out there running your business with faith and integrity.

May God bless you and your work.

In Christ,
Charles Prescott
Trinity College, University of Toronto
charles@columbiataxlawyer.com""" % greeting

    html = """<html><body style="font-family: Georgia, serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="border-left: 4px solid #8B4513; padding-left: 20px; margin-bottom: 20px;">
<p style="font-style: italic; color: #666;">"And my God will supply every need of yours according to his riches in glory in Christ Jesus."<br>-- Philippians 4:19</p>
</div>

<p>%s</p>

<p>I know this is an unusual email to receive, but I'm writing to you as a fellow believer - <strong>stepping out in faith</strong> and trusting that God will provide.</p>

<p>My name is Charles Prescott. I'm currently pursuing a <strong>Certificate in Theology</strong> at Trinity College at the University of Toronto — a feeder program into the PhD track. My goal is to devote my life to theological scholarship and teaching.</p>

<p>But here's the honest truth: advanced theological education is expensive. My tuition costs about <strong>$30,000 CAD</strong> for the program, and I'm working hard to make it happen. I've sent letters to foundations, applied for scholarships, and taken every step I can think of.</p>

<p>And now - in what feels like a real act of faith - <strong>I'm asking you</strong>.</p>

<p>I'm not asking for a large gift. Even <strong>$10, $25, or $50</strong> would be a tremendous help and a powerful encouragement. If every Christian business that receives this gave just a small amount, it would be more than enough.</p>

<p>Your support would go directly toward my tuition: books, classes, and the research training I need to serve God's people through theological scholarship.</p>

<div style="background: #f8f4ee; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
<p style="font-size: 18px; font-weight: bold; margin: 0 0 10px 0;">Support a Future Theologian</p>
<a href="https://buy.stripe.com/eVaeYj3U78jt8Io8ww" style="display: inline-block; background: #8B4513; color: white; padding: 12px 32px; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: bold;">Give a Gift -></a>
</div>

<p>Or if you'd like to learn more about my journey, just reply to this email. I'd love to connect.</p>

<p>Thank you for reading this. Thank you for even considering it. Whether you give or not, I'm grateful that you're out there running your business with faith and integrity.</p>

<p>May God bless you and your work.</p>

<p style="margin-top: 30px;">
<strong>Charles Prescott</strong><br>
Trinity College, University of Toronto<br>
charles@columbiataxlawyer.com
</p>

<div style="border-top: 1px solid #ddd; margin-top: 20px; padding-top: 15px; font-size: 12px; color: #999;">
<p><em>If you'd rather not receive future emails, reply with "unsubscribe" and I'll remove you immediately. No hard feelings.</em></p>
</div>
</body></html>""" % greeting

    return body, html

# -- SMTP --
def send_email(smtp, to_email, subject, body, html):
    msg = MIMEMultipart('alternative')
    msg['From'] = formataddr((FROM_NAME, FROM_EMAIL))
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    msg.attach(MIMEText(html, 'html'))

    smtp.sendmail(FROM_EMAIL, [to_email], msg.as_string())

# -- LOAD CONTACTS --
def load_contacts(tier):
    contacts = []

    christian_csv = os.path.join(SCRIPT_DIR, "christian_contacts.csv")
    enriched_csv = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")

    if tier in ('all', 'directories'):
        if os.path.exists(christian_csv):
            with open(christian_csv, 'r', encoding='utf-8') as f:
                for r in csv.DictReader(f):
                    if r.get('EMAIL') or r.get('SOURCE'):
                        contacts.append(r)

    if tier in ('all', 'religious'):
        if os.path.exists(enriched_csv):
            with open(enriched_csv, 'r', encoding='utf-8') as f:
                for r in csv.DictReader(f):
                    ntee = r.get('NTEE_CD', '').strip()
                    if ntee.startswith('X') or ntee.startswith('B'):
                        if r not in contacts:
                            contacts.append(r)

    return contacts

# -- SENT LOG --
def load_sent():
    if not os.path.exists(SENT_LOG):
        return set()
    with open(SENT_LOG, 'r', encoding='utf-8') as f:
        return set(r['email'] for r in csv.DictReader(f))

def log_sent(email, name, source, status, error=""):
    exists = os.path.exists(SENT_LOG)
    with open(SENT_LOG, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['email','name','source','status','error','timestamp'])
        if not exists:
            w.writeheader()
        w.writerow({'email': email, 'name': name, 'source': source,
                     'status': status, 'error': error[:100],
                     'timestamp': datetime.now().isoformat()})

# -- PROGRESS --
def save_progress(sent, total):
    with open(PROGRESS_LOG, 'w') as f:
        json.dump({'sent': sent, 'total': total, 'timestamp': datetime.now().isoformat()}, f)

# -- WORKER --
stats_lock = threading.Lock()
worker_stats = {'sent': 0, 'errors': 0, 'total': 0}

def worker_thread(smtp, contacts, sent_set, idx):
    sent = 0
    for c in contacts:
        email = c.get('EMAIL', '').strip() or (c.get('NAME','').replace(' ','').lower() + "@placeholder.org")
        name = c.get('NAME', '').strip()
        first = name.split()[0] if name.split() else None

        if email in sent_set or '@placeholder' in email:
            continue

        subject = random.choice(SUBJECT_TEMPLATES)
        body, html = build_email(first, name)

        try:
            send_email(smtp, email, subject, body, html)
            sent_set.add(email)
            log_sent(email, name, c.get('SOURCE',''), 'sent')
            with stats_lock:
                worker_stats['sent'] += 1
            sent += 1
        except smtplib.SMTPServerDisconnected:
            time.sleep(2)
            try:
                smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(SMTP_USER, SMTP_PASS)
                send_email(smtp, email, subject, body, html)
                sent_set.add(email)
                log_sent(email, name, c.get('SOURCE',''), 'sent')
                with stats_lock:
                    worker_stats['sent'] += 1
                sent += 1
            except Exception as e:
                log_sent(email, name, c.get('SOURCE',''), 'error', str(e))
                with stats_lock:
                    worker_stats['errors'] += 1
        except Exception as e:
            log_sent(email, name, c.get('SOURCE',''), 'error', str(e))
            with stats_lock:
                worker_stats['errors'] += 1

        time.sleep(random.uniform(2, 5))

    return sent

# -- MAIN --
def main():
    parser = argparse.ArgumentParser(description="Christian donation ask sender")
    parser.add_argument("--tier", choices=['all','religious','directories'], default='all')
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--resume", action="store_true", help="Resume from sent log")
    parser.add_argument("--max", type=int, default=0, help="Max total to send (0=unlimited)")
    parser.add_argument("--test", action="store_true", help="Test mode - send to yourself")
    args = parser.parse_args()

    contacts = load_contacts(args.tier)
    print("\n  Loaded %d contacts (%s tier)" % (len(contacts), args.tier))

    if args.test:
        print("  TEST MODE - sending to self only")
        contacts = [{'EMAIL': FROM_EMAIL, 'NAME': 'Charles Prescott', 'SOURCE': 'test'}]

    sent_set = load_sent() if args.resume else set()
    print("  Already sent: %d" % len(sent_set))

    if args.max > 0:
        contacts = [c for c in contacts if c.get('EMAIL','') not in sent_set][:args.max]
        print("  Limited to %d new sends" % args.max)

    # Filter out already sent
    unsent = [c for c in contacts if c.get('EMAIL','') not in sent_set and '@placeholder' not in c.get('EMAIL','')]
    print("  To send: %d" % len(unsent))

    if not unsent:
        print("  Nothing to send!")
        return

    # Connect SMTP
    print("\n  Connecting to %s..." % SMTP_HOST)
    smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
    smtp.starttls(context=ssl.create_default_context())
    smtp.login(SMTP_USER, SMTP_PASS)
    print("  Connected")

    worker_stats['total'] = len(unsent)

    # Split contacts among workers
    chunk_size = max(1, len(unsent) // args.workers)
    chunks = [unsent[i:i+chunk_size] for i in range(0, len(unsent), chunk_size)]

    # Create SMTP connections for each worker
    def create_smtp():
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        s.starttls(context=ssl.create_default_context())
        s.login(SMTP_USER, SMTP_PASS)
        return s

    threads = []
    for i, chunk in enumerate(chunks):
        s = create_smtp()
        t = threading.Thread(target=worker_thread, args=(s, chunk, sent_set, i), daemon=True)
        threads.append(t)
        t.start()

    # Dashboard
    start = datetime.now()
    try:
        while any(t.is_alive() for t in threads):
            elapsed = (datetime.now() - start).total_seconds()
            rate = worker_stats['sent'] / elapsed * 3600 if elapsed > 0 else 0
            remaining = max(0, worker_stats['total'] - worker_stats['sent'] - worker_stats['errors'])
            eta = remaining / max(rate/3600, 0.0001) if rate > 0 else 0

            msg = "\r  Sent: %d  Errors: %d  Rate: %.0f/hr  ETA: %s  Elapsed: %s   " % (
                worker_stats['sent'], worker_stats['errors'], rate,
                str(timedelta(seconds=int(eta))), str(timedelta(seconds=int(elapsed))))
            sys.stdout.write(msg)
            sys.stdout.flush()
            save_progress(worker_stats['sent'], worker_stats['total'])
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n  Stopped by user")

    for t in threads:
        t.join(timeout=1)

    elapsed = (datetime.now() - start).total_seconds()
    print("\n")
    print("="*60)
    print("  CHRISTIAN DONATION ASK COMPLETE")
    print("  Sent: %d" % worker_stats['sent'])
    print("  Errors: %d" % worker_stats['errors'])
    print("  Time: %s" % str(timedelta(seconds=int(elapsed))))
    print("  Rate: %.0f/hr" % (worker_stats['sent']/elapsed*3600 if elapsed > 0 else 0))
    print("="*60)

if __name__ == '__main__':
    main()
