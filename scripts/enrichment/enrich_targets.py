"""Enrich targets with IPQS email validation + PDL company data."""
import os, json, csv, sys, re, time, urllib.request

IPQS_KEY = os.environ.get("IPQS_KEY", "")
PDL_KEY = os.environ.get("PDL_KEY", "")

if not IPQS_KEY:
    print("ERROR: IPQS_KEY not set"); sys.exit(1)

RESULTS_FILE = "enriched_targets.csv"

def check_ipqs(email):
    url = "https://www.ipqualityscore.com/api/json/email/" + IPQS_KEY + "/" + email
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)[:60]}

def enrich_pdl(company_name):
    if not PDL_KEY or not company_name:
        return {}
    url = "https://api.peopledatalabs.com/v5/company/enrich?api_key=" + PDL_KEY + "&name=" + company_name
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            d = json.loads(r.read())
            return d if d.get("status") == 200 else {}
    except:
        return {}

def extract_company(email):
    domain = email.split("@")[1] if "@" in email else ""
    name = re.sub(r'\.(org|com|net|edu|gov|io|us)$', '', domain)
    name = name.split(".")[0] if "." in name else name
    return name.title(), domain

def main():
    emails = []
    if os.path.exists("failed_targets.txt"):
        with open("failed_targets.txt") as f:
            emails = [line.strip() for line in f if line.strip() and "@" in line]

    if not emails:
        for fname in ["send_mensa_batch.py", "send_autism_parent_batch.py",
                       "send_film_industry_batch.py", "send_arts_nonprofit_batch.py"]:
            if os.path.exists(fname):
                with open(fname) as f:
                    c = f.read()
                    found = re.findall(r'\(["\']([\w.@+-]+)["\']', c)
                    emails.extend([e for e in found if "@" in e])
        emails = list(set(emails))

    test_limit = min(100, len(emails))
    emails = emails[:test_limit]

    print("Enriching %d targets..." % test_limit)
    print("IPQS: %s  PDL: %s" % ("OK" if IPQS_KEY else "NO", "OK" if PDL_KEY else "NO"))
    print()

    results = []
    valid_count = 0

    for i, email in enumerate(emails, 1):
        company_name, domain = extract_company(email)
        print("[%d/%d] %s" % (i, len(emails), email), end="")

        ipqs = check_ipqs(email)
        is_valid = ipqs.get("valid", False)
        is_generic = ipqs.get("generic", True)
        score = ipqs.get("fraud_score", 0)
        is_risky = ipqs.get("risky", False)

        status = "V" if is_valid else ("G" if is_generic else "?")
        print(" IPQS:%s score=%d" % (status, score), end="")

        if is_valid:
            valid_count += 1

        pdl = {}
        if PDL_KEY and (i % 10 == 1 or (is_valid and not is_generic)):
            pdl = enrich_pdl(company_name)
            pname = (pdl.get("name") or "")[:20]
            if pname:
                print(" PDL:%s" % pname, end="")
            time.sleep(0.5)

        print()

        results.append({
            "email": email,
            "domain": domain,
            "valid": is_valid,
            "fraud_score": score,
            "generic": is_generic,
            "risky": is_risky,
            "org_name": pdl.get("name", ""),
            "industry": pdl.get("industry", ""),
            "org_size": pdl.get("employee_count", ""),
            "description": (pdl.get("description") or "")[:80],
        })

    if results:
        with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)

    non_generic = sum(1 for r in results if r.get("valid") and not r.get("generic"))
    print()
    print("Done! %d targets enriched" % len(results))
    print("  Valid:        %d/%d (%d%%)" % (valid_count, len(results), valid_count*100//len(results)))
    print("  Non-generic:  %d (real person emails)" % non_generic)
    print("  Saved to:     %s" % RESULTS_FILE)

    if non_generic > 0:
        with open("person_emails.txt", "w") as f:
            for r in results:
                if r.get("valid") and not r.get("generic"):
                    f.write(r["email"] + "\n")
        print("  Person emails saved to: person_emails.txt")

if __name__ == "__main__":
    main()
