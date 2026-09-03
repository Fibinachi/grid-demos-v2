"""
gw_filters — Centralized GrantWizard Filtering & Classification
================================================================
Single source of truth for ALL filters, scorers, classifiers, and validators.
Every scraper and pipeline imports from here — no duplicate logic anywhere.

Usage:
    from gw_filters import faith, email, web, geo, clean
    label = faith.classify_from_name("First Baptist Church of Columbia")
    score = email.score("pastor@firstbaptist.org")
    match_pct = web.score_match("First Baptist", "columbia", page_title, meta_desc, body)
"""

# Version — bump when rules change
__version__ = "1.0.0"
