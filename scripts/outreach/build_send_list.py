#!/usr/bin/env python3
"""
Build Clean Send List
=====================
Creates a clean, filtered send list from enriched_contacts.csv by:
  1. Removing exact-match placeholder/fake domains
  2. Removing bounced addresses (from bounced_emails.txt)
  3. Removing declined foundations (from declined_foundations.txt)
  4. Skipping already-sent EINs (from ses_logs/ses_sent.txt)
  5. Keeping only records with valid-looking emails
  6. Optionally running SES Email Validation on remaining
  7. Generating SES validation enrichments

Output: send_list_clean.csv (the file ses_foundation_sender.py uses)

Usage:
  python build_send_list.py                         # Build from enriched_contacts.csv
  python build_send_list.py --validate 100           # Build + SES-validate first 100
  python build_send_list.py --validate               # Build + SES-validate all
  python build_send_list.py --resume                 # Resume SES validation
  python build_send_list.py --status                 # Show counts only
"""

import csv, os, sys, json, time, re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Input
ENRICHED_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
BOUNCED_FILE = os.path.join(SCRIPT_DIR, "bounced_emails.txt")
DECLINED_FILE = os.path.join(SCRIPT_DIR, "declined_foundations.txt")
SENT_LOG = os.path.join(SCRIPT_DIR, "ses_logs", "ses_sent.txt")

# Output
CLEAN_CSV = os.path.join(SCRIPT_DIR, "send_list_clean.csv")
VALIDATE_STATE = os.path.join(SCRIPT_DIR, "send_list_validate_state.json")

# Placeholder domains (exact match only — NOT substring)
PLACEHOLDER_DOMAINS = {
    "fam.com", "familyfoundation.com", "privatefoundation.org",
    "educationalfoundation.org", "educationfoundation.com",
    "scholarshipfoundation.org", "charitablefoundation.org",
    "legacyfoundation.org", "iii.org", "bank.org", "research.com",
    "robert.org",
}

# Role-based prefixes that are risky for cold outreach
ROLE_PREFIXES = (
    "info@", "contact@", "hello@", "admin@", "mail@",
    "office@", "webmaster@", "support@", "donations@",
    "giving@", "noreply@", "no-reply@",
)

AWS_REGION = "us-east-1"


def load_bounced():
    """Load bounced addresses."""
    bounced = set()
    if os.path.exists(BOUNCED_FILE):
        with open(BOUNCED_FILE) as f:
            for line in f:
                addr = line.strip().lower()
                if addr and "@" in addr:
                    bounced.add(addr)
    return bounced


def load_declined():
    """Load declined foundation EINs."""
    declined = set()
    if os.path.exists(DECLINED_FILE):
        with open(DECLINED_FILE) as f:
            for line in f:
                parts = line.strip().split("|")
                if parts and parts[0].strip():
                    declined.add(parts[0].strip())
    return declined


def load_sent():
    """Load already-sent EINs."""
    sent = set()
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG) as f:
            for line in f:
                if "|" in line:
                    sent.add(line.split("|")[0].strip())
    return sent


def is_fake_email(email):
    """Check if email is on a known placeholder domain."""
    if not email or "@" not in email:
        return True
    domain = email.lower().split("@")[1]
    return domain in PLACEHOLDER_DOMAINS


def load_state():
    if os.path.exists(VALIDATE_STATE):
        with open(VALIDATE_STATE) as f:
            return json.load(f)
    return {"processed": {}, "results": {}}


def save_state(state):
    with open(VALIDATE_STATE, "w") as f:
        json.dump(state, f, indent=2)


def run_ses_validation(rows, max_count=None, resume=False):
    """
    Run SES Email Validation on rows.
    Returns enriched rows with SES validation fields.
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("❌ boto3 not installed. Skipping SES validation.")
        return rows

    if max_count:
        rows = rows[:max_count]

    client = boto3.client("sesv2", region_name=AWS_REGION)
    state = load_state() if resume else {"processed": {}, "results": {}}
    start_from = len(state["processed"]) if resume else 0

    if resume and start_from > 0:
        print(f"  Resuming SES validation from row {start_from}")

    for i, row in enumerate(rows[start_from:], start=start_from):
        email = (row.get("EMAIL") or "").strip()
        ein = row.get("EIN", "")

        if not email or "@" not in email:
            state["results"][ein] = {"SES_IS_VALID": "", "SES_ERROR": "no_email"}
            state["processed"][ein] = True
            continue

        if i > start_from:
            time.sleep(0.1)  # 10/sec

        try:
            resp = client.get_email_address_insights(EmailAddress=email)
            mv = resp.get("MailboxValidation", {})
            ev = mv.get("Evaluations", {})
            state["results"][ein] = {
                "SES_IS_VALID": mv.get("IsValid", {}).get("ConfidenceVerdict", ""),
                "SES_SYNTAX": ev.get("HasValidSyntax", {}).get("ConfidenceVerdict", ""),
                "SES_DNS": ev.get("HasValidDnsRecords", {}).get("ConfidenceVerdict", ""),
                "SES_MAILBOX": ev.get("MailboxExists", {}).get("ConfidenceVerdict", ""),
                "SES_ROLE": ev.get("IsRoleAddress", {}).get("ConfidenceVerdict", ""),
                "SES_DISPOSABLE": ev.get("IsDisposable", {}).get("ConfidenceVerdict", ""),
                "SES_RANDOM": ev.get("IsRandomInput", {}).get("ConfidenceVerdict", ""),
            }
        except Exception as e:
            state["results"][ein] = {"SES_IS_VALID": "", "SES_ERROR": str(e)[:60]}

        state["processed"][ein] = True

        if (i + 1) % 50 == 0:
            save_state(state)
            print(f"    SES validated {i+1}/{len(rows)}...", end="\r")
            sys.stdout.flush()

    save_state(state)
    print(f"\n    SES validation complete: {len(state['processed'])} checked")

    # Merge results back
    ses_fields = ["SES_IS_VALID", "SES_SYNTAX", "SES_DNS", "SES_MAILBOX",
                   "SES_ROLE", "SES_DISPOSABLE", "SES_RANDOM"]
    for row in rows:
        ein = row.get("EIN", "")
        r = state["results"].get(ein, {})
        for f in ses_fields:
            row[f] = r.get(f, "")
        row["SES_ERROR"] = r.get("SES_ERROR", "")

    return rows


def main():
    if "--status" in sys.argv:
        d = [r for r in csv.DictReader(open(ENRICHED_CSV, encoding="utf-8-sig"))]
        total = len(d)
        with_email = sum(1 for r in d if r.get("EMAIL", "").strip())
        fake = sum(1 for r in d if is_fake_email(r.get("EMAIL", "")))
        bounced = len(load_bounced())
        declined = len(load_declined())
        sent = len(load_sent())
        remaining = with_email - fake - bounced
        print(f"📊 Send List Status:")
        print(f"   Total records:         {total:>6,}")
        print(f"   With email:            {with_email:>6,}")
        print(f"   ❌ Placeholder domains: {fake:>6,}")
        print(f"   ❌ Bounced:             {bounced:>6,}")
        print(f"   ❌ Declined:            {declined:>6,}")
        print(f"   ✅ Already sent:        {sent:>6,}")
        print(f"   📬 Ready to send:       {remaining:>6,}")
        print(f"\n   Run: python build_send_list.py")
        print(f"       python build_send_list.py --validate (adds SES checks)")
        return

    validate_all = False
    validate_count = None
    resume = False
    for arg in sys.argv[1:]:
        if arg == "--validate":
            validate_all = True
        elif arg == "--resume":
            resume = True
            validate_all = True
        elif arg.startswith("--validate="):
            validate_count = int(arg.split("=")[1])
            validate_all = True

    # ── Load data ──
    print("📄 Loading enriched_contacts.csv...")
    with open(ENRICHED_CSV, encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))
    print(f"   Total: {len(all_rows):,}")

    # ── Load exclusion lists ──
    bounced = load_bounced()
    declined = load_declined()
    sent = load_sent()
    print(f"   Excluding: {len(bounced):,} bounced, {len(declined):,} declined, {len(sent):,} already sent")

    # ── Filter ──
    clean = []
    removed_placeholder = 0
    removed_bounced = 0
    removed_declined = 0
    removed_sent = 0
    removed_no_email = 0

    for row in all_rows:
        email = (row.get("EMAIL") or "").strip().lower()
        ein = row.get("EIN", "")

        # Skip no email
        if not email or "@" not in email:
            removed_no_email += 1
            continue

        # Skip placeholder domains
        if is_fake_email(email):
            removed_placeholder += 1
            continue

        # Skip bounced
        if email in bounced:
            removed_bounced += 1
            continue

        # Skip declined
        if ein in declined:
            removed_declined += 1
            continue

        # Skip sent
        if ein in sent:
            removed_sent += 1
            continue

        clean.append(row)

    print(f"\n📊 Filter Results:")
    print(f"   ❌ No email:          {removed_no_email:>6,}")
    print(f"   ❌ Placeholder domain: {removed_placeholder:>6,}")
    print(f"   ❌ Bounced:            {removed_bounced:>6,}")
    print(f"   ❌ Declined:           {removed_declined:>6,}")
    print(f"   ✅ Already sent:       {removed_sent:>6,}")
    print(f"   {'='*35}")
    print(f"   📬 Remaining:          {len(clean):>6,}")

    if not clean:
        print("\n❌ Nothing to send!")
        return

    # ── Optional SES Validation ──
    if validate_all:
        print(f"\n🔍 Running SES Email Validation...")
        target = validate_count or len(clean)
        clean = run_ses_validation(clean, max_count=target, resume=resume)

        # Show SES results distribution
        ses_valid = [r for r in clean if r.get("SES_IS_VALID")]
        if ses_valid:
            high = sum(1 for r in ses_valid if r.get("SES_IS_VALID") == "HIGH")
            med = sum(1 for r in ses_valid if r.get("SES_IS_VALID") == "MEDIUM")
            low = sum(1 for r in ses_valid if r.get("SES_IS_VALID") == "LOW")
            role = sum(1 for r in ses_valid if r.get("SES_ROLE") == "HIGH")
            print(f"   SES results on {len(ses_valid)} checked:")
            print(f"     ✅ High: {high}  📬 Medium: {med}  ❌ Low: {low}  👤 Role: {role}")

    # ── Write clean CSV ──
    fieldnames = list(all_rows[0].keys())
    extra_fields = ["SES_IS_VALID", "SES_SYNTAX", "SES_DNS", "SES_MAILBOX",
                     "SES_ROLE", "SES_DISPOSABLE", "SES_RANDOM", "SES_ERROR"]
    all_fields = fieldnames + [f for f in extra_fields if f not in fieldnames]

    with open(CLEAN_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields)
        writer.writeheader()
        for row in clean:
            out = {k: row.get(k, "") for k in fieldnames}
            for ef in extra_fields:
                if ef not in out:
                    out[ef] = row.get(ef, "")
            writer.writerow(out)

    print(f"\n✅ Clean send list written: {CLEAN_CSV}")
    print(f"   Records: {len(clean):,}")

    # ── Show sample ──
    print(f"\n📋 First 5 records:")
    for r in clean[:5]:
        email = r.get("EMAIL", "")
        name = r.get("NAME", "")[:50]
        ein = r.get("EIN", "")
        print(f"   {email:45s} {name} [{ein}]")

    print(f"\n💡 Next step: python ses_foundation_sender.py --clean-list")


if __name__ == "__main__":
    main()
