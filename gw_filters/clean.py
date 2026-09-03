"""
Data Cleaning Utilities
=========================
Consolidates: clean() functions from denom_scraper_v2, scrape_catholic,
              import_denom_csv, guess_pastor_emails, etc.
"""

import re

# ═══════════════════════════════════════════════════════════════════
# TEXT CLEANING
# ═══════════════════════════════════════════════════════════════════

def clean_text(text):
    """Clean arbitrary text: normalize whitespace, strip punctuation noise."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', str(text)).strip()
    text = re.sub(r'[,;:]+$', '', text)
    return text


def clean_denomination(denom):
    """Normalize a denomination string."""
    if not denom:
        return ""
    denom = clean_text(denom)
    denom = denom.replace("''", "'")
    # Remove parenthetical codes like "(X20)"
    denom = re.sub(r'\s*\([A-Z0-9]+\)\s*$', '', denom)
    return denom.strip()


def clean_church_name(name):
    """Normalize a church name for matching."""
    if not name:
        return ""
    name = clean_text(name)
    name = re.sub(r'\b(INC|LLC|CORP|CORPORATION|ORG)\b\.?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(.*?\)\s*', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


# ═══════════════════════════════════════════════════════════════════
# DOMAIN CLEANING
# ═══════════════════════════════════════════════════════════════════

def clean_domain(website):
    """Extract clean domain from a URL."""
    if not website:
        return ""
    website = website.strip().lower()
    # Remove protocol
    website = re.sub(r'^https?://', '', website)
    # Remove path/query
    website = website.split('/')[0].split('?')[0].split('#')[0]
    # Remove www. prefix
    website = re.sub(r'^www\.', '', website)
    return website


def ensure_url(domain):
    """Ensure a domain has http:// prefix."""
    if not domain:
        return ""
    domain = domain.strip()
    if not domain.startswith(('http://', 'https://')):
        return 'https://' + domain
    return domain


# ═══════════════════════════════════════════════════════════════════
# PHONE CLEANING
# ═══════════════════════════════════════════════════════════════════

def clean_phone(phone):
    """Normalize a US phone number to (XXX) XXX-XXXX format."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return phone.strip()


# ═══════════════════════════════════════════════════════════════════
# ZIP CODE CLEANING
# ═══════════════════════════════════════════════════════════════════

def clean_zip(zipcode):
    """Normalize to 5-digit ZIP."""
    if not zipcode:
        return ""
    return re.sub(r'\D', '', str(zipcode))[:5]
