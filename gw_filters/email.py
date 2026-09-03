"""
Email Validation & Scoring
============================
Consolidates: ec2_scraper.score_email, ec2_phones_scraper.score_email,
              scrape_black_churches.score_email, ses_email_validate,
              guess_emails.validate_email_ses, enrich_emails._prefix_score

Single email scoring and validation pipeline.
"""

import re
import socket
import dns.resolver  # optional — falls back to socket if unavailable

# ═══════════════════════════════════════════════════════════════════
# EMAIL PREFIX SCORING
# ═══════════════════════════════════════════════════════════════════

# High-quality prefixes (likely real human recipient)
HIGH_VALUE_PREFIXES = {
    "pastor", "reverend", "rev", "fr", "father", "priest",
    "minister", "vicar", "rector", "canon", "deacon",
    "bishop", "apostle", "evangelist",
    "admin", "office", "info", "contact", "hello",
    "secretary", "administrator", "manager",
    "youth", "children", "worship", "music",
    "outreach", "missions", "communications",
}

# Low-quality prefixes (likely bounced or unmonitored)
LOW_VALUE_PREFIXES = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "bounce", "mailer-daemon", "postmaster",
    "spam", "junk", "abuse",
}

# Prefix patterns for scoring
PREFIX_PATTERNS = {
    "pastor": 1.0, "reverend": 1.0, "rev": 1.0, "fr": 0.9, "father": 0.9,
    "minister": 1.0, "vicar": 1.0, "rector": 1.0, "canon": 0.9, "deacon": 0.9,
    "bishop": 1.0, "apostle": 0.9, "evangelist": 0.9,
    "admin": 0.7, "office": 0.7, "info": 0.6, "contact": 0.6, "hello": 0.5,
    "secretary": 0.8, "administrator": 0.7, "manager": 0.6,
    "youth": 0.7, "children": 0.7, "worship": 0.7, "music": 0.7,
    "outreach": 0.7, "missions": 0.7, "communications": 0.7,
    "webmaster": 0.4, "hostmaster": 0.3, "support": 0.4,
    "noreply": 0.0, "no-reply": 0.0, "donotreply": 0.0,
    "bounce": 0.0, "mailer-daemon": 0.0, "postmaster": 0.0,
}


def score_prefix(local_part):
    """Score an email prefix 0.0-1.0 based on how likely it reaches a human."""
    prefix = local_part.strip().lower()

    # Direct match in patterns
    if prefix in PREFIX_PATTERNS:
        return PREFIX_PATTERNS[prefix]

    # Check for firstname or firstname.lastname patterns
    if re.match(r'^[a-z]+(\.[a-z]+)?$', prefix) and len(prefix) > 2:
        return 0.8  # Real person name

    # Check for first initial + lastname
    if re.match(r'^[a-z]\.[a-z]+$', prefix):
        return 0.7

    # Generic catch-all
    return 0.3


def score(email):
    """
    Score an email address 0.0-1.0.
    Combines prefix score + domain quality + syntax validity.

    Returns dict with score and breakdown.
    """
    if not email or not isinstance(email, str):
        return {"score": 0.0, "valid": False, "reason": "empty"}

    email = email.strip()

    # Syntax check
    match = re.match(r'^([^@]+)@([^@]+)$', email)
    if not match:
        return {"score": 0.0, "valid": False, "reason": "invalid_syntax"}

    local, domain = match.group(1), match.group(2).lower()

    if not local or not domain:
        return {"score": 0.0, "valid": False, "reason": "empty_part"}

    # Domain quality
    domain_score = _score_domain(domain)

    # Prefix quality
    prefix_score = score_prefix(local)

    # Composite score
    composite = (prefix_score * 0.6) + (domain_score * 0.4)
    composite = round(min(1.0, max(0.0, composite)), 2)

    return {
        "score": composite,
        "valid": composite > 0.1,
        "prefix_score": prefix_score,
        "domain_score": domain_score,
        "local": local,
        "domain": domain,
        "prefix_quality": _quality_label(prefix_score),
    }


def _score_domain(domain):
    """Score domain quality 0.0-1.0."""
    # Common free email domains (less reliable for churches)
    free_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                     "aol.com", "verizon.net", "comcast.net", "att.net",
                     "msn.com", "live.com", "icloud.com", "mail.com"}
    if domain in free_domains:
        return 0.4

    # Subdomain-only (churchwebsite.org/something)
    if domain.count(".") > 2:
        return 0.5

    # Normal domain
    return 0.9


def _quality_label(score):
    if score >= 0.8:
        return "high"
    elif score >= 0.5:
        return "medium"
    elif score >= 0.2:
        return "low"
    return "very_low"


# ═══════════════════════════════════════════════════════════════════
# MX / SMTP VALIDATION
# ═══════════════════════════════════════════════════════════════════

def has_mx_record(domain, timeout=5):
    """Check if domain has an MX record (can receive email)."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX', lifetime=timeout)
        return len(answers) > 0
    except ImportError:
        # Fallback: try to resolve any record
        try:
            socket.getaddrinfo(domain, 25, timeout=timeout)
            return True
        except Exception:
            return False
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
# EMAIL CLEANING
# ═══════════════════════════════════════════════════════════════════

def clean(email_str):
    """Clean and normalize an email string."""
    if not email_str:
        return ""
    email_str = email_str.strip().lower()
    # Remove mailto: prefix
    email_str = re.sub(r'^mailto:', '', email_str, flags=re.IGNORECASE)
    # Remove surrounding angle brackets
    email_str = re.sub(r'^<(.*)>$', r'\1', email_str)
    # Remove parenthetical notes
    email_str = re.sub(r'\s*\(.*?\)\s*', '', email_str)
    # Remove trailing dots, spaces
    email_str = email_str.strip().rstrip('.')
    return email_str
