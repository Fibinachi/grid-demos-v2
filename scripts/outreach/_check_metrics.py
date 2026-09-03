"""Check outreach metrics: sent, bounced, replied, response rate."""
import os, json, sqlite3
from pathlib import Path
from collections import Counter

OUT = Path("outputs/outreach")

# Sent counts
sent_log = OUT / "gmail_sent.txt"
church_sent = OUT / "church_campaign_sent.txt"
failed_log = OUT / "gmail_failed.txt"

total_sent = 0
for log in [sent_log, church_sent]:
    if log.exists():
        with open(log) as f:
            total_sent += len([l for l in f if l.strip()])

total_failed = 0
if failed_log.exists():
    with open(failed_log) as f:
        total_failed += len([l for l in f if l.strip()])

print(f"Total sent: {total_sent:,}")
print(f"Total failed/bounced: {total_failed:,}")
if total_sent:
    print(f"Bounce rate: {100*total_failed/total_sent:.1f}%")

# Check reply logs
reply_files = [
    "outputs/outreach/hostinger_responses.csv",
    "outputs/outreach/hostinger_responses.json",
    "scripts/outreach/hostinger_responses.csv",
    "scripts/outreach/hostinger_responses.json",
]
for f in reply_files:
    if os.path.exists(f):
        print(f"\nReply file: {f}")
        if f.endswith('.csv'):
            with open(f) as fh:
                lines = [l for l in fh if l.strip()]
            print(f"  {len(lines)-1} replies")
        elif f.endswith('.json'):
            with open(f) as fh:
                data = json.load(fh)
            print(f"  {len(data)} replies")

# Check inbox monitor logs
for f in ['scripts/outreach/inbox_check_log.txt', 'scripts/outreach/inbox_monitor.py']:
    if os.path.exists(f):
        print(f"\nInbox monitor: {f} EXISTS")

# Check response classifier
classifier = Path("scripts/outreach/gmail_response_classifier.py")
if classifier.exists():
    print(f"\nResponse classifier: EXISTS")

# Industry benchmarks
print(f"""
{'='*60}
INDUSTRY BENCHMARKS (cold B2B email):
{'='*60}
  Average open rate:    15-25%
  Average reply rate:   1-5%
  Average bounce rate:  2-5%
  
For our specific audiences:
  Political data firms:   3-8% reply (data product = relevant)
  Research/foundations:   5-15% reply (free for academic use)
  Insurance:              2-5% reply (church insurance = niche but targeted)
  Church pastors:         3-10% reply (fear-based + local relevance)
  Data brokers:           2-5% reply (they get pitched constantly)

EXPECTED from 26 emails:
  0-4 replies within first week
  1-2 meaningful conversations
  
KEY: Follow-up doubles reply rates. Wait 5-7 days, then send a 
brief follow-up to non-responders.
""")
