"""Validate unsent queue emails via IPQS and remove bad ones."""
import json, urllib.request, time
from pathlib import Path

KEY = "TDBK4MVtTuFqehjtWvS5YKAZU99b4hf9"
QF = Path("outputs/outreach/unified_queue.jsonl")
SENT = Path("outputs/outreach/gmail_sent.txt")
BOUNCE = Path("outputs/outreach/gmail_bounced.txt")
RESULTS = Path("outputs/outreach/ipqs_results.json")

# Load already-sent
sent = set()
if SENT.exists():
    sent = {l.strip().lower() for l in SENT.read_text().splitlines() if l.strip() and "@" in l}

# Load existing bounces
bounced = set()
if BOUNCE.exists():
    bounced = {l.strip().lower() for l in BOUNCE.read_text().splitlines() if l.strip()}

# Load queue
entries = [json.loads(l) for l in QF.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

# Unique unsent emails
unsent = [e for e in entries if e["to"].lower() not in sent]
unique = list({e["to"].lower() for e in unsent})
print(f"Queue: {len(entries)} | Sent: {len(sent)} | Unsent unique: {len(unique)}")

# Load cached results
results = {}
if RESULTS.exists():
    results = json.loads(RESULTS.read_text())

# Validate uncached emails
new_checks = [e for e in unique if e not in results and e not in bounced]
print(f"New IPQS checks needed: {len(new_checks)}")

BAD = 0
for i, email in enumerate(new_checks):
    if (i + 1) % 50 == 0:
        print(f"  {i+1}/{len(new_checks)}... (bad so far: {BAD})")
    url = f"https://www.ipqualityscore.com/api/json/email/{KEY}/{email}"
    req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  ERROR {email}: {e}")
        results[email] = {"valid": False, "reason": str(e)}
        BAD += 1
        continue

    valid = data.get("valid", False)
    disposable = data.get("disposable", False)
    smtp_score = data.get("smtp_score", 0)
    overall = data.get("overall_score", 0)
    catchall = "catch_all" in str(data.get("message", "")).lower()

    is_bad = not valid or disposable or catchall or overall <= 1

    results[email] = {
        "valid": valid,
        "disposable": disposable,
        "smtp_score": smtp_score,
        "overall_score": overall,
        "catchall": catchall,
        "bad": is_bad,
    }
    if is_bad:
        BAD += 1
        print(f"  BAD: {email} (valid={valid}, disposable={disposable}, catchall={catchall}, score={overall})")

    # Save periodically
    if (i + 1) % 100 == 0:
        RESULTS.write_text(json.dumps(results, indent=2))
    time.sleep(0.3)  # rate limit

# Save final results
RESULTS.write_text(json.dumps(results, indent=2))

# Build clean queue: remove bad & bounced emails
bad_emails = {e for e, r in results.items() if r.get("bad")} | bounced
clean = []
removed = 0
for e in entries:
    if e["to"].lower() in sent:
        clean.append(e)  # keep already-sent
    elif e["to"].lower() in bad_emails:
        removed += 1
    else:
        clean.append(e)

# Write clean queue
with open(QF, "w", encoding="utf-8") as f:
    for item in clean:
        f.write(json.dumps(item) + "\n")

# Add bad emails to bounce list
new_bounces = bad_emails - bounced
if new_bounces:
    with open(BOUNCE, "a") as f:
        for e in sorted(new_bounces):
            f.write(f"{e}\n")

print(f"\n=== RESULTS ===")
print(f"  Checked: {len(results)} emails")
print(f"  Bad: {BAD} (newly identified)")
print(f"  Previously bounced: {len(bounced)}")
print(f"  Queue: {len(entries)} -> {len(clean)} entries")
print(f"  Removed: {removed}")
print(f"  New bounces added: {len(new_bounces)}")
print(f"  Approx send time now: {len(clean)*3/3600:.1f} hours")
