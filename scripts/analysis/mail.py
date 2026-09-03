#!/usr/bin/env python3
"""
Hostinger Email Client
=======================
Reusable utility to read/search the columbiataxlawyer.com inbox via IMAP.

Usage:
    python scripts/analysis/mail.py ls                   # List last 15 messages
    python scripts/analysis/mail.py ls --all             # List ALL messages
    python scripts/analysis/mail.py ls --limit 30        # List last 30
    python scripts/analysis/mail.py ls --search "HERE"   # Search for keyword
    python scripts/analysis/mail.py read 3               # Read message #3 (from ls output)
    python scripts/analysis/mail.py read N --html         # Include HTML body
    python scripts/analysis/mail.py read N --raw          # Show raw email source

Examples:
    python scripts/analysis/mail.py ls --search "here platform verify"
    python scripts/analysis/mail.py read 1
"""
import imaplib, email, sys, argparse, html
from email.header import decode_header
from datetime import datetime

HOST = 'imap.hostinger.com'
USER = 'charles@columbiataxlawyer.com'
PASS = 'FlorenceFlamingo1!'


def connect():
    mail = imaplib.IMAP4_SSL(HOST)
    mail.login(USER, PASS)
    mail.select('INBOX')
    return mail


def decode_mime(s):
    """Decode MIME-encoded headers to readable text."""
    if not s:
        return ''
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or 'utf-8', errors='replace'))
            except:
                result.append(part.decode('utf-8', errors='replace'))
        else:
            result.append(str(part))
    return ' '.join(result)


def get_header(msg, name):
    val = msg.get(name, '')
    return decode_mime(val) if val else ''


def list_messages(mail, search_criteria=None, limit=15):
    """List messages matching optional search. Returns list of (id, from, subject, date)."""
    if search_criteria:
        status, ids = mail.search(None, 'ALL')
    else:
        status, ids = mail.search(None, 'ALL')

    all_ids = ids[0].split() if ids[0] else []
    if not all_ids:
        print("  (empty inbox)")
        return []

    # Apply search filter locally (IMAP search is finicky with special chars)
    if search_criteria:
        search_terms = search_criteria.lower().split()
        filtered = []
        for mid in all_ids:
            status, data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
            if status != 'OK':
                continue
            raw = data[0][1].decode('utf-8', errors='replace').lower()
            if all(t in raw for t in search_terms):
                filtered.append(mid)
        all_ids = filtered
        if not all_ids:
            print(f"  No messages matching '{search_criteria}'")
            return []

    total = len(all_ids)
    msg_ids = all_ids[-limit:] if limit else all_ids
    msgs = []

    print(f"\n{'#' :>4} {'From':45s} | {'Subject':60s}")
    print(f"{'─' * 4} {'─' * 45}─┼─{'─' * 60}")
    for i, mid in enumerate(msg_ids, 1):
        status, data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
        if status != 'OK':
            continue
        raw = data[0][1].decode('utf-8', errors='replace')
        f = get_header(email.message_from_string(raw), 'From')
        s = get_header(email.message_from_string(raw), 'Subject')
        d = get_header(email.message_from_string(raw), 'Date')
        msgs.append((mid, f, s, d))
        print(f"{i:4d} {f[:45]:45s} | {s[:60]}")

    if limit and total > limit:
        print(f"\n  ({total} total, showing last {limit}. Use --all or --limit N for more)")
    return msgs


def read_message(mail, msg_num, show_html=False, show_raw=False):
    """Read a specific message by its position number."""
    status, ids = mail.search(None, 'ALL')
    all_ids = ids[0].split() if ids[0] else []
    if not all_ids or msg_num < 1 or msg_num > len(all_ids):
        print(f"  Message #{msg_num} not found. Use 'ls' to see available messages.")
        return

    mid = all_ids[-msg_num]  # Reverse order (newest first in ls)
    status, data = mail.fetch(mid, '(RFC822)')
    if status != 'OK':
        print("  Failed to fetch message")
        return

    raw_email = data[0][1]
    msg = email.message_from_bytes(raw_email)

    # Headers
    print(f"{'─' * 70}")
    print(f"From:    {get_header(msg, 'From')}")
    print(f"To:      {get_header(msg, 'To')}")
    print(f"Subject: {get_header(msg, 'Subject')}")
    print(f"Date:    {get_header(msg, 'Date')}")
    print(f"{'─' * 70}")

    if show_raw:
        print("\n=== RAW SOURCE ===")
        print(raw_email.decode('utf-8', errors='replace')[:5000])
        return

    # Body
    body_text = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain':
                try:
                    body_text = part.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    body_text = str(part.get_payload())
            elif ct == 'text/html' and show_html:
                try:
                    body_html = part.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    body_html = str(part.get_payload())
    else:
        ct = msg.get_content_type()
        if ct == 'text/plain':
            try:
                body_text = msg.get_payload(decode=True).decode('utf-8', errors='replace')
            except:
                body_text = str(msg.get_payload())
        elif ct == 'text/html' and show_html:
            try:
                body_html = msg.get_payload(decode=True).decode('utf-8', errors='replace')
            except:
                body_html = str(msg.get_payload())

    # Check for links in the body
    import re
    if body_text:
        # Find verification links
        urls = re.findall(r'https?://[^\s<>"\']+', body_text)
        if urls:
            print(f"\n🔗 Links found:")
            for url in urls[:10]:
                print(f"  {url}")
        print(f"\n{body_text[:3000]}")
    elif body_html and show_html:
        # Strip tags for display
        text = re.sub(r'<[^>]+>', ' ', body_html)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        urls = re.findall(r'https?://[^\s<>"\']+', body_html)
        if urls:
            print("\n🔗 Links found:")
            for url in urls[:10]:
                print(f"  {url}")
        print(f"\n{text[:3000]}")
    else:
        print("\n(no plain text body. Use --html to see HTML version)")
        # Still show links from HTML
        if body_html:
            urls = re.findall(r'https?://[^\s<>"\']+', body_html)
            if urls:
                print("\n🔗 Links found in HTML:")
                for url in urls[:5]:
                    print(f"  {url}")


def main():
    parser = argparse.ArgumentParser(description="Hostinger Email Client")
    sub = parser.add_subparsers(dest='command')

    # ls
    ls_p = sub.add_parser('ls', help='List messages')
    ls_p.add_argument('--limit', type=int, default=15, help='Number to show')
    ls_p.add_argument('--all', action='store_true', help='Show all messages')
    ls_p.add_argument('--search', type=str, default='', help='Search keyword')

    # read
    read_p = sub.add_parser('read', help='Read a message by number')
    read_p.add_argument('num', type=int, help='Message number (from ls)')
    read_p.add_argument('--html', action='store_true', help='Show HTML version')
    read_p.add_argument('--raw', action='store_true', help='Show raw source')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    mail = connect()

    try:
        if args.command == 'ls':
            limit = None if args.all else args.limit
            list_messages(mail, args.search, limit)

        elif args.command == 'read':
            read_message(mail, args.num, args.html, args.raw)

    finally:
        mail.logout()


if __name__ == '__main__':
    main()
