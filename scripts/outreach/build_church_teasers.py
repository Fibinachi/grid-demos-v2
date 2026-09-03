import sqlite3, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect
from pathlib import Path
import random

db = connect()
cur = db.cursor()
OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)

# Load existing state
sent_file = OUT / "gmail_sent.txt"
bounce_file = OUT / "gmail_bounced.txt"
queue_file = OUT / "unified_queue.jsonl"

sent = set()
if sent_file.exists():
    sent = {l.strip().lower() for l in sent_file.read_text().splitlines() if l.strip()}

bounced = set()
if bounce_file.exists():
    bounced = {l.strip().lower() for l in bounce_file.read_text().splitlines() if l.strip()}

# Read existing queue
existing_queue = []
if queue_file.exists():
    with open(queue_file) as f:
        for line in f:
            if line.strip():
                existing_queue.append(json.loads(line))

existing_emails = {q['to'].lower() for q in existing_queue} | sent | bounced

# Count pending
pending_old = [q for q in existing_queue if q.get('to','').lower() not in sent and q.get('to','').lower() not in bounced]
print(f"Existing queue: {len(existing_queue)} total, {len(pending_old)} pending")

# Find US churches with email that haven't been contacted
cur.execute("""
    SELECT c.id, c.name, c.address, c.city, c.state, c.zip5, c.faith, cv.value as email
    FROM churches c
    JOIN church_contact_values cv ON c.id = cv.church_id
    WHERE c.country = 'US'
      AND cv.contact_type = 'email'
      AND cv.value LIKE '%@%'
      AND c.address IS NOT NULL AND c.address != ''
      AND c.city IS NOT NULL AND c.city != ''
      AND c.zip5 IS NOT NULL AND c.zip5 != ''
    ORDER BY RANDOM()
""")
rows = cur.fetchall()
print(f"US churches with email + full address: {len(rows):,}")

# Filter: only emails not already in queue/sent/bounced
fresh = [r for r in rows if r[7].lower() not in existing_emails]
print(f"Not yet contacted: {len(fresh):,}")

# Build church teaser entries
new_queue = []
for cid, name, addr, city, state, zip5, faith, email in fresh[:500]:
    subject = "GRID Community Intelligence Report — $250"
    body = f"""Hi {name},

I run GRID, the Global Religious Infrastructure Database — we've mapped over 3.5 million places of worship worldwide.

Your church at {addr}, {city}, {state} {zip5} is in our database, and I wanted to let you know about our Community Intelligence Report. For $250, we provide:

• Demographic analysis of your 3/5/10-mile radius
• Competitive landscape (other churches nearby)
• Community needs assessment
• Custom maps and visualizations

This is the kind of data that helps with outreach planning, grant applications, and understanding your community better.

Interested? Just reply to this email.

Best,
Charles Prescott
Creator, GRID
(843) 504-4542"""

    new_queue.append({
        "to": email,
        "subject": subject,
        "body": body,
        "campaign": "church_teaser",
        "church_id": cid,
        "church_name": name
    })

# Merge with existing queue
merged = existing_queue + new_queue

# Write merged queue
with open(queue_file, 'w', encoding='utf-8') as f:
    for entry in merged:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

print(f"\nAdded {len(new_queue)} church teasers to queue")
print(f"Queue total: {len(merged)} entries")
print()

# Check if sender is running
import subprocess
r = subprocess.run(["powershell", "-c", 
    "Get-Process python* -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'send_unified' } | Measure-Object | Select -Expand Count"],
    capture_output=True, text=True)
running = r.stdout.strip()
print(f"Unified sender running: {'YES' if running and running != '0' else 'NO'}")

db.close()
print("Done.")
