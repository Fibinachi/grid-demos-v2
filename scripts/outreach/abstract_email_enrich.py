#!/usr/bin/env python3
"""
Abstract Email Reputation API Enrichment
========================================
Uses Abstract API's Email Reputation API to validate and enrich
foundation email addresses with deliverability, quality, risk,
domain, and breach data.

Usage:
  python abstract_email_enrich.py                         # Full run
  python abstract_email_enrich.py --quick 50              # Test first 50
  python abstract_email_enrich.py --resume                # Resume from checkpoint
  python abstract_email_enrich.py --status                # Show results summary
  python abstract_email_enrich.py --credits               # Check remaining credits

Endpoint: https://emailreputation.abstractapi.com/v1
Set env var:  ABSTRACT_API_KEY
"""

import os, sys, csv, json, time, urllib.request, urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "enriched_contacts_abstract.csv")
STATE_FILE = os.path.join(SCRIPT_DIR, "abstract_enrich_state.json")
API_KEY = os.environ.get("ABSTRACT_API_KEY", "")
API_URL = "https://emailreputation.abstractapi.com/v1"

RATE_LIMIT = 1  # 1 req/sec on free tier (adjust for paid plans)


def check_credits():
    """Quick test to see if the key works (Abstract doesn't expose a credit endpoint)."""
    if not API_KEY:
        print("❌ ABSTRACT_API_KEY not set")
        return 0
    url = f"{API_URL}?api_key={API_KEY}&email=test@test.com"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read())
            return 1  # key works
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if "too_many_requests" in body:
            return -1  # rate limited but key works
        print(f"❌ API error: {body[:200]}")
        return 0
    except Exception as e:
        print(f"❌ Failed: {e}")
        return 0


def verify_email(email):
    """Call Abstract Email Reputation API for a single email."""
    if not email or "@" not in email:
        return {"error": "no_email"}
    params = urllib.parse.urlencode({"api_key": API_KEY, "email": email})
    url = f"{API_URL}?{params}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 2 ** attempt
                print(f"  ⏳ Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            body = e.read().decode()[:200]
            return {"error": f"HTTP {e.code}", "detail": body}
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return {"error": str(e)[:100]}
    return {"error": "max_retries"}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"processed": {}, "results": {}}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def flatten_result(data):
    """Flatten the nested API response into a flat dict."""
    dd = data.get("email_deliverability", {})
    sender = data.get("email_sender", {})
    dom = data.get("email_domain", {})
    quality = data.get("email_quality", {})
    risk = data.get("email_risk", {})
    breaches = data.get("email_breaches", {})
    return {
        "AB_DELIVERABILITY": dd.get("status", ""),
        "AB_DETAIL": dd.get("status_detail", ""),
        "AB_SMTP_VALID": str(dd.get("is_smtp_valid", "")),
        "AB_MX_VALID": str(dd.get("is_mx_valid", "")),
        "AB_FIRSTNAME": sender.get("first_name", ""),
        "AB_LASTNAME": sender.get("last_name", ""),
        "AB_ORG_TYPE": sender.get("organization_type", ""),
        "AB_EMAIL_PROVIDER": sender.get("email_provider_name", ""),
        "AB_DOMAIN": dom.get("domain", ""),
        "AB_DOMAIN_AGE": dom.get("domain_age", ""),
        "AB_REGISTRAR": dom.get("registrar", ""),
        "AB_DATE_REGISTERED": dom.get("date_registered", ""),
        "AB_DATE_EXPIRES": dom.get("date_expires", ""),
        "AB_QUALITY_SCORE": quality.get("score", ""),
        "AB_FREE_EMAIL": str(quality.get("is_free_email", "")),
        "AB_CATCHALL": str(quality.get("is_catchall", "")),
        "AB_ROLE_BASED": str(quality.get("is_role", "")),
        "AB_DISPOSABLE": str(quality.get("is_disposable", "")),
        "AB_RISK_ADDRESS": risk.get("address_risk_status", ""),
        "AB_RISK_DOMAIN": risk.get("domain_risk_status", ""),
        "AB_BREACHES": breaches.get("total_breaches", ""),
    }


def load_csv(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    if "--credits" in sys.argv:
        c = check_credits()
        print(f"{'✅ Key works' if c == 1 else '⏳ Rate limited (key works)' if c == -1 else '❌ Key invalid'}")
        return

    if "--status" in sys.argv:
        state = load_state()
        total = len(state.get("results", {}))
        results = state.get("results", {}).values()
        deliverable = sum(1 for r in results if r.get("AB_DELIVERABILITY") == "deliverable")
        undeliverable = sum(1 for r in results if r.get("AB_DELIVERABILITY") == "undeliverable")
        risky = sum(1 for r in results if r.get("AB_RISK_ADDRESS") == "high")
        catchall = sum(1 for r in results if r.get("AB_CATCHALL") == "True")
        role = sum(1 for r in results if r.get("AB_ROLE_BASED") == "True")
        errors = sum(1 for r in results if r.get("error"))
        print(f"📊 Abstract Email Reputation results:")
        print(f"   Total processed: {total}")
        print(f"   ✅ Deliverable:  {deliverable}")
        print(f"   ❌ Undeliverable: {undeliverable}")
        print(f"   📬 Catch-all:    {catchall}")
        print(f"   👤 Role-based:   {role}")
        print(f"   ⚠️  High risk:   {risky}")
        print(f"   ❓ Errors:       {errors}")
        return

    quick = None
    resume = False
    for arg in sys.argv[1:]:
        if "--quick" in arg:
            quick = int(arg.split("=")[-1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1])
        elif arg == "--resume":
            resume = True

    if not API_KEY:
        print("❌ ABSTRACT_API_KEY environment variable not set.")
        sys.exit(1)

    check_credits()
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
            state["results"][ein] = {"error": "no_email", "AB_DELIVERABILITY": ""}
            state["processed"][ein] = True
            continue

        if i > start_from:
            time.sleep(1.0 / RATE_LIMIT)

        print(f"  [{i+1}/{len(rows)}] {email}", end="")

        result = verify_email(email)
        if "error" in result and result["error"] not in ("no_email",):
            state["results"][ein] = {"error": result.get("error", "unknown"), "AB_DELIVERABILITY": ""}
        else:
            state["results"][ein] = flatten_result(result)

        state["processed"][ein] = True

        status = state["results"][ein].get("AB_DELIVERABILITY", "error")
        icon = {"deliverable": "✅", "undeliverable": "❌", "unknown": "❓", "risky": "⚠️"}.get(status, "❓")
        print(f" {icon} {status}")

        if (i + 1) % 50 == 0:
            save_state(state)
            print(f"  💾 Checkpoint saved at row {i+1}")

    save_state(state)
    print(f"\n💾 State saved. Processed {len(state['processed'])} records.")

    # Generate output CSV
    print(f"\n📊 Generating {OUTPUT_PATH}...")
    fieldnames = list(rows[0].keys()) if rows else []
    ab_fields = [
        "AB_DELIVERABILITY", "AB_DETAIL", "AB_SMTP_VALID", "AB_MX_VALID",
        "AB_FIRSTNAME", "AB_LASTNAME", "AB_ORG_TYPE", "AB_EMAIL_PROVIDER",
        "AB_DOMAIN", "AB_DOMAIN_AGE", "AB_REGISTRAR",
        "AB_DATE_REGISTERED", "AB_DATE_EXPIRES",
        "AB_QUALITY_SCORE", "AB_FREE_EMAIL", "AB_CATCHALL",
        "AB_ROLE_BASED", "AB_DISPOSABLE",
        "AB_RISK_ADDRESS", "AB_RISK_DOMAIN", "AB_BREACHES",
    ]

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames + ab_fields)
        writer.writeheader()
        for row in rows:
            ein = row.get("EIN", "")
            ab = state["results"].get(ein, {})
            out = dict(row)
            for k in ab_fields:
                out[k] = ab.get(k, "")
            writer.writerow(out)

    print(f"✅ Output: {OUTPUT_PATH} ({len(rows)} records)")

    # Summary
    results = state["results"].values()
    deliverable = sum(1 for r in results if r.get("AB_DELIVERABILITY") == "deliverable")
    undeliverable = sum(1 for r in results if r.get("AB_DELIVERABILITY") == "undeliverable")
    unknown = sum(1 for r in results if r.get("AB_DELIVERABILITY") == "unknown")
    errors = sum(1 for r in results if r.get("error"))
    print(f"\n📊 Summary:")
    print(f"   ✅ Deliverable:   {deliverable:,}")
    print(f"   ❌ Undeliverable: {undeliverable:,}")
    print(f"   ❓ Unknown:       {unknown:,}")
    print(f"   ⚠️  Errors:       {errors:,}")


if __name__ == "__main__":
    main()
