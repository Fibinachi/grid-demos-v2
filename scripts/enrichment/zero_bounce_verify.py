#!/usr/bin/env python3
"""
Zero Bounce Email Verification Script
======================================
Uses Zero Bounce API (zerobounce.net) to validate foundation emails
and enrich with available contact data (names, location if available).

Usage:
  python zero_bounce_verify.py                          # Full run
  python zero_bounce_verify.py --quick 50               # Test first 50
  python zero_bounce_verify.py --resume                 # Resume from last checkpoint
  python zero_bounce_verify.py --status                 # Show current results
  python zero_bounce_verify.py --credits                # Check remaining credits

Set env var:  ZEROBOUNCE_API_KEY  (or hardcode below)
"""

import os, sys, csv, json, time, urllib.request, urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts_zb.csv")
STATE_FILE = os.path.join(SCRIPT_DIR, "zero_bounce_state.json")
API_KEY = os.environ.get("ZEROBOUNCE_API_KEY", "")
ZB_API = "https://api.zerobounce.net/v2/validate"

RATE_LIMIT = 5  # requests per second (ZB allows ~10/sec on paid plans)


def check_credits():
    """Check remaining credits."""
    if not API_KEY:
        print("❌ ZEROBOUNCE_API_KEY not set")
        return 0
    url = f"https://api.zerobounce.net/v2/getcredits?api_key={API_KEY}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read())
            credits = int(d.get("Credits", 0))
            print(f"💰 Zero Bounce credits remaining: {credits}")
            return credits
    except Exception as e:
        print(f"❌ Failed to check credits: {e}")
        return 0


def verify_email(email):
    """Call Zero Bounce API to validate a single email."""
    if not email or "@" not in email:
        return {"status": "no_email", "sub_status": "", "error": "blank_email"}
    params = urllib.parse.urlencode({"api_key": API_KEY, "email": email})
    url = f"{ZB_API}?{params}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            return {"status": "error", "sub_status": str(e.code), "error": str(e)[:80]}
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
                continue
            return {"status": "error", "sub_status": "timeout", "error": str(e)[:80]}
    return {"status": "error", "sub_status": "max_retry", "error": "exhausted retries"}


def load_state():
    """Load checkpoint state (which rows have been processed)."""
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


def main():
    if "--credits" in sys.argv:
        check_credits()
        return

    if "--status" in sys.argv:
        state = load_state()
        total = len(state.get("results", {}))
        valid = sum(1 for v in state["results"].values() if v.get("status") == "valid")
        invalid = sum(1 for v in state["results"].values() if v.get("status") in ("invalid", "do_not_mail"))
        catchall = sum(1 for v in state["results"].values() if v.get("status") == "catch-all")
        unknown = sum(1 for v in state["results"].values() if v.get("status") == "unknown")
        errors = sum(1 for v in state["results"].values() if v.get("status") == "error")
        print(f"📊 Zero Bounce verification status:")
        print(f"   Total processed: {total}")
        print(f"   ✅ Valid:        {valid}")
        print(f"   ❌ Invalid:      {invalid}")
        print(f"   📬 Catch-all:    {catchall}")
        print(f"   ❓ Unknown:      {unknown}")
        print(f"   ⚠️  Errors:      {errors}")
        remaining = check_credits()
        print(f"   📝 Remaining credits: {remaining}")
        return

    quick = None
    resume = False
    for arg in sys.argv[1:]:
        if arg.startswith("--quick"):
            quick = int(arg.split("=")[-1]) if "=" in arg else int(sys.argv[sys.argv.index(arg) + 1])
        elif arg == "--resume":
            resume = True

    if not API_KEY:
        print("❌ ZEROBOUNCE_API_KEY environment variable not set.")
        print("   Run: [Environment]::SetEnvironmentVariable('ZEROBOUNCE_API_KEY', 'your_key', 'User')")
        sys.exit(1)

    # Check credits first
    credits = check_credits()
    if credits <= 0:
        print("❌ No credits remaining. Top up at https://www.zerobounce.net/")
        sys.exit(1)

    rows = load_csv(CSV_PATH)
    print(f"📄 Loaded {len(rows)} records from enriched_contacts.csv")

    if quick:
        rows = rows[:quick]
        print(f"🔍 Quick mode: processing first {quick} records")

    state = load_state() if resume else {"processed": {}, "results": {}}
    start_from = len(state["processed"]) if resume else 0

    if resume and start_from > 0:
        print(f"📌 Resuming from row {start_from} ({len(state['processed'])} already processed)")

    credits_used = 0
    for i, row in enumerate(rows[start_from:], start=start_from):
        if credits_used >= credits:
            print(f"\n⛔ Credits exhausted after {credits_used} verifications.")
            break

        email = (row.get("EMAIL") or "").strip()
        ein = row.get("EIN", "")
        name = row.get("NAME", "")

        # Skip rows without email
        if not email:
            state["results"][ein] = {"status": "no_email", "sub_status": "", "email": ""}
            state["processed"][ein] = True
            continue

        # Rate limiting
        if i > start_from:
            time.sleep(1.0 / RATE_LIMIT)

        print(f"  [{i+1}/{len(rows)}] {email}", end="")

        result = verify_email(email)
        state["results"][ein] = {
            "email": email,
            "status": result.get("status", "error"),
            "sub_status": result.get("sub_status", ""),
            "catchall_domain": result.get("catchall_domain"),
            "free_email": result.get("free_email"),
            "mx_found": result.get("mx_found"),
            "smtp_provider": result.get("smtp_provider", ""),
            "firstname": result.get("firstname", ""),
            "lastname": result.get("lastname", ""),
            "gender": result.get("gender", ""),
            "country": result.get("country", ""),
            "region": result.get("region", ""),
            "city": result.get("city", ""),
            "zipcode": result.get("zipcode", ""),
            "domain_age_days": result.get("domain_age_days", ""),
        }
        state["processed"][ein] = True
        credits_used += 1

        status_icon = {"valid": "✅", "catch-all": "📬", "invalid": "❌",
                       "do_not_mail": "⛔", "unknown": "❓", "error": "⚠️"}.get(
            result.get("status", ""), "❓")
        print(f" {status_icon} {result.get('status', '?')}")

        # Save state every 100 rows
        if (i + 1) % 100 == 0:
            save_state(state)
            print(f"  💾 Checkpoint saved at row {i+1}")

    save_state(state)
    print(f"\n💾 Final state saved. Processed {credits_used} emails.")

    # Generate output CSV
    print(f"\n📊 Generating {OUTPUT_PATH}...")
    fieldnames = list(rows[0].keys()) if rows else []
    zb_fields = ["ZB_STATUS", "ZB_SUB_STATUS", "ZB_CATCHALL", "ZB_FREE_EMAIL",
                  "ZB_MX_FOUND", "ZB_SMTP_PROVIDER",
                  "ZB_FIRSTNAME", "ZB_LASTNAME", "ZB_GENDER",
                  "ZB_COUNTRY", "ZB_REGION", "ZB_CITY", "ZB_ZIPCODE",
                  "ZB_DOMAIN_AGE_DAYS"]

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames + zb_fields)
        writer.writeheader()
        for row in rows:
            ein = row.get("EIN", "")
            zb = state["results"].get(ein, {})
            out = dict(row)
            out.update({
                "ZB_STATUS": zb.get("status", ""),
                "ZB_SUB_STATUS": zb.get("sub_status", ""),
                "ZB_CATCHALL": str(zb.get("catchall_domain", "")),
                "ZB_FREE_EMAIL": str(zb.get("free_email", "")),
                "ZB_MX_FOUND": str(zb.get("mx_found", "")),
                "ZB_SMTP_PROVIDER": zb.get("smtp_provider", ""),
                "ZB_FIRSTNAME": zb.get("firstname", ""),
                "ZB_LASTNAME": zb.get("lastname", ""),
                "ZB_GENDER": zb.get("gender", ""),
                "ZB_COUNTRY": zb.get("country", ""),
                "ZB_REGION": zb.get("region", ""),
                "ZB_CITY": zb.get("city", ""),
                "ZB_ZIPCODE": zb.get("zipcode", ""),
                "ZB_DOMAIN_AGE_DAYS": zb.get("domain_age_days", ""),
            })
            writer.writerow(out)

    print(f"✅ Output written to {OUTPUT_PATH}")
    print(f"   Records: {len(rows)}, Verified: {credits_used}")

    # Summary
    valid = sum(1 for v in state["results"].values() if v.get("status") == "valid")
    catchall = sum(1 for v in state["results"].values() if v.get("status") == "catch-all")
    invalid = sum(1 for v in state["results"].values() if v.get("status") in ("invalid", "do_not_mail"))
    no_email = sum(1 for v in state["results"].values() if v.get("status") == "no_email")
    errors = sum(1 for v in state["results"].values() if v.get("status") == "error")

    printable_valid = f"{valid:,}"
    printable_catchall = f"{catchall:,}"
    print(f"\n📊 Final Summary:")
    print(f"   ✅ Valid:       {printable_valid}")
    print(f"   📬 Catch-all:   {printable_catchall}")
    print(f"   ❌ Invalid:     {invalid}")
    print(f"   📭 No email:    {no_email}")
    print(f"   ⚠️  Errors:     {errors}")


if __name__ == "__main__":
    main()
