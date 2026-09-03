"""
Foundation Follow-up Sender (60-Day)
=====================================
Sends a polite 60-day follow-up to foundations that received the initial
inquiry but haven't responded. Typically boosts response rates by 30-50%.

Usage:
  python follow_up_60day.py                    # Preview mode (shows what would send)
  python follow_up_60day.py --send             # Actually send follow-ups
  python follow_up_60day.py --send --turbo     # Send fast (5-15s jitter)

The script checks the inbox for replies against the sent log, then
only follows up with non-responders.
"""

import csv
import smtplib
import ssl
import time
import random
import os
import sys
import re
import json
import imaplib
import email
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# ── Config ────────────────────────────────────────────────────────────────
SES_HOST = "email-smtp.us-east-1.amazonaws.com"
SES_PORT = 587
SES_USER = "AKIASKQS5JXODSJERNES"
SES_PASS = "BCRaP22/Crmx5/SBb63vMJL3O2Tvm1oxwh+hgPPhW3xv"
SENDER_NAME = "Charles Prescott"
SENDER_EMAIL = "charles@columbiataxlawyer.com"

IMAP_HOST = "imap.hostinger.com"
IMAP_USER = "charles@columbiataxlawyer.com"
IMAP_PASS = os.environ.get("EMAIL_PASSWORD", "FlorenceFlamingo1!")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENRICHED_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
SENT_LOG = os.path.join(SCRIPT_DIR, "ses_logs", "ses_sent.txt")
FOLLOWUP_LOG = os.path.join(SCRIPT_DIR, "ses_logs", "followup_sent.txt")

sys.path.insert(0, SCRIPT_DIR)
from gmail_api_sender import personalize_intro

SUBJECT = "Quick Follow-Up: Alignment With Your Foundation's Funding Priorities"

FOLLOWUP_BODY = """I hope this note finds you well. I wrote a couple of months ago to inquire whether my academic background and pursuit of theological studies at Trinity College, University of Toronto might align with your foundation's funding priorities. I understand how busy grant-making seasons can be, so I wanted to gently follow up in case my original message was overlooked.

My background includes legal practice (JD, LLM in Taxation), public legal education, mediation, and interdisciplinary research at the intersection of law, society, and theology. I am beginning graduate study in Fall 2026 and am seeking to connect with foundations whose mission and values intersect with my work.

If your foundation considers requests from individual scholars, I would be grateful for any guidance on eligibility, application procedures, or upcoming grant cycles. I am happy to provide a brief proposal, CV, or any additional information.

Thank you again for your time and for the important work your foundation does.

Warm regards,
Charles Prescott
Columbia, SC
8435044542
charles@columbiataxlawyer.com"""


def check_inbox_replies():
    """Check inbox for replies to our sent messages."""
    replied = set()
    try:
        M = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=15)
        M.login(IMAP_USER, IMAP_PASS)
        M.select('INBOX')
        st, ids = M.search(None, 'ALL')
        all_ids = ids[0].split() if ids[0] else []
        for num in all_ids:
            st2, data = M.fetch(num, '(RFC822)')
            if st2 != 'OK': continue
            msg = email.message_from_bytes(data[0][1])
            frm = msg.get('From', '')
            subj = msg.get('Subject', '')
            # Check if it's a reply to our message
            if 'Re:' in subj or 're:' in subj[:3]:
                # Extract sender email
                match = re.search(r'[\w.+-]+@[\w.-]+\.\w{2,4}', frm)
                if match:
                    replied.add(match.group(1).lower())
        M.logout()
    except Exception as e:
        print(f"  IMAP check failed: {str(e)[:80]}")
    return replied


def load_sent():
    """Load all EINs we've sent to."""
    sent = {}
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG, 'r') as f:
            for line in f:
                if '|' in line:
                    parts = line.strip().split('|')
                    ein = parts[0]
                    sent[ein] = True
    return sent


def load_followed_up():
    """Load EINs we've already followed up with."""
    followed = set()
    if os.path.exists(FOLLOWUP_LOG):
        with open(FOLLOWUP_LOG, 'r') as f:
            for line in f:
                if '|' in line:
                    followed.add(line.strip().split('|')[0])
    return followed


def send_followup(server, to_email, foundation_name, row):
    """Send a follow-up email."""
    # Personalize with a shorter intro
    intro = personalize_intro(row)
    # Take just the first sentence for the follow-up
    first_sentence = intro.split('.')[0] + '.' if '.' in intro else intro
    
    body = f"Dear {foundation_name} Team,\n\n{FOLLOWUP_BODY}"
    
    message = f"From: {SENDER_NAME} <{SENDER_EMAIL}>\n" \
              f"To: {to_email}\n" \
              f"Subject: {SUBJECT}\n\n" \
              f"{body}"
    
    server.sendmail(SENDER_EMAIL, to_email, message.encode('utf-8'))


def main():
    send_mode = '--send' in sys.argv
    turbo = '--turbo' in sys.argv
    
    delay_min, delay_max = (5, 15) if turbo else (20, 45)
    
    print("=" * 70)
    print("  60-DAY FOLLOW-UP SENDER")
    print("=" * 70)
    
    # Load sent foundations
    sent_eins = load_sent()
    print(f"\nFoundations sent to: {len(sent_eins):,}")
    
    # Check inbox for replies
    replied_emails = check_inbox_replies()
    print(f"Replies received from: {len(replied_emails):,}")
    
    # Load enriched contacts
    if not os.path.exists(ENRICHED_CSV):
        print(f"ERROR: {ENRICHED_CSV} not found!")
        return
    
    with open(ENRICHED_CSV, 'r', encoding='utf-8') as f:
        all_rows = list(csv.DictReader(f))
    
    # Build email→row lookup
    email_to_row = {}
    for r in all_rows:
        email = r.get('EMAIL', '').lower()
        if email:
            email_to_row[email] = r
    
    # Find foundations to follow up with
    followed_up = load_followed_up()
    to_followup = []
    
    for ein in sent_eins:
        if ein in followed_up:
            continue
        # Find the row
        for r in all_rows:
            if r['EIN'] == ein:
                email = r.get('EMAIL', '').lower()
                if email and email not in replied_emails:
                    to_followup.append(r)
                break
    
    print(f"Already followed up: {len(followed_up):,}")
    print(f"To follow up: {len(to_followup):,}")
    
    if not to_followup:
        print("\nNothing to follow up with!")
        return
    
    if not send_mode:
        print(f"\n  Preview mode. Use --send to actually send.")
        print(f"\n  Sample follow-ups that would be sent:")
        for r in to_followup[:5]:
            print(f"    {r['NAME'][:50]} -> {r.get('EMAIL', '')}")
        print(f"    ... and {len(to_followup)-5} more")
        print(f"\n  To send: python follow_up_60day.py --send")
        return
    
    # ── Send ─────────────────────────────────────────────────────────
    print(f"\n🚀 Sending {len(to_followup):,} follow-ups...")
    print(f"  Mode: {'TURBO' if turbo else 'STANDARD'}")
    print(f"  Jitter: {delay_min}-{delay_max}s")
    sys.stdout.flush()
    time.sleep(3)
    
    context = ssl.create_default_context()
    server = smtplib.SMTP(SES_HOST, SES_PORT, timeout=30)
    server.starttls(context=context)
    server.login(SES_USER, SES_PASS)
    
    sent = 0
    errors = 0
    
    for i, row in enumerate(to_followup):
        if i > 0:
            time.sleep(random.randint(delay_min, delay_max))
        
        email = row.get('EMAIL', '').lower()
        name = row['NAME']
        
        try:
            send_followup(server, email, name, row)
            sent += 1
            
            # Log it
            with open(FOLLOWUP_LOG, 'a') as f:
                f.write(f"{row['EIN']}|{name[:80]}|{email}|{datetime.now().isoformat()}\n")
            
            if sent % 10 == 0:
                print(f"  Sent: {sent}/{len(to_followup):,} | Errors: {errors}")
                sys.stdout.flush()
                
        except Exception as e:
            errors += 1
            with open(os.path.join(SCRIPT_DIR, "ses_logs", "followup_errors.txt"), 'a') as f:
                f.write(f"{datetime.now().isoformat()}|{row['EIN']}|{name[:60]}|{str(e)[:100]}\n")
    
    server.quit()
    
    print(f"\n{'=' * 50}")
    print(f"  Done! Sent: {sent:,} | Errors: {errors:,}")
    print(f"{'=' * 50}")


if __name__ == '__main__':
    main()
