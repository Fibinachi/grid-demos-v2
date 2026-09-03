"""
Scrape Status Tracking
=======================
Consolidates: website_scrape_status / email_scrape_status logic from
              sync_and_import.py, enrich_pipeline.py, and _check_scrape_status.py

Defines valid states and transitions.
"""

# Valid states
PENDING = "pending"
FOUND = "found"
NOT_FOUND = "not_found"
VERIFIED = "verified"
ERROR = "error"

STATUSES = [PENDING, FOUND, NOT_FOUND, VERIFIED, ERROR]

# Allowed transitions
TRANSITIONS = {
    None: [PENDING],
    "": [PENDING],
    PENDING: [FOUND, NOT_FOUND, ERROR],
    FOUND: [VERIFIED, NOT_FOUND, ERROR],
    NOT_FOUND: [FOUND, ERROR],
    VERIFIED: [ERROR],
    ERROR: [PENDING, FOUND, NOT_FOUND],
}


def valid_transition(current, new):
    """Check if a status transition is valid."""
    if current in TRANSITIONS:
        return new in TRANSITIONS[current]
    return new in [FOUND, NOT_FOUND, VERIFIED, ERROR]


def needs_check(status):
    """Should this record be checked/scraped?"""
    return status in (None, "", PENDING, ERROR)


def is_done(status):
    """Has scraping been resolved for this record?"""
    return status in (FOUND, NOT_FOUND, VERIFIED)
