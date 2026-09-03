"""
Webpage Match Scoring
======================
Consolidates: verify_domains.score_match, search_api_finder.score_result,
              common_crawl_enrich.page_title_score

Scores how well a webpage matches a known church record.
"""

import re
from difflib import SequenceMatcher

# ═══════════════════════════════════════════════════════════════════
# PAGE TITLE SCORING
# ═══════════════════════════════════════════════════════════════════

def title_score(page_title, church_name):
    """
    Score how well a page title matches a church name. 0.0-1.0.
    Checks: exact match, substring containment, fuzzy similarity.
    """
    if not page_title or not church_name:
        return 0.0

    title = page_title.strip().lower()
    name = church_name.strip().lower()

    # Exact match (after cleanup)
    if _normalize(title) == _normalize(name):
        return 1.0

    # Church name is fully contained in title
    if name in title:
        return 0.9

    # Key words from church name appear in title
    name_words = set(_tokenize(name))
    title_words = set(_tokenize(title))
    if name_words and title_words:
        overlap = name_words & title_words
        ratio = len(overlap) / len(name_words)
        if ratio >= 0.7:
            return 0.8
        elif ratio >= 0.5:
            return 0.6

    # Fuzzy string similarity
    similarity = SequenceMatcher(None, title, name).ratio()
    return round(similarity * 0.7, 2)


# ═══════════════════════════════════════════════════════════════════
# FULL MATCH SCORING
# ═══════════════════════════════════════════════════════════════════

def score_match(church_name, city, state, page_title="", meta_desc="", body=""):
    """
    Composite match score 0.0-1.0 using title, description, and body text.
    Returns dict with score and breakdown.

    Used by verify_domains.py to confirm a domain belongs to a church.
    """
    score = 0.0
    signals = []

    # Title match
    ts = title_score(page_title, church_name)
    if ts > 0:
        score += ts * 0.5
        signals.append(f"title={ts:.2f}")

    # City/state in body or meta
    text_to_check = (page_title + " " + meta_desc + " " + body).lower() if page_title else ""
    if text_to_check:
        if city and city.lower() in text_to_check:
            score += 0.15
            signals.append("city_match")
        if state and state.lower() in text_to_check:
            score += 0.10
            signals.append("state_match")

    # Church keywords in body
    church_kws = ["church", "ministry", "worship", "sunday", "service",
                   "pastor", "congregation", "chapel", "gospel"]
    if body:
        body_lower = body.lower()
        found_kws = [kw for kw in church_kws if kw in body_lower]
        if found_kws:
            kw_score = min(len(found_kws) * 0.05, 0.25)
            score += kw_score
            signals.append(f"keywords={len(found_kws)}")

    return {
        "score": round(min(score, 1.0), 2),
        "signals": signals,
        "is_match": score >= 0.5,
    }


# ═══════════════════════════════════════════════════════════════════
# SEARCH RESULT SCORING
# ═══════════════════════════════════════════════════════════════════

def score_search_result(church_name, url, title):
    """
    Score a search engine result for relevance to a church.
    Used by search_api_finder.py.
    """
    ts = title_score(title, church_name)
    if ts > 0.5:
        return ts  # Good title match

    # Check URL for church name fragments
    url_lower = url.lower()
    name_fragments = re.findall(r'[a-z]+', church_name.lower())
    url_matches = sum(1 for frag in name_fragments if len(frag) > 3 and frag in url_lower)
    url_ratio = url_matches / max(len(name_fragments), 1) if name_fragments else 0

    return round(max(ts, url_ratio * 0.6), 2)


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _normalize(s):
    """Remove common suffixes and normalize whitespace."""
    s = re.sub(r'\b(inc|llc|church|ministries|org|corporation)\b\.?', '', s, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', s).strip()

def _tokenize(s):
    return re.findall(r'[a-z0-9]+', s.lower())
