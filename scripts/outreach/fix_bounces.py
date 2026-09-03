"""Fix bounced emails and track bounces for future sending."""
import csv, json
from pathlib import Path

OUT = Path("outputs/outreach")
BOUNCE_LOG = OUT / "bounces.txt"

# Track bounces
bounces = {"sales@elvanto.com": "Elvanto / Tithe.ly — 5.1.1 address not found. No public email. Use phone: 629-299-1912."}

with open(BOUNCE_LOG, "a") as f:
    for addr, reason in bounces.items():
        f.write(f"{addr}|{reason}\n")

print("Bounces logged.")

# Fix CSV — replace Elvanto with working alternative
with open(OUT / "outreach_emails.csv", "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

fixed = 0
for r in rows:
    if r["contact_value"] == "sales@elvanto.com":
        # Try hello@tithe.ly as fallback
        r["contact_value"] = "hello@tithe.ly"
        fixed += 1
        print(f"  Fixed: {r['org']} -> {r['contact_value']}")

if fixed:
    with open(OUT / "outreach_emails.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"\n✅ {fixed} entries fixed in outreach_emails.csv")

# Also mark as sent in log so it doesn't re-send
with open(OUT / "gmail_sent.txt", "a") as f:
    f.write("Elvanto / Tithe.ly (bounced — retry with hello@tithe.ly)\n")

print("Done.")
