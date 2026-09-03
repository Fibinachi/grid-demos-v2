#!/usr/bin/env python3
"""
Foundation Enrichment Pipeline
===============================
Multi-source enrichment for foundations missing contact info.
Runs in stages, each feeding into the next:

Stage 0: AI Lookup      — Gemini API (free, most capable) → Knowledge Graph API (fallback)
Stage 1: Website Scrape — Guess domains, fetch homepages, extract mailto:/emails
Stage 2: RDAP/WHOIS     — Query domain registration for admin/tech emails
Stage 3: IRS XML         — Extract officer/trustee names from 990-PF filings
Stage 4: Name Patterns   — Generate email patterns from extracted names, validate via SES

API keys needed:
  GOOGLE_GEMINI_API_KEY  — Free from https://aistudio.google.com/apikey (recommended)
  GOOGLE_KG_API_KEY      — From GCP (fallback if Gemini unavailable)

Usage:
  python enrich_foundations.py                          # Full pipeline
  python enrich_foundations.py --stage 1                # Run stage 1 only
  python enrich_foundations.py --quick 50               # Test first 50 missing
  python enrich_foundations.py --status                 # Show enrichment stats
  python enrich_foundations.py --apply                  # Merge findings into send list
"""

import csv, os, sys, json, time, re, urllib.request, urllib.parse, socket, threading
from datetime import datetime
from collections import defaultdict
from email.utils import parseaddr

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENRICHED_CSV = os.path.join(SCRIPT_DIR, "enriched_contacts.csv")
CLEAN_CSV = os.path.join(SCRIPT_DIR, "send_list_clean.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "send_list_enriched.csv")
STATE_FILE = os.path.join(SCRIPT_DIR, "enrich_foundations_state.json")
FOUND_FILE = os.path.join(SCRIPT_DIR, "enrich_foundings.csv")

# ── Config ──
AWS_REGION = "us-east-1"
MAX_WORKERS_HTTP = 20
MAX_WORKERS_DNS = 50

# ── Gemini API (Google AI Studio — free tier) ──
GEMINI_API_KEY = os.environ.get("GOOGLE_GEMINI_API_KEY", "")
GEMINI_ENABLED = bool(GEMINI_API_KEY)
GEMINI_MODEL = "models/gemini-2.0-flash"  # Generous free tier

try:
    from google import genai
    HAVE_GENAI = True
except ImportError:
    HAVE_GENAI = False

# ── Knowledge Graph API ──
KG_API_KEY = os.environ.get("GOOGLE_KG_API_KEY", "")
KG_API_URL = "https://kgsearch.googleapis.com/v1/entities:search"
KG_ENABLED = bool(KG_API_KEY)

# ── Gemini API Lookup ──

GEMINI_SYSTEM_PROMPT = """You are a foundation research assistant. Given a foundation name, return:
1. Its official website URL (if you know it)
2. Likely contact email patterns (e.g., info@, grants@, foundation@)
3. Any program officer names you know

Respond ONLY with valid JSON in this exact format:
{"domain": "example.org", "url": "https://example.org", "emails": ["info@example.org"], "officers": []}

If you don't know the foundation, return {"domain": null, "url": null, "emails": [], "officers": []}
Do NOT include any text outside the JSON."""


def gemini_lookup(foundation_name):
    """
    Query Gemini API for foundation website and contact info.
    Returns dict with domain, url, emails, officers or None.
    Free tier: 60 req/min for gemini-2.0-flash.
    """
    if not GEMINI_ENABLED or not HAVE_GENAI or not foundation_name:
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"Foundation name: {foundation_name}",
            config=genai.types.GenerateContentConfig(
                system_instruction=GEMINI_SYSTEM_PROMPT,
                temperature=0.1,
                max_output_tokens=256,
            ),
        )
        text = resp.text.strip()
        # Strip markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("\n", 1)[0]
            if text.endswith("```"):
                text = text[:-3]
        result = json.loads(text)
        if result.get("domain"):
            return result
        return None
    except Exception:
        return None


# ── Knowledge Graph API Lookup ──

def kg_search_lookup(foundation_name):
    """
    Query Google Knowledge Graph API for a foundation name.
    Returns the best-guess official website URL + entity info, or None.
    """
    if not KG_ENABLED or not foundation_name:
        return None

    params = urllib.parse.urlencode({
        "query": foundation_name,
        "key": KG_API_KEY,
        "limit": 3,
        "types": "Organization",
    })
    url = f"{KG_API_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "grantwizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return None

    results = data.get("itemListElement", [])
    if not results:
        return None

    # Score threshold — skip very low-confidence matches
    best = results[0]
    score = best.get("resultScore", 0)
    if score < 10:
        return None

    result = best.get("result", {})
    name = result.get("name", "")
    url = result.get("url", "")
    desc = result.get("description", "")
    detailed = result.get("detailedDescription", {})
    kg_id = result.get("@id", "")

    if not url:
        return None

    # Clean URL: strip protocol, get domain
    domain = url.replace("https://", "").replace("http://", "").split("/")[0].lower()
    if not domain:
        return None

    return {
        "domain": domain,
        "canonical_url": url,
        "name": name,
        "description": desc,
        "detailed_description": detailed.get("articleBody", ""),
        "kg_id": kg_id,
        "score": score,
    }


def kg_supported_domain(domain):
    """Check if a domain from KG has DNS records."""
    if not domain:
        return False
    # Quick check via DNS
    return domain_exists(domain)


# ── Stop words for name extraction ──
STOP_WORDS = {
    "THE", "AND", "&", "FOUNDATION", "INC", "CORP", "CORPORATION",
    "FAMILY", "MEMORIAL", "TRUST", "FUND", "ENDOWMENT",
    "FOR", "OF", "IN", "TO", "A", "AN",
    "PRIVATE", "CHARITABLE", "PHILANTHROPIC",
    "SR", "JR", "III", "II", "IV",
    "COMPANY", "ENTERPRISES", "LLC", "PA", "LIMITED",
}

GENERIC_WORDS = {
    "COMMUNITY", "SCHOLARSHIP", "EDUCATION", "EDUCATIONAL",
    "LEGACY", "HERITAGE", "FUTURE", "CHILDREN", "FAMILIES",
    "AMERICAN", "NATIONAL", "INTERNATIONAL", "GLOBAL",
    "SCIENCE", "ARTS", "CULTURE", "HEALTH", "HUMANITIES",
    "OPPORTUNITY", "IMPACT", "ACTION", "ALLIANCE", "NETWORK",
    "SOUTH", "NORTH", "EAST", "WEST",
    "PROMOTE", "ADVANCE", "SUPPORT", "DEVELOPMENT",
    "INSTITUTE", "CENTER", "CENTRE", "PROGRAM",
}

COMMON_GIVEN = {
    "JOHN", "JAMES", "ROBERT", "WILLIAM", "CHARLES", "DAVID",
    "RICHARD", "JOSEPH", "THOMAS", "HENRY", "GEORGE", "EDWARD",
    "SAMUEL", "FRANK", "ALBERT", "WALTER", "HARRY", "ARTHUR",
    "FRED", "LOUIS", "PAUL", "PHILIP", "CARL", "ANDREW",
    "MARY", "HELEN", "MARGARET", "RUTH", "ELIZABETH", "ANNA",
    "MARIE", "JANE", "ANN", "ALICE", "DOROTHY", "MARTHA",
    "PETER", "STEPHEN", "MICHAEL", "DONALD", "KENNETH",
    "DANIEL", "MARK", "BRIAN", "KEVIN", "GARY", "STEVEN",
    "BENJAMIN", "NATHAN", "AARON", "ADAM", "JASON",
}

# ── Helpers ──

def extract_surname(foundation_name):
    """Extract the most likely surname from a foundation name."""
    if not foundation_name:
        return None
    name = foundation_name.strip().upper()
    words = re.findall(r"[A-Z]+(?:'S)?|[A-Z]\.", name)
    candidates = [w.replace("'S", "").rstrip(".") for w in words
                  if w.replace("'S", "").rstrip(".") not in STOP_WORDS
                  and w.replace("'S", "").rstrip(".") not in GENERIC_WORDS
                  and w.replace("'S", "").rstrip(".") not in COMMON_GIVEN
                  and len(w.replace("'S", "").rstrip(".")) > 2]
    if not candidates:
        all_words = name.split()
        filtered = [w for w in all_words if w not in STOP_WORDS]
        if filtered:
            candidates = [filtered[-1]]
    if not candidates:
        return None
    return candidates[-1].lower().replace("'S", "s")


def guess_domains(name):
    """Generate domain candidates from a foundation name."""
    if not name:
        return []
    candidates = []
    upper = name.upper()
    words = upper.split()
    while words and words[-1] in STOP_WORDS:
        words = words[:-1]
    if not words:
        return []

    key_word = words[-1].lower().replace("'S", "s")
    for tld in [".org", ".com", ".net"]:
        candidates.append(f"{key_word}{tld}")
        if not key_word.endswith("foundation"):
            candidates.append(f"{key_word}foundation{tld}")

    # Full name slug
    name_words = [w.lower().replace("'S", "s") for w in words
                  if w not in STOP_WORDS and len(w) > 1]
    if name_words:
        slug = "-".join(name_words)
        candidates.append(f"{slug}.org")

    return list(dict.fromkeys(candidates))  # deduplicate preserving order


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
    cache_key = f"mx:{domain}"
    with _dns_lock:
        if cache_key in _dns_cache:
            return _dns_cache[cache_key]
    
    # Fast path: OS resolver
    try:
        socket.getaddrinfo(domain, 25, socket.AF_UNSPEC, socket.SOCK_STREAM)
        with _dns_lock:
            _dns_cache[cache_key] = True
        return True
    except (socket.gaierror, OSError):
        pass
    try:
        socket.getaddrinfo(domain, 80, socket.AF_UNSPEC, socket.SOCK_STREAM)
        with _dns_lock:
            _dns_cache[cache_key] = True
        return True
    except (socket.gaierror, OSError):
        pass
    
    if not HAVE_DNS:
        with _dns_lock:
            _dns_cache[cache_key] = False
        return False
    try:
        _resolver.resolve(domain, "MX", lifetime=2.0)
        with _dns_lock:
            _dns_cache[cache_key] = True
        return True
    except:
        try:
            _resolver.resolve(domain, "A", lifetime=2.0)
            with _dns_lock:
                _dns_cache[cache_key] = True
            return True
        except:
            with _dns_lock:
                _dns_cache[cache_key] = False
            return False


def domain_exists(domain):
    """Check if a domain has any DNS records.
    
    Uses OS resolver (fast) first, falls back to dnspython if needed.
    """
    cache_key = f"exists:{domain}"
    with _dns_lock:
        if cache_key in _dns_cache:
            return _dns_cache[cache_key]
    
    # Fast path: use OS resolver (Windows DNS cache, ~0.01s)
    try:
        socket.getaddrinfo(domain, 80, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_CANONNAME)
        with _dns_lock:
            _dns_cache[cache_key] = True
        return True
    except (socket.gaierror, OSError):
        pass
    try:
        socket.getaddrinfo(domain, 443, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_CANONNAME)
        with _dns_lock:
            _dns_cache[cache_key] = True
        return True
    except (socket.gaierror, OSError):
        pass
    
    # Slow path: dnspython (checks additional record types)
    if not HAVE_DNS:
        with _dns_lock:
            _dns_cache[cache_key] = False
        return False
    for qtype in ["MX", "AAAA", "NS"]:
        try:
            _resolver.resolve(domain, qtype, lifetime=2.0)
            with _dns_lock:
                _dns_cache[cache_key] = True
            return True
        except:
            continue
    with _dns_lock:
        _dns_cache[cache_key] = False
    return False


# ── Website Scraping ──

def fetch_page(url, timeout=10):
    """Fetch a webpage, return HTML or None."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except:
        return None


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def extract_emails_from_html(html, domain):
    """Extract emails from HTML, filtering out obvious garbage."""
    if not html:
        return set()
    emails = set()
    domain_lower = domain.lower().replace("www.", "")
    
    # mailto: links
    for m in re.finditer(r'href=["\']mailto:([^"\']+)["\']', html, re.IGNORECASE):
        email = m.group(1).strip().lower()
        email = email.split("?")[0]  # strip subject params
        if "@" in email:
            emails.add(email)
    
    # Plain text emails
    for m in EMAIL_RE.finditer(html):
        email = m.group(0).strip().lower()
        emails.add(email)
    
    # JSON-LD contactPoint
    jsonld_matches = re.finditer(
        r'"@type"\s*:\s*"ContactPoint"[^}]*"email"\s*:\s*"([^"]+)"',
        html, re.IGNORECASE
    )
    for m in jsonld_matches:
        emails.add(m.group(1).strip().lower())
    
    # Filter: remove obvious garbage
    clean = set()
    for e in emails:
        local, dom = e.split("@")
        # Skip image files, scripts, placeholder domains
        if any(x in e for x in [".png", ".jpg", ".gif", ".svg", ".css", ".js",
                                 "example.com", "domain.com", "yourdomain",
                                 "rspack@", "sentry@", "noreply@", "no-reply@",
                                 "wordpress@", "localhost"]):
            continue
        # Skip very long addresses
        if len(e) > 80:
            continue
        # Prefer emails on the same domain
        clean.add(e)
    
    return clean


SCRAPE_PAGES = ["", "contact", "about", "staff", "board", "grants",
                 "about-us", "contact-us", "team", "our-team",
                 "about/contact", "foundation", "who-we-are"]


def scrape_foundation_domain(domain):
    """
    Scrape a foundation domain for contact emails.
    Tries homepage + common subpages.
    Returns dict of {email: source_page}
    """
    found = {}
    if not domain:
        return found
    
    for page in SCRAPE_PAGES:
        url = f"https://www.{domain}/{page}" if page else f"https://www.{domain}/"
        html = fetch_page(url, timeout=8)
        if html:
            emails = extract_emails_from_html(html, domain)
            for e in emails:
                if e not in found:
                    found[e] = page if page else "homepage"
        time.sleep(0.3)  # be polite
    
    return found


# ── SES Email Validation ──

try:
    import boto3
    from botocore.exceptions import ClientError
    HAVE_SES = True
except ImportError:
    HAVE_SES = False


def validate_email_ses(client, email):
    """Validate a single email via SES. Returns verdict or None."""
    if not email or "@" not in email:
        return None
    try:
        resp = client.get_email_address_insights(EmailAddress=email)
        mv = resp.get("MailboxValidation", {})
        return {
            "valid": mv.get("IsValid", {}).get("ConfidenceVerdict", ""),
            "mailbox": mv.get("Evaluations", {}).get("MailboxExists", {}).get("ConfidenceVerdict", ""),
            "role": mv.get("Evaluations", {}).get("IsRoleAddress", {}).get("ConfidenceVerdict", ""),
        }
    except ClientError as e:
        if e.response["Error"]["Code"] == "Throttling":
            return {"error": "throttled"}
        return None
    except:
        return None


# ── State Management ──

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "found_emails": {},      # ein -> {email, source, domain, foundation}
        "domains_tried": {},     # domain -> True/False (has website)
        "scraped_domains": {},   # domain -> {emails found}
        "patterns_tested": 0,
        "patterns_found": 0,
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ── Stage 1: Website Scraping ──

def stage1_website_scrape(rows, state, max_count=None):
    """
    For foundations missing emails:
    A0. Gemini API lookup (AI-powered, most accurate — try first!)
    A1. Knowledge Graph API lookup (knowledge base — fallback)
    B.  Guess domain candidates from name (last resort)
    2.  Check DNS → scrape pages → extract emails → validate via SES
    """
    if max_count:
        rows = rows[:max_count]

    missing = [r for r in rows if not r.get("EMAIL", "").strip()]
    print(f"\n{'='*60}")
    print(f"  STAGE 1: Foundation Lookup + Website Scraping ({len(missing):,} missing emails)")
    if GEMINI_ENABLED:
        print(f"  🤖 Gemini API: ENABLED (most accurate — tried first)")
    if KG_ENABLED:
        print(f"  ⚡ Knowledge Graph API: ENABLED (fallback)")
    print(f"{'='*60}")

    try:
        client = boto3.client("sesv2", region_name=AWS_REGION)
    except:
        client = None

    found_count = 0
    gemini_found_count = 0
    kg_found_count = 0
    skipped_existing = 0
    
    for i, row in enumerate(missing):
        ein = row["EIN"]
        name = row.get("NAME", "")
        
        if ein in state["found_emails"]:
            skipped_existing += 1
            continue
        
        if not name:
            continue
        
        best_email = None
        best_source = None
        best_domain = None
        
        # ── Phase A0: Gemini API lookup (AI, most capable) ──
        if GEMINI_ENABLED and not best_email:
            gemini_key = f"gemini:{ein}"
            gemini_cache = state.setdefault("gemini_cache", {})
            if gemini_key in gemini_cache:
                gemini_result = gemini_cache[gemini_key]
            else:
                gemini_result = gemini_lookup(name)
                gemini_cache[gemini_key] = gemini_result
                if (i + 1) % 10 == 0:
                    save_state(state)
            
            if gemini_result:
                domain = gemini_result["domain"]
                exists = domain_exists(domain)
                state.setdefault("domains_tried", {})[domain] = exists
                
                if exists:
                    scrape_key = f"scraped:{domain}"
                    if scrape_key not in state.get("scraped_domains", {}):
                        found_emails = scrape_foundation_domain(domain)
                        state.setdefault("scraped_domains", {})[scrape_key] = list(found_emails.keys())
                        save_state(state)
                    else:
                        found_emails = {e: "" for e in state["scraped_domains"].get(scrape_key, [])}
                    
                    # Also check Gemini-suggested emails
                    suggested = gemini_result.get("emails", [])
                    for e in suggested:
                        if e not in found_emails:
                            found_emails[e] = "gemini_suggested"
                    
                    if found_emails:
                        candidates = []
                        for email in found_emails:
                            edomain = email.split("@")[1] if "@" in email else ""
                            is_role = any(email.startswith(p) for p in ["info@", "contact@", "admin@",
                                                                          "office@", "webmaster@", "support@"])
                            candidates.append((email, edomain == domain, not is_role))
                        candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
                        best_email = candidates[0][0]
                        best_source = "gemini_api"
                        best_domain = domain
        
        # ── Phase A1: Knowledge Graph API lookup ──
        kg_result = None
        if KG_ENABLED and not best_email:
            kg_key = f"kg:{ein}"
            # Cache KG results in state
            kg_cache = state.setdefault("kg_cache", {})
            if kg_key in kg_cache:
                kg_result = kg_cache[kg_key]
            else:
                kg_result = kg_search_lookup(name)
                kg_cache[kg_key] = kg_result
                if (i + 1) % 20 == 0:
                    save_state(state)
            
            if kg_result:
                domain = kg_result["domain"]
                # Check DNS for KG-provided domain
                exists = domain_exists(domain)
                state.setdefault("domains_tried", {})[domain] = exists
                
                if exists:
                    # Scrape the KG domain
                    scrape_key = f"scraped:{domain}"
                    if scrape_key not in state.get("scraped_domains", {}):
                        found_emails = scrape_foundation_domain(domain)
                        state.setdefault("scraped_domains", {})[scrape_key] = list(found_emails.keys())
                        save_state(state)
                    else:
                        found_emails = {e: "" for e in state["scraped_domains"].get(scrape_key, [])}
                    
                    if found_emails:
                        # Pick the best email
                        candidates = []
                        for email in found_emails:
                            edomain = email.split("@")[1] if "@" in email else ""
                            is_role = any(email.startswith(p) for p in ["info@", "contact@", "admin@",
                                                                          "office@", "webmaster@", "support@"])
                            candidates.append((email, edomain == domain, not is_role))
                        candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
                        best_email = candidates[0][0]
                        best_source = "kg_api"
                        best_domain = domain
        
        # ── Phase B: Fallback to domain guessing ──
        if not best_email:
            domains = guess_domains(name)
            if domains:
                for domain in domains:
                    if domain in state.get("domains_tried", {}):
                        if not state["domains_tried"][domain]:
                            continue
                    
                    # Check DNS
                    exists = domain_exists(domain)
                    state.setdefault("domains_tried", {})[domain] = exists
                    
                    if not exists:
                        continue
                    
                    # Scrape the domain
                    scrape_key = f"scraped:{domain}"
                    if scrape_key not in state.get("scraped_domains", {}):
                        found_emails = scrape_foundation_domain(domain)
                        state.setdefault("scraped_domains", {})[scrape_key] = list(found_emails.keys())
                        save_state(state)
                    else:
                        found_emails = {e: "" for e in state["scraped_domains"].get(scrape_key, [])}
                    
                    if found_emails:
                        # Pick the best email: prefer non-role-based on the same domain
                        candidates = []
                        for email in found_emails:
                            edomain = email.split("@")[1] if "@" in email else ""
                            is_role = any(email.startswith(p) for p in ["info@", "contact@", "admin@",
                                                                          "office@", "webmaster@", "support@"])
                            candidates.append((email, edomain == domain, not is_role))
                        
                        # Sort: same domain & non-role first
                        candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
                        best_email = candidates[0][0]
                        best_source = f"website_scrape"
                        best_domain = domain
                        
                        # Validate if SES available
                        if client and best_email:
                            result = validate_email_ses(client, best_email)
                            if result and result.get("error") != "throttled":
                                if result.get("valid") in ("HIGH", "MEDIUM"):
                                    pass  # Keep it
                                elif result.get("valid") == "LOW":
                                    # Try next candidate
                                    best_email = None
                            time.sleep(0.1)
                    
                    if best_email:
                        break
        
        if best_email and best_domain:
            if best_source == "gemini_api":
                method = "gemini_api"
            elif best_source == "kg_api":
                method = "kg_api"
            else:
                method = "website_scrape"
            state.setdefault("found_emails", {})[ein] = {
                "email": best_email,
                "source": best_source,
                "domain": best_domain,
                "foundation": name[:80],
                "method": method,
            }
            found_count += 1
            if method == "gemini_api":
                gemini_found_count += 1
            elif method == "kg_api":
                kg_found_count += 1
        
        if (i + 1) % 50 == 0:
            print(f"    Progress: {i+1}/{len(missing)}  Found: {found_count}")
            sys.stdout.flush()
            save_state(state)
    
    save_state(state)
    print(f"\n  Stage 1 complete: {found_count} emails found")
    by_method = []
    if GEMINI_ENABLED:
        by_method.append(f"🤖 Gemini: {gemini_found_count}")
    if KG_ENABLED:
        by_method.append(f"⚡ KG: {kg_found_count}")
    guessed = found_count - gemini_found_count - kg_found_count
    if guessed > 0:
        by_method.append(f"🔍 Guessed: {guessed}")
    if by_method:
        print(f"    {' | '.join(by_method)}")
    return found_count


# ── Stage 2: RDAP/WHOIS ──

def stage2_rdap_whois(rows, state, max_count=None):
    """
    For foundations with domains that exist, query WHOIS/RDAP 
    for registrant/admin/tech emails.
    """
    print(f"\n{'='*60}")
    print(f"  STAGE 2: RDAP/WHOIS Lookup")
    print(f"{'='*60}")
    
    try:
        import whois
    except ImportError:
        print("  ⚠️  python-whois not installed. Skip RDAP stage.")
        return 0
    
    missing = [r for r in rows if not r.get("EMAIL", "").strip() and r.get("EIN", "") not in state.get("found_emails", {})]
    
    if max_count:
        missing = missing[:max_count]
    
    try:
        client = boto3.client("sesv2", region_name=AWS_REGION)
    except:
        client = None
    
    found_count = 0
    
    for i, row in enumerate(missing):
        ein = row["EIN"]
        name = row.get("NAME", "")
        
        if ein in state.get("found_emails", {}):
            continue
        
        domains = guess_domains(name)
        
        for domain in domains:
            if not state.get("domains_tried", {}).get(domain, False):
                continue
            
            try:
                w = whois.whois(domain)
                
                # Collect all emails from WHOIS
                whois_emails = []
                if w.emails:
                    if isinstance(w.emails, list):
                        whois_emails.extend(w.emails)
                    else:
                        whois_emails.append(w.emails)
                
                # Filter to plausible contact emails
                found_domain = domain.lower().replace("www.", "")
                for email in whois_emails:
                    if not email or "@" not in email:
                        continue
                    email = email.lower().strip()
                    
                    # Skip privacy/abuse emails
                    if any(x in email for x in ["abuse@", "whois@", "proxy@", "privacy@",
                                                  "domains@", "hostmaster@"]):
                        continue
                    
                    # Skip if email domain doesn't match foundation domain
                    # (e.g. help@hosting.kr for gfoundation.com — hosting provider, not contact)
                    email_domain = email.split("@")[1] if "@" in email else ""
                    if email_domain and email_domain != found_domain and not email_domain.endswith("." + found_domain):
                        continue
                    
                    # Validate if SES available
                    is_valid = False
                    if client:
                        result = validate_email_ses(client, email)
                        if result and result.get("valid") in ("HIGH", "MEDIUM"):
                            is_valid = True
                        time.sleep(0.1)
                    else:
                        is_valid = True
                    
                    if is_valid:
                        state.setdefault("found_emails", {})[ein] = {
                            "email": email,
                            "source": f"whois:{domain}",
                            "domain": domain,
                            "foundation": name[:80],
                            "method": "rdap_whois",
                        }
                        found_count += 1
                        break  # One email per foundation
                
                if ein in state.get("found_emails", {}):
                    break
                    
            except:
                continue
        
        if (i + 1) % 20 == 0 and found_count > 0:
            print(f"    Progress: {i+1}/{len(missing)}  Found: {found_count}")
            sys.stdout.flush()
            save_state(state)
    
    save_state(state)
    print(f"\n  Stage 2 complete: {found_count} emails found via WHOIS/RDAP")
    return found_count


# ── Stage 3: Name Pattern Generation ──

def stage3_name_patterns(rows, state, max_count=None):
    """
    For foundations still missing emails, generate email patterns
    from extracted surnames and test via SES validation.
    """
    print(f"\n{'='*60}")
    print(f"  STAGE 3: Name Pattern Generation & SES Validation")
    print(f"{'='*60}")
    
    missing = [r for r in rows if not r.get("EMAIL", "").strip() and 
               r.get("EIN", "") not in state.get("found_emails", {})]
    
    if max_count:
        missing = missing[:max_count]
    
    try:
        client = boto3.client("sesv2", region_name=AWS_REGION)
    except:
        print("  ⚠️  boto3 not available. Skip SES validation.")
        client = None
    
    if not client:
        return 0
    
    # Count how many have extractable surnames and available domains
    candidates = []
    for row in missing:
        name = row.get("NAME", "")
        surname = extract_surname(name)
        if not surname:
            continue
        domains = guess_domains(name)
        for domain in domains:
            if state.get("domains_tried", {}).get(domain, False):
                candidates.append((row, surname, domain))
                break
    
    print(f"  Candidates with name + valid domain: {len(candidates):,}")
    
    # Test email patterns
    found_count = 0
    skipped_role = 0
    
    for i, (row, surname, domain) in enumerate(candidates):
        ein = row["EIN"]
        
        if ein in state.get("found_emails", {}):
            continue
        
        # Generate patterns
        patterns = [
            (f"info@{domain}", "info@"),
            (f"contact@{domain}", "contact@"),
            (f"grants@{domain}", "grants@"),
            (f"giving@{domain}", "giving@"),
            (f"admin@{domain}", "admin@"),
            (f"office@{domain}", "office@"),
        ]
        
        # Add name-based patterns
        first_initial = surname[0]
        name_patterns = [
            (f"{surname}@{domain}", "lastname@"),
            (f"{first_initial}{surname}@{domain}", "f_lastname@"),
        ]
        patterns = name_patterns + patterns
        
        best_email = None
        best_pattern = None
        
        for email, pattern_label in patterns:
            result = validate_email_ses(client, email)
            
            retries = 0
            while result and result.get("error") == "throttled" and retries < 3:
                time.sleep(2 ** retries)
                result = validate_email_ses(client, email)
                retries += 1
            
            if result and result.get("valid") in ("HIGH", "MEDIUM"):
                best_email = email
                best_pattern = pattern_label
                break
            
            time.sleep(0.1)
        
        if best_email:
            state.setdefault("found_emails", {})[ein] = {
                "email": best_email,
                "source": f"pattern:{best_pattern}",
                "domain": domain,
                "foundation": row.get("NAME", "")[:80],
                "method": "name_pattern",
            }
            found_count += 1
        
        if (i + 1) % 50 == 0:
            print(f"    Progress: {i+1}/{len(candidates)}  Found: {found_count}")
            sys.stdout.flush()
            save_state(state)
    
    save_state(state)
    print(f"\n  Stage 3 complete: {found_count} emails found via name patterns")
    return found_count


# ── Apply: Merge Findings ──

def apply_findings():
    """Merge all found emails into send_list_clean.csv → send_list_enriched.csv."""
    state = load_state()
    found = state.get("found_emails", {})
    
    if not found:
        print("❌ No found emails to apply. Run enrichment first.")
        return
    
    print(f"📄 Merging {len(found):,} found emails into send list...")
    
    with open(ENRICHED_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    
    fieldnames = list(rows[0].keys())
    extra_fields = ["EMAIL_SOURCE", "FOUND_BY"]
    all_fields = fieldnames + [f for f in extra_fields if f not in fieldnames]
    
    updated = 0
    new_contacts = 0
    
    for row in rows:
        ein = row["EIN"]
        ein = f"{int(ein):09d}" if ein.isdigit() else ein
        
        # Check if this EIN has a found email
        for found_ein, data in found.items():
            # Normalize EIN comparison
            fe = f"{int(found_ein):09d}" if found_ein.isdigit() else found_ein
            if fe == ein or found_ein == ein:
                current_email = (row.get("EMAIL") or "").strip()
                new_email = data["email"]
                
                if not current_email:
                    row["EMAIL"] = new_email
                    row["EMAIL_SOURCE"] = data.get("source", "enrichment")
                    row["FOUND_BY"] = data.get("method", "enrichment")
                    new_contacts += 1
                elif current_email.startswith("info@") or current_email.startswith("contact@"):
                    # Upgrade generic to specific
                    if not new_email.startswith("info@") and not new_email.startswith("contact@"):
                        row["ORIGINAL_EMAIL"] = current_email
                        row["EMAIL"] = new_email
                        row["EMAIL_SOURCE"] = data.get("source", "enrichment")
                        row["FOUND_BY"] = data.get("method", "enrichment")
                        updated += 1
                break
    
    # Filter to only those with emails for the clean send list
    with_email = [r for r in rows if r.get("EMAIL", "").strip()]
    
    # Write enriched output
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n✅ Enriched output: {OUTPUT_CSV}")
    print(f"   New contacts added:        {new_contacts:,}")
    print(f"   Existing upgraded:         {updated:,}")
    print(f"   Total with email:          {len(with_email):,}")
    print(f"   Total records:             {len(rows):,}")


# ── Status ──

def show_status():
    state = load_state()
    found = state.get("found_emails", {})
    domains = state.get("domains_tried", {})
    scraped = state.get("scraped_domains", {})
    
    mx_yes = sum(1 for v in domains.values() if v)
    mx_no = sum(1 for v in domains.values() if not v)
    
    methods = defaultdict(int)
    for data in found.values():
        methods[data.get("method", "unknown")] += 1
    
    print(f"📊 Enrichment Pipeline Status:")
    print(f"   Domains checked:          {len(domains):,}")
    print(f"   Domains with DNS:         {mx_yes:,}")
    print(f"   Domains scraped:          {len(scraped):,}")
    print(f"   Total emails found:       {len(found):,}")
    print(f"\n   By method:")
    for method, count in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"     {method:20s} {count:,}")
    print(f"\n   Run: python enrich_foundations.py")
    print(f"        python enrich_foundations.py --quick 50")
    print(f"        python enrich_foundations.py --stage 1")


# ── Main ──

def main():
    if "--status" in sys.argv:
        show_status()
        return
    
    if "--apply" in sys.argv:
        apply_findings()
        return
    
    quick = None
    stages = []
    chunk_id = None
    chunks_total = None
    for arg in sys.argv[1:]:
        if arg.startswith("--quick"):
            quick = int(arg.split("=")[-1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1])
        elif arg.startswith("--stage"):
            stages.append(int(arg.split("=")[-1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1]))
        elif arg.startswith("--chunk-id"):
            chunk_id = int(arg.split("=")[-1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1])
        elif arg.startswith("--chunks"):
            chunks_total = int(arg.split("=")[-1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1])
    
    # Default: run all stages
    if not stages:
        stages = [1, 2, 3]
    
    state = load_state()
    
    with open(ENRICHED_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    
    # Parallel chunk support: each instance processes EINs where hash % N == M
    if chunks_total and chunk_id is not None:
        rows = [r for r in rows if hash(r["EIN"]) % chunks_total == chunk_id]
        # Use a chunk-specific state file to avoid conflicts
        global STATE_FILE
        chunk_state = ENRICHED_CSV.replace(".csv", f"_state_chunk{chunk_id}.json")
        STATE_FILE = chunk_state
        state = load_state()
        print(f"   Chunk {chunk_id+1}/{chunks_total}: {len(rows):,} records")
    
    print(f"📄 Loaded {len(rows):,} records from enriched_contacts.csv")
    print(f"   Missing emails: {sum(1 for r in rows if not r.get('EMAIL','').strip()):,}")
    print(f"   Already found:  {len(state.get('found_emails', {})):,}")
    
    if 1 in stages:
        stage1_website_scrape(rows, state, max_count=quick)
    
    if 2 in stages:
        stage2_rdap_whois(rows, state, max_count=quick)
    
    if 3 in stages:
        stage3_name_patterns(rows, state, max_count=quick)
    
    # Final summary
    found = state.get("found_emails", {})
    print(f"\n{'='*60}")
    print(f"  ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"   Total emails found: {len(found):,}")
    print(f"   Remaining missing:  {sum(1 for r in rows if not r.get('EMAIL','').strip() and r['EIN'] not in found):,}")
    print(f"\n   Next: python enrich_foundations.py --apply")
    print(f"         (merges findings into send_list_enriched.csv)")


if __name__ == "__main__":
    main()
