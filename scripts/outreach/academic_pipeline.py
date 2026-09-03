#!/usr/bin/env python3
"""
GrantWizard — Academic Outreach Pipeline
=========================================
Fully automated pipeline that:
  1. Discovers academics via Semantic Scholar (by research topic)
  2. Finds each academic's most recent/relevant paper
  3. Extracts research dimensions (faith, geography, topic)
  4. Builds tailored data samples from churches.db
  5. Generates personalized email drafts
  6. Sends via Gmail API (with --send flag)

Usage:
  .venv\Scripts\python scripts/outreach/academic_pipeline.py --dry-run --limit 5
  .venv\Scripts\python scripts/outreach/academic_pipeline.py --limit 10
  .venv\Scripts\python scripts/outreach/academic_pipeline.py --resume --send
  .venv\Scripts\python scripts/outreach/academic_pipeline.py --search-only --limit 50
  .venv\Scripts\python scripts/outreach/academic_pipeline.py --drafts-only
  .venv\Scripts\python scripts/outreach/academic_pipeline.py --status
"""

import os
import sys
import json
import time
import sqlite3
import argparse
import base64
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from email.message import EmailMessage
from datetime import datetime
from typing import Optional

# Add outreach dir to path for paper_to_query import
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from paper_to_query import (
    extract_research_dimensions,
    build_query,
    query_to_sql,
    format_sample_row,
    describe_dimensions,
    ResearchDimensions,
)

PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
CHURCHES_DB = os.path.join(PROJECT_DIR, "churches.db")
OUTREACH_DB = os.path.join(SCRIPT_DIR, "academic_outreach.db")
CHECKPOINT_FILE = os.path.join(SCRIPT_DIR, "academic_pipeline_checkpoint.json")

# ── Gmail auth ──
TOKEN_FILE = os.path.join(PROJECT_DIR, "data", "gmail_token.json")
CREDENTIALS_FILE = os.path.join(PROJECT_DIR, "data", "gmail_credentials.json")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
SENDER_EMAIL = "charlesaprescottjr@gmail.com"
SENDER_NAME = "Charles Prescott"

# ── API sources ──
# OpenAlex: 100k/day, no key needed, generous rate limits — PRIMARY
# Semantic Scholar: 100/5min without key — FALLBACK
OA_BASE = "https://api.openalex.org"
OA_RATE_LIMIT = 0.15  # OpenAlex allows ~10/sec with polite email header

S2_BASE = "https://api.semanticscholar.org/graph/v1"
S2_RATE_LIMIT = 3.0  # seconds between calls (100/5min = 1 per 3s for free tier)

# Polite contact header (OpenAlex prefers this)
API_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "GrantWizard/1.0 (mailto:charlesaprescottjr@gmail.com)",
}

# ── Research topics to search for academics ──
SEARCH_QUERIES = [
    # Sociology of religion
    "sociology of religion congregation neighborhood",
    "religious organizations spatial distribution",
    "congregational ecology community",
    "religion demographic change neighborhood",
    # Political science
    "religion voting behavior geographic",
    "religious geography election turnout",
    "church density political polarization",
    "faith-based organizations public policy",
    # Geography / GIS
    "geography of religion spatial analysis",
    "GIS religious institutions mapping",
    "spatial distribution places of worship",
    "religious landscape geographic information",
    # Urban planning
    "religious institutions urban planning",
    "faith-based community development neighborhood",
    "church property land use zoning",
    "places of worship urban geography",
    # Data science / computational
    "computational social science religion",
    "religious organizations census data analysis",
    "religion demographic data machine learning",
    # Public health / food
    "faith-based organizations food desert",
    "religious congregations health outcomes",
    "church community health disparities",
    # Criminology
    "religion crime neighborhood effects",
    "religious institutions violence prevention",
    # Economics
    "religion economic inequality spatial",
    "religious organizations poverty mapping",
    # Immigration
    "immigrant religion spatial distribution",
    "ethnic church neighborhood enclave",
    "religious diversity immigration geography",
]


# ═══════════════════════════════════════════════════════════════════════════════
# OPENALEX API (primary — 100k/day, no key)
# ═══════════════════════════════════════════════════════════════════════════════

def _oa_api(path: str, params: dict = None, retries: int = 3) -> dict:
    """Call OpenAlex API with rate limiting and retries."""
    url = f"{OA_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=API_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 403):
                wait = 5 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...", end="\r")
                time.sleep(wait)
                continue
            if e.code == 404:
                return {}
            raise
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"    API error (attempt {attempt+1}): {e}")
            return {}
    return {}


def _reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract text from OpenAlex's inverted index format."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    try:
        word_positions = []
        for word, positions in inverted_index.items():
            if not isinstance(positions, list):
                continue
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return " ".join(w for _, w in word_positions)
    except Exception:
        return ""


def _oa_author_id_to_short(author_id: str) -> str:
    """Extract short ID from OpenAlex URL (https://openalex.org/A5023888391 -> A5023888391)."""
    return author_id.split("/")[-1] if "/" in author_id else author_id


def search_academics_oa(query: str, limit: int = 15) -> list:
    """
    Search OpenAlex for authors by topic.
    Searches works, then extracts unique authors with institution info.
    """
    academics = []
    seen_ids = set()

    # Search works matching the topic
    results = _oa_api("/works", {
        "search": query,
        "per_page": min(limit, 50),
        "sort": "cited_by_count:desc",
        "filter": "type:article",
    })

    works = results.get("results", [])
    if not works:
        return academics

    for work in works:
        authorships = work.get("authorships", [])
        if not authorships:
            continue
        for authorship in authorships:
            author_data = authorship.get("author", {})
            author_id = author_data.get("id", "")
            if not author_id or author_id in seen_ids:
                continue
            seen_ids.add(author_id)

            # Get institution from first authorship
            institutions = authorship.get("institutions", [])
            institution = institutions[0].get("display_name", "") if institutions else ""

            academics.append({
                "name": author_data.get("display_name", ""),
                "author_id": _oa_author_id_to_short(author_id),
                "institution": institution,
                "source": "openalex",
                "source_query": query,
                "source_paper_title": work.get("title", "")[:200],
                "source_paper_year": work.get("publication_year"),
                "source_paper_doi": work.get("doi", ""),
            })

    time.sleep(OA_RATE_LIMIT)
    return academics


def get_recent_papers_oa(author_id: str, limit: int = 5) -> list:
    """Get an author's recent papers from OpenAlex with abstracts."""
    results = _oa_api("/works", {
        "filter": f"authorships.author.id:{author_id}",
        "sort": "cited_by_count:desc",
        "per_page": limit,
    })

    papers = []
    for work in results.get("results", []):
        abstract = ""
        inv_idx = work.get("abstract_inverted_index")
        if inv_idx:
            abstract = _reconstruct_abstract(inv_idx)

        source = work.get("primary_location", {}) or {}
        source_display = source.get("source", {}) or {}
        journal = source_display.get("display_name", "")

        papers.append({
            "paperId": work.get("id", ""),
            "title": work.get("title", ""),
            "abstract": abstract,
            "year": work.get("publication_year"),
            "journal": journal,
            "externalIds": {"DOI": work.get("doi", "")},
            "citationCount": work.get("cited_by_count", 0) or 0,
        })

    time.sleep(OA_RATE_LIMIT)
    return papers


# ═══════════════════════════════════════════════════════════════════════════════
# SEMANTIC SCHOLAR API (fallback)
# ═══════════════════════════════════════════════════════════════════════════════

def s2_api(path: str, params: dict = None, retries: int = 3) -> dict:
    """Call Semantic Scholar API with rate limiting and retries."""
    url = f"{S2_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 5 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...", end="\r")
                time.sleep(wait)
                continue
            if e.code == 404:
                return {}
            raise
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"    API error (attempt {attempt+1}): {e}")
            return {}
    return {}


def search_academics_s2(query: str, limit: int = 10) -> list:
    """
    Search Semantic Scholar for authors by topic keywords.
    Searches papers, then extracts unique authors.
    """
    academics = []
    seen_ids = set()

    results = s2_api("/paper/search", {
        "query": query,
        "limit": min(limit, 100),
        "fields": "title,year,authors,abstract,externalIds,journal",
    })

    papers = results.get("data", [])
    if not papers:
        return academics

    for paper in papers:
        if not paper or not paper.get("authors"):
            continue
        for author in paper["authors"]:
            author_id = author.get("authorId")
            if not author_id or author_id in seen_ids:
                continue
            seen_ids.add(author_id)
            academics.append({
                "name": author.get("name", ""),
                "author_id": author_id,
                "institution": "",
                "source": "semanticscholar",
                "source_query": query,
                "source_paper_title": paper.get("title", "")[:200],
                "source_paper_year": paper.get("year"),
                "source_paper_doi": (paper.get("externalIds") or {}).get("DOI", ""),
            })

    time.sleep(S2_RATE_LIMIT)
    return academics


def get_recent_papers_s2(author_id: str, limit: int = 5) -> list:
    """Get an author's recent papers from Semantic Scholar."""
    results = s2_api(f"/author/{author_id}/papers", {
        "limit": limit,
        "fields": "title,abstract,year,journal,externalIds,citationCount",
    })
    papers = results.get("data", [])
    time.sleep(S2_RATE_LIMIT)
    return [p for p in papers if p] if papers else []


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED API (OpenAlex primary, Semantic Scholar fallback)
# ═══════════════════════════════════════════════════════════════════════════════

def search_academics(query: str, limit: int = 15, source: str = "openalex") -> list:
    """Search for academics. Uses OpenAlex primary, S2 fallback."""
    if source == "semanticscholar":
        return search_academics_s2(query, limit)

    # Try OpenAlex first
    try:
        results = search_academics_oa(query, limit)
        if results:
            return results
    except Exception as e:
        print(f"    OpenAlex failed: {e}, trying Semantic Scholar...")

    # Fallback to Semantic Scholar
    try:
        return search_academics_s2(query, limit)
    except Exception as e:
        print(f"    Semantic Scholar also failed: {e}")
        return []


def get_recent_papers(author_id: str, limit: int = 5, source: str = "openalex") -> list:
    """Get recent papers for an author. Uses OpenAlex primary, S2 fallback."""
    if source == "semanticscholar":
        return get_recent_papers_s2(author_id, limit)

    try:
        papers = get_recent_papers_oa(author_id, limit)
        if papers:
            return papers
    except Exception as e:
        print(f"    OpenAlex failed: {e}, trying Semantic Scholar...")

    try:
        return get_recent_papers_s2(author_id, limit)
    except Exception as e:
        print(f"    Semantic Scholar also failed: {e}")
        return []


def get_db():
    """Get read-only churches DB connection with retries."""
    for attempt in range(10):
        try:
            conn = sqlite3.connect(f"file:{CHURCHES_DB}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.OperationalError:
            if attempt < 9:
                time.sleep(3)
            else:
                raise


def get_db_rw():
    """Get read-write outreach DB connection."""
    conn = sqlite3.connect(OUTREACH_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema():
    """Create academic outreach tables if they don't exist."""
    conn = get_db_rw()
    c = conn.cursor()

    # Check if migration needed (old schema missing 'source' column)
    existing = [r[1] for r in c.execute("PRAGMA table_info('academic_contacts')").fetchall()]
    if existing and 'source' not in existing:
        print("  Migrating schema: adding source column...")
        c.execute("ALTER TABLE academic_contacts ADD COLUMN source TEXT DEFAULT 'semanticscholar'")
        conn.commit()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS academic_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id TEXT UNIQUE,
            name TEXT NOT NULL,
            email TEXT,
            institution TEXT,
            field TEXT,
            source TEXT DEFAULT 'openalex',
            scholar_url TEXT,
            search_queries TEXT,
            total_papers INTEGER,
            h_index INTEGER,
            outreach_status TEXT DEFAULT 'new',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS academic_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id TEXT NOT NULL,
            paper_id TEXT UNIQUE,
            title TEXT,
            abstract TEXT,
            year INTEGER,
            journal TEXT,
            doi TEXT,
            citation_count INTEGER,
            is_selected INTEGER DEFAULT 0,
            faith_label TEXT,
            geo_label TEXT,
            topic_labels TEXT,
            query_sql TEXT,
            query_row_count INTEGER,
            outreach_status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (author_id) REFERENCES academic_contacts(author_id)
        );

        CREATE TABLE IF NOT EXISTS academic_outreach_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id TEXT,
            paper_id TEXT,
            action TEXT,
            email_to TEXT,
            email_subject TEXT,
            email_body_hash TEXT,
            status TEXT,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_academic_contacts_author
            ON academic_contacts(author_id);
        CREATE INDEX IF NOT EXISTS idx_academic_contacts_status
            ON academic_contacts(outreach_status);
        CREATE INDEX IF NOT EXISTS idx_academic_papers_author
            ON academic_papers(author_id);
        CREATE INDEX IF NOT EXISTS idx_academic_papers_selected
            ON academic_papers(is_selected);
        CREATE INDEX IF NOT EXISTS idx_academic_outreach_log_author
            ON academic_outreach_log(author_id);
    """)

    conn.commit()
    conn.close()
    print("  Schema initialized.")


def guess_email(name: str, institution: str) -> str:
    """Guess academic email from name + institution. Returns '' if can't guess."""
    if not name or not institution:
        return ""
    # Extract domain from institution
    # Common patterns: "Harvard University" -> harvard.edu, "University of X" -> x.edu
    inst_lower = institution.lower().strip()
    # Remove "Press" suffix (common OpenAlex artifact)
    inst_lower = inst_lower.replace(" press", "").replace(", inc", "").replace(" inc", "")
    
    domain = None
    # Known mappings for common institutions
    KNOWN_DOMAINS = {
        "harvard": "harvard.edu",
        "princeton": "princeton.edu",
        "stanford": "stanford.edu",
        "yale": "yale.edu",
        "mit": "mit.edu",
        "columbia": "columbia.edu",
        "chicago": "uchicago.edu",
        "berkeley": "berkeley.edu",
        "michigan": "umich.edu",
        "duke": "duke.edu",
        "northwestern": "northwestern.edu",
        "cornell": "cornell.edu",
        "penn": "upenn.edu",
        "pennsylvania": "upenn.edu",
        "ucla": "ucla.edu",
        "nyu": "nyu.edu",
        "unc": "unc.edu",
        "wisconsin": "wisc.edu",
        "texas": "utexas.edu",
        "washington": "uw.edu",
        "illinois": "illinois.edu",
        "ohio state": "osu.edu",
        "indiana": "indiana.edu",
        "purdue": "purdue.edu",
        "notre dame": "nd.edu",
        "georgetown": "georgetown.edu",
        "boston university": "bu.edu",
        "boston college": "bc.edu",
        "arizona": "arizona.edu",
        "arizona state": "asu.edu",
        "florida": "ufl.edu",
        "florida state": "fsu.edu",
        "georgia": "uga.edu",
        "emory": "emory.edu",
        "vanderbilt": "vanderbilt.edu",
        "rice": "rice.edu",
        "johns hopkins": "jhu.edu",
        "carnegie mellon": "cmu.edu",
        "caltech": "caltech.edu",
        "brown": "brown.edu",
        "dartmouth": "dartmouth.edu",
        "virginia": "virginia.edu",
        "maryland": "umd.edu",
        "penn state": "psu.edu",
        "rutgers": "rutgers.edu",
        "minnesota": "umn.edu",
        "uc davis": "ucdavis.edu",
        "uc san diego": "ucsd.edu",
        "uc irvine": "uci.edu",
        "uc santa": "ucsb.edu",
        "northeastern": "northeastern.edu",
        "tufts": "tufts.edu",
        "rochester": "rochester.edu",
        "case western": "case.edu",
        "wake forest": "wfu.edu",
        "tulane": "tulane.edu",
        "miami": "miami.edu",
        "syracuse": "syr.edu",
        "baylor": "baylor.edu",
        "pepperdine": "pepperdine.edu",
    }
    
    for key, dom in KNOWN_DOMAINS.items():
        if key in inst_lower:
            domain = dom
            break
    
    if not domain:
        return ""
    
    # Generate email from name
    parts = name.lower().replace(",", "").replace(".", "").split()
    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        return f"{first}.{last}@{domain}"
    return ""


def find_email_pdl(name: str, institution: str, api_key: str) -> Optional[str]:
    """
    Find academic email via People Data Labs enrichment API.
    Free tier: 1,000 records/month. Returns email or None.
    """
    if not api_key or not name or not institution:
        return None

    url = "https://api.peopledatalabs.com/v5/person/enrich"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = json.dumps({
        "name": [name],
        "company": [institution],
        "location": ["United States"],
        "profile": ["linkedin"],
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    if data.get("status") != 200:
        return None

    emails = []
    for email_obj in data.get("data", {}).get("emails", []) or []:
        addr = email_obj.get("address", "")
        if addr and "@" in addr:
            emails.append(addr)

    for e in emails:
        if ".edu" in e:
            return e
    return emails[0] if emails else None


def enrich_emails_with_pdl(conn, limit: int = 0, api_key: str = "") -> int:
    """
    Enrich academics without emails using PDL.
    Returns number of emails found.
    """
    if not api_key:
        api_key = os.environ.get("PDL_API_KEY", "")
    if not api_key:
        print("  No PDL API key (set PDL_API_KEY env var or use --pdl-key)")
        return 0

    c = conn.cursor()
    query = """
        SELECT author_id, name, institution
        FROM academic_contacts
        WHERE (email IS NULL OR email = '')
          AND institution IS NOT NULL AND institution != ''
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = c.execute(query).fetchall()
    total = len(rows)
    found = 0

    print(f"  PDL enriching {total} academics...")

    for i, row in enumerate(rows):
        author_id = row["author_id"]
        name = row["name"]
        institution = row["institution"]

        email = find_email_pdl(name, institution, api_key)
        if email:
            c.execute("UPDATE academic_contacts SET email = ? WHERE author_id = ?",
                     (email.lower(), author_id))
            found += 1
            if found <= 5:
                print(f"    + {name[:25]:25s} -> {email}")

        if (i + 1) % 20 == 0:
            conn.commit()
            print(f"    {i+1}/{total}, found {found}...", end="\r")

    conn.commit()
    print(f"\n  PDL: {found}/{total} emails found")
    return found


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL VALIDATION (IPQS + ZeroBounce)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_email_ipqs(email: str, api_key: str) -> dict:
    """Validate email via IPQualityScore. Returns {valid, disposable, score, reason}."""
    if not api_key or not email:
        return {"valid": False, "disposable": False, "score": 0, "reason": "no_key"}

    url = f"https://www.ipqualityscore.com/api/json/email/{api_key}/{urllib.parse.quote(email)}"
    try:
        req = urllib.request.Request(url, headers=API_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return {"valid": False, "disposable": False, "score": 0, "reason": str(e)[:80]}

    return {
        "valid": data.get("valid", False),
        "disposable": data.get("disposable", False),
        "score": data.get("overall_score", 0),
        "reason": data.get("reason", "") or "ok",
    }


def validate_email_zerobounce(email: str, api_key: str) -> dict:
    """Validate email via ZeroBounce. Returns {valid, status, sub_status}."""
    if not api_key or not email:
        return {"valid": False, "status": "no_key", "sub_status": ""}

    url = f"https://api.zerobounce.net/v2/validate?api_key={api_key}&email={urllib.parse.quote(email)}"
    try:
        req = urllib.request.Request(url, headers=API_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return {"valid": False, "status": "error", "sub_status": str(e)[:80]}

    status = data.get("status", "")
    return {
        "valid": status == "valid",
        "status": status,
        "sub_status": data.get("sub_status", ""),
    }


def validate_emails(conn, limit: int = 0, ipqs_key: str = "", zb_key: str = "") -> dict:
    """
    Validate all emails in DB that haven't been validated yet.
    Uses IPQS and/or ZeroBounce depending on available keys.
    Returns stats dict.
    """
    ipqs_key = ipqs_key or os.environ.get("IPQS_API_KEY", "")
    zb_key = zb_key or os.environ.get("ZEROBOUNCE_API_KEY", "")

    if not ipqs_key and not zb_key:
        print("  No validation API keys (set IPQS_API_KEY or ZEROBOUNCE_API_KEY)")
        return {"validated": 0, "good": 0, "bad": 0}

    c = conn.cursor()

    # Ensure validation columns exist
    try:
        c.execute("ALTER TABLE academic_contacts ADD COLUMN email_validated INTEGER DEFAULT 0")
        c.execute("ALTER TABLE academic_contacts ADD COLUMN email_validation_result TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # columns already exist

    query = """
        SELECT author_id, name, email FROM academic_contacts
        WHERE email IS NOT NULL AND email != ''
          AND email_validated = 0
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = c.execute(query).fetchall()
    total = len(rows)
    good = 0
    bad = 0

    providers = []
    if ipqs_key:
        providers.append("IPQS")
    if zb_key:
        providers.append("ZeroBounce")
    print(f"  Validating {total} emails via {' + '.join(providers)}...")

    for i, row in enumerate(rows):
        author_id = row["author_id"]
        email = row["email"]

        results = []
        if ipqs_key:
            r = validate_email_ipqs(email, ipqs_key)
            results.append(f"ipqs:{r['score']}/{r['valid']}")
        if zb_key:
            r = validate_email_zerobounce(email, zb_key)
            results.append(f"zb:{r['status']}")

        result_str = "; ".join(results)
        is_valid = 1 if any("valid" in r.lower() or "True" in r for r in results) else 0

        c.execute("""
            UPDATE academic_contacts SET email_validated = 1, email_validation_result = ?
            WHERE author_id = ?
        """, (result_str, author_id))

        if is_valid:
            good += 1
        else:
            bad += 1
            if bad <= 3:
                name = row["name"][:25]
                print(f"    - {name:25s} | {email:40s} | {result_str}")

        if (i + 1) % 20 == 0:
            conn.commit()
            print(f"    {i+1}/{total}, good={good} bad={bad}...", end="\r")

    conn.commit()
    print(f"\n  Validation: {good} good, {bad} bad out of {total}")
    return {"validated": total, "good": good, "bad": bad}


def load_academics_from_db(limit: int = 0) -> list:
    """Load academics from DB that need processing (no selected paper yet)."""
    conn = get_db_rw()
    c = conn.cursor()
    query = """
        SELECT ac.author_id, ac.name, ac.institution, ac.source, ac.email
        FROM academic_contacts ac
        WHERE ac.author_id NOT IN (
            SELECT DISTINCT author_id FROM academic_papers WHERE is_selected = 1
        )
        ORDER BY ac.id
    """
    if limit:
        query += f" LIMIT {limit}"
    
    rows = [dict(r) for r in c.execute(query).fetchall()]
    
    # Guess emails for those without
    for row in rows:
        if not row.get("email"):
            row["email"] = guess_email(row.get("name", ""), row.get("institution", ""))
            if row["email"]:
                c.execute("UPDATE academic_contacts SET email = ? WHERE author_id = ?",
                         (row["email"], row["author_id"]))
    
    conn.commit()
    conn.close()
    return rows


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {
        "stage": "search",
        "search_index": 0,
        "academics_found": 0,
        "samples_generated": 0,
        "emails_sent": 0,
        "sent_author_ids": [],
        "errors": [],
    }


def save_checkpoint(cp):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(cp, f, indent=2)


def upsert_academic(conn, acad: dict):
    """Insert or update an academic contact."""
    c = conn.cursor()
    c.execute("""
        INSERT INTO academic_contacts (author_id, name, institution, source, search_queries)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(author_id) DO UPDATE SET
            institution = COALESCE(excluded.institution, institution),
            search_queries = search_queries || '; ' || excluded.search_queries,
            updated_at = datetime('now')
    """, (
        acad["author_id"],
        acad["name"],
        acad.get("institution", ""),
        acad.get("source", "openalex"),
        acad.get("source_query", ""),
    ))
    conn.commit()


def upsert_paper(conn, author_id: str, paper: dict, selected: bool = False):
    """Insert or update a paper record."""
    c = conn.cursor()
    paper_id = paper.get("paperId", "")
    if not paper_id:
        return

    doi = (paper.get("externalIds") or {}).get("DOI", "")
    journal = ""
    if paper.get("journal"):
        journal = paper["journal"].get("name", "") if isinstance(paper["journal"], dict) else str(paper["journal"])

    c.execute("""
        INSERT INTO academic_papers (author_id, paper_id, title, abstract, year, journal, doi, citation_count, is_selected)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(paper_id) DO UPDATE SET
            abstract = COALESCE(excluded.abstract, abstract),
            citation_count = excluded.citation_count,
            is_selected = MAX(is_selected, excluded.is_selected)
    """, (
        author_id, paper_id,
        paper.get("title", "")[:500],
        paper.get("abstract", "")[:3000] if paper.get("abstract") else "",
        paper.get("year"),
        journal[:200],
        doi,
        paper.get("citationCount", 0),
        1 if selected else 0,
    ))
    conn.commit()
    return paper_id


def store_dimensions(conn, paper_id: str, dims, query_sql: str):
    """Store extracted dimensions and generated SQL on the paper record."""
    c = conn.cursor()
    c.execute("""
        UPDATE academic_papers SET
            faith_label = ?,
            geo_label = ?,
            topic_labels = ?,
            query_sql = ?
        WHERE paper_id = ?
    """, (
        dims.faith_label,
        dims.geo_label,
        ", ".join(dims.topic_labels) if dims.topic_labels else "",
        query_sql,
        paper_id,
    ))
    conn.commit()


def run_sample_query(query_sql: str, limit: int = 10) -> list:
    """Execute the generated SQL and return sample rows."""
    conn = get_db()
    try:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(query_sql).fetchall()]
        return rows
    except Exception as e:
        print(f"    Query error: {e}")
        return []
    finally:
        conn.close()


def build_email(acad_name: str, paper: dict, sample_rows: list, dims) -> str:
    """Build a personalized outreach email."""
    first_name = acad_name.split()[-1] if acad_name.split() else acad_name
    paper_title = paper.get("title", "your recent work")[:120]
    journal = paper.get("journal", "")
    if isinstance(journal, dict):
        journal = journal.get("name", "")
    year = paper.get("year", "")

    # Paper reference line
    paper_ref = f'"{paper_title}"'
    if journal and year:
        paper_ref += f" ({journal}, {year})"
    elif year:
        paper_ref += f" ({year})"

    # Faith context
    faith_ctx = ""
    if dims.faith_label and dims.faith_label != "All faiths":
        faith_ctx = f" Your focus on {dims.faith_label.lower()} institutions"
        if dims.geo_label and dims.geo_label != "National":
            faith_ctx += f" in {dims.geo_label.lower()}"
        faith_ctx += " is exactly the kind of research this dataset can support."

    # Format sample
    sample_block = ""
    if sample_rows:
        header = f"  {'Name':45s} | {'City':18s} {'St':4s} | {'Faith':15s} | {'Type':15s} | {'Coordinates':18s} | Enrichment data"
        sep = f"  {'-'*45} | {'-'*18} {'-'*4} | {'-'*15} | {'-'*15} | {'-'*18} | {'-'*30}"
        sample_lines = [header, sep]
        for row in sample_rows:
            sample_lines.append(format_sample_row(row, dims))
        sample_block = "\n".join(sample_lines)

    # Topic data description
    topic_desc = ""
    if dims.topic_labels:
        topic_desc = "This sample includes: " + ", ".join(dims.topic_labels[:4]).lower() + "."

    body = f"""Dear Dr. {first_name},

I came across {paper_ref} and was struck by how well my dataset aligns with your research agenda.{faith_ctx}

I've built a national religious organization database — 385,000 records spanning every US faith tradition, cross-referenced with tract-level ACS demographics, county-level election returns (2000-2024), USDA food desert indicators, FBI crime data, and more. That's ~130,000 records beyond what the government's HIFLD dataset captures.

To give you a concrete sense of the fit, I queried the database for data matching your research focus:

Faith tradition: {dims.faith_label}
Geography: {dims.geo_label}
Topics: {', '.join(dims.topic_labels) if dims.topic_labels else 'General demographics'}

Here's a sample of {len(sample_rows)} records drawn from that query:

{sample_block}

{topic_desc}

What I can offer:
• A custom data extract aligned to your specific research geography and variables of interest
• Direct SQL or CSV access for reproducible research
• Dataset documentation including provenance tracking for every record
• Updates as enrichment layers expand (we're actively adding more ACS variables, crime data, and health indicators)

If this might be useful for your work — whether for a current project, a grant proposal, or a student's dissertation — I'd be glad to discuss what a tailored extract would look like.

Best,
Charles Prescott
charlesaprescottjr@gmail.com"""

    return body


def get_gmail_service():
    """Get authenticated Gmail API service."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None  # Force re-auth below
        if not creds or not creds.valid:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def log_outreach(conn, author_id: str, paper_id: str, action: str,
                 email_to: str = "", subject: str = "", body: str = "",
                 status: str = "ok", error: str = ""):
    """Log an outreach action."""
    body_hash = hashlib.md5(body.encode()).hexdigest() if body else ""
    c = conn.cursor()
    c.execute("""
        INSERT INTO academic_outreach_log (author_id, paper_id, action, email_to, email_subject, email_body_hash, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (author_id, paper_id, action, email_to, subject, body_hash, status, error))
    conn.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def _handle_send_or_draft(args, conn, gmail, name, author_id, paper_id, body, subject, cp):
    """Send or draft an email. Extracted to avoid code duplication."""
    if args.dry_run or args.drafts_only:
        print(f"\n{'='*70}")
        print(f"TO: {name}")
        print(f"SUBJECT: {subject}")
        print(f"\n{body[:1000]}")
        if len(body) > 1000:
            print(f"... (truncated, {len(body)} total chars)")
        print(f"{'='*70}\n")
        log_outreach(conn, author_id, paper_id, "drafted",
                    subject=subject, body=body, status="draft")
    elif args.send and gmail:
        email_row = conn.execute(
            "SELECT email FROM academic_contacts WHERE author_id = ?", (author_id,)
        ).fetchone()
        to_email = (email_row["email"] if email_row else "").strip() if email_row else ""

        if not to_email or "@" not in to_email:
            print(f"  No email, skipping.")
            log_outreach(conn, author_id, paper_id, "skipped_no_email",
                        status="skipped", error="No email available")
            return

        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['To'] = to_email
            msg['From'] = SENDER_EMAIL
            msg['Subject'] = subject[:200]
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            gmail.users().messages().send(userId='me', body={'raw': raw}).execute()
            print(f"  + SENT to {to_email}")
            log_outreach(conn, author_id, paper_id, "sent",
                        email_to=to_email, subject=subject, body=body, status="sent")
            cp["sent_author_ids"].append(author_id)
            cp["emails_sent"] += 1
            save_checkpoint(cp)
            time.sleep(2.5)
        except Exception as e:
            print(f"  SEND ERROR: {e}")
            log_outreach(conn, author_id, paper_id, "send_failed",
                        email_to=to_email, status="error", error=str(e)[:200])


def main():
    parser = argparse.ArgumentParser(description="GrantWizard Academic Outreach Pipeline")
    parser.add_argument("--limit", type=int, default=0, help="Max academics to process per query")
    parser.add_argument("--sample-limit", type=int, default=10, help="Sample rows per academic")
    parser.add_argument("--dry-run", action="store_true", help="Don't send emails, show drafts")
    parser.add_argument("--send", action="store_true", help="Actually send emails via Gmail")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--search-only", action="store_true", help="Only search for academics, don't process")
    parser.add_argument("--drafts-only", action="store_true", help="Generate draft emails, don't send")
    parser.add_argument("--status", action="store_true", help="Show pipeline status")
    parser.add_argument("--query", type=str, help="Search a single custom query")
    parser.add_argument("--author-id", type=str, help="Process a single author by ID (OpenAlex or S2)")
    parser.add_argument("--source", type=str, default="openalex",
                        choices=["openalex", "semanticscholar"],
                        help="API source for academic discovery (default: openalex)")
    parser.add_argument("--max-queries", type=int, default=29,
                        help="Max search queries to run (default: all 29)")
    parser.add_argument("--pdl-key", type=str, default="",
                        help="People Data Labs API key for email enrichment")
    parser.add_argument("--enrich-emails", action="store_true",
                        help="Enrich emails via PDL before processing")
    parser.add_argument("--validate-emails", action="store_true",
                        help="Validate emails via IPQS/ZeroBounce before sending")
    parser.add_argument("--ipqs-key", type=str, default="",
                        help="IPQualityScore API key for email validation")
    parser.add_argument("--zb-key", type=str, default="",
                        help="ZeroBounce API key for email validation")
    args = parser.parse_args()

    # ── Status check ──
    if args.status:
        show_status()
        return

    # ── Init ──
    print("GrantWizard — Academic Outreach Pipeline")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'SEND' if args.send else 'DRAFT' if args.drafts_only else 'SEARCH ONLY' if args.search_only else 'FULL'}")
    print(f"Source: {args.source}")
    print()

    init_schema()

    cp = load_checkpoint() if args.resume else {
        "stage": "search",
        "search_index": 0,
        "academics_found": 0,
        "samples_generated": 0,
        "emails_sent": 0,
        "sent_author_ids": [],
        "errors": [],
    }

    conn_rw = get_db_rw()

    # ── Stage 0: If --send with validated drafts, go straight to sending ──
    all_academics = []
    if args.send and not args.query and not args.author_id:
        c = conn_rw.cursor()
        c.execute("""
            SELECT ac.author_id, ac.name, ac.institution, ac.source, ac.email
            FROM academic_contacts ac
            JOIN academic_papers ap ON ap.author_id = ac.author_id AND ap.is_selected = 1
            WHERE ac.email_validated = 1
              AND ac.author_id NOT IN (
                  SELECT DISTINCT author_id FROM academic_outreach_log WHERE action = 'sent'
              )
            ORDER BY ac.id
            LIMIT ?
        """, (args.limit or 100,))
        all_academics = [dict(r) for r in c.fetchall()]
        if all_academics:
            print(f"Send mode: {len(all_academics)} validated, drafted, unsent academics ready.")
        else:
            print("No validated unsent drafts. Run --drafts-only first, then --validate-emails.")

    # ── Stage 1: Get academics (search or load from DB) ──
    queries = [args.query] if args.query else SEARCH_QUERIES
    if args.author_id:
        queries = []

    # If resuming with academics already in DB, skip search
    db_count = conn_rw.execute("SELECT COUNT(1) FROM academic_contacts").fetchone()[0]
    skip_search = (args.resume and db_count > 0 and not args.query and not args.author_id)
    # Also skip search if only enriching/validating emails (no processing needed)
    only_email_ops = (args.enrich_emails or args.validate_emails) and not args.drafts_only and not args.send

    if skip_search or only_email_ops:
        if skip_search:
            print(f"Stage 1: Loading {db_count} academics from DB (--resume, skipping search)")
            all_academics = load_academics_from_db(limit=args.limit or 0)
            print(f"  Loaded {len(all_academics)} unprocessed academics")
        else:
            print("Stage 1: Skipping search (email enrichment/validation only)")
    elif queries and not all_academics:
        queries = queries[:args.max_queries]
        print(f"Stage 1: Searching for academics ({len(queries)} queries)")
        for qi, query in enumerate(queries):
            if args.resume and qi < cp.get("search_index", 0):
                continue

            print(f"  [{qi+1}/{len(queries)}] {query[:80]}...")
            acads = search_academics(query, limit=args.limit or 15, source=args.source)
            print(f"    Found {len(acads)} authors")

            for acad in acads:
                upsert_academic(conn_rw, acad)
                all_academics.append(acad)

            cp["search_index"] = qi + 1
            cp["academics_found"] += len(acads)
            save_checkpoint(cp)

            if args.search_only:
                continue

    # Add single author if specified
    if args.author_id:
        all_academics = [{"author_id": args.author_id, "name": "Unknown", "institution": "", "source": args.source, "source_query": "manual"}]

    if args.search_only:
        print(f"\nSearch complete. Found {cp['academics_found']} academics total.")
        conn_rw.close()
        return

    # ── Email enrichment (PDL) + validation (IPQS/ZeroBounce) ──
    if args.enrich_emails:
        print("\nStage 1.5: Enriching emails via PDL...")
        enrich_emails_with_pdl(conn_rw, api_key=args.pdl_key)
        print()

    if args.validate_emails:
        # Guess emails for any academics that don't have one yet
        c = conn_rw.cursor()
        to_guess = c.execute("""
            SELECT author_id, name, institution FROM academic_contacts
            WHERE (email IS NULL OR email = '') AND institution IS NOT NULL AND institution != ''
        """).fetchall()
        if to_guess:
            print(f"  Guessing emails for {len(to_guess)} academics...")
            for row in to_guess:
                email = guess_email(row["name"], row["institution"])
                if email:
                    c.execute("UPDATE academic_contacts SET email = ? WHERE author_id = ?",
                             (email, row["author_id"]))
            conn_rw.commit()
            guessed = c.execute("SELECT COUNT(1) FROM academic_contacts WHERE email IS NOT NULL AND email != ''").fetchone()[0]
            print(f"  {guessed} total with emails after guessing")

        print("Stage 1.6: Validating emails...")
        validate_emails(conn_rw, ipqs_key=args.ipqs_key, zb_key=args.zb_key)
        print()

    # If only doing email ops, stop here
    if only_email_ops:
        print("Email operations complete.")
        conn_rw.close()
        return

    # Deduplicate
    seen = set()
    unique_academics = []
    for a in all_academics:
        if a["author_id"] not in seen:
            seen.add(a["author_id"])
            unique_academics.append(a)
    all_academics = unique_academics

    if args.limit and len(all_academics) > args.limit:
        all_academics = all_academics[:args.limit]

    print(f"\nProcessing {len(all_academics)} academics...\n")

    # ── Stage 2-5: For each academic, find papers, extract dimensions, build sample, draft email ──
    gmail = None
    if args.send and not args.dry_run:
        gmail = get_gmail_service()
        print("Gmail API ready.\n")

    for ai, acad in enumerate(all_academics):
        author_id = acad["author_id"]
        acad_name = acad["name"]

        if args.resume and author_id in cp.get("sent_author_ids", []):
            continue

        print(f"[{ai+1}/{len(all_academics)}] {acad_name} ({author_id})")

        # Check if this academic already has a drafted paper with stored query
        existing = conn_rw.execute("""
            SELECT paper_id, title, abstract, year, journal, citation_count,
                   faith_label, geo_label, topic_labels, query_sql, query_row_count
            FROM academic_papers
            WHERE author_id = ? AND is_selected = 1 AND query_sql IS NOT NULL
            ORDER BY citation_count DESC LIMIT 1
        """, (author_id,)).fetchone()

        if existing and existing["query_row_count"] and existing["query_row_count"] > 0:
            # Reuse existing draft — handle everything inline, then skip common code
            paper_id = existing["paper_id"]
            paper_title = existing["title"] or "Unknown"
            best_paper = {
                "title": paper_title,
                "year": existing["year"] or "?",
                "journal": existing["journal"] or "",
                "citationCount": existing["citation_count"] or 0,
            }
            dims = ResearchDimensions(
                faith_label=existing["faith_label"] or "All faiths",
                geo_label=existing["geo_label"] or "National",
                topic_labels=existing["topic_labels"].split(", ") if existing["topic_labels"] else [],
            )
            query_sql = existing["query_sql"]
            print(f"  Reusing: {paper_title[:80]} ({best_paper['year']}, {best_paper['citationCount']} cites)")

            sample_rows = []
            if not args.dry_run:
                try:
                    sample_rows = run_sample_query(query_sql, limit=args.sample_limit)
                    print(f"  Sample: {len(sample_rows)} rows")
                except Exception as e:
                    print(f"  Query error: {e}")
                    continue

            if sample_rows or args.dry_run:
                body = build_email(acad_name, best_paper, sample_rows, dims)
                subject = f"Religious organization database — data matching your research on {dims.faith_label.lower()} institutions"
                _handle_send_or_draft(args, conn_rw, gmail, acad_name, author_id, paper_id,
                                      body, subject, cp)
            else:
                print(f"  No sample rows, skipping.")
            continue  # Skip common code below

        else:
            # Find papers fresh
            papers = get_recent_papers(author_id, limit=5, source=args.source)
            if not papers:
                print(f"  No papers found, skipping.")
                continue

            best_paper = None
            for p in sorted(papers, key=lambda x: x.get("citationCount", 0) or 0, reverse=True):
                if p.get("abstract") or p.get("title"):
                    best_paper = p
                    break
            if not best_paper:
                best_paper = papers[0]

            paper_title = best_paper.get("title", "Unknown")[:120]
            paper_abstract = best_paper.get("abstract", "")[:2000] if best_paper.get("abstract") else ""
            citations = best_paper.get("citationCount", 0) or 0
            year = best_paper.get("year", "?")
            print(f"  Paper: {paper_title} ({year}, {citations} cites)")

            paper_id = upsert_paper(conn_rw, author_id, best_paper, selected=True)

            dims = extract_research_dimensions(paper_title, paper_abstract)
            print(f"  Dimensions: {describe_dimensions(dims)}")

            qs = build_query(dims, limit=args.sample_limit)
            query_sql = query_to_sql(qs)
            store_dimensions(conn_rw, paper_id, dims, query_sql)

        # Run sample query
        sample_rows = []
        if not args.dry_run:
            try:
                sample_rows = run_sample_query(query_sql, limit=args.sample_limit)
                print(f"  Sample: {len(sample_rows)} rows returned")
                # Update row count
                conn_rw.execute("UPDATE academic_papers SET query_row_count = ? WHERE paper_id = ?",
                                (len(sample_rows), paper_id))
                conn_rw.commit()
            except Exception as e:
                print(f"  Query error (continuing): {e}")

        if not sample_rows and not args.dry_run:
            print(f"  No sample rows, skipping email.")
            continue

        cp["samples_generated"] += 1

        # Build email
        body = build_email(acad_name, best_paper, sample_rows if sample_rows else [], dims)
        subject = f"Religious organization database — data matching your research on {dims.faith_label.lower()} institutions"

        # ── Output / Send ──
        _handle_send_or_draft(args, conn_rw, gmail, acad_name, author_id, paper_id,
                              body, subject, cp)

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"Pipeline complete.")
    print(f"  Academics processed: {len(all_academics)}")
    print(f"  Samples generated:   {cp['samples_generated']}")
    print(f"  Emails sent:         {cp['emails_sent']}")
    print(f"  Errors:              {len(cp.get('errors', []))}")
    print(f"  Checkpoint:          {CHECKPOINT_FILE}")

    conn_rw.close()


def show_status():
    """Print pipeline status from database."""
    conn = sqlite3.connect(OUTREACH_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM academic_contacts")
    total_academics = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM academic_papers WHERE is_selected = 1")
    total_papers = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM academic_papers WHERE query_sql IS NOT NULL")
    total_with_queries = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM academic_papers WHERE query_row_count > 0")
    total_with_samples = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT author_id) FROM academic_outreach_log WHERE action = 'sent'")
    total_sent = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT author_id) FROM academic_outreach_log WHERE action = 'drafted'")
    total_drafted = c.fetchone()[0]

    c.execute("""
        SELECT faith_label, COUNT(*) as cnt FROM academic_papers
        WHERE is_selected = 1 AND faith_label IS NOT NULL
        GROUP BY faith_label ORDER BY cnt DESC LIMIT 15
    """)
    faith_dist = c.fetchall()

    c.execute("""
        SELECT geo_label, COUNT(*) as cnt FROM academic_papers
        WHERE is_selected = 1 AND geo_label IS NOT NULL
        GROUP BY geo_label ORDER BY cnt DESC LIMIT 10
    """)
    geo_dist = c.fetchall()

    conn.close()

    print("GrantWizard — Academic Outreach Pipeline Status")
    print(f"{'='*50}")
    print(f"  Academics in DB:     {total_academics:>6,}")
    print(f"  Selected papers:     {total_papers:>6,}")
    print(f"  With queries built:  {total_with_queries:>6,}")
    print(f"  With valid samples:  {total_with_samples:>6,}")
    print(f"  Drafts generated:    {total_drafted:>6,}")
    print(f"  Emails sent:         {total_sent:>6,}")
    print()
    print("  Faith tradition distribution:")
    for row in faith_dist:
        print(f"    {row[0]:30s} {row[1]:>5,}")
    print()
    print("  Geography distribution:")
    for row in geo_dist:
        print(f"    {row[0]:30s} {row[1]:>5,}")


if __name__ == '__main__':
    main()
