"""
GRID LEAD SCORING & PRIORITIZATION ENGINE
==========================================
Scores leads based on multiple signals to prioritize outreach.
Higher scores = contact first. Integrates with sales_campaign_manager.

Scoring factors:
  - Persona priority (data_broker > mapping > insurance > academic > ...)
  - Organization size/revenue (if known)
  - Email quality (ZeroBounce validation)
  - Contact data completeness (phone + website + email = higher score)
  - Previous engagement (replies, opens)
  - Time in pipeline (older leads get urgency boost)

Usage:
    python scripts/outreach/lead_scoring.py --score-all    # Score all leads
    python scripts/outreach/lead_scoring.py --top 20       # Show top N leads
    python scripts/outreach/lead_scoring.py --rebuild      # Rescore and reprioritize queue
    python scripts/outreach/lead_scoring.py --enrich       # Enrich leads with additional data

Author: Charles Prescott — GRID
Created: 2026-07-08
"""

import sqlite3
import json
import sys
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.outreach.sales_campaign_config import (
    LEAD_SOURCES, PERSONAS, PRODUCTS
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT_ROOT / "outputs" / "outreach"
CRM_DB = OUT_DIR / "sales_crm.db"
DB_PATH = PROJECT_ROOT / "churches.db"

# ══════════════════════════════════════════════════════════════════════════
# SCORING WEIGHTS
# ══════════════════════════════════════════════════════════════════════════

WEIGHTS = {
    "persona_priority": 0.20,      # Higher-value personas score higher
    "email_quality": 0.15,         # Verified emails score higher
    "contact_completeness": 0.15,  # Phone + website + email = best
    "org_prestige": 0.15,          # Known big companies score higher
    "previous_engagement": 0.15,   # Replied before? Score higher
    "data_freshness": 0.10,        # Newer leads score slightly higher
    "deal_potential": 0.10,        # Based on persona avg deal size
    "time_urgency": 0.05,          # Older untouched leads get slight boost
}

# Persona priority scores (0-100)
PERSONA_PRIORITY = {
    "data_broker": 95,
    "mapping_company": 90,
    "insurance": 70,
    "enterprise": 75,
    "nonprofit": 55,
    "academic": 50,
    "marketer": 45,
    "roofing": 30,
    "church_admin": 25,
    "consultant": 40,
    "startup": 35,
    "unknown": 20
}

# Prestigious orgs — these get a bonus
PRESTIGE_DOMAINS = {
    # Major data brokers
    "data-axle.com": 95, "infousa.com": 85, "dnb.com": 95,
    "zoominfo.com": 85, "apollo.io": 80, "experian.com": 98,
    # Major mapping
    "google.com": 100, "apple.com": 100, "mapbox.com": 95,
    "here.com": 90, "tomtom.com": 90, "esri.com": 95,
    # Major research
    "pewresearch.org": 95, "pewforum.org": 95, "barna.com": 85,
    "gallup.com": 90, "prri.org": 80, "lifeway.com": 75,
    # Major foundations
    "gatesfoundation.org": 95, "fordfoundation.org": 90,
    "pewtrusts.org": 95, "lillyendowment.org": 90,
    # Major insurers
    "statefarm.com": 85, "allstate.com": 85, "libertymutual.com": 85,
    "progressive.com": 80, "travelers.com": 85, "aig.com": 90,
    "chubb.com": 90, "axa.com": 90, "zurich.com": 90,
    # Big orgs
    "mckinsey.com": 90, "bcg.com": 90, "deloitte.com": 85,
    "salesforce.com": 85, "oracle.com": 85, "ibm.com": 85
}

# Deal potential by persona (annual revenue potential)
DEAL_POTENTIAL = {
    "data_broker": 15000,
    "mapping_company": 25000,
    "insurance": 3500,
    "enterprise": 10000,
    "nonprofit": 1500,
    "academic": 750,
    "marketer": 500,
    "roofing": 200,
    "church_admin": 250,
    "consultant": 1500,
    "startup": 800,
    "unknown": 500
}

# ══════════════════════════════════════════════════════════════════════════

def get_crm_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(CRM_DB))
    db.row_factory = sqlite3.Row
    return db

def extract_domain(email: str) -> str:
    """Extract domain from email address."""
    match = re.search(r'@(.+)$', email)
    return match.group(1).lower() if match else ""

def score_email_quality(lead: Dict) -> float:
    """Score email quality (0-100)."""
    email = lead.get("contact_email", "")
    if not email or "@" not in email:
        return 0

    domain = extract_domain(email)

    # Disposable email domains
    disposable = {"mailinator.com", "guerrillamail.com", "tempmail.com",
                  "10minutemail.com", "sharklasers.com", "trashmail.com"}
    if domain in disposable:
        return 10

    # Free email providers (less ideal for B2B, okay for church admins)
    free_providers = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
                      "aol.com", "icloud.com", "protonmail.com", "mail.com"}
    if domain in free_providers:
        return 50

    # Business domain = best for B2B
    return 85

def _safe_json_loads(s):
    """Parse string as JSON, return dict or {} on failure."""
    if not s:
        return {}
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except (json.JSONDecodeError, TypeError):
        return {}

def score_contact_completeness(lead: Dict) -> float:
    """Score based on available contact data (0-100)."""
    score = 0
    notes = lead.get("notes", "")

    if lead.get("contact_email"):
        score += 40
    if lead.get("contact_phone"):
        score += 30
    if lead.get("contact_name"):
        score += 20
    # Check notes for additional data
    if notes:
        n = _safe_json_loads(notes)
        if n.get("website"):
            score += 10

    return min(score, 100)

def score_org_prestige(lead: Dict) -> float:
    """Score organization prestige (0-100)."""
    domain = extract_domain(lead.get("contact_email", ""))
    if domain in PRESTIGE_DOMAINS:
        return PRESTIGE_DOMAINS[domain]

    org_name = (lead.get("org_name", "") or "").lower()

    # Check org name for known patterns
    prestige_patterns = [
        (r'\b(google|apple|microsoft|amazon|meta|netflix)\b', 95),
        (r'\b(experian|equifax|transunion)\b', 95),
        (r'\b(tomtom|here\s*technologies|mapbox|esri|carto)\b', 90),
        (r'\b(mckinsey|bain|bcg|deloitte|accenture|pwc|kpmg|ey)\b', 85),
        (r'\b(chubb|aig|allianz|axa|zurich|munich\s*re|swiss\s*re)\b', 85),
        (r'\b(gallup|nielsen|ipsos|kantar|yougov|morning\s*consult)\b', 80),
        (r'\b(pew|barna|prri|arda|lifeway|hartford)\b', 75),
        (r'\b(harvard|mit|stanford|yale|princeton|oxford|cambridge)\b', 75),
        (r'\b(gates|ford|rockefeller|macarthur|kellogg|mellon)\b', 85),
        (r'\b(state\s*farm|allstate|liberty\s*mutual|progressive|nationwide|farmers)\b', 75),
    ]

    for pattern, pscore in prestige_patterns:
        if re.search(pattern, org_name):
            return pscore

    return 35  # Average — not known but not disposable

def score_previous_engagement(crm: sqlite3.Connection, lead_id: int) -> float:
    """Score based on previous engagement (0-100)."""
    if not lead_id:
        return 0

    touches = crm.execute("""
        SELECT replied, reply_classification FROM touch_log WHERE lead_id=?
    """, (lead_id,)).fetchall()

    if not touches:
        return 0

    score = 0
    for t in touches:
        if t["replied"]:
            classification = t["reply_classification"] or ""
            if classification == "interested":
                score += 35
            elif classification == "question":
                score += 25
            elif classification == "other":
                score += 10
            # Negative classifications don't reduce score here
            # (they're handled by pipeline stage, not scoring)

    # Bonus for multiple touches (persistence pays)
    score += min(len(touches) * 3, 15)

    return min(score, 100)

def score_deal_potential(lead: Dict) -> float:
    """Score based on persona's average deal size (0-100)."""
    persona = lead.get("persona", "unknown")
    potential = DEAL_POTENTIAL.get(persona, 500)

    # Normalize: $250 = 10, $25,000 = 100
    normalized = min(potential / 250, 100)
    return normalized

def score_time_urgency(lead: Dict) -> float:
    """Score based on time in pipeline — older untouched = slight urgency boost."""
    created = lead.get("created_at")
    if not created:
        return 50

    try:
        created_dt = datetime.strptime(created[:10], "%Y-%m-%d")
        days_old = (datetime.now() - created_dt).days

        # 0-7 days: 30, 8-30 days: 50, 31-60 days: 70, 60+: 85
        if days_old <= 7:
            return 30
        elif days_old <= 30:
            return 50
        elif days_old <= 60:
            return 70
        else:
            return min(85, 70 + (days_old - 60) * 0.1)
    except:
        return 50

def compute_lead_score(crm: sqlite3.Connection, lead: Dict) -> float:
    """Compute composite lead score (0-100)."""
    lead_dict = dict(lead)

    scores = {
        "persona_priority": PERSONA_PRIORITY.get(lead_dict.get("persona", "unknown"), 20),
        "email_quality": score_email_quality(lead_dict),
        "contact_completeness": score_contact_completeness(lead_dict),
        "org_prestige": score_org_prestige(lead_dict),
        "previous_engagement": score_previous_engagement(crm, lead_dict.get("id")),
        "data_freshness": score_time_urgency(lead_dict),  # Alias — same calc
        "deal_potential": score_deal_potential(lead_dict),
        "time_urgency": score_time_urgency(lead_dict),
    }

    composite = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    return round(composite, 1), scores

def score_all_leads(crm: sqlite3.Connection) -> List[Dict]:
    """Score all active leads and return sorted list."""
    leads = crm.execute("""
        SELECT * FROM leads
        WHERE is_active=1
        AND pipeline_stage NOT IN ('won','lost','unsubscribed','no_response')
    """).fetchall()

    results = []
    for lead in leads:
        composite, breakdown = compute_lead_score(crm, lead)

        # Update priority in DB
        new_priority = 10 - int(composite / 10)  # 0-100 score → 10-1 priority
        new_priority = max(1, min(10, new_priority))

        crm.execute("UPDATE leads SET priority=? WHERE id=?", (new_priority, lead["id"]))

        results.append({
            "lead_id": lead["id"],
            "org_name": lead["org_name"],
            "persona": lead["persona"],
            "stage": lead["pipeline_stage"],
            "score": composite,
            "breakdown": breakdown,
            "priority": new_priority,
            "email": lead["contact_email"]
        })

    crm.commit()

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def enrich_leads_from_db(crm: sqlite3.Connection):
    """Enrich leads with additional data from churches.db."""
    try:
        db = sqlite3.connect(str(DB_PATH))
        db.row_factory = sqlite3.Row
    except:
        print("  ⚠️ Could not connect to churches.db for enrichment")
        return

    leads = crm.execute("""
        SELECT id, contact_email, org_name FROM leads
        WHERE (notes IS NULL OR notes = '' OR notes = '{}')
        AND is_active=1
    """).fetchall()

    enriched = 0
    for lead in leads:
        enrich_data = {}

        # Try to find by email match in church_contact_values
        row = db.execute("""
            SELECT c.name, c.city, c.state, c.country, c.tradition, c.faith,
                   c.latitude, c.longitude, c.address
            FROM churches c
            JOIN church_contact_values cv ON c.id = cv.church_id
            WHERE cv.value = ? AND cv.contact_type = 'email'
            LIMIT 1
        """, (lead["contact_email"],)).fetchone()

        if row:
            enrich_data = {
                "matched_church": row["name"],
                "city": row["city"],
                "state": row["state"],
                "country": row["country"],
                "tradition": row["tradition"],
                "faith": row["faith"],
                "lat": row["latitude"],
                "lon": row["longitude"],
                "address": row["address"]
            }

        # Try to find by org name
        if not enrich_data:
            row = db.execute("""
                SELECT name, city, state, country, tradition, faith, latitude, longitude
                FROM churches WHERE name LIKE ?
                LIMIT 1
            """, (f"%{lead['org_name']}%",)).fetchone()

            if row:
                enrich_data = {
                    "matched_church": row["name"],
                    "city": row["city"],
                    "state": row["state"],
                    "country": row["country"],
                    "tradition": row["tradition"],
                    "faith": row["faith"]
                }

        if enrich_data:
            crm.execute("UPDATE leads SET notes=? WHERE id=?",
                       (json.dumps(enrich_data), lead["id"]))
            enriched += 1

    crm.commit()
    db.close()
    print(f"  Enriched {enriched} leads with church data")

def print_top_leads(results: List[Dict], n: int = 20):
    """Print top N scored leads."""
    print(f"\n{'='*90}")
    print(f"  TOP {n} LEADS BY SCORE")
    print(f"{'='*90}")
    print(f"  {'Rank':<5} {'Score':<7} {'Organization':<30} {'Persona':<20} {'Stage':<15}")
    print(f"  {'─'*5} {'─'*7} {'─'*30} {'─'*20} {'─'*15}")

    for i, r in enumerate(results[:n], 1):
        print(f"  {i:<5} {r['score']:<7.1f} {r['org_name'][:29]:<30} {r['persona']:<20} {r['stage']:<15}")

    # Summary
    if results:
        avg_score = sum(r["score"] for r in results) / len(results)
        print(f"\n  Average score: {avg_score:.1f} | Total leads scored: {len(results)}")

    print(f"{'='*90}")

def rebuild_queue_by_score(crm: sqlite3.Connection, results: List[Dict]):
    """Rebuild the unified queue with top-scored leads first."""
    from scripts.outreach.sales_campaign_manager import (
        build_campaign_batch, append_to_queue, QUEUE_FILE
    )

    # Clear existing queue
    if QUEUE_FILE.exists():
        QUEUE_FILE.unlink()

    # Reorder leads in DB by score
    for r in results:
        crm.execute("UPDATE leads SET priority=? WHERE id=?",
                   (r["priority"], r["lead_id"]))
    crm.commit()

    # Build new batch from top-scored
    print("\n  Rebuilding queue with scored leads...")
    entries = build_campaign_batch(crm, max_new=200)
    added = append_to_queue(entries)
    print(f"  ✅ Queued {added} leads (top-scored first)")

# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    crm = get_crm_db()
    cmd = sys.argv[1]

    if cmd == "--score-all":
        print("Scoring all leads...")
        results = score_all_leads(crm)
        print_top_leads(results, n=20)

    elif cmd == "--top":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        results = score_all_leads(crm)
        print_top_leads(results, n=n)

    elif cmd == "--rebuild":
        print("Scoring and rebuilding queue...")
        results = score_all_leads(crm)
        print_top_leads(results, n=10)
        rebuild_queue_by_score(crm, results)

    elif cmd == "--enrich":
        print("Enriching leads with church data...")
        enrich_leads_from_db(crm)
        results = score_all_leads(crm)
        print_top_leads(results, n=10)

    elif cmd == "--persona-stats":
        stats = crm.execute("""
            SELECT persona, COUNT(*) as cnt,
                   SUM(CASE WHEN pipeline_stage='won' THEN 1 ELSE 0 END) as won,
                   AVG(CASE WHEN pipeline_stage IN ('engaged','negotiating','proposal_sent')
                       THEN 1 ELSE 0 END) as active_ratio
            FROM leads WHERE is_active=1
            GROUP BY persona ORDER BY cnt DESC
        """).fetchall()

        print(f"\n{'Persona':<25} {'Leads':<8} {'Won':<6} {'Active%':<8}")
        print(f"{'─'*25} {'─'*8} {'─'*6} {'─'*8}")
        for s in stats:
            print(f"  {s['persona']:<25} {s['cnt']:<8} {s['won']:<6} {s['active_ratio']*100 if s['active_ratio'] else 0:<8.1f}")

    crm.close()

if __name__ == "__main__":
    main()
