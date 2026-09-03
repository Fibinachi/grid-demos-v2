#!/usr/bin/env python3
"""
Email Pattern Guesser
=====================
For foundation domains with valid MX records, generates and tests
common email patterns to find real human contacts.

Patterns tested per domain:
  - {lastname}@domain.com          (e.g., smith@foundation.org)
  - {first_initial}{lastname}@     (e.g., jsmith@)
  - {firstname}.{lastname}@        (e.g., john.smith@)
  - {firstname}@{lastname}@        (e.g., john@)
  - contact@, office@, admin@

Name is extracted from the foundation name:
  "Smith Family Foundation" → "smith"
  "John & Mary Jones Foundation" → "jones"
  "THE SMITH FOUNDATION" → "smith"

Usage:
  python guess_emails.py                         # Full run (17K foundations)
  python guess_emails.py --quick 100             # Test first 100
  python guess_emails.py --resume                # Resume from checkpoint
  python guess_emails.py --status                # Show results
  python guess_emails.py --apply                 # Merge found emails into send_list_clean.csv
"""

import csv, os, sys, json, time, re, socket, threading
from datetime import datetime
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLEAN_CSV = os.path.join(SCRIPT_DIR, "send_list_clean.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "send_list_enriched.csv")
STATE_FILE = os.path.join(SCRIPT_DIR, "guess_emails_state.json")
FOUND_CSV = os.path.join(SCRIPT_DIR, "guessed_contacts.csv")

AWS_REGION = "us-east-1"

# ── Name extraction ──

# Words to strip from foundation names when extracting the key name
STOP_WORDS = {
    "THE", "AND", "&", "FOUNDATION", "INC", "CORP", "CORPORATION",
    "FAMILY", "MEMORIAL", "TRUST", "FUND", "ENDOWMENT",
    "FOR", "OF", "IN", "TO", "A", "AN",
    "PRIVATE", "CHARITABLE", "PHILANTHROPIC",
    "SR", "JR", "III", "II", "IV",
    "COMPANY", "ENTERPRISES", "LLC", "PA",
}

# Words that are too generic to be a person's name
GENERIC_WORDS = {
    "COMMUNITY", "SCHOLARSHIP", "EDUCATION", "EDUCATIONAL",
    "LEGACY", "HERITAGE", "FUTURE", "CHILDREN", "FAMILIES",
    "AMERICAN", "NATIONAL", "INTERNATIONAL", "GLOBAL",
    "SCIENCE", "ARTS", "CULTURE", "HEALTH", "HUMANITIES",
    "OPPORTUNITY", "IMPACT", "ACTION", "ALLIANCE", "NETWORK",
    "METHODIST", "BAPTIST", "CATHOLIC", "PRESBYTERIAN", "LUTHERAN",
    "EPISCOPAL", "UNITED", "CHRISTIAN", "JEWISH", "ISLAMIC",
    "METHODIST", "ANGLICAN", "REFORMED",
    "SOUTH", "NORTH", "EAST", "WEST", "SOUTHERN", "NORTHERN",
    "PROMOTE", "ADVANCE", "SUPPORT", "DEVELOPMENT",
    "INSTITUTE", "CENTER", "CENTRE", "PROGRAM",
}

# Common first initials and names (to avoid treating as surname)
COMMON_GIVEN = {
    "JOHN", "JAMES", "ROBERT", "WILLIAM", "CHARLES", "DAVID",
    "RICHARD", "JOSEPH", "THOMAS", "HENRY", "GEORGE", "EDWARD",
    "SAMUEL", "FRANK", "ALBERT", "WALTER", "HARRY", "ARTHUR",
    "FRED", "LOUIS", "HERBERT", "PAUL", "PHILIP", "CARL",
    "HOWARD", "ROY", "RALPH", "CLARENCE", "ANDREW", "RAYMOND",
    "MARY", "HELEN", "MARGARET", "RUTH", "ELIZABETH", "ANNA",
    "MARIE", "JANE", "ANN", "FRANCIS", "ALICE", "DOROTHY",
    "VIRGINIA", "MARTHA", "MILDRED", "FRANCES", "KATHARINE",
    "JOSEPHINE", "ELEANOR", "LILLIAN", "FLORENCE", "ETHEL",
    "PETER", "STEPHEN", "MICHAEL", "DONALD", "KENNETH",
    "DANIEL", "MARK", "BRIAN", "KEVIN", "GARY", "STEVEN",
    "LARRY", "SCOTT", "ERIC", "JEFFREY", "CHRISTOPHER",
    "GENE", "ALAN", "HUGH", "LEWIS", "JACK", "NORMAN",
    "HAROLD", "LEONARD", "LAWRENCE", "ROGER", "WAYNE",
    "RUSSELL", "BRUCE", "GERALD", "JEROME", "MARVIN",
    "JAY", "LEE", "GLENN", "CRAIG", "BRUCE", "TODD",
    "WARREN", "STEVE", "GORDON", "MELVIN", "ALFRED",
    "BENJAMIN", "NATHAN", "AARON", "ADAM", "JASON",
    "SEAN", "RYAN", "BRANDON", "JUSTIN", "TYLER",
    "CAROL", "SUSAN", "KAREN", "NANCY", "LINDA",
    "BARBARA", "LISA", "SANDRA", "BETTY", "SHARON",
    "CATHERINE", "CHRISTINE", "JANET", "THERESA",
    "DEBORAH", "PATRICIA", "CYNTHIA", "LORRAINE",
    "DONNA", "DIANE", "JOYCE", "JANICE", "JUDITH",
}

MOUNTH_NAMES = {
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
    "JAN", "FEB", "MAR", "APR", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
}


def extract_name(foundation_name):
    """
    Extract the most likely surname/person name from a foundation name.
    
    "CHARLES AND MARGERY BARANCIK FOUNDATION" → "barancik"
    "THE RICHARD H DRIEHAUS FOUNDATION" → "driehaus"
    "SCHULTZ FAMILY FOUNDATION" → "schultz"
    "MARION AND HENRY BLOCH FAMILY FOUNDATION" → "bloch"
    "FOUNDATION TO PROMOTE OPEN SOCIETY" → None (no identifiable name)
    """
    if not foundation_name:
        return None
    
    name = foundation_name.strip().upper()
    
    # Split into words
    words = re.findall(r"[A-Z]+(?:'S)?|[A-Z]\.", name)
    
    # Filter out stop words, generic words, given names, months
    candidates = []
    for w in words:
        w_clean = w.replace("'S", "").rstrip(".")
        if w_clean in STOP_WORDS or w_clean in GENERIC_WORDS or w_clean in MOUNTH_NAMES:
            continue
        if w_clean in COMMON_GIVEN:
            continue
        if len(w_clean) < 2:
            continue
        candidates.append(w_clean)
    
    if not candidates:
        # Try harder - take the last word that isn't a stop word
        all_words = name.split()
        filtered = [w for w in all_words if w not in STOP_WORDS and not w.startswith("FOUNDATION")]
        if filtered:
            candidates = [filtered[-1]]
    
    if not candidates:
        return None
    
    # Take the LAST candidate (usually the surname comes last in foundation names)
    # e.g., "CHARLES AND MARGERY BARANCIK" → "BARANCIK"
    surname = candidates[-1]
    
    # Clean up
    surname = surname.lower().replace("'S", "s")
    
    # Skip if it looks like a single letter
    if len(surname) <= 1:
        return None
    
    return surname


# ── DNS MX Check ──

_dns_cache = {}
_dns_lock = threading.Lock()

try:
    import dns.resolver
    _resolver = dns.resolver.Resolver()
    _resolver.nameservers = ["8.8.8.8", "8.8.4.4"]
    _resolver.timeout = 3.0
    _resolver.lifetime = 3.0
    HAVE_DNS = True
except ImportError:
    HAVE_DNS = False


def has_mx(domain):
    """Check if domain has MX records (with caching)."""
    cache_key = f"mx:{domain}"
    with _dns_lock:
        if cache_key in _dns_cache:
            return _dns_cache[cache_key]
    if not HAVE_DNS:
        with _dns_lock:
            _dns_cache[cache_key] = False
        return False
    try:
        answers = _resolver.resolve(domain, "MX")
        has = len(answers) > 0
        with _dns_lock:
            _dns_cache[cache_key] = has
        return has
    except:
        # Try A record fallback
        try:
            _resolver.resolve(domain, "A")
            with _dns_lock:
                _dns_cache[cache_key] = True
            return True
        except:
            with _dns_lock:
                _dns_cache[cache_key] = False
            return False


# ── SES Email Validation ──

try:
    import boto3
    from botocore.exceptions import ClientError
    HAVE_SES = True
except ImportError:
    HAVE_SES = False


def validate_email_ses(client, email):
    """Validate a single email via SES GetEmailAddressInsights."""
    if not email or "@" not in email:
        return None
    try:
        resp = client.get_email_address_insights(EmailAddress=email)
        mv = resp.get("MailboxValidation", {})
        valid = mv.get("IsValid", {}).get("ConfidenceVerdict", "")
        mailbox = mv.get("Evaluations", {}).get("MailboxExists", {}).get("ConfidenceVerdict", "")
        return {
            "valid": valid,
            "mailbox": mailbox,
        }
    except ClientError as e:
        if e.response["Error"]["Code"] == "Throttling":
            return {"error": "throttled"}
        return {"error": e.response["Error"]["Code"]}
    except Exception as e:
        return {"error": str(e)[:60]}


# ── Email pattern generation ──

def generate_patterns(domain, surname):
    """Generate candidate email patterns for a given domain and surname."""
    if not domain or not surname:
        return []
    
    surname_lower = surname.lower()
    # Take first letter as initial
    first_initial = surname_lower[0]
    
    patterns = [
        (f"{surname_lower}@", f"lastname@{domain}"),
        (f"{first_initial}{surname_lower}@", f"f_lastname@{domain}"),
        (f"{surname_lower}.{surname_lower}@", f"first.last@{domain}"),
    ]
    
    # Add generic role-based patterns
    generic = ["contact@", "office@", "admin@", "manager@", "foundation@", "executivedirector@", "director@"]
    for g in generic:
        patterns.append((g, f"{g}{domain}"))
    
    return patterns


# ── Load / Save State ──

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "domains_checked": {},
        "found_emails": {},
        "patterns_tested": 0,
        "patterns_found": 0,
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_csv(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ── Main ──

def main():
    if "--status" in sys.argv:
        state = load_state()
        found = state.get("found_emails", {})
        domains_checked = state.get("domains_checked", {})
        mx_good = sum(1 for v in domains_checked.values() if v)
        mx_bad = sum(1 for v in domains_checked.values() if not v)
        print(f"📊 Email Pattern Guesser Status:")
        print(f"   Domains with MX:          {mx_good:,}")
        print(f"   Domains without MX:       {mx_bad:,}")
        print(f"   Patterns tested:          {state.get('patterns_tested', 0):,}")
        print(f"   Patterns found:           {state.get('patterns_found', 0):,}")
        print(f"   Unique EINs with new email: {len(found):,}")
        
        if found:
            print(f"\n📋 Sample found emails:")
            count = 0
            for ein, data in sorted(found.items(), key=lambda x: x[1].get("pattern", ""))[:15]:
                print(f"   {data.get('email',''):45s} (pattern: {data.get('pattern','')}) [{data.get('foundation','')[:35]}]")
                count += 1
        return

    quick = None
    resume = False
    apply_mode = False
    for arg in sys.argv[1:]:
        if arg == "--apply":
            apply_mode = True
        elif arg == "--resume":
            resume = True
        elif arg.startswith("--quick"):
            quick = int(arg.split("=")[-1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1])

    if apply_mode:
        apply_found_emails()
        return

    if not HAVE_DNS:
        print("❌ dnspython not installed. Run: pip install dnspython")
        sys.exit(1)

    if not HAVE_SES:
        print("❌ boto3 not installed. Run: pip install boto3")
        sys.exit(1)

    client = boto3.client("sesv2", region_name=AWS_REGION)
    rows = load_csv(CLEAN_CSV)
    print(f"📄 Loaded {len(rows):,} records from send_list_clean.csv")

    if quick:
        rows = rows[:quick]
        print(f"🔍 Quick mode: processing first {quick} records")

    state = load_state() if resume else {
        "domains_checked": {},
        "found_emails": {},
        "patterns_tested": 0,
        "patterns_found": 0,
    }
    start_from = 0
    if resume:
        start_from = len([e for e in rows if e["EIN"] in state.get("found_emails", {}) or
                          extract_name(e.get("NAME", "")) is None])
        if start_from > 0:
            print(f"📌 Resuming from approximately row {start_from}")

    # Phase 1: Collect unique domains and check MX
    print("\n🔎 Phase 1: Checking MX records for unique domains...")
    domain_rows = defaultdict(list)
    for row in rows:
        email = (row.get("EMAIL") or "").strip()
        if "@" in email:
            domain = email.split("@")[1].lower()
            domain_rows[domain].append(row)

    # Check which domains we already know about
    domains_to_check = [d for d in domain_rows if d not in state["domains_checked"]]
    print(f"   Unique domains: {len(domain_rows):,} ({len(domains_to_check):,} to check)")

    for i, domain in enumerate(domains_to_check):
        result = has_mx(domain)
        state["domains_checked"][domain] = result
        if (i + 1) % 500 == 0:
            print(f"   MX check: {i+1}/{len(domains_to_check)}...", end="\r")
            sys.stdout.flush()
            save_state(state)

    save_state(state)

    mx_good = sum(1 for v in state["domains_checked"].values() if v)
    mx_bad = sum(1 for v in state["domains_checked"].values() if not v)
    print(f"\n   Domains with MX: {mx_good:,}  Without MX: {mx_bad:,}")

    # Phase 2: Generate and test email patterns for domains with MX
    print(f"\n🔎 Phase 2: Testing email patterns...")
    
    domains_with_mx = {d for d, v in state["domains_checked"].items() if v}
    pattern_count = 0
    found_count = 0

    for domain in sorted(domains_with_mx):
        batch = domain_rows[domain]
        
        # Get the first foundation name to extract surname
        foundation_name = batch[0].get("NAME", "")
        surname = extract_name(foundation_name)
        
        if not surname:
            continue
        
        # Generate patterns
        local_parts, full_patterns = zip(*generate_patterns(domain, surname))
        
        for local_part, full_email in zip(local_parts, full_patterns):
            if not full_email:
                continue
            
            # Skip if we already know this pattern works for this domain
            cache_key = f"{domain}:{local_part}"
            if cache_key in state.get("pattern_cache", {}):
                if state["pattern_cache"][cache_key]:
                    # Already known good
                    pass
                else:
                    continue
            
            pattern_count += 1
            
            # Validate
            result = validate_email_ses(client, full_email)
            
            # Handle throttling
            retries = 0
            while result and result.get("error") == "throttled" and retries < 3:
                time.sleep(2 ** retries)
                result = validate_email_ses(client, full_email)
                retries += 1
            
            if not result or result.get("error"):
                continue
            
            # Check if valid or medium confidence
            is_valid = result.get("valid") in ("HIGH", "MEDIUM")
            
            if "pattern_cache" not in state:
                state["pattern_cache"] = {}
            state["pattern_cache"][cache_key] = is_valid
            
            if is_valid:
                # Found a working pattern! Apply to all foundations with this domain
                for row in batch:
                    ein = row["EIN"]
                    if ein not in state["found_emails"]:
                        new_email = f"{local_part}{domain}"
                        state["found_emails"][ein] = {
                            "email": new_email,
                            "pattern": local_part.rstrip("@"),
                            "domain": domain,
                            "foundation": row.get("NAME", "")[:60],
                            "original_email": row.get("EMAIL", ""),
                        }
                        found_count += 1
            
            # Rate limit: 10 req/sec for SES
            time.sleep(0.1)
        
        if (pattern_count + found_count) % 100 == 0:
            print(f"   Tested: {pattern_count:,} patterns | Found: {found_count:,} emails", end="\r")
            sys.stdout.flush()
            save_state(state)

    state["patterns_tested"] = pattern_count
    state["patterns_found"] = found_count
    save_state(state)

    print(f"\n\n📊 Results:")
    print(f"   Patterns tested: {pattern_count:,}")
    print(f"   Emails found:    {found_count:,}")
    print(f"   Unique EINs:     {len(state['found_emails']):,}")

    # Write found contacts CSV
    if state["found_emails"]:
        with open(FOUND_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["EIN", "FOUNDATION", "ORIGINAL_EMAIL", "NEW_EMAIL", "PATTERN", "DOMAIN"])
            writer.writeheader()
            for ein, data in sorted(state["found_emails"].items()):
                writer.writerow({
                    "EIN": ein,
                    "FOUNDATION": data.get("foundation", ""),
                    "ORIGINAL_EMAIL": data.get("original_email", ""),
                    "NEW_EMAIL": data.get("email", ""),
                    "PATTERN": data.get("pattern", ""),
                    "DOMAIN": data.get("domain", ""),
                })
        print(f"\n✅ Found contacts saved: {FOUND_CSV}")
        print(f"\n💡 Next: python guess_emails.py --apply")
        print(f"   (Merges found emails into send_list_enriched.csv)")


def apply_found_emails():
    """Merge found emails into a new enriched send list."""
    state = load_state()
    found = state.get("found_emails", {})
    
    if not found:
        print("❌ No found emails to apply. Run guess_emails.py first.")
        return
    
    print(f"📄 Merging {len(found):,} found emails into send list...")
    
    rows = load_csv(CLEAN_CSV)
    updated = 0
    skipped_because_better = 0
    
    for row in rows:
        ein = row["EIN"]
        if ein in found:
            new_email = found[ein]["email"]
            current_email = (row.get("EMAIL") or "").strip().lower()
            pattern = found[ein]["pattern"]
            
            # Only update if the new email is better than the current one
            # Better = not an info@/contact@ etc. role address
            current_is_role = any(
                current_email.startswith(p) for p in ["info@", "contact@", "hello@", 
                                                       "admin@", "mail@", "office@",
                                                       "webmaster@", "support@"]
            )
            
            new_is_role = any(
                new_email.startswith(p) for p in ["contact@", "office@", "admin@",
                                                    "manager@", "foundation@",
                                                    "executivedirector@", "director@"]
            )
            
            if current_is_role and not new_is_role:
                # New email is better (personal name vs role-based)
                row["ORIGINAL_EMAIL"] = current_email
                row["EMAIL"] = new_email
                row["EMAIL_SOURCE"] = f"guessed_{pattern}"
                updated += 1
            elif current_is_role and new_is_role:
                # Both role-based - keep the more specific one
                # (contact@ is better than info@ typically)
                if current_email.startswith("info@") and not new_email.startswith("info@"):
                    row["ORIGINAL_EMAIL"] = current_email
                    row["EMAIL"] = new_email
                    row["EMAIL_SOURCE"] = f"guessed_{pattern}"
                    updated += 1
                else:
                    skipped_because_better += 1
            else:
                # Current is already a personal email - keep it
                skipped_because_better += 1
    
    # Write output
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else []
        # Add EMAIL_SOURCE if not present
        all_fields = fieldnames
        if "EMAIL_SOURCE" not in all_fields:
            all_fields = fieldnames + ["EMAIL_SOURCE"]
            if "ORIGINAL_EMAIL" not in all_fields:
                all_fields = all_fields + ["ORIGINAL_EMAIL"]
        writer = csv.DictWriter(f, fieldnames=all_fields)
        writer.writeheader()
        for row in rows:
            if "EMAIL_SOURCE" not in row:
                row["EMAIL_SOURCE"] = "original"
            if "ORIGINAL_EMAIL" not in row:
                row["ORIGINAL_EMAIL"] = ""
            writer.writerow(row)
    
    print(f"\n✅ Merged into: {OUTPUT_CSV}")
    print(f"   Updated:     {updated:,} records with better emails")
    print(f"   Skipped:     {skipped_because_better:,} (existing email was better or equal)")
    print(f"   Total:       {len(rows):,}")
    print(f"\n💡 Next: python ses_foundation_sender.py --clean-list")
    print(f"   (ses_foundation_sender already reads send_list_enriched.csv if present)")


if __name__ == "__main__":
    main()
