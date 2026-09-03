#!/usr/bin/env python3
"""
SES Email Validation Enrichment
================================
Uses Amazon SES's built-in Email Validation API (GetEmailAddressInsights)
to validate foundation email addresses. No extra API key needed —
uses your existing AWS credentials.

Built-in checks:
  - HasValidSyntax     — RFC-compliant format?
  - HasValidDnsRecords — Domain exists & configured for email?
  - MailboxExists      — Does the mailbox exist? (SMTP-level check)
  - IsRoleAddress      — Role-based (info@, admin@, etc.)?
  - IsDisposable       — Disposable/temporary domain?
  - IsRandomInput      — Randomly generated pattern?

Usage:
  python ses_email_validate.py                         # Full run
  python ses_email_validate.py --quick 50              # Test first 50
  python ses_email_validate.py --resume                # Resume from checkpoint
  python ses_email_validate.py --status                # Show results
  python ses_email_validate.py --enable-auto           # Enable SES Auto Validation

Requirements:
  pip install boto3
  AWS credentials configured (same as your SES sending setup)
"""

import os, sys, csv, json, time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts_ses.csv")
STATE_FILE = os.path.join(SCRIPT_DIR, "ses_validate_state.json")

AWS_REGION = "us-east-1"  # Change if your SES is in a different region
RATE_LIMIT = 10  # SES API allows burst

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    print("❌ boto3 not installed. Run: pip install boto3")
    sys.exit(1)


def get_client():
    """Create SESv2 client."""
    return boto3.client("sesv2", region_name=AWS_REGION)


def check_account():
    """Check current SES account settings."""
    client = get_client()
    try:
        acct = client.get_account()
        suppression = acct.get("SuppressionAttributes", {})
        validation = acct.get("ValidationOptions", {})
        threshold = validation.get("ConditionThreshold", {})

        print(f"📊 SES Account Status:")
        print(f"   Sending enabled:      {acct.get('SendingEnabled', False)}")
        print(f"   Production access:    {acct.get('ProductionAccessEnabled', False)}")
        print(f"   Max send rate:        {acct.get('SendQuota', {}).get('MaxSendRate', '?')}/sec")
        print(f"   Max 24h send:         {acct.get('SendQuota', {}).get('Max24HourSend', '?')}")
        print(f"   Suppressed reasons:   {suppression.get('SuppressedReasons', [])}")
        print(f"   Auto Validation:      {'ENABLED' if threshold.get('ConditionThresholdEnabled') == 'ENABLED' else 'DISABLED'}")
        if threshold.get("ConditionThresholdEnabled") == "ENABLED":
            print(f"   Validation threshold: {threshold.get('OverallConfidenceThreshold', {}).get('Verdict', '?')}")
        return acct
    except Exception as e:
        print(f"❌ Failed to check account: {e}")
        return None


def enable_auto_validation(threshold="MEDIUM"):
    """
    Enable SES Auto Validation to automatically filter outbound emails.
    Threshold: HIGH, MEDIUM, or MANAGED.
    Note: suppressed sends still incur standard SES fees + Auto Validation fees.
    """
    client = get_client()
    params = {
        "SuppressedReasons": ["BOUNCE", "COMPLAINT"],
        "ValidationOptions": {
            "ConditionThreshold": {
                "ConditionThresholdEnabled": "ENABLED",
                "OverallConfidenceThreshold": {
                    "Verdict": threshold
                }
            }
        }
    }
    try:
        client.put_account_suppression_attributes(**params)
        print(f"✅ Auto Validation enabled with threshold: {threshold}")
        print(f"   Addresses below {threshold} confidence will be suppressed.")
        print(f"   Note: Suppressed sends still count toward send quota and incur fees.")
        return True
    except Exception as e:
        print(f"❌ Failed to enable Auto Validation: {e}")
        return False


def validate_email(client, email):
    """Call SES GetEmailAddressInsights for a single email."""
    if not email or "@" not in email:
        return {"error": "no_email"}
    try:
        resp = client.get_email_address_insights(EmailAddress=email)
        mv = resp.get("MailboxValidation", {})
        evals = mv.get("Evaluations", {})
        return {
            "IsValid": mv.get("IsValid", {}).get("ConfidenceVerdict", ""),
            "HasValidSyntax": evals.get("HasValidSyntax", {}).get("ConfidenceVerdict", ""),
            "HasValidDnsRecords": evals.get("HasValidDnsRecords", {}).get("ConfidenceVerdict", ""),
            "MailboxExists": evals.get("MailboxExists", {}).get("ConfidenceVerdict", ""),
            "IsRoleAddress": evals.get("IsRoleAddress", {}).get("ConfidenceVerdict", ""),
            "IsDisposable": evals.get("IsDisposable", {}).get("ConfidenceVerdict", ""),
            "IsRandomInput": evals.get("IsRandomInput", {}).get("ConfidenceVerdict", ""),
        }
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "Throttling":
            return {"error": "throttled"}
        return {"error": f"AWS_{code}"}
    except Exception as e:
        return {"error": str(e)[:80]}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"processed": {}, "results": {}}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_csv(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


VVERDICT_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "": 3, None: 4}
VVERDICT_LABEL = {
    "HIGH": "✅ High",
    "MEDIUM": "📬 Medium",
    "LOW": "❌ Low",
}


def main():
    if "--enable-auto" in sys.argv:
        threshold = "MEDIUM"
        for arg in sys.argv[1:]:
            if arg.upper() in ("HIGH", "MEDIUM", "MANAGED"):
                threshold = arg.upper()
        check_account()
        print()
        enable_auto_validation(threshold)
        return

    if "--status" in sys.argv:
        check_account()
        print()
        state = load_state()
        results = list(state.get("results", {}).values())
        total = len(results)
        if total == 0:
            print("📊 No validation results yet. Run the script first.")
            return
        high = sum(1 for r in results if r.get("IsValid") == "HIGH")
        med = sum(1 for r in results if r.get("IsValid") == "MEDIUM")
        low = sum(1 for r in results if r.get("IsValid") == "LOW")
        role = sum(1 for r in results if r.get("IsRoleAddress") == "HIGH")
        disposable = sum(1 for r in results if r.get("IsDisposable") == "HIGH")
        random = sum(1 for r in results if r.get("IsRandomInput") == "HIGH")
        errors = sum(1 for r in results if r.get("error"))
        print(f"📊 SES Email Validation Results:")
        print(f"   Total validated:   {total:,}")
        print(f"   ✅ High confidence: {high:,}")
        print(f"   📬 Medium:          {med:,}")
        print(f"   ❌ Low confidence:  {low:,}")
        print(f"   👤 Role-based:      {role:,}")
        print(f"   🗑️  Disposable:     {disposable:,}")
        print(f"   🎲 Random patterns: {random:,}")
        print(f"   ⚠️  Errors:         {errors:,}")
        return

    quick = None
    resume = False
    for arg in sys.argv[1:]:
        if "--quick" in arg:
            quick = int(arg.split("=")[-1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1])
        elif arg == "--resume":
            resume = True

    check_account()
    print()

    client = get_client()
    rows = load_csv(CSV_PATH)
    print(f"📄 Loaded {len(rows)} records from enriched_contacts.csv")

    if quick:
        rows = rows[:quick]
        print(f"🔍 Quick mode: processing first {quick} records")

    state = load_state() if resume else {"processed": {}, "results": {}}
    start_from = len(state["processed"]) if resume else 0

    if resume and start_from > 0:
        print(f"📌 Resuming from row {start_from} ({len(state['processed'])} already processed)")

    for i, row in enumerate(rows[start_from:], start=start_from):
        email = (row.get("EMAIL") or "").strip()
        ein = row.get("EIN", "")

        if not email:
            state["results"][ein] = {"error": "no_email", "IsValid": ""}
            state["processed"][ein] = True
            continue

        # Rate limiting
        if i > start_from:
            time.sleep(1.0 / RATE_LIMIT)

        print(f"  [{i+1}/{len(rows)}] {email}", end="")

        result = validate_email(client, email)

        # Handle throttling with backoff
        retries = 0
        while result.get("error") == "throttled" and retries < 3:
            wait = 2 ** retries
            print(f" ⏳ throttled, waiting {wait}s...", end="")
            time.sleep(wait)
            result = validate_email(client, email)
            retries += 1

        state["results"][ein] = result
        state["processed"][ein] = True

        if "error" in result:
            print(f" ⚠️ {result['error']}")
        else:
            icon = {"HIGH": "✅", "MEDIUM": "📬", "LOW": "❌"}.get(result.get("IsValid", ""), "❓")
            print(f" {icon} Valid={result.get('IsValid','?')} Role={result.get('IsRoleAddress','?')}")

        if (i + 1) % 100 == 0:
            save_state(state)
            print(f"  💾 Checkpoint saved at row {i+1}")

    save_state(state)
    print(f"\n💾 State saved. Processed {len(state['processed'])} records.")

    # Generate output CSV
    print(f"\n📊 Generating {OUTPUT_PATH}...")
    fieldnames = list(rows[0].keys()) if rows else []
    ses_fields = [
        "SES_IS_VALID", "SES_SYNTAX", "SES_DNS", "SES_MAILBOX",
        "SES_ROLE", "SES_DISPOSABLE", "SES_RANDOM",
    ]

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames + ses_fields)
        writer.writeheader()
        for row in rows:
            ein = row.get("EIN", "")
            r = state["results"].get(ein, {})
            out = dict(row)
            out.update({
                "SES_IS_VALID": r.get("IsValid", ""),
                "SES_SYNTAX": r.get("HasValidSyntax", ""),
                "SES_DNS": r.get("HasValidDnsRecords", ""),
                "SES_MAILBOX": r.get("MailboxExists", ""),
                "SES_ROLE": r.get("IsRoleAddress", ""),
                "SES_DISPOSABLE": r.get("IsDisposable", ""),
                "SES_RANDOM": r.get("IsRandomInput", ""),
            })
            writer.writerow(out)

    print(f"✅ Output: {OUTPUT_PATH} ({len(rows)} records)")

    # Summary
    results = list(state["results"].values())
    high = sum(1 for r in results if r.get("IsValid") == "HIGH")
    med = sum(1 for r in results if r.get("IsValid") == "MEDIUM")
    low = sum(1 for r in results if r.get("IsValid") == "LOW")
    errors = sum(1 for r in results if r.get("error"))
    role_high = sum(1 for r in results if r.get("IsRoleAddress") == "HIGH")

    print(f"\n📊 Summary:")
    print(f"   ✅ High confidence: {high:,}")
    print(f"   📬 Medium:          {med:,}")
    print(f"   ❌ Low confidence:  {low:,}")
    print(f"   👤 Role-based:      {role_high:,}")
    print(f"   ⚠️  Errors:         {errors:,}")


if __name__ == "__main__":
    main()
