"""
GrantWizard Pipeline Orchestrator
==================================
Chains: Website Scraper → Email Verification → SES Sender
Runs automatically as each stage completes.

Deploy on EC2: python3 pipeline_orchestrator.py
"""

import subprocess
import time
import os
import sys
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "pipeline.log")

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"  [{ts}] {msg}")
    sys.stdout.flush()

def run(cmd, desc, timeout=7200):
    """Run a command and wait for completion."""
    log(f"▶ {desc}")
    sys.stdout.flush()
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=SCRIPT_DIR,
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            log(f"✅ {desc} — completed")
            return True
        else:
            log(f"⚠️ {desc} — exit code {result.returncode}")
            # Print last few lines of error
            err = result.stderr.strip().split("\n")[-3:]
            for line in err:
                log(f"  {line}")
            return False
    except subprocess.TimeoutExpired:
        log(f"⏰ {desc} — timed out after {timeout}s")
        return False
    except Exception as e:
        log(f"❌ {desc} — {str(e)[:100]}")
        return False

def run_bg(cmd, logfile, desc):
    """Run a command in background."""
    log(f"🚀 {desc}")
    full_cmd = f"cd {SCRIPT_DIR} && nohup {cmd} > {logfile} 2>&1 &"
    subprocess.run(full_cmd, shell=True, cwd=SCRIPT_DIR)

def is_running(process_name):
    """Check if a process is running."""
    result = subprocess.run(
        f"ps aux | grep '{process_name}' | grep -v grep",
        shell=True, capture_output=True, text=True
    )
    return len(result.stdout.strip()) > 0

def wait_for_completion(process_name, desc, check_interval=60):
    """Wait for a background process to finish."""
    log(f"⏳ Waiting for {desc} to complete...")
    while is_running(process_name):
        time.sleep(check_interval)
    log(f"✅ {desc} finished")
    time.sleep(5)  # Let files flush

def main():
    log("=" * 60)
    log("  GRANTWIZARD PIPELINE ORCHESTRATOR")
    log("=" * 60)
    
    stage = 0
    
    # ── STAGE 1: Website Scraper ──
    stage += 1
    log(f"\n{'─'*40}")
    log(f"  STAGE {stage}: Website Scraper")
    log(f"{'─'*40}")
    
    if is_running("scrape_websites.py"):
        log("Scraper already running — monitoring completion...")
        wait_for_completion("scrape_websites.py", "website scraper", 120)
    else:
        log("Starting website scraper...")
        run_bg("python3 scrape_websites.py", "scrape_dashboard.log", "scraper")
        wait_for_completion("scrape_websites.py", "website scraper", 120)
    
    # ── STAGE 2: Merge Results ──
    stage += 1
    log(f"\n{'─'*40}")
    log(f"  STAGE {stage}: Merge Scraped Emails")
    log(f"{'─'*40}")
    
    # Read scraped output and merge into enriched_contacts.csv
    run('python3 -c "
import csv, sys
# Load scraped results
try:
    with open(\"scraped_contacts.csv\", encoding=\"utf-8\") as f:
        scraped = {r[\"EIN\"]: r for r in csv.DictReader(f) if r.get(\"SCRAPED_EMAIL\",\"\")}
    print(f\"Loaded {len(scraped):,} scraped emails\")
except:
    print(\"No scraped_contacts.csv found\")
    scraped = {}

# Load enriched contacts
with open(\"enriched_contacts.csv\", encoding=\"utf-8\") as f:
    rows = list(csv.DictReader(f))

updated = 0
for r in rows:
    ein = r[\"EIN\"]
    if ein in scraped:
        sr = scraped[ein]
        new_email = sr.get(\"SCRAPED_EMAIL\",\"\").strip()
        if new_email and new_email != r.get(\"EMAIL\",\"\").strip():
            # Check if scraped email is better priority
            old_prefix = r.get(\"EMAIL\",\"\").split(\"@\")[0].lower() if \"@\" in r.get(\"EMAIL\",\"\") else \"\"
            new_prefix = new_email.split(\"@\")[0].lower()
            priority = {\"grants\":10,\"apply\":9,\"proposals\":9,\"contact\":5,\"info\":4,\"director\":3,\"admin\":2}
            if priority.get(new_prefix,0) > priority.get(old_prefix,0):
                r[\"EMAIL\"] = new_email
                r[\"METHOD\"] = \"scraped\"
                updated += 1

with open(\"enriched_contacts.csv\", \"w\", newline=\"\", encoding=\"utf-8\") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

print(f\"Updated {updated:,} rows with better scraped emails\")
"', "Merging scraped emails", timeout=60)
    
    # ── STAGE 3: Verify Emails ──
    stage += 1
    log(f"\n{'─'*40}")
    log(f"  STAGE {stage}: SMTP Email Verification")
    log(f"{'─'*40}")
    
    run("python3 verify_emails.py --quick 100", "Quick verification test (100)", timeout=300)
    
    # Full verification in background
    log("Starting full verification in background...")
    run_bg("python3 verify_emails.py", "verify_output.log", "full verification")
    
    # ── STAGE 4: SES Sender ──
    stage += 1
    log(f"\n{'─'*40}")
    log(f"  STAGE {stage}: SES Sender")
    log(f"{'─'*40}")
    
    if is_running("ses_foundation_sender.py"):
        log("SES sender already running")
    else:
        log("Starting SES sender...")
        run_bg(
            "python3 ses_foundation_sender.py --tier theology --workers 10 --turbo --resume",
            "ses_output.log",
            "SES sender"
        )
    
    # ── SUMMARY ──
    log(f"\n{'='*60}")
    log(f"  ✅ PIPELINE RUNNING")
    log(f"  Scraper → Verification → Sending")
    log(f"  Check progress:")
    log(f"    Scraper:  tail -5 scrape_dashboard.log")
    log(f"    Verify:   tail -5 verify_output.log")
    log(f"    Sender:   tail -5 ses_output.log")
    log(f"    Pipeline: tail -20 pipeline.log")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()
